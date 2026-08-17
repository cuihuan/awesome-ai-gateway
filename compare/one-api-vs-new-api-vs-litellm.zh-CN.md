# one-api vs new-api vs LiteLLM:国内大模型 API 中转/网关怎么选(2026)

*更新于 2026-06-13 · [Awesome AI Gateway](../README.zh-CN.md) 的一部分。[⭐ 点个 Star](https://github.com/cuihuan/awesome-ai-gateway)。*

> 📊 **关键数字** · **new-api(<!--s:QuantumNous/new-api-->⭐ 45.3k<!--/s-->)已超越 one-api(<!--s:songquanpeng/one-api-->⭐ 36.4k<!--/s-->)** 成为最活跃的国内中转/分发面板(LiteLLM <!--s:BerriAI/litellm-->⭐ 56.5k<!--/s-->)。⚠️ 别用转售「免费 API」中转:2026 年研究在转售中转里测出 **45.8%** 的指纹测试模型身份不符、输出偏差最高 **47%**([*Real Money, Fake Models*](https://arxiv.org/abs/2603.01919))——自建、用你自己的 key 才安全。另一个大背景：OpenRouter 100 万亿 token 真实流量研究显示，**中国开源模型的 token 占比从 2024 底的 1.2% 涨到峰值周约 30%**、开源权重整体已占 ~⅓（[arXiv 2601.10088](https://arxiv.org/abs/2601.10088)）——分发面板前置多模型路由，正是吃这波红利的方式。

国内自建大模型 API 中转/分发,绕不开这三个名字:**one-api、new-api、LiteLLM**。它们都能"一个接口打通多家模型",但定位差别很大。这是一份基于数据的实话对比。

## 一眼对比

| | one-api | new-api | LiteLLM |
|---|---|---|---|
| **定位** | 元祖级中转/分发系统 | one-api 的活跃继任者 | 功能最全的自托管网关 |
| **语言** | Go | Go | Python |
| **协议** | MIT | AGPL-3.0 | MIT(核心) |
| **国产模型** | ✅ 豆包/DeepSeek/通义… | ✅ + Rerank/Realtime | ✅(走 OpenAI 格式) |
| **计费/分发** | ✅ | ✅ 更完善 | ✅ 虚拟 Key/预算 |
| **维护活跃度** | 已放缓 | 最活跃 | 高(周更) |
| **Star** | <!--s:songquanpeng/one-api-->⭐ 36.4k<!--/s--> | <!--s:QuantumNous/new-api-->⭐ 45.3k<!--/s-->(已反超) | <!--s:BerriAI/litellm-->⭐ 56.5k<!--/s--> |

## 按需求选

- **要团队计费 + 卖/分发额度 → new-api。** 现在国内最活跃的中转系统,已在 Star 上反超 one-api,协议转换、计费、Rerank/Realtime 都更全。**注意是 AGPL-3.0**,商用嵌入前务必看清协议义务。
- **只要个人/小团队跑通、图稳定经典 → one-api。** 元祖、MIT、生态成熟,但维护节奏明显放缓——新需求建议直接上 new-api。
- **要功能最全、虚拟 Key/预算/护栏/可观测 → LiteLLM。** Python 生态、100+ 厂商、社区最大。国产模型也能通过 OpenAI 兼容层接入。代价:功能重,且因太流行成了攻击目标(见下)。

## 安全:别只看 Star 数

自托管 = 安全你自己扛。2026 年的实话:

- **new-api** 2026 年有一串 CVE(IDOR 越权 CVE-2026-30886、SSRF、SQLi/DoS)——**务必隔离部署、限制出站、别把后台暴露公网、及时打补丁**。
- **one-api** 同源风险,且维护放缓,上生产前自行审计。
- **LiteLLM** 两个严重 CVE(预鉴权 SQLi + 一个上了 CISA 在野利用清单的 RCE)均**已在 v1.83.7 修复**——但其后又发布了 10 条安全公告,请跑 ≥1.84.0 并锁定版本。

23 个网关的合规/安全/稳定 ★1–5 评分见[网关评分卡](../BENCHMARKS.zh-CN.md#第四部分--网关五维评分合规价格安全稳定可观测)。

## 别忽略模型成本

网关本身 0 加价,真正花钱的是**背后的模型**。同一份 10 万 token 报告:**DeepSeek $0.03 vs GPT-5.5 $3.01,差 106 倍**。国产模型(DeepSeek/Kimi/GLM/通义)把成本压到了几十分之一,还能私有化、数据零出境——这正是国内自建中转的最大价值。[完整成本对比表](../BENCHMARKS.zh-CN.md)。

## 结论

- **团队计费/分发 → new-api**(看清 AGPL)
- **个人跑通/经典稳定 → one-api**
- **功能最全/要护栏可观测 → LiteLLM**(锁最新 stable)

完整 50+ 网关(按痛点分类、带决策树和评测数据):
👉 **[Awesome AI Gateway](https://github.com/cuihuan/awesome-ai-gateway)** · [在线交互站](https://cuihuan.github.io/awesome-ai-gateway/) · [English](../README.md)
