# 对话记忆文件

> **用途**：跨设备、跨对话保持连贯性。新对话开始时，告诉 Claude "请先阅读 CONVERSATION_MEMORY.md"

---

## 📅 最近更新：2026-01-28

### 当前项目状态

**阶段**：项目重塑完成，进入稳定使用阶段

**项目结构**：
```
bilingual-sync-engine/
├── src/
│   ├── __init__.py        # v2.0.0
│   ├── config.py          # 多 LLM 提供商配置
│   ├── extractor.py       # XML 解析，修订提取
│   ├── mapper.py          # 统一 mapper（7 提供商，2 策略）
│   ├── applier.py         # 词级别 diff，track changes 生成
│   └── engine.py          # 主引擎，CLI
├── tests/
│   └── benchmark_mapper.py
├── docs/
│   ├── DATA_FLOW.md
│   └── KNOWLEDGE_MAP.md
└── examples/
    └── example_usage.py
```

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

### 📁 当前 mapper.py 结构

```
RevisionMapper 类
├── __init__(provider, api_key, model, strategy, max_output_tokens)
│
├── map_row_pairs()                    # 主入口
│   ├── _map_max_tokens_strategy()     # 每次调用顶格输出，正则抢救
│   │       └── _salvage_objects()     # 正则提取完整 JSON 对象
│   └── _map_batch_strategy()          # 预估批次，json.loads
│           ├── _build_batches()
│           └── _map_single_batch()
│
├── map_text_revision()                # 单行便捷方法（包装为列表调用 map_row_pairs）
│
└── LLM Client 层
    ├── LLMClient (ABC)                # 抽象基类
    ├── AnthropicClient               # 原生 Anthropic API，支持 Prompt Caching
    ├── OpenAICompatibleClient        # DeepSeek/Qwen/Doubao/Zhipu/OpenAI
    └── WenxinClient                  # 百度文心，OAuth 令牌管理
```

---

### 📝 重要学习点

1. **max_tokens 策略 ≠ 只调一次 API**
   - 每次调用顶格输出，用满输出配额
   - 长文档会自动分多次调用
   - 关键是"每次都用满"，不是"只用一次"

2. **正则抢救模式**
   - 输出被截断时，最后一个 JSON 对象可能不完整
   - 用正则 `r"\{[^{}]*\"row_index\"\s*:\s*\d+[^{}]*\}"` 提取完整对象
   - 丢弃最后一个对象（截断不可信），剩余行重试

3. **多 LLM 提供商支持**
   - Anthropic：原生 API，支持 Prompt Caching
   - DeepSeek/Qwen/Doubao/Zhipu/OpenAI：OpenAI 兼容格式
   - Wenxin：原生 API，需要 OAuth 令牌

---

### ⏭️ 下次对话可继续的内容

1. 用真实双语 Word 文档测试完整流程
2. 运行 `tests/benchmark_mapper.py` 对比提供商性能
3. 深入学习 `applier.py` 的词级别 diff 实现
4. 讨论产品化方向

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
