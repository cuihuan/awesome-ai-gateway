#!/usr/bin/env python3
"""Canary check: is a relay actually serving the model it claims?

Some "cheap" relays silently swap or quantize the model you paid for. This tool
makes that empirical: it sends a fixed set of discriminating "canary" prompts to
**both** a relay endpoint and the official provider (or any reference endpoint),
then diffs the outputs. A downgraded/swapped model shows up as low output
similarity and failed capability probes — reproducible evidence you can paste
into a watch-list report.

Beyond output similarity it also runs a **fingerprint / tokenizer probe**: it
compares each side's `system_fingerprint` and the `prompt_tokens` they report for
the *same* fixed prompt. A different tokenizer (different prompt_tokens) or a
diverging system_fingerprint is an independent tell that the relay isn't serving
the model it claims — even when the text looks plausible.

Both endpoints are OpenAI-compatible (POST /chat/completions). Keys are read
from flags or env (RELAY_KEY / REF_KEY) and never logged.

Stdlib only. The scoring/verdict/fingerprint logic is pure and unit-tested; the
live HTTP call is a thin wrapper so the tool works with your own keys.

Usage:
  python scripts/canary_check.py \
    --relay-url https://some-relay.example/v1 --relay-key sk-... \
    --ref-url https://api.openai.com/v1       --ref-key  sk-... \
    --model gpt-5.5,claude-opus-4-8        # one or more, comma-separated
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass


# Fixed canaries: each is deterministic and discriminating — a downgraded model
# tends to fail the capability ones and diverge in wording on all of them.
@dataclass(frozen=True)
class Canary:
    id: str
    prompt: str
    must_contain: str | None  # exact-answer capability check (None = compare-only)


CANARIES = [
    Canary("echo", "Reply with EXACTLY this token and nothing else: AGW-CANARY-7F3A2C", "AGW-CANARY-7F3A2C"),
    Canary("primes", "Output only a JSON array of the first 6 prime numbers, no prose.", "[2, 3, 5, 7, 11, 13]"),
    Canary(
        "reason",
        "A bat and a ball cost $1.10 together. The bat costs $1.00 more than the ball. "
        "How much does the ball cost? Reply with only the dollar amount.",
        "0.05",
    ),
    Canary(
        "count",
        "How many times does the letter 'r' appear in the word 'strawberry'? Reply with only the number.",
        "3",
    ),
]


# ── Pure scoring logic (unit-tested) ─────────────────────────────────────────

def normalize(text: str) -> str:
    """Lowercase, collapse whitespace, drop punctuation — for fuzzy comparison."""
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", (text or "").lower())).strip()


def token_similarity(a: str, b: str) -> float:
    """Jaccard similarity over word tokens of two normalized strings (0..1)."""
    sa, sb = set(normalize(a).split()), set(normalize(b).split())
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def capability_hit(output: str, must_contain: str | None) -> bool | None:
    """Did the output contain the exact expected answer? None if not a capability probe."""
    if must_contain is None:
        return None
    return normalize(must_contain) in normalize(output)


def verdict(rows: list[dict]) -> dict:
    """Aggregate per-canary results into a verdict.

    rows: [{id, similarity, relay_hit, ref_hit}]. relay_hit/ref_hit may be None.
    Returns {label, mean_similarity, downgrade_flags}.
    """
    sims = [r["similarity"] for r in rows]
    mean_sim = sum(sims) / len(sims) if sims else 0.0
    # a "downgrade" signal = reference passed a capability probe the relay failed
    downgrades = [r["id"] for r in rows if r.get("ref_hit") and r.get("relay_hit") is False]
    if downgrades or mean_sim < 0.45:
        label = "SUSPICIOUS — likely a different / downgraded model"
    elif mean_sim < 0.7:
        label = "INCONCLUSIVE — some divergence; re-run with more canaries"
    else:
        label = "OK — outputs consistent with the reference model"
    return {"label": label, "mean_similarity": round(mean_sim, 3), "downgrade_flags": downgrades}


@dataclass(frozen=True)
class Reply:
    """The comparable fields of one OpenAI-compatible chat response."""
    content: str
    system_fingerprint: str | None
    prompt_tokens: int | None


def parse_reply(data: dict) -> Reply:
    """Extract content + fingerprint/usage fields from a chat-completions body,
    tolerating missing keys (relays vary in what they echo). Pure → unit-tested."""
    data = data or {}
    choices = data.get("choices") or [{}]
    content = ((choices[0] or {}).get("message") or {}).get("content") or ""
    usage = data.get("usage") or {}
    pt = usage.get("prompt_tokens")
    fp = data.get("system_fingerprint")
    return Reply(
        content=content,
        system_fingerprint=fp if isinstance(fp, str) and fp else None,
        prompt_tokens=pt if isinstance(pt, int) else None,
    )


def parse_models(spec: str) -> list[str]:
    """Split a comma-separated --model value into a clean, de-duplicated list
    (order preserved). 'a, b ,a' -> ['a', 'b']."""
    out = []
    for m in (spec or "").split(","):
        m = m.strip()
        if m and m not in out:
            out.append(m)
    return out


def fingerprint_summary(pairs: list[tuple[Reply, Reply]], prompt_token_tol: float = 0.15) -> dict:
    """Tokenizer/fingerprint probe across canaries. pairs: [(relay, ref), ...].

    Two independent tells that a relay isn't serving the claimed model:
      - system_fingerprint differs when BOTH sides report one (same build → same fp);
      - prompt_tokens for the SAME fixed prompt differ beyond prompt_token_tol — a
        different tokenizer, or hidden injected system text, changes the count.
    Both are *signals to investigate*, not proof (a relay may legitimately run a
    different backend region/template), so they never alone force a SUSPICIOUS text
    verdict. Returns {fp_mismatch, max_prompt_token_skew, flags, comparable}.
    """
    fp_mismatch = None
    skews = []
    for relay, ref in pairs:
        if relay.system_fingerprint and ref.system_fingerprint:
            fp_mismatch = bool(fp_mismatch) or (relay.system_fingerprint != ref.system_fingerprint)
        if relay.prompt_tokens and ref.prompt_tokens:
            skews.append(abs(relay.prompt_tokens - ref.prompt_tokens) / ref.prompt_tokens)
    flags = []
    if fp_mismatch:
        flags.append("system_fingerprint")
    max_skew = max(skews) if skews else None
    if max_skew is not None and max_skew > prompt_token_tol:
        flags.append("prompt_tokens")
    return {
        "fp_mismatch": fp_mismatch,
        "max_prompt_token_skew": round(max_skew, 3) if max_skew is not None else None,
        "flags": flags,
        "comparable": len(skews),
    }


# ── Live call (thin wrapper; not unit-tested) ────────────────────────────────

# Two independent canary reports (#70, #82) could not run this script at all
# until they patched it: the gateways sat behind a WAF whose bot rules reject
# the default `Python-urllib/3.x` User-Agent, while curl passed.
# Any explicit UA gets through, so send one rather than making every
# contributor rediscover the workaround.
USER_AGENT = "awesome-ai-gateway-canary/1.0 (+https://github.com/cuihuan/awesome-ai-gateway)"


def build_request(base_url: str, api_key: str, model: str, prompt: str,
                  temperature: int | None = 0) -> urllib.request.Request:
    """Build the POST for one canary prompt. Pure, so it is unit-tested.

    `temperature=None` omits the field entirely — see negotiate_temperature.
    """
    payload: dict = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    if temperature is not None:
        payload["temperature"] = temperature
    return urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )


def is_temperature_refusal(body: str) -> bool:
    """Does this error body mean "I won't accept an explicit temperature"?

    Newer reasoning models reject `temperature: 0` outright ("Only the default
    (1) value is supported"), which used to abort the whole run.
    """
    low = body.lower()
    return "temperature" in low and any(
        s in low for s in ("only the default", "unsupported", "not supported", "does not support")
    )


def call_chat(base_url: str, api_key: str, model: str, prompt: str, timeout: int = 60,
              temperature: int | None = 0) -> dict:
    """POST one chat completion and return the raw decoded JSON body (parsing into
    a Reply is done by the pure parse_reply so it stays unit-testable)."""
    req = build_request(base_url, api_key, model, prompt, temperature)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def negotiate_temperature(endpoints, model: str, timeout: int = 60) -> int | None:
    """Return 0 if every endpoint accepts an explicit temperature, else None.

    Determinism is worth having — temperature 0 is what makes the output diff
    meaningful — but only if both sides get the *same* treatment. If one
    endpoint refuses temperature and the other honours 0, the two replies
    diverge for a reason that has nothing to do with model identity: a false
    positive on the exact thing this script exists to measure. So one cheap
    probe per endpoint decides it for both.
    """
    for base_url, api_key in endpoints:
        try:
            call_chat(base_url, api_key, model, "ping", timeout=timeout, temperature=0)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if is_temperature_refusal(body):
                print(f"note: {base_url} rejects an explicit temperature; "
                      "running both sides on provider defaults")
                return None
        except Exception:  # noqa: BLE001 - a dead endpoint is the canary loop's problem to report
            pass
    return 0


def run_model(relay_url, relay_key, ref_url, ref_key, model) -> dict:
    """Run the full canary set for one model. Returns {verdict, fingerprint, ok}."""
    rows = []
    pairs = []
    temp = negotiate_temperature([(relay_url, relay_key), (ref_url, ref_key)], model)
    print(f"canary check · model={model}\n{'id':10} {'sim':>5}  relay  ref")
    for c in CANARIES:
        try:
            relay = parse_reply(call_chat(relay_url, relay_key, model, c.prompt, temperature=temp))
            ref = parse_reply(call_chat(ref_url, ref_key, model, c.prompt, temperature=temp))
        except Exception as e:  # noqa: BLE001 - surface any endpoint/network error per-canary
            print(f"{c.id:10}  ERROR  {e}")
            continue
        sim = token_similarity(relay.content, ref.content)
        rh, fh = capability_hit(relay.content, c.must_contain), capability_hit(ref.content, c.must_contain)
        rows.append({"id": c.id, "similarity": sim, "relay_hit": rh, "ref_hit": fh})
        pairs.append((relay, ref))
        mark = lambda h: "—" if h is None else ("✓" if h else "✗")
        print(f"{c.id:10} {sim:5.2f}  {mark(rh):^5}  {mark(fh):^3}")
    v = verdict(rows)
    fp = fingerprint_summary(pairs)
    print(f"\nmean similarity: {v['mean_similarity']}")
    if v["downgrade_flags"]:
        print(f"capability probes the relay failed but the reference passed: {', '.join(v['downgrade_flags'])}")
    # fingerprint / tokenizer probe (informational — a flag to investigate, not proof)
    if fp["comparable"]:
        skew = fp["max_prompt_token_skew"]
        fp_line = f"fingerprint/tokenizer: max prompt_tokens skew {skew if skew is not None else 'n/a'}"
        fp_line += f", flags: {', '.join(fp['flags'])}" if fp["flags"] else ", no divergence"
        print(fp_line)
    else:
        print("fingerprint/tokenizer: not comparable (neither side reported usage/system_fingerprint)")
    suffix = "  ⚠ + fingerprint/tokenizer divergence (investigate)" if (fp["flags"] and "OK" in v["label"]) else ""
    print(f"VERDICT: {v['label']}{suffix}")
    return {"model": model, "verdict": v, "fingerprint": fp}


def run(relay_url, relay_key, ref_url, ref_key, models) -> int:
    """Run every model in `models` (a list); blank line between blocks."""
    for i, model in enumerate(models):
        if i:
            print()
        run_model(relay_url, relay_key, ref_url, ref_key, model)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Detect a relay silently swapping/downgrading a model.")
    p.add_argument("--relay-url", required=True)
    p.add_argument("--relay-key", default=os.environ.get("RELAY_KEY", ""))
    p.add_argument("--ref-url", required=True)
    p.add_argument("--ref-key", default=os.environ.get("REF_KEY", ""))
    p.add_argument("--model", required=True, help="model id, or several comma-separated")
    a = p.parse_args()
    if not a.relay_key or not a.ref_key:
        p.error("provide --relay-key/--ref-key or set RELAY_KEY/REF_KEY env vars")
    models = parse_models(a.model)
    if not models:
        p.error("--model must name at least one model")
    return run(a.relay_url, a.relay_key, a.ref_url, a.ref_key, models)


if __name__ == "__main__":
    sys.exit(main())
