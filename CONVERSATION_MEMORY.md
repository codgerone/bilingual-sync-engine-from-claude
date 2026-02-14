# 对话记忆文件

> **用途**：跨设备、跨对话保持连贯性。新对话开始时，告诉 Claude "请先阅读 CONVERSATION_MEMORY.md"

---

## 📅 最近更新：2026-02-14

### 当前项目状态

**阶段**：mapper.py 代码优化 & 深入学习

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

### 🎯 2026-02-14 对话记录：mapper.py 代码优化与学习

#### 本轮完成的代码修改

1. **删除冗余方法**
   - 删除 `map_text_revision()`（单行便捷方法，不必要的包装）
   - 删除 `quick_map()` 函数

2. **max_tokens 策略改进**（`_map_max_tokens_strategy()`）
   - 用"无进展检测"（连续3次无进展才停止）代替固定 `max_retries`
   - 删除了错误的 `pop()` 操作（丢弃最后一个结果的做法不正确）

3. **batch 策略改进**（`_map_batch_strategy()`）
   - 同样使用"无进展检测"代替固定重试次数

4. **解析函数重构**
   - 删除旧函数：`_parse_batch_response`、`_strip_code_fence`、`_salvage_objects`、`_normalize_batch_results`
   - 新增 `_parse_json_response()`：batch 策略用，json.loads 直接解析
   - 新增 `_salvage_valid_results()`：max_tokens 策略用，精确正则匹配 prompt 规定的字段顺序
   - 新增 `_is_valid_result()`：统一字段类型验证

5. **Prompt 改进**（`_build_batch_system_prompt()`）
   - 更严格的格式规定（禁止 markdown code fence、规定字段顺序）
   - 新增 STRING ESCAPING 规则

6. **`create_llm_client()` 重构**
   - 函数签名：`api_key` 改为显式必需参数，移除 `**kwargs`
   - PROVIDERS 字典加入 wenxin，移除 `env_key`（api_key 由调用方传入）
   - 条件判断统一用 `config["client_class"]` 分叉（不再混用 provider 字符串和 client_class）

7. **`RevisionMapper.__init__` 重构**
   - 移除 `api_key` 和 `**kwargs` 参数
   - 新增 `PROVIDER_ENV_KEYS` 类属性，内部从环境变量读取 api_key
   - 职责分离：RevisionMapper 负责读取环境变量，create_llm_client 负责创建 Client

8. **简化 `_build_batch_user_message()`**
   - 去掉不必要的 payload 重构，直接 `json.dumps(batch)`

#### Meiqi 展现的设计思维

- **显式 vs 隐式的平衡**：常用参数（api_key）显式放在函数签名中，边缘参数（wenxin secret_key）隐式处理
- **条件判断一致性**：同一个 if-elif-else 应基于同一个参量分叉
- **代码简洁性**：发现不必要的数据重构（payload 转写）并提出简化
- **可读性追求**：函数签名应明确表达需要什么输入

#### 学习的 Python 知识点

- **装饰器** `@abstractmethod`：强制子类实现方法，抽象基类（ABC）的概念
- **`os.getenv()`**：从操作系统环境变量读取值
- **`or` 短路求值**：`model = model or config["default_model"]`
- **多态**：同样的方法调用，不同的具体实现

---

### 📁 当前 mapper.py 结构（2026-02-14 更新）

```
RevisionMapper 类
├── PROVIDER_ENV_KEYS              # 类属性：provider → 环境变量名映射
├── __init__(provider, model, strategy, ...)
│
├── map_row_pairs()                # 主入口
│   ├── _map_max_tokens_strategy() # while + 无进展检测
│   └── _map_batch_strategy()      # while + 无进展检测
│       ├── _build_batches()
│       └── _map_single_batch()
│
├── _build_batch_system_prompt()   # 严格格式 prompt
├── _build_batch_user_message()    # 简化版
│
├── _parse_json_response()         # batch 策略用
├── _salvage_valid_results()       # max_tokens 策略用，精确正则
└── _is_valid_result()             # 字段类型验证

create_llm_client(provider, api_key, model)  # 工厂函数

LLM Client 层
├── LLMClient (ABC)
├── AnthropicClient
├── OpenAICompatibleClient
└── WenxinClient
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

### 📁 mapper.py 结构（2026-01-28 版本，已被 2026-02-14 版本替代，见上方）

---

### 📝 重要学习点

1. **max_tokens 策略 ≠ 只调一次 API**
   - 每次调用顶格输出，用满输出配额
   - 长文档会自动分多次调用
   - 关键是"每次都用满"，不是"只用一次"

2. **正则抢救模式**（已优化）
   - 输出被截断时，用精确正则匹配 prompt 规定的字段顺序提取完整对象
   - 不再丢弃最后一个对象（正则只匹配完整闭合的 `{...}`）
   - 使用"无进展检测"代替固定重试次数

3. **多 LLM 提供商支持**
   - Anthropic：原生 API，支持 Prompt Caching
   - DeepSeek/Qwen/Doubao/Zhipu/OpenAI：OpenAI 兼容格式
   - Wenxin：原生 API，需要 OAuth 令牌

4. **代码设计原则**（Meiqi 总结）
   - 显式优于隐式：函数签名明确列出所有核心输入
   - 常用参数显式、边缘参数隐式：平衡可读性和简洁性
   - 条件分叉基于同一参量：逻辑更一致、更美
   - 不做多余转写：如果数据结构已经正确，不要重新构造

---

### ⏭️ 下次对话可继续的内容

1. 继续学习 mapper.py 剩余部分（解析函数、策略逻辑细节）
2. 同步更新 engine.py（如果有受 mapper.py 修改影响的调用）
3. 深入学习 `applier.py` 的词级别 diff 实现
4. 用真实双语 Word 文档测试完整流程
5. 讨论产品化方向

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
