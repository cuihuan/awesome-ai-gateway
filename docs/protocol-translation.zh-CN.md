# 兼容面——网关为什么会弄坏 Claude Code(以及怎么在踩坑之前看出来)

**语言：** [English](protocol-translation.md) · 简体中文

*最近更新 2026-07-29 · [Awesome AI Gateway](../README.zh-CN.md) 的一部分——唯一带[可复算成本基准](../BENCHMARKS.zh-CN.md)与[诚实安全记分卡](../BENCHMARKS.zh-CN.md#第四部分--网关五维评分合规价格安全稳定可观测)的 AI 网关榜单。[⭐ 点个 Star](https://github.com/cuihuan/awesome-ai-gateway)。*

> 📊 **关键数字** · 三大 LLM 线协议的 usage 对象里**没有任何一个同名字段**(`prompt_tokens` vs `input_tokens` vs `promptTokenCount`——已对照下方官方参考核实,2026-07-29),所以每一次跨格式请求都是一场实时且有损的翻译。在最难的那条路径上——Anthropic 格式客户端(如 Claude Code)路由到 OpenAI 格式上游——独立实测结果是 **LiteLLM 3/3 · Bifrost 3/3 · Portkey OSS:未提供该路径**([xformat.json](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/xformat.json),中立 CI,2026-07-10)。"claude code" 一词出现在 **465 条 LiteLLM issue** 和 **138 条 new-api issue** 里(GitHub issue 搜索,2026-07-29)。而其中一种静默失败是明码标价的:`cache_control` 断点被剥离后,已缓存的输入会按 **10×** 重新计费——按 [Anthropic 官方价格表](https://platform.claude.com/docs/en/build-with-claude/prompt-caching),缓存读取只按基础输入价的 0.1× 收费。

[榜单](../README.zh-CN.md)上的每个网关都宣称某种版本的「OpenAI 兼容、支持 Claude、支持 Gemini」。这句话隐藏的是兼容性*住在哪一层*。一个网关从你的 Agent 接收 Anthropic 的 Messages 格式、再转发给 Anthropic 上游,做的是透传——便宜,也很难出错。而一个网关接收 Messages 格式、却由 OpenAI 格式的上游来供给(或者反过来),做的是**对每个请求、以及每个响应流式传输的每一个字节的结构化翻译**。这个翻译层是「网关弄坏了我的 Agent」类 bug 报告的最大单一来源,本章就是它的地图:三种协议到底在哪些地方不一致、翻译失败的五种方式(每一种都锚定到一条真实且经核实的 GitHub issue)、独立实测给出了什么结果,以及怎么用十分钟测试你自己的网关。

---

## 1. 60 秒讲清概念

2026 年真正要紧的线协议家族有三个:

| 家族 | 端点 | 原生使用方 | 参考文档(核实于 2026-07-29) |
|---|---|---|---|
| **OpenAI Chat Completions** | `POST /v1/chat/completions` | OpenAI + 整个「OpenAI 兼容」生态 | [developers.openai.com](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions) |
| **Anthropic Messages** | `POST /v1/messages` | Anthropic;Claude Code 发出的就是这个格式 | [platform.claude.com](https://platform.claude.com/docs/en/api/messages) |
| **Gemini generateContent** | `POST …:generateContent` / `:streamGenerateContent` | Google Gemini | [ai.google.dev](https://ai.google.dev/api/generate-content) |

一个「三种都会说」的网关坐在中间做实时翻译:请求体向下翻成上游的 schema,响应——包括 SSE 流,逐事件——再向上翻回客户端的 schema。翻译必须跨轮次保持工具调用的身份、实时重塑流式信封,还要在没有一个字段同名的 schema 之间重新推导 token 记账。透传保真是已解决的问题;**翻译保真才是 Agent 折戟之处**,因为编码 Agent 恰好把 schema 分歧最大的犄角旮旯全用上了:并行工具调用、超长 system prompt、增量式工具参数流式传输,以及缓存断点。

### 同一个工具调用,三种写法

下面是同一个模型响应——「为 San Francisco 调用 `get_weather`」——在三种协议线上的真实形态(形状取自上方官方参考;Gemini 的函数形状另见 [Google 的函数调用指南](https://ai.google.dev/gemini-api/docs/function-calling),检索于 2026-07-29):

```jsonc
// OpenAI chat.completions——arguments 是 JSON 编码的「字符串」;finish_reason: "tool_calls"
{ "role": "assistant",
  "tool_calls": [{
    "id": "call_abc123",
    "type": "function",
    "function": { "name": "get_weather",
                  "arguments": "{\"location\": \"San Francisco, CA\"}" } }] }
```

```jsonc
// Anthropic messages——input 是解析好的「对象」;stop_reason: "tool_use"
{ "role": "assistant",
  "content": [{
    "type": "tool_use",
    "id": "toolu_01T1x1fJ34qAmk2tNTrN7Up6",
    "name": "get_weather",
    "input": { "location": "San Francisco, CA" } }] }
```

```jsonc
// Gemini generateContent——一个 functionCall part,位于 "model" content 之内
{ "role": "model",
  "parts": [{
    "functionCall": { "name": "get_weather",
                      "args": { "location": "San Francisco, CA" } } }] }
```

三种不同的容器形状,两种不同的参数编码(字符串 vs 对象),外加工具*结果*回传时三种不同的配对机制:OpenAI 在专门的 `tool` 角色消息里按 `tool_call_id` 配对,Anthropic 在 `user` 消息内的 `tool_result` 块里按 `tool_use_id` 配对,而 Gemini 文档化的 `functionResponse` 形状按函数*名*配对、不是按 id。做翻译的网关要带着 `toolu_01N9FRKhMkWtQ77NLCKGy4An` 这样的 id 穿越从未铸造过它们的 schema——[Portkey-AI/gateway#980](https://github.com/Portkey-AI/gateway/issues/980) 里的原样载荷,展示的正是配对断裂那一刻:Anthropic 铸造的 `toolu_…` id 骑在 OpenAI 形状的 `tool_calls` 消息里。

---

## 2. 逐字段的分歧对照

以下全部取自当前的官方参考——[OpenAI Chat Completions](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions)(+ [流式事件](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events))、[Anthropic Messages](https://platform.claude.com/docs/en/api/messages)(+ [流式](https://platform.claude.com/docs/en/build-with-claude/streaming)、[提示缓存](https://platform.claude.com/docs/en/build-with-claude/prompt-caching))、[Gemini generateContent](https://ai.google.dev/api/generate-content)——均检索于 2026-07-29。

| 关注点 | OpenAI `chat.completions` | Anthropic `messages` | Gemini `generateContent` | 翻译器绝不能失手的地方 |
|---|---|---|---|---|
| **System prompt** | 是一条消息:`messages[]` 里的 `role: "system"`(或 `"developer"`);允许多条 | 顶层 `system` 参数(字符串或 text 块数组);`messages[]` 只在 `user`/`assistant` 间交替 | 顶层 `systemInstruction` 对象,带 `parts` | 把 N 条 system 消息收进 1 个顶层字段——一条都不能丢(见[失败模式 4](#failure-4)) |
| **角色** | `developer` · `system` · `user` · `assistant` · `tool` | `user` · `assistant` | `user` · `model` | `tool` 角色消息在 Anthropic/Gemini 里没有直接等价物——必须变成 `user` 轮次内的 content 块/part |
| **工具调用(模型 → 你)** | 带 `tool_calls[]` 的 `assistant` 消息:`{id, type: "function", function: {name, arguments}}`——`arguments` 是 **JSON 编码的字符串** | `tool_use` content 块:`{type, id, name, input}`——`input` 是**解析好的对象** | `model` content 内的 `functionCall` part | 参数的字符串↔对象转换,双向都要;把 `input` 当原始字符串转发是经典 bug |
| **工具结果(你 → 模型)** | 独立消息:`role: "tool"`,带 `tool_call_id` | `user` 消息内的 `tool_result` content 块:`{tool_use_id, content, is_error}` | `functionResponse` part | id 配对:每个 `tool_use.id` 都必须对上一个 `tool_result.tool_use_id`——任何一个落单,Anthropic 就 400(见[失败模式 1](#failure-1)) |
| **流式信封** | 无名 SSE `data:` 行,每行一个带 `choices[].delta` 的 `chat.completion.chunk`;以 `data: [DONE]` 收尾 | **具名 SSE 事件**:`message_start` → `content_block_start`/`content_block_delta`/`content_block_stop`(逐块,带 `index`)→ `message_delta` → `message_stop`,外加 `ping`/`error` | 经 `?alt=sse` 的 SSE;每个 chunk 是一个完整的 `GenerateContentResponse` JSON | 两边形状在结构上完全陌生:扁平 delta 流 ↔ 带索引的块状态机。翻译器必须*凭空合成*上游从未发出过的事件 |
| **流式文本** | `delta.content` 字符串碎片 | `content_block_delta`,`delta.type: "text_delta"` | `candidates[].content.parts[].text` | 在这里丢掉粒度 = 缓冲式「假」流式(见[失败模式 2](#failure-2)) |
| **流式工具参数** | 按 `index` 键控的 `delta.tool_calls[]` 碎片;`function.arguments` 以字符串片段累积 | `input_json_delta` 带 `partial_json` 字符串片段;最终 `tool_use.input` 必须是解析好的对象 | (未文档化等价的增量 JSON 契约) | 累积 partial JSON 再解析——块 `index` 记账错位会在流中途弄断客户端 |
| **结束/停止** | `finish_reason`:`stop` · `length` · `tool_calls` · `content_filter` · `function_call` | `stop_reason`:`end_turn` · `max_tokens` · `stop_sequence` · `tool_use` · `pause_turn` · `refusal` · `model_context_window_exceeded`;随 `message_delta` 到达 | `finishReason`(自有枚举) | `tool_calls`↔`tool_use` 必须精确映射,否则 Agent 不知道自己该去跑工具 |
| **思考/推理** | 推理只以计数暴露:`completion_tokens_details.reasoning_tokens` | 一等公民的 `thinking` content 块,经 `thinking_delta` 流式传输,并在 `content_block_stop` 前带一个 `signature_delta`(完整性签名) | `usageMetadata` 里的 `thoughtsTokenCount` | Anthropic 的 thinking 块(及其签名)在 OpenAI 格式的一跳里根本无处安放——往返一趟就丢 |
| **usage 命名** | `usage`:`prompt_tokens` · `completion_tokens` · `total_tokens`;流式:**只有最后一个 chunk** 携带 usage,且仅当 `stream_options: {"include_usage": true}` | `usage`:`input_tokens` · `output_tokens`(+ 缓存字段);流式:`message_start` 带初始 usage,`message_delta` 带**累计**总量 | `usageMetadata`:`promptTokenCount` · `candidatesTokenCount` · `totalTokenCount` | 零同名字段。翻译器若忘了向下游带 `include_usage`,或向上游丢了 `message_delta.usage`,账就对不上了 |
| **缓存记账** | `prompt_tokens` **包含**缓存 token;`prompt_tokens_details.cached_tokens` 是子集明细 | `input_tokens` **不含**缓存流量:总输入 = `input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens` | `usageMetadata` 里的 `cachedContentTokenCount` | 这个包含语义的反转是内置的重复计数陷阱(见[失败模式 3](#failure-3)) |
| **缓存断点** | 无——服务端自动缓存 | 在 content 块上显式 `cache_control: {"type": "ephemeral"}`(可选 `ttl`:`"5m"`/`"1h"`),每请求 ≤4 个 | 独立的 cached-content 机制 | `cache_control` **只**存在于 Anthropic 的 schema——朴素的翻译器会把它剥掉,悄无声息(见[失败模式 5](#failure-5)) |

### 同一句两个词的回复,流式,两边各一遍

对照表里最难凭空想象的一行是流式信封,所以这里把它摆出来。OpenAI 格式上游把 "Hello!" 以无名 `data:` chunk 流出(形状按[流式事件参考](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events)):

```text
data: {"object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":null}]}
data: {"object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}
data: {"object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}
data: {"object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}
data: [DONE]
```

而一个 Anthropic 格式客户端期待的,是同样两个词以*具名事件状态机*的形式到来(此序列即[官方文档自己的示例](https://platform.claude.com/docs/en/build-with-claude/streaming),有删节):

```text
event: message_start
data: {"type":"message_start","message":{"id":"msg_…","role":"assistant","content":[],"usage":{"input_tokens":25,"output_tokens":1},…}}

event: content_block_start
data: {"type":"content_block_start","index":0,"content_block":{"type":"text","text":""}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hello"}}

event: content_block_delta
data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"!"}}

event: content_block_stop
data: {"type":"content_block_stop","index":0}

event: message_delta
data: {"type":"message_delta","delta":{"stop_reason":"end_turn","stop_sequence":null},"usage":{"output_tokens":15}}

event: message_stop
data: {"type":"message_stop"}
```

做翻译的网关必须实时地从左边*制造出*右边:在上游第一个 chunk 到达之前就发明出 `message_start`,打开并关闭上游从未告知过的带编号 content 块,把 `finish_reason: "stop"` 转换成携带 `stop_reason: "end_turn"` 的 `message_delta`,*外加*上游只在最后一个 chunk 才发的 usage(且前提是网关记得向下游请求 `stream_options: {"include_usage": true}`)。流中途再来一个工具调用,它还得在正确的 `index` 处交错插入携带 `input_json_delta` 片段的第二个块。任何一处记账出错,客户端的流解析器就会抛异常——这正是[失败模式 2](#failure-2)里的 `Content block not found` 错误。

对照表里有两行在实践中破坏力最大。**usage 语义的反转**(OpenAI 把缓存 token 算在 `prompt_tokens` *里面*;Anthropic 把它们算在 `input_tokens` *外面*)意味着按 1:1 映射字段的翻译器,不是重复计数就是少算缓存输入——这不是某一家网关的 bug,而是这对 schema 内置的陷阱。而 **`cache_control` 在 OpenAI 里没有等价物**,意味着任何「内部统一归一化到 OpenAI 格式」的架构都默认摧毁它——除非有人显式写保留代码,而且要按 provider 适配器一个个写、永远写下去。

---

## 3. 五种失败模式

下面每种失败模式都锚定到一条真实、公开的 GitHub issue,均已核实其存在且确实说了我们引用它的内容(经 GitHub API,2026-07-29)。日期为 issue 创建日期;已关闭的 issue 在当前版本已修复——引用它们是作为这一*类别*的证据,而类别会复发。

<a name="failure-1"></a>
### 3.1 工具调用被改写或丢弃

翻译器在格式边界上丢掉了工具调用的身份或结构。典型形态:客户端把并行工具调用及其结果经网关送回,id 配对在翻译中断裂——上游以 `400 … the following tool_use ids were not found in tool_result blocks` 拒掉整个对话([Portkey-AI/gateway#980](https://github.com/Portkey-AI/gateway/issues/980),2025-03-09,已关闭——OpenAI 格式客户端带多个 `tool_calls` 转发到 Anthropic)。更隐蔽的变体是丢弃或字符串化参数:[跨格式探针](https://github.com/cuihuan/llm-gateway-bench/blob/main/probe/xformat.mjs)专门检查 `tool_use.input` 是否以*解析好的对象*到达,「经典的误翻」就是一个原始 JSON 字符串。对 Agent 而言,两种变体都是致命的:要么执行不了工具,要么续不上对话。

<a name="failure-2"></a>
### 3.2 假流式或坏流重组

把扁平的 OpenAI delta 流实时翻译成 Anthropic 的带索引块状态机(或反向)是真难,由此长出两种截然不同的失败。**重组后破碎**:合成的事件流违反客户端的状态预期——Claude Code 经 LiteLLM 的 `/v1/messages` 驱动 OpenAI 模型时,每次工具调用都记录 `Error streaming, falling back to non-streaming mode: Content block not found`([BerriAI/litellm#13373](https://github.com/BerriAI/litellm/issues/13373),2025-08-07,已关闭)。**假流式**:网关把上游的整个响应缓冲下来一坨吐出——你失去首 token 时间,也失去观察排队延迟的任何能力。实测特征是流只以 0–1 个 delta 事件到达、而非许多个:恰是 [fidelity.json](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/fidelity.json) 在干净 CI runner 上对 Portkey OSS v1.15.2 记录到的("only 0 chunk(s) — collapsed/buffered",2026-07-10;非流式正常,托管产品未测)。

<a name="failure-3"></a>
### 3.3 usage 误报与虚增

因为三种 usage schema 在命名和*语义*上都各说各话,翻译后的 usage 就是计费悄悄出错的地方。同一个陷阱的两侧各有一例已核实的实例:LiteLLM 的成本计算曾把 `cache_creation_input_tokens` 收了两次费——"once as prompt tokens and then again as cache creation tokens"——对着 Anthropic 控制台核实为 $0.05439 的真实成本报出 $0.091311,约 1.7×([BerriAI/litellm#9812](https://github.com/BerriAI/litellm/issues/9812),2025-04-08,已关闭)。而 new-api 的 `/v1/messages` → OpenAI 兼容上游的转换,返回的 `input_tokens` 仍然*包含*缓存 token——Anthropic 格式一侧的 usage 被虚增,正是上表里那个包含语义的反转([QuantumNous/new-api#4395](https://github.com/QuantumNous/new-api/issues/4395),2026-04-22,开放,中文)。如果你按 token 经网关付费,这种失败模式在你拿厂商自家控制台对账之前都是隐形的。

<a name="failure-4"></a>
### 3.4 上下文与 system prompt 截断

在「system prompt 是消息、且可以有多条」(OpenAI)与「system prompt 是一个顶层字段」(Anthropic)之间做翻译,天然招来静默的内容丢失。已核实实例:Portkey 的 Anthropic 适配器在每次迭代时覆盖 `system` 参数,于是客户端发多条 system 消息时**只有最后一条被转发**——之前的每条指令都无声消失([Portkey-AI/gateway#457](https://github.com/Portkey-AI/gateway/issues/457),2024-07-11,已关闭)。镜像变体是*搅碎*而非截断:new-api 的消息重序列化产生了 Anthropic 拒收的空 text content 块(`400 … text content blocks must be non-empty`),让 Claude Code 经该网关连 Anthropic 自家模型都完全不可用([QuantumNous/new-api#1854](https://github.com/QuantumNous/new-api/issues/1854),2025-09-20,已关闭,中文)。两者中截断更毒:400 你看得见;被丢掉的 system prompt 只会让你的 Agent 悄悄变笨。

<a name="failure-5"></a>
### 3.5 `cache_control` 被剥离——无声的 10× 账单

`cache_control` 断点只存在于 Anthropic 的 schema,所以任何不显式携带它的内部归一化步骤都会把它丢掉——而且*什么都不会报错*。请求成功,响应看起来一模一样;唯一的症状是 `cache_read_input_tokens: 0` 和一张更大的账单。已核实实例:Portkey 在通往 Vertex AI Anthropic 模型的路上剥掉 `cache_control`,报告者自己的前后 usage 显示缓存 token 为零([Portkey-AI/gateway#1579](https://github.com/Portkey-AI/gateway/issues/1579),2026-03-25,开放);LiteLLM 的 SDK→proxy 路径把 cache-control 注入静默变成 no-op([BerriAI/litellm#30319](https://github.com/BerriAI/litellm/issues/30319),2026-06-12,已关闭)。这一类别在各适配器上持续复发——如 [BerriAI/litellm#34797](https://github.com/BerriAI/litellm/issues/34797)(2026-07-27,开放)在更新的 provider 路径上报告了同样的剥离。算笔账:Anthropic 对缓存读取按**基础输入价的 0.1×** 计费([定价,检索于 2026-07-29](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)),于是本应按缓存读取计费的输入现在按全价计费——**这些 token 上就是 10×**。对一个 Claude Code 会话来说,system prompt 和工具定义占输入的大头且每次请求都重复,「这些 token」就是你账单的大头([榜单](../README.zh-CN.md#-评测速递)引用的生产遥测显示 system prompt 占输入 token 的 69%——Datadog,2026-04)。

---

## 4. 实测结果为什么长这样

[llm-gateway-bench](https://github.com/cuihuan/llm-gateway-bench) 项目测的正是本章的主题:黑盒方式、对着一个符合 spec 的 mock 上游、跑在中立 CI runner 上(无 API key、无厂商参与)。两个数据集,都测于 2026-07-10:

**同格式透传**([fidelity.json](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/fidelity.json))——OpenAI 客户端 → 网关 → OpenAI 格式上游。一个符合 spec 的响应能否在中转中幸存?

| 网关(版本) | tool_calls | 流式 | 流内 usage | 得分 |
|---|---|---|---|---|
| LiteLLM 1.91.1 | ✅ 完整 | ✅ 7 个 chunk,内容完整 | ✅ `total_tokens=14` 正常转发 | **3/3** |
| Bifrost(docker `95caedb1c368`) | ✅ 完整 | ✅ 5 个 chunk,内容完整 | ✅ 正常转发 | **3/3** |
| Portkey OSS 1.15.2 | ✅ 完整 | ❌ 0 个 chunk——被合并/缓冲 | ❌ 流中无 usage | **1/3** |

**跨格式翻译**([xformat.json](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/xformat.json))——Anthropic 格式客户端(即 Claude Code 路径)→ 网关 `/v1/messages` → OpenAI 格式上游。最难的路径,也是本章讲的路径:

| 网关(版本) | tool_use | 流式 | 流内 usage | 得分 |
|---|---|---|---|---|
| LiteLLM 1.91.1 | ✅ name + 解析好的 `input` | ✅ 3 个 `text_delta` 事件,完整 | ✅ `message_delta` 里有 `output_tokens` | **3/3** |
| Bifrost(docker `95caedb1c368`) | ✅ | ✅ 4 个 `text_delta` 事件 | ✅ | **3/3** |
| Portkey OSS 1.15.2 | — | — | — | **未提供**——其 `/v1/messages` 在 header 配置的自托管模式下仅限 Anthropic 系 provider;指向 OpenAI 上游返回 500 `"messages is not supported by openai"` |

三条解读,均立足于原始数据:

1. **LiteLLM 和 Bifrost 是在真翻译,而且翻得干净**——在本探针的三项检查上,两者都合成出形态良好的 Anthropic 事件流(`message_start` → `content_block_delta` …——在记录的 `stream_snippet` 里原文可见),把 `tool_use.input` 以解析好的对象交付,并把 `output_tokens` 落在最后的 `message_delta` 里。这等于把 §3 的全部五个失败模式面,在各自的咽喉要道上都过了一遍,全部通过。
2. **Portkey OSS 的跨格式「失败」是诚实的范围界定,不是坏掉**——数据里记的是 `unsupported: true`,不是撒谎的 3/3,也不是崩溃。其 `/v1/messages` 端点在这种部署模式下只向 *Anthropic 系 provider* 方向翻译。如果你的 Agent 说 Anthropic 格式而上游说 OpenAI 格式,这个网关(OSS header 配置模式)就不在菜单上——它在*同格式*流式探针上的 1/3 才是另一个独立的、真实的发现。
3. **你脚下的路径会随版本变——把版本锁死。**[探针自己的文件头](https://github.com/cuihuan/llm-gateway-bench/blob/main/probe/xformat.mjs)记载(测于 2026-07-09):LiteLLM ≤1.57.x 通过翻译到上游的 **Chat Completions** 端点来服务 `/v1/messages`,而 ≥~1.9x 把路径改写到了 OpenAI **Responses API**(`/v1/responses`、`input`/`max_output_tokens`)——且新 transformer 在上游用 `chat.completion` body 应答时会抛 `KeyError('created_at')`。同一个网关、同一份配置、不同的小版本:一个只支持 chat-completions 的上游从正常工作变成一段 Python traceback。bench 的处理方式是把两个端点都 mock 出来,并把不匹配标为 inconclusive 而非 0/3;你的生产栈可不会这么宽容。

---

## 5. 十分钟验证*你自己的*网关

别轻信本章——也别轻信任何厂商 README。整个失败目录的意义,就在于每个特征都便宜可查:

1. **先锁定并记录版本**——网关版本/镜像 digest 和 Agent 版本。§4 的 `KeyError('created_at')` 故事,就是「上个月还好好的」跨过一个小版本后的样子。
2. **跑黑盒探针(不需要 API key):**
   ```bash
   git clone https://github.com/cuihuan/llm-gateway-bench && cd llm-gateway-bench
   node probe/fidelity.mjs   # 同格式透传:tool_calls / 流式 / usage
   node probe/xformat.mjs    # Claude Code 路径:Anthropic 客户端 → OpenAI 上游
   ```
   把它们指向你的网关;它们在本地起一个符合 spec 的 mock 上游,打分与 §4 相同的 3 项检查。
3. **把你真实的 Agent 跑过去**——在草稿仓库里跑一个最小的 Claude Code 任务(`claude -p "list the files here and read one"`),一次性覆盖并行工具、流式、system prompt 和缓存。背靠背连跑两遍(第二遍就是缓存检查)。
4. **拿一笔请求的 usage 对账**——对着厂商自己的控制台。这是抓[失败模式 3](#failure-3)的唯一办法。

然后拿输出对照五种特征:

| 你看到的特征 | 失败模式 | 锚定 issue |
|---|---|---|
| `400 … tool_use ids were not found in tool_result blocks`;工具能触发,但下一轮 400 | 工具调用被改写/丢弃 | [Portkey#980](https://github.com/Portkey-AI/gateway/issues/980) |
| `Error: Streaming fallback triggered` / 长时间停顿后整个答案一次吐出 / 探针报 "collapsed/buffered" | 假流式或坏流重组 | [litellm#13373](https://github.com/BerriAI/litellm/issues/13373) |
| 网关计费 token ≠ 厂商控制台;`input_tokens` 随缓存活动波动 | usage 误报 | [litellm#9812](https://github.com/BerriAI/litellm/issues/9812)、[new-api#4395](https://github.com/QuantumNous/new-api/issues/4395) |
| Agent「忘掉」长期指令;`400 … text content blocks must be non-empty` | 上下文/system prompt 截断或搅碎 | [Portkey#457](https://github.com/Portkey-AI/gateway/issues/457)、[new-api#1854](https://github.com/QuantumNous/new-api/issues/1854) |
| *第二次*相同请求上 `cache_read_input_tokens: 0` | `cache_control` 剥离(无声 10×) | [Portkey#1579](https://github.com/Portkey-AI/gateway/issues/1579)、[litellm#30319](https://github.com/BerriAI/litellm/issues/30319) |

十分钟。另一个选项,是从账单上发现。

---

## 6. 各网关实现注记

只有行为能给出来源的网关——出自其自家文档或实测数据——才配得到一行论断;[榜单](../README.zh-CN.md)上的其余一切都诚实地标为**未实测**。厂商文档描述的是意图;*实测*列才是在中立 runner 上真实发生的事(2026-07-10)。

| 网关 | Anthropic 格式入站(`/v1/messages`) | 跨格式翻译 | 来源(检索于 2026-07-29) | 实测(xformat · fidelity) |
|---|---|---|---|---|
| **LiteLLM** | ✅ 有文档 | ✅ 到 "all LiteLLM supported providers"(openai、bedrock、vertex、gemini、azure…) | [docs.litellm.ai — `/v1/messages`](https://docs.litellm.ai/docs/anthropic_unified) | **3/3 · 3/3**(v1.91.1)——注意 §4 的传输层变更;锁死你的版本 |
| **Bifrost** | ✅ 即插即用的 Anthropic SDK 端点(`/anthropic`) | ✅ 在 OpenAI 兼容内核之上统一 23+ 家 provider | [README](https://github.com/maximhq/bifrost) · [Anthropic SDK 集成文档](https://docs.getbifrost.ai/integrations/anthropic-sdk/overview) | **3/3 · 3/3**(docker `95caedb1c368`) |
| **Portkey OSS** | 端点存在,但 header 配置自托管下仅限 Anthropic 系 provider | ❌ 该模式下不提供 Anthropic→OpenAI 路径(`"messages is not supported by openai"`) | 实测行为,[xformat.json](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/xformat.json) | **未提供 · 1/3**(v1.15.2;托管产品未测) |
| **new-api** | ✅ 有 "Native Claude Format" 文档 | ✅ 在 `/v1/messages` ↔ OpenAI 兼容上游之间转换(usage 转换的告诫:[#4395](https://github.com/QuantumNous/new-api/issues/4395)) | [docs.newapi.pro — Native Claude Format](https://docs.newapi.pro/en/docs/api/ai-model/chat/createmessage) | 未实测 |
| **one-api** | ❌——入站只收 OpenAI 格式("access all models via the standard OpenAI API format") | 仅出站:向非 OpenAI 下游渠道(含 Claude)改写请求/响应体 | [README](https://github.com/songquanpeng/one-api)(中文;含架构图) | 未实测 |
| [榜单](../README.zh-CN.md)上的其余一切 | — | — | — | **未实测**——在探测之前,把所有兼容性宣称都当厂商宣称对待 |

---

## 7. 这对选型意味着什么

如果你的 Agent 说 Anthropic 格式而上游不是(或者一旦[路由](../README.zh-CN.md#-智能路由与模型选择)生效后可能不是),那么翻译层*就是*产品本身——从[自托管开源](../README.zh-CN.md#-自托管开源)里有实测跨格式保真度的网关中列短名单,目前是 LiteLLM 和 Bifrost 的 3/3,并锁死你验证过的确切版本。在任何网关碰生产流量之前,把 §5 的那十分钟花掉,因为五种失败模式里有四种是无声的,还有一种在你最大的 token 桶上收 10×——缓存的经济账摊在[缓存过网关——钱的问题](../README.zh-CN.md#-缓存过网关钱的问题)里。然后按[如何安全选型](../README.zh-CN.md#如何安全选型)的做法,定期拿 usage 对厂商控制台对账——一个在版本 *N* 忠实的网关,离版本 *N+1* 的失败模式 3 只隔一次重构。

---

## 附录——本章依赖的全部来源

**一手协议参考**(均于 2026-07-29 检索并逐字段核对):

- OpenAI Chat Completions — [create / 参数与 usage schema](https://developers.openai.com/api/reference/python/resources/chat/subresources/completions) · [流式事件](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events)
- Anthropic Messages — [API 参考](https://platform.claude.com/docs/en/api/messages) · [流式](https://platform.claude.com/docs/en/build-with-claude/streaming) · [提示缓存与价格系数](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- Gemini — [generateContent / streamGenerateContent 参考](https://ai.google.dev/api/generate-content) · [函数调用形状](https://ai.google.dev/gemini-api/docs/function-calling)

**GitHub issue**(每条均经 GitHub API 核实其存在且确实说了所引内容,2026-07-29):

| Issue | 标题(节录) | 创建 | 状态 | 引用于 |
|---|---|---|---|---|
| [Portkey-AI/gateway#980](https://github.com/Portkey-AI/gateway/issues/980) | 400 anthropic error: `tool_use` ids not found in `tool_result` blocks | 2025-03-09 | 已关闭 | §3.1 |
| [BerriAI/litellm#13373](https://github.com/BerriAI/litellm/issues/13373) | Claude Code with an OpenAI model throws "Streaming fallback triggered" | 2025-08-07 | 已关闭 | §3.2 |
| [BerriAI/litellm#9812](https://github.com/BerriAI/litellm/issues/9812) | Anthropic cost calculations incorrect with prompt caching | 2025-04-08 | 已关闭 | §3.3 |
| [QuantumNous/new-api#4395](https://github.com/QuantumNous/new-api/issues/4395) | `/v1/messages` → OpenAI-compatible upstream usage conversion(中文) | 2026-04-22 | 开放 | §3.3 |
| [Portkey-AI/gateway#457](https://github.com/Portkey-AI/gateway/issues/457) | Anthropic only uses last system message | 2024-07-11 | 已关闭 | §3.4 |
| [QuantumNous/new-api#1854](https://github.com/QuantumNous/new-api/issues/1854) | Claude Code via new-api → "text content blocks must be non-empty"(中文) | 2025-09-20 | 已关闭 | §3.4 |
| [Portkey-AI/gateway#1579](https://github.com/Portkey-AI/gateway/issues/1579) | `cache_control` stripped when routing to Vertex AI Anthropic | 2026-03-25 | 开放 | §3.5 |
| [BerriAI/litellm#30319](https://github.com/BerriAI/litellm/issues/30319) | Prompt caching silently stripped through proxy path | 2026-06-12 | 已关闭 | §3.5 |
| [BerriAI/litellm#34797](https://github.com/BerriAI/litellm/issues/34797) | `cache_control` stripped in SAP provider path | 2026-07-27 | 开放 | §3.5 |

**实测数据与厂商文档**:

- [xformat.json](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/xformat.json) · [fidelity.json](https://github.com/cuihuan/llm-gateway-bench/blob/main/data/fidelity.json) — 中立 CI 探针结果,测于 2026-07-10(LiteLLM 1.91.1、Bifrost docker `95caedb1c368`、Portkey OSS 1.15.2)
- [probe/xformat.mjs](https://github.com/cuihuan/llm-gateway-bench/blob/main/probe/xformat.mjs) — 探针源码;LiteLLM `/v1/messages` 传输层变更与 `KeyError('created_at')` 的注记(测于 2026-07-09)
- [LiteLLM `/v1/messages` 文档](https://docs.litellm.ai/docs/anthropic_unified) · [Bifrost README](https://github.com/maximhq/bifrost) + [Anthropic SDK 集成](https://docs.getbifrost.ai/integrations/anthropic-sdk/overview) · [new-api Native Claude Format](https://docs.newapi.pro/en/docs/api/ai-model/chat/createmessage) · [one-api README](https://github.com/songquanpeng/one-api)(均检索于 2026-07-29)
- issue 计数("claude code" 在 tracker 里:LiteLLM 465 · new-api 138 · Portkey 6)— GitHub issue 搜索 API,查询于 2026-07-29

---

*觉得有用?[⭐ 给榜单点个 Star](https://github.com/cuihuan/awesome-ai-gateway) — 下一个选网关的工程师就是这样找到它的。欢迎经 [PR](https://github.com/cuihuan/awesome-ai-gateway) 或 [issue](https://github.com/cuihuan/awesome-ai-gateway/issues) 修正与补充 — 上面每条论断都标了日期、带了链接,方便你自己复核;如果某条链接的 issue 已修复、或某个探针结果变了,那正是我们想收的 PR。*
