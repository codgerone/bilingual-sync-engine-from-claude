# mapper.py 知识地图

> 本文档详细介绍 mapper.py 涉及的核心概念，适合初学者阅读

---

## 1. 模块定位

```
extractor.py ──→ mapper.py ──→ applier.py
(提取修订)       (LLM映射)      (应用修订)
                    ↓
              Anthropic API
```

**mapper.py 的唯一职责**：调用 Claude API，让 AI 理解源语言的修订，然后告诉我们目标语言应该怎么改。

这是整个项目中**唯一需要联网**的模块。

---

## 2. 什么是 API？

### 2.1 通俗理解

**API = 程序之间对话的方式**

想象你去餐厅吃饭：
- 你（程序）不能直接进厨房做菜
- 你需要通过**服务员（API）**点菜
- 服务员把你的需求传达给厨房
- 厨房做好后，服务员把菜端给你

API 就是这个"服务员"。它定义了：
- 你可以点什么菜（可用的功能）
- 怎么点菜（请求格式）
- 菜会怎么端上来（响应格式）

### 2.2 Anthropic API

Anthropic 是开发 Claude 的公司。他们提供的 API 让你可以：
- 发送文本给 Claude
- 接收 Claude 的回复
- 控制回复的各种参数

**为什么需要 API？**
- Claude 的大脑（模型）运行在 Anthropic 的服务器上
- 你的电脑没有能力运行这么大的模型
- 通过 API，你的程序可以"借用"Anthropic 的服务器来思考

### 2.3 API 密钥

**API 密钥 = 你的身份证明 + 付款凭证**

```
ANTHROPIC_API_KEY = "sk-ant-api03-xxxxx..."
```

- 每次调用 API 都需要携带密钥
- Anthropic 根据密钥知道是谁在调用
- 根据调用量收费（按 token 计费）

**安全提醒**：密钥就像银行卡密码，绝对不能：
- 提交到 GitHub
- 分享给他人
- 硬编码在代码里

正确做法是放在环境变量中：
```bash
# Windows
set ANTHROPIC_API_KEY=你的密钥

# Mac/Linux
export ANTHROPIC_API_KEY='你的密钥'
```

---

## 3. Anthropic SDK 使用方法

### 3.1 什么是 SDK？

**SDK = 已经写好的工具包**

如果说 API 是"服务员"，那 SDK 就是"餐厅的点菜 APP"。

没有 SDK，你需要手动：
- 构造 HTTP 请求
- 处理网络连接
- 解析响应数据
- 处理各种错误

有了 SDK，一行代码搞定：
```python
response = client.messages.create(...)
```

### 3.2 核心代码解析

**步骤 1：导入并初始化客户端**

```python
import anthropic

# 创建客户端，传入 API 密钥
client = anthropic.Anthropic(api_key="你的密钥")
```

`client` 对象就是你和 Anthropic 服务器之间的"通讯员"。

**步骤 2：发送消息**

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",  # 使用哪个模型
    max_tokens=2000,                     # 最多返回多少 token
    temperature=0.0,                     # 随机性（后面详解）
    messages=[                           # 对话内容
        {"role": "user", "content": "你好，Claude！"}
    ]
)
```

**步骤 3：获取回复**

```python
reply = response.content[0].text
print(reply)  # "你好！有什么我可以帮助你的吗？"
```

### 3.3 参数详解

| 参数 | 作用 | mapper.py 中的值 |
|------|------|-----------------|
| `model` | 选择使用哪个 Claude 模型 | `claude-sonnet-4-20250514` |
| `max_tokens` | 限制回复的最大长度 | `2000` |
| `temperature` | 控制输出的随机性 | `0.0` |
| `messages` | 对话历史 | 只有一条 user 消息 |

**关于 temperature**：

```
temperature = 0.0  → 确定性输出（相同输入总是相同输出）
temperature = 1.0  → 较高随机性（相同输入可能不同输出）
```

我们设为 0.0 是因为：
- 处理法律文档需要**一致性**
- 同样的修订应该得到同样的翻译
- 不希望每次运行结果都不一样

### 3.4 什么是 Token？

**Token ≈ 词或词的一部分**

Claude 不是按字符计费，而是按 token 计费：
- 英文：约 1 token = 0.75 个单词
- 中文：约 1 token = 0.5-1 个汉字

例如：
```
"Hello, world!" → 4 tokens
"你好世界" → 4-5 tokens
```

`max_tokens=2000` 意味着：最多让 Claude 回复 2000 个 token（约 1500 个英文单词或 1000-2000 个汉字）。

---

## 4. Prompt 工程

### 4.1 什么是 Prompt？

**Prompt = 你发给 AI 的指令**

Prompt 工程就是研究"如何给 AI 写指令，才能得到最好的结果"。

类比：
- 你问实习生"帮我改一下这份文件" → 结果可能五花八门
- 你详细说明"找到第三段，把'公司'改成'企业'，其他不变" → 结果精准

同理，给 AI 的 prompt 越清晰、越具体，结果越好。

### 4.2 mapper.py 的 Prompt 结构

我们的 prompt 分为 5 个部分：

```
1. 角色设定
   ↓
2. 任务背景
   ↓
3. 输入数据
   ↓
4. 任务要求
   ↓
5. 输出格式
```

**让我们逐一解析 `_build_text_mapping_prompt()` 方法：**

```python
prompt = f"""你是一个专业的双语法律文档翻译专家。
```
**第1部分：角色设定**
- 告诉 AI 它应该扮演什么角色
- "法律文档翻译专家"让 AI 知道要使用专业、严谨的语言

```python
## 任务背景

一份双语文档中，{source_lang}版本进行了修订。现在需要将这个修订同步到{target_lang}版本。
```
**第2部分：任务背景**
- 解释为什么要做这件事
- 帮助 AI 理解上下文

```python
## {source_lang}的变化

**修订前：**
{source_before}

**修订后：**
{source_after}

## {target_lang}当前文本

{target_current}
```
**第3部分：输入数据**
- 清晰地呈现 AI 需要处理的数据
- 使用 Markdown 格式，结构清晰

```python
## 你的任务

1. 首先理解{source_lang}从"修订前"到"修订后"发生了什么**语义变化**
2. 然后在{target_lang}当前文本的基础上，做**最小的改动**来反映相同的语义变化
3. 返回{target_lang}修订后的**完整文本**

## 重要原则

- **语义对应**：翻译是语义对应，不是词汇对应...
- **最小改动**：只改必须改的部分...
- **语法正确**：确保修订后的文本语法正确...
```
**第4部分：任务要求**
- 明确告诉 AI 要做什么
- 强调重要原则（语义对应、最小改动）
- 这是 V2 方案的核心思想体现

```python
## 输出格式

请以 JSON 格式返回：
```json
{
  "target_after": "修订后的目标语言完整文本",
  "explanation": "简要说明...",
  "confidence": 0.95
}
```
**第5部分：输出格式**
- 明确要求 JSON 格式
- 指定每个字段的含义
- 便于程序解析

### 4.3 Prompt 设计技巧

在 mapper.py 中使用的技巧：

| 技巧 | 在 prompt 中的体现 |
|------|-------------------|
| **角色扮演** | "你是一个专业的双语法律文档翻译专家" |
| **结构化** | 使用 Markdown 标题分段 |
| **明确输出格式** | 指定 JSON schema |
| **强调重点** | 用粗体标记"语义变化"、"最小的改动" |
| **给示例** | JSON 格式示例 |

### 4.4 为什么 V2 的 Prompt 更好？

**V1 的问题**：告诉 AI "删除了什么、插入了什么"
```
删除的文本: "正在"
插入的文本: ""
```
AI 可能机械地找"正在"的英文翻译去删除，但英文可能根本没有对应的词。

**V2 的改进**：告诉 AI "修订前是什么、修订后是什么"
```
修订前: "AI正在改变我们的生活。"
修订后: "AI改变了我们的生活。"
```
AI 能理解"时态从进行时变成了过去时"，然后在英文中做相应调整。

---

## 5. JSON 解析

### 5.1 什么是 JSON？

**JSON = 结构化的数据格式**

```json
{
  "name": "张三",
  "age": 25,
  "skills": ["Python", "Java"]
}
```

特点：
- 用花括号 `{}` 包裹对象
- 键值对用冒号 `:` 分隔
- 多个键值对用逗号 `,` 分隔
- 可以嵌套（对象里包含数组、数组里包含对象）

### 5.2 为什么要用 JSON？

AI 返回的是自然语言文本，比如：
```
好的，我来分析一下这个修订...
修订后的英文应该是 "AI changed our life."
我的置信度是 95%。
```

这种格式对人友好，但对程序不友好——很难提取出我们需要的数据。

所以我们要求 AI 返回 JSON：
```json
{
  "target_after": "AI changed our life.",
  "confidence": 0.95
}
```

程序可以直接用 `result['target_after']` 取值。

### 5.3 `_parse_text_response()` 解析过程

```python
def _parse_text_response(self, response_text: str) -> Dict:
    # AI 可能返回：
    # "好的，这是结果：
    # ```json
    # {"target_after": "...", "confidence": 0.95}
    # ```
    # "

    # 步骤1：找到 JSON 代码块
    if "```json" in response_text:
        start = response_text.find("```json") + 7  # 跳过 "```json"
        end = response_text.find("```", start)      # 找到结束的 ```
        json_str = response_text[start:end].strip()

    # 步骤2：解析 JSON 字符串
    result = json.loads(json_str)

    # 步骤3：验证必要字段
    if 'target_after' not in result:
        raise ValueError("响应缺少 target_after 字段")

    return result
```

### 5.4 错误处理

AI 有时会返回格式不正确的 JSON。我们的处理方式：

```python
except Exception as e:
    print(f"解析响应失败: {e}")
    return {
        'target_after': '',
        'confidence': 0.0,
        'error': str(e)
    }
```

返回一个带 `error` 字段的空结果，而不是让程序崩溃。

---

## 6. Prompt Caching（性能优化）

### 6.1 问题：重复发送相同内容

原来每次处理一行修订，都会发送完整的 prompt：

```
调用1: [角色+背景+原则+格式+示例](800 tokens) + [数据](100 tokens)
调用2: [角色+背景+原则+格式+示例](800 tokens) + [数据](100 tokens)
调用3: [角色+背景+原则+格式+示例](800 tokens) + [数据](100 tokens)
...
```

**问题**：800 tokens 的固定内容每次都重复发送，浪费成本！

### 6.2 解决方案：Prompt Caching

Anthropic API 支持**缓存 prompt 的固定部分**：

```
调用1: [system prompt 创建缓存](800×1.25) + [数据](100) = 1100 tokens
调用2: [读取缓存](800×0.1) + [数据](100) = 180 tokens
调用3: [读取缓存](800×0.1) + [数据](100) = 180 tokens
...
```

**效果**：
- 首次调用稍贵（创建缓存，1.25 倍）
- 后续调用便宜很多（读取缓存，0.1 倍）
- 10 行修订总成本：从 9000 tokens 降到约 2700 tokens（**节省 60%**）

### 6.3 代码实现

**使用 `system` 参数分离固定内容**：

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=2000,
    temperature=0.0,
    system=[  # 固定内容，带缓存标记
        {
            "type": "text",
            "text": "你是专业翻译专家...(角色+原则+示例)",
            "cache_control": {"type": "ephemeral"}  # 关键：标记为可缓存
        }
    ],
    messages=[  # 变化内容
        {"role": "user", "content": "修订前:... 修订后:... 当前:..."}
    ]
)
```

**关键点**：
- `system` 参数：放固定内容（角色、原则、示例）
- `cache_control`: `{"type": "ephemeral"}` 标记缓存点
- `messages` 参数：放变化内容（每行的数据）

### 6.4 缓存注意事项

| 事项 | 说明 |
|------|------|
| 最小 token 数 | Sonnet 模型要求至少 1024 tokens 才能缓存 |
| 缓存有效期 | 默认 5 分钟 |
| 语言切换 | 当 source_lang/target_lang 变化时需要重建缓存 |

### 6.5 我们的实现

```python
# mapper.py 中的实现

# 1. __init__ 添加缓存变量
self._cached_system_prompt = None
self._cached_source_lang = None
self._cached_target_lang = None

# 2. _build_system_prompt() 构建可缓存的系统提示
def _build_system_prompt(self, source_lang, target_lang) -> list:
    return [{
        "type": "text",
        "text": "...(角色+原则+示例)...",
        "cache_control": {"type": "ephemeral"}
    }]

# 3. _build_user_message() 构建变化的用户消息
def _build_user_message(self, source_before, source_after, target_current, ...) -> str:
    return "修订前:... 修订后:... 当前:..."

# 4. map_text_revision() 使用缓存
def map_text_revision(self, ...) -> Dict:
    # 检查是否需要更新缓存
    if self._cached_system_prompt is None or 语言变化:
        self._cached_system_prompt = self._build_system_prompt(...)

    # 调用 API
    response = client.messages.create(
        system=self._cached_system_prompt,  # 固定部分
        messages=[{"role": "user", "content": user_message}]  # 变化部分
    )
```

---

## 7. 文件结构图

```
mapper.py
│
├── 文件头注释
│   ├── 模块定位图
│   ├── 核心职责
│   ├── 数据流
│   ├── 设计原则
│   └── Prompt Caching 说明
│
├── class RevisionMapper
│   │
│   ├── __init__(api_key, model)
│   │   ├── 创建 Anthropic 客户端
│   │   └── 初始化缓存变量
│   │
│   ├── map_row_pairs(row_pairs, ...)        ← 主入口
│   │   └── 循环调用 map_text_revision()
│   │
│   ├── map_text_revision(...)               ← 单行映射（使用缓存）
│   │   ├── 检查/更新缓存
│   │   ├── 调用 _build_user_message()
│   │   ├── 调用 client.messages.create()   ← 唯一的 API 调用点
│   │   └── 调用 _parse_text_response()
│   │
│   ├── _parse_text_response(...)            ← 解析响应
│   │   ├── 提取 JSON 代码块
│   │   ├── json.loads() 解析
│   │   └── 验证 + 默认值填充
│   │
│   └── Prompt Caching 相关
│       ├── _build_system_prompt(...)        ← 构建可缓存的系统提示
│       └── _build_user_message(...)         ← 构建变化的用户消息
│
└── 使用示例（if __name__ == "__main__"）
    ├── 示例1：单行映射
    └── 示例2：批量映射
```

---

## 8. 完整数据流示例

假设有这样的修订：

**输入（来自 extractor）**：
```python
{
    'row_index': 0,
    'source_before': 'AI正在改变我们的生活。',
    'source_after': 'AI改变了我们的生活。',
    'target_current': 'AI is changing our life.'
}
```

**处理流程**：

```
1. map_row_pairs() 接收数据
       ↓
2. map_text_revision() 处理单行
       ↓
3. 检查缓存：首次调用时 _build_system_prompt() 创建缓存
       ↓
4. _build_user_message() 生成变化的用户消息
       ↓
5. client.messages.create() 发送给 Claude API
   - system: 固定内容（带 cache_control）
   - messages: 变化内容
       ↓
6. Claude 返回：
   ```json
   {
     "target_after": "AI changed our life.",
     "explanation": "中文从进行时改为过去时，英文相应地从 is changing 改为 changed",
     "confidence": 0.95
   }
   ```
       ↓
7. _parse_text_response() 解析 JSON
       ↓
8. 返回结果
```

**输出（给 applier）**：
```python
{
    'row_index': 0,
    'target_current': 'AI is changing our life.',
    'target_after': 'AI changed our life.',
    'explanation': '中文从进行时改为过去时...',
    'confidence': 0.95
}
```

---

## 9. 常见问题

### Q1: API 调用失败怎么办？

可能的原因：
- 网络问题
- API 密钥无效
- 余额不足
- 请求频率过高

目前代码会打印错误并返回空结果。后续可以加重试机制。

### Q2: 为什么每个修订都要单独调用 API？

**当前方式（顺序调用）**：
```python
for pair in row_pairs:
    result = self.map_text_revision(...)  # 每行一次 API 调用
```

**可优化为（批量调用）**：
- 把多个修订打包成一个 prompt
- 一次 API 调用处理多个修订
- 但需要更复杂的 prompt 和解析逻辑

### Q3: 置信度 (confidence) 有什么用？

AI 自己评估的准确度：
- 0.95+ → 很有把握
- 0.7-0.95 → 比较有把握
- <0.7 → 可能需要人工复核

后续可以根据置信度决定是否自动应用修订。

---

## 10. 下一步学习

学完 mapper.py 后，下一个模块是 **applier.py**：

- 接收 mapper 的输出（`target_current` + `target_after`）
- 计算两者的差异（用 diff 算法）
- 生成 Word 的 track changes XML

---

*文档生成时间：2026-01-10*
