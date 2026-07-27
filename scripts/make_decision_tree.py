#!/usr/bin/env python3
"""Render the "which AI gateway should you use?" decision tree to a PNG.

This turns the README's ASCII decision tree into a shareable image — the
second-most-viral asset after the cost chart (a "which X should I use?" framing
travels well on HN / 掘金 / 知乎). Two columns: hosted vs. self-host, each a
list of (condition → recommended gateways) leaves.

The tree is editorial (decision logic, not a metric), but it must stay
*consistent* with the list: every self-hostable gateway it recommends maps to a
repo tracked in data/projects.json. ``build_tree`` is a pure function and
``self_hosted_slugs`` exposes that mapping so a unit test can enforce it — if a
recommendation drifts from the tracked set, CI fails.

PIL is imported lazily inside ``render()`` so the data layer stays importable
(and unit-testable) on the CI runner, which has no Pillow.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_FILE = ROOT / "data" / "projects.json"
OUT = ROOT / "assets" / "decision-tree.png"

# Self-hostable gateways named in the tree → their tracked repo in
# data/projects.json. Used by the test to prove the tree never recommends a
# gateway the list doesn't actually track.
SELF_HOSTED_REPO = {
    "LiteLLM": "BerriAI/litellm",
    "Bifrost": "maximhq/bifrost",
    "TensorZero": "tensorzero/tensorzero",
    "new-api": "QuantumNous/new-api",
    "one-api": "songquanpeng/one-api",
    "GPT-Load": "tbphp/gpt-load",
    "Kong": "Kong/kong",
    "Higress": "higress-group/higress",
    "APISIX": "apache/apisix",
    "Envoy AI Gateway": "envoyproxy/ai-gateway",
    "agentgateway": "agentgateway/agentgateway",
}


def build_tree(lang: str = "en") -> dict:
    """The decision tree as structured data (no rendering).

    Returns ``{"title": str, "branches": [{"label", "kind", "leaves": [
    {"cond": str, "picks": [str, ...], "tag": str|None}]}]}``. ``kind`` is
    ``"hosted"`` or ``"self"`` so the renderer can colour the two columns.
    """
    t = _TREE_ZH if lang == "zh" else _TREE_EN
    return json.loads(json.dumps(t))  # deep copy so callers can't mutate the constant


def self_hosted_slugs(tree: dict) -> set[str]:
    """Every gateway recommended under a ``kind == "self"`` branch."""
    picks = set()
    for b in tree["branches"]:
        if b["kind"] == "self":
            for leaf in b["leaves"]:
                picks.update(leaf["picks"])
    return picks


def tracked_repos() -> set[str]:
    data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    return set(data["release_tracked_repos"])


_TREE_EN = {
    "title": "Which AI gateway should you use?",
    "branches": [
        {
            "label": "NO — hosted, minimal ops",
            "kind": "hosted",
            "leaves": [
                {"cond": "Cheapest access to many models", "picks": ["OpenRouter", "Vercel AI Gateway"], "tag": "0% markup"},
                {"cond": "Your own keys + free control plane", "picks": ["Cloudflare AI Gateway"], "tag": None},
                {"cond": "Already committed to one cloud", "picks": ["AWS Bedrock", "Azure OpenAI", "Vertex AI"], "tag": None},
                {"cond": "Enterprise compliance (SOC2 / HIPAA)", "picks": ["Portkey", "Azure / Bedrock"], "tag": None},
            ],
        },
        {
            "label": "YES — self-host, open source",
            "kind": "self",
            "leaves": [
                {"cond": "Python stack, most features", "picks": ["LiteLLM"], "tag": None},
                {"cond": "Max performance (Go)", "picks": ["Bifrost"], "tag": None},
                {"cond": "Multi-user keys + budgets + admin UI", "picks": ["LiteLLM", "new-api"], "tag": "family / small team"},
                {"cond": "China models + key distribution", "picks": ["new-api", "one-api", "GPT-Load"], "tag": None},
                {"cond": "Enterprise K8s + audit", "picks": ["Kong", "Higress", "APISIX"], "tag": None},
                {"cond": "Govern agent / MCP traffic", "picks": ["Envoy AI Gateway", "agentgateway"], "tag": None},
            ],
        },
    ],
}

_TREE_ZH = {
    "title": "我该用哪个 AI 网关？",
    "branches": [
        {
            "label": "不部署：托管，省运维",
            "kind": "hosted",
            "leaves": [
                {"cond": "最低成本接入多模型", "picks": ["OpenRouter", "Vercel AI Gateway"], "tag": "0 加价"},
                {"cond": "自己的 Key + 免费控制面", "picks": ["Cloudflare AI Gateway"], "tag": None},
                {"cond": "已绑定某朵云", "picks": ["AWS Bedrock", "Azure OpenAI", "Vertex AI"], "tag": None},
                {"cond": "企业合规（SOC2 / HIPAA）", "picks": ["Portkey", "Azure / Bedrock"], "tag": None},
            ],
        },
        {
            "label": "要部署：自托管，开源",
            "kind": "self",
            "leaves": [
                {"cond": "Python 栈、功能最全", "picks": ["LiteLLM"], "tag": None},
                {"cond": "追求性能（Go）", "picks": ["Bifrost"], "tag": None},
                {"cond": "多用户 Key + 预算 + 管理面板", "picks": ["LiteLLM", "new-api"], "tag": "家庭/小团队"},
                {"cond": "国产模型、Key 分发计费", "picks": ["new-api", "one-api", "GPT-Load"], "tag": None},
                {"cond": "企业 K8s、审计合规", "picks": ["Kong", "Higress", "APISIX"], "tag": None},
                {"cond": "治理 Agent / MCP 流量", "picks": ["Envoy AI Gateway", "agentgateway"], "tag": None},
            ],
        },
    ],
}


# ── Rendering (PIL only; not exercised by unit tests) ────────────────────────

W, H = 1280, 800
BG = "#0d1117"
WHITE = "#f0f6fc"
GRAY = "#8b949e"
BLUE = "#58a6ff"
GREEN = "#3fb950"
GOLD = "#e3b341"
TRACK = "#161b22"
PILL_BG = "#1f2630"


def _font(lang: str):
    from PIL import ImageFont

    if lang == "zh":
        for p in (
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
        ):
            if Path(p).exists():
                return lambda s, bold=False: ImageFont.truetype(p, s)
    fdir = "/System/Library/Fonts/Supplemental/"
    return lambda s, bold=False: ImageFont.truetype(fdir + ("Arial Bold.ttf" if bold else "Arial.ttf"), s)


def render(tree: dict, out: Path = OUT, lang: str = "en") -> Path:
    from PIL import Image, ImageDraw

    fnt = _font(lang)
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 6], fill=BLUE)

    d.text((48, 38), tree["title"], font=fnt(40, bold=True), fill=WHITE)
    d.text((48, 96), "github.com/cuihuan/awesome-ai-gateway", font=fnt(20), fill=GRAY)

    col_w = (W - 48 * 2 - 40) / 2
    cols_x = [48, 48 + col_w + 40]
    top = 150

    def pill(dr, x, y, text, color):
        f = fnt(19, bold=True)
        bb = dr.textbbox((0, 0), text, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        pad_x, pad_y = 14, 8
        dr.rounded_rectangle(
            [x, y, x + tw + pad_x * 2, y + th + pad_y * 2 + 4], radius=9, fill=PILL_BG, outline=color, width=2
        )
        dr.text((x + pad_x, y + pad_y), text, font=f, fill=color)
        return x + tw + pad_x * 2 + 10  # next x

    for ci, branch in enumerate(tree["branches"]):
        x0 = cols_x[ci]
        color = BLUE if branch["kind"] == "hosted" else GREEN
        # header bar
        d.rounded_rectangle([x0, top, x0 + col_w, top + 44], radius=10, fill=TRACK, outline=color, width=2)
        d.text((x0 + 16, top + 11), branch["label"], font=fnt(22, bold=True), fill=color)

        y = top + 64
        for leaf in branch["leaves"]:
            d.text((x0 + 8, y), "• " + leaf["cond"], font=fnt(18, bold=True), fill=WHITE)
            y += 30
            px = x0 + 22
            for name in leaf["picks"]:
                px = pill(d, px, y, name, color)
            if leaf.get("tag"):
                d.text((px + 2, y + 8), leaf["tag"], font=fnt(16), fill=GOLD)
            y += 52

    d.text(
        (48, H - 40),
        "Cost · routing · security scorecard inside — pick the gateway, then the model."
        if lang == "en"
        else "内附成本 · 路由 · 安全评分卡 — 先选网关，再选模型。",
        font=fnt(20, bold=True),
        fill=BLUE,
    )

    out.parent.mkdir(exist_ok=True)
    img.save(out, "PNG")
    return out


def main() -> int:
    targets = [("en", OUT), ("zh", ROOT / "assets" / "decision-tree.zh-CN.png")]
    for lang, path in targets:
        try:
            render(build_tree(lang), path, lang)
            print(f"wrote {path} ({path.stat().st_size // 1024} KB)")
        except Exception as e:  # zh may lack a CJK font on some machines — don't fail the EN render
            print(f"skipped {path.name}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
