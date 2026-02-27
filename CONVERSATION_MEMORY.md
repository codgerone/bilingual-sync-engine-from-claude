# 对话记忆文件

> **用途**：跨设备、跨对话保持连贯性。新对话开始时，告诉 Claude "请先阅读 CONVERSATION_MEMORY.md"

---

## 📅 最近更新：2026-02-27

### 当前项目状态

**阶段**：mapper.py 代码优化（继续） — 职责重新分配 & 顶格输出策略修正

---

### 🎯 2026-02-25/27 对话记录：mapper.py 持续优化

#### 本轮完成的代码修改

1. **API key 读取逻辑从 RevisionMapper 移入 `create_llm_client()`**
   - Meiqi 发现：RevisionMapper 中的 `PROVIDER_ENV_KEYS` + provider 合法性检查与 `create_llm_client()` 中的检查重复
   - 修改：`PROVIDER_ENV_KEYS` 字典和 `os.getenv()` 逻辑全部移入工厂函数
   - 删除 RevisionMapper 的 `PROVIDER_ENV_KEYS` 类属性
   - RevisionMapper 调用简化为 `create_llm_client(self.provider, model)`
   - `api_key` 保留在 `create_llm_client` 签名中作为显式参数（默认 None，内部从环境变量读取）

2. **`_map_max_tokens_strategy()` 简化**
   - `results_by_row`（字典）→ `results`（列表）+ `done_ids`（set）
   - 每轮直接 `results.append(item)`，最后 `return results`
   - Meiqi 的论点：pending_rows 已排除已处理行，不可能重复，不需要字典去重

3. **删除所有 LLM Client 的 `max_tokens` 参数**
   - Meiqi 质疑：为什么人为设 `max_output_tokens = 4096`？顶格输出应该用模型的真实上限
   - 从 `LLMClient`、`AnthropicClient`、`OpenAICompatibleClient`、`WenxinClient` 的 `call()` 和 `call_with_cache()` 中删除 `max_tokens` 参数
   - OpenAI 兼容 API 和 Wenxin：不传 max_tokens，让模型自动用自己的上限
   - Anthropic API（强制要求 max_tokens）：在 AnthropicClient 内部用 `MODEL_MAX_TOKENS` 字典查询模型真实上限
   - 删除 RevisionMapper 的 `max_output_tokens` 参数

4. **AnthropicClient 添加 MODEL_MAX_TOKENS 字典**
   - 从官方文档获取准确数据（之前写的 16384 完全错误）
   - Opus 4.6: 128K, Sonnet 4.6: 64K, Sonnet 4: 64K, Opus 4: 32K 等

#### 未完成的修改（下次继续）

1. **`_map_batch_strategy()` 需要同步修改**
   - `results_by_row` → `results` + `done_ids`（同 max_tokens 策略的改法）
   - `self.max_output_tokens` 已被删除，第 565 行 `batch_output_limit = int(self.max_output_tokens * self.output_safety_ratio)` 会报错
   - 需要改为从 `self.client.model_max_output_tokens` 获取

2. **每个 LLM Client 需要存 `model_max_output_tokens` 属性**
   - 已确认方案：在 PROVIDERS 字典中为每个 provider 加 `model_max_output_tokens` 字段
   - AnthropicClient 已有 MODEL_MAX_TOKENS 字典
   - OpenAICompatibleClient 和 WenxinClient 需要在创建时传入
   - 各 provider 默认模型的最大输出上限（已查实）：
     - DeepSeek (deepseek-chat): 8,000
     - Qwen (qwen-plus): 32,768
     - Wenxin (ernie-4.0): 2,000
     - Doubao (doubao-pro-32k): 4,000
     - Zhipu (glm-4): 4,000
     - OpenAI (gpt-4o): 16,384

#### Meiqi 展现的设计思维

- **消除重复**：发现 RevisionMapper 和 create_llm_client 中 provider 检查的重复，提出合并
- **职责归属**：工厂函数的职责就是"造出能用的 client"，包括拿 key 都是它的事
- **质疑人为限制**：顶格输出策略不应该有人为设定的低上限（4096），应该用模型真实上限
- **命名精确性**：提出 `model_max_output_tokens` 比 `max_tokens` 更准确

#### 学习的 Python 知识点

- **Python 属性查找顺序**：`self.X` 先找实例属性，找不到再找类属性
- **`dict.get(key)` vs `dict[key]`**：前者 key 不存在返回 None，后者抛 KeyError
- **列表推导式**：`[expr for item in list if condition]`

---

### 📁 当前 mapper.py 结构（2026-02-27 更新）

```
RevisionMapper 类
├── __init__(provider, model, strategy, ...)  # 无 PROVIDER_ENV_KEYS，无 max_output_tokens
│
├── map_row_pairs()                # 主入口
│   ├── _map_max_tokens_strategy() # results 列表 + done_ids set
│   └── _map_batch_strategy()      # ⚠️ 待修改：仍用 results_by_row 和 self.max_output_tokens
│       ├── _build_batches()
│       └── _map_single_batch()
│
├── _build_batch_system_prompt()   # 严格格式 prompt
├── _build_batch_user_message()    # 简化版
│
├── _parse_json_response()         # batch 策略用
├── _salvage_valid_results()       # max_tokens 策略用，精确正则
└── _is_valid_result()             # 字段类型验证

create_llm_client(provider, api_key, model)  # 工厂函数，内含 PROVIDER_ENV_KEYS

LLM Client 层
├── LLMClient (ABC)               # call() 和 call_with_cache() 无 max_tokens 参数
├── AnthropicClient                # 内部用 MODEL_MAX_TOKENS 字典传 max_tokens 给 API
├── OpenAICompatibleClient         # 不传 max_tokens，模型自动用上限
└── WenxinClient                   # 不传 max_tokens，模型自动用上限
```

---

### 🎯 2026-02-14 对话记录归档：mapper.py 代码优化与学习

#### 完成的代码修改（精简）

- 删除冗余方法（`map_text_revision()`、`quick_map()`）
- 两个策略改用"无进展检测"代替固定重试
- 解析函数重构（`_parse_json_response`、`_salvage_valid_results`、`_is_valid_result`）
- Prompt 改进（更严格格式、STRING ESCAPING 规则）
- `create_llm_client()` 重构（统一用 `config["client_class"]` 分叉）
- `RevisionMapper.__init__` 重构（移除 `**kwargs`）
- 简化 `_build_batch_user_message()`

#### 学习的 Python 知识点

- `@abstractmethod`、`os.getenv()`、`or` 短路求值、多态

---

### 🎯 2026-01-28 对话记录：策略描述修正

#### 问题

在之前的重塑过程中，我对 `max_tokens` 策略的描述有严重误导：
- 错误描述："ALL rows in ONE API call"（所有行在一次 API 调用中完成）
- 用户纠正：这不是说全过程只调一次 API！

#### 用户的核心观点

> "单次调用 API 达到输出上限才停止这个方案，并不是说全过程只调用一次 API。面对特别长的文档不可能只调用一次 API 就完成所有工作，肯定还是得分批处理，只不过在每次调用 API 的时候，一直使用到输出极限，让 LLM 顶格输出才停止。"

#### 正确理解

**max_tokens 策略的真正含义**：
```
第1次调用: 发送待处理行 → 输出到 token 上限被截断 → 正则抢救 → 拿到一部分结果
第2次调用: 只发送剩余行 → 输出到 token 上限 → 抢救 → 又拿到一部分
第3次调用: 再发剩余行 → ...
直到全部完成
```

- 对于短文档：可能一次调用就够
- 对于长文档：会自动分多次调用完成
- 核心思想：**每次调用都顶格输出**，不提前估算批次大小

#### 代码逻辑确认

实际上 `_map_max_tokens_strategy()` 的代码逻辑是正确的——retry 循环就是处理多次调用的机制。问题只是描述文字误导。

#### 修正的文件

| 文件 | 修正内容 |
|------|---------|
| `src/mapper.py` | 架构图、Strategies 说明、类 docstring、方法 docstring、print 信息 |
| `src/engine.py` | `__init__` docstring、CLI `--strategy` 帮助文本 |
| `CLAUDE.md` | 策略描述 |
| `docs/DATA_FLOW.md` | 策略表格、函数树注释 |
| `README.md` | CLI 选项说明 |

#### 修正后的策略描述

| 策略 | 描述 |
|------|------|
| `max_tokens` | 每次调用顶格输出到 token 上限，正则抢救解析，剩余行继续下次调用 |
| `batch` | 预估批次大小，json.loads 解析，失败时缩小批次重试 |

---

### 🎯 2026-01-22/28 项目重塑完成

#### 完成的工作

1. **Mapper 模块重塑**
   - 合并 `mapper.py` 和 `mapper2_from_codex.py` 为统一的 `mapper.py`
   - 支持 7 个 LLM 提供商：Anthropic、DeepSeek、Qwen、Wenxin、Doubao、Zhipu、OpenAI
   - 两种策略：`max_tokens`（默认）和 `batch`
   - LLM Client 抽象层：`LLMClient` → `AnthropicClient`, `OpenAICompatibleClient`, `WenxinClient`

2. **配置模块更新**
   - `config.py` 添加 `LLM_PROVIDERS` 字典（7 个提供商配置）
   - `LANGUAGE_PRESETS` 语言预设
   - `DEFAULT_STRATEGY = "max_tokens"`
   - `LLM_MAX_TOKENS = 4096`

3. **文档整理**
   - 创建 `docs/DATA_FLOW.md`（完整管道文档）
   - 创建 `docs/KNOWLEDGE_MAP.md`（合并两个知识地图）
   - 更新 `README.md`、`CLAUDE.md`

4. **文件清理**（删除 13+ 文件）
   - `mapper2_from_codex.py`
   - 学习用测试文件
   - 旧文档文件

5. **基准测试**
   - 创建 `tests/benchmark_mapper.py`

---

### 📁 mapper.py 结构（2026-01-28 版本，已被 2026-02-14 版本替代，见上方）

---

### 📝 重要学习点

1. **max_tokens 策略 ≠ 只调一次 API**
   - 每次调用顶格输出，用满模型的真实输出上限（不是人为设定的低值）
   - 长文档会自动分多次调用
   - 关键是"每次都用满"，不是"只用一次"

2. **正则抢救模式**（已优化）
   - 输出被截断时，用精确正则匹配 prompt 规定的字段顺序提取完整对象
   - 不再丢弃最后一个对象（正则只匹配完整闭合的 `{...}`）
   - 使用"无进展检测"代替固定重试次数

3. **多 LLM 提供商支持**
   - Anthropic：原生 API，支持 Prompt Caching，API 强制要求 max_tokens
   - DeepSeek/Qwen/Doubao/Zhipu/OpenAI：OpenAI 兼容格式，不传 max_tokens 自动用模型上限
   - Wenxin：原生 API，需要 OAuth 令牌

4. **代码设计原则**（Meiqi 总结）
   - 显式优于隐式：函数签名明确列出所有核心输入
   - 常用参数显式、边缘参数隐式：平衡可读性和简洁性
   - 条件分叉基于同一参量：逻辑更一致、更美
   - 不做多余转写：如果数据结构已经正确，不要重新构造
   - 消除重复：同一个检查不要在两个地方各做一遍
   - 职责归属：工厂函数负责"造出能用的东西"，调用方不该关心内部细节
   - 不设人为低限：顶格输出就应该用模型真实上限，不是程序员拍脑袋定的值

---

### ⏭️ 下次对话可继续的内容

1. **⚠️ 优先**：完成 `_map_batch_strategy()` 修改（results_by_row → results + done_ids, 修复 self.max_output_tokens 引用）
2. **⚠️ 优先**：为每个 LLM Client 添加 `model_max_output_tokens` 属性（方案已确认：通过 PROVIDERS 字典传入）
3. 同步更新 engine.py（如果有受 mapper.py 修改影响的调用）
4. 同步更新 config.py（`LLM_MAX_TOKENS = 4096` 可能需要删除）
5. 深入学习 `applier.py` 的词级别 diff 实现
6. 用真实双语 Word 文档测试完整流程
7. 讨论产品化方向

---

## 📜 历史记录归档

### 2026-01-18：批量处理优化方案讨论

- Meiqi 提出当前 mapper.py 对每行单独调用 API 浪费资源
- 讨论了单行调用 vs 批量调用的数据对比
- Meiqi 核心观点：速度至上、错误预防、精准重试
- 讨论了动态分批、容错解析等方案
- 此讨论内容在 2026-01-22 的项目重塑中实现

### 2026-01-10：mapper.py 重构 & Prompt Caching

- 清理 V1 代码，只保留 V2
- 实现 Prompt Caching 优化（节省约 60% API 成本）
- 学习 Token 消耗机制

### 2026-01-08：extractor.py 重构完成

- 清理 V1 代码
- 实现打包提取（`extract_row_pairs()`）
- 新增快速检查优化（`_has_revisions()`）

### 2026-01-07：V2 重塑方案实现

- 核心洞察：翻译是语义对应，不是词汇对应
- extractor 输出 `{before_text, after_text}`
- applier 用词级别 diff 生成 track changes

### 2026-01-06：minidom 学习 & 项目初始化

- 理解 minidom 基本概念
- 项目从 Claude 网页端生成
- Meiqi 的学习目标：通过实际项目学习 coding、Python、AI 产品开发

---

## 如何使用这个文件

**开始新对话时**，发送：
```
请先阅读 CONVERSATION_MEMORY.md，了解我们之前的讨论进展，然后我们继续
```

**结束对话前**，让我更新这个文件：
```
请更新 CONVERSATION_MEMORY.md，记录今天的讨论进展
```
