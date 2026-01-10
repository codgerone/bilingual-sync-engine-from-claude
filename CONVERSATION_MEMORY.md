# 对话记忆文件

> **用途**：跨设备、跨对话保持连贯性。新对话开始时，告诉 Claude "请先阅读 CONVERSATION_MEMORY.md"

---

## 📅 最近更新：2026-01-10

### 当前学习进度

**阶段**：mapper.py 重构完成（Prompt Caching 优化），继续深入学习

**已完成**：
- ✅ 理解 minidom 的基本概念
- ✅ 理解 extractor.py 各函数的输入输出
- ✅ 讨论并确定了 V2 重塑方案（语义驱动）
- ✅ 清理 extractor.py - 删除所有 V1 代码，只保留 V2
- ✅ 重构 extractor.py - 打包提取 + 快速检查优化
- ✅ **清理 mapper.py** - 删除 V1 代码
- ✅ **生成 mapper.py 知识地图** - 详细介绍 API、Prompt 工程、JSON 解析
- ✅ **实现 Prompt Caching 优化** - 节省约 60% API 成本

**进行中**：
- 🔄 继续深入学习 mapper.py 的其他细节

---

### 🎯 mapper.py 重构要点（2026-01-10）

**1. 清理 V1 代码**
- 删除 `map_revision()`, `map_revisions_batch()` 等旧方法
- 只保留 V2 的 `map_text_revision()`, `map_row_pairs()`

**2. Prompt Caching 优化**

Meiqi 提出的问题：每行修订都发送完整 prompt，重复的部分（角色、原则、格式）是否浪费 token？

**答案**：是的！输入 token 也消耗费用。

**解决方案**：使用 Anthropic Prompt Caching

```
优化前：每行都发送 ~600 tokens
调用1: [角色+原则+格式](450) + [数据](150)
调用2: [角色+原则+格式](450) + [数据](150)  ← 重复！

优化后：固定部分缓存
调用1: [system prompt 创建缓存](450×1.25) + [数据](150)
调用2: [读取缓存](450×0.1) + [数据](150)  ← 便宜 90%！
```

**新增方法**：
- `_build_system_prompt()` - 构建可缓存的系统提示（含 3 个 few-shot 示例）
- `_build_user_message()` - 构建每行变化的用户消息

**关键代码**：
```python
response = client.messages.create(
    system=[{
        "type": "text",
        "text": "固定内容...",
        "cache_control": {"type": "ephemeral"}  # 关键：标记缓存
    }],
    messages=[{"role": "user", "content": "变化内容..."}]
)
```

**3. 关键学习：Token 消耗机制**

| 类型 | 内容 | 消耗 |
|------|------|------|
| 输入 token | 你发送的 prompt | ✅ 消耗（较便宜） |
| 输出 token | LLM 生成的回复 | ✅ 消耗（较贵，约 5 倍） |

---

### 📁 mapper.py 当前结构

```
RevisionMapper 类
├── __init__(api_key, model)           # 初始化客户端 + 缓存变量
│
├── map_row_pairs()                    # 主入口：处理 extractor 输出的行对
├── map_text_revision()                # 单行映射：调用 LLM API（使用缓存）
│
├── _parse_text_response()             # 解析 JSON 响应
│
└── Prompt Caching 相关
    ├── _build_system_prompt()         # 构建可缓存的系统提示（固定部分）
    └── _build_user_message()          # 构建用户消息（变化部分）
```

---

### 📝 学习方法约定

根据 CLAUDE.md 中的约定：
1. **先全局后局部**：对于新知识点，先生成一页纸知识地图，再逐个深入
2. **文字优先**：能用文字解释的不要生成测试代码，除非代码效果明显更好
3. **聚焦提问**：一次最多围绕一个知识点提 1-3 个问题

---

### ⏭️ 下次对话继续的内容

1. 继续深入学习 mapper.py 的其他细节（如有问题）
2. 学习 applier.py
3. 学习 engine.py
4. 用真实双语 Word 文档测试完整流程

---

## 📜 历史记录归档

### 2026-01-08：extractor.py 重构完成

**完成的工作**：
- 清理 extractor.py 中的 V1 代码
- 实现打包提取（`extract_row_pairs()`）
- 新增快速检查优化（`_has_revisions()`）
- 添加文件结构图到 extractor.py 开头

### 2026-01-07：V2 重塑方案实现

**完成的工作**：
- 重塑 extractor.py - 输出 before_text/after_text
- 重塑 mapper.py - 新 prompt 让 LLM 理解语义差异
- 重塑 applier.py - 词级别 diff（jieba 分词）
- 调整 engine.py - 新增 sync_v2() 方法
- 添加 jieba 依赖到 requirements.txt

**V2 核心思想**：
- Meiqi 的洞察：翻译是语义对应，不是词汇对应
- extractor 输出 `{before_text, after_text}` 而非 `{deletion, insertion}`
- mapper 让 LLM 看完整句子，理解语义差异
- applier 用词级别 diff 生成 track changes

### 2026-01-06：minidom 学习 & V2 设计讨论

**学习内容**：
- 理解 minidom 的基本概念（Document, Element, Text, NodeList）
- 理解"空白字符也是文本节点"这个陷阱
- 理解 `firstChild`, `childNodes`, `getElementsByTagName` 的区别

**重要发现**：
- Meiqi 发现原 `_pair_deletions_insertions()` 方法设计有缺陷
- 核心洞察：翻译是语义对应，不是词汇对应
- 决定重塑为 V2 语义驱动方案

### 2026-01-06之前：项目初始化

- 项目从 Claude 网页端生成
- 目标：开发双语 Word 文档 track changes 自动同步引擎
- Meiqi 的学习目标：通过实际项目学习 coding、Python、AI 产品开发

---

## 📁 学习过程中创建的文件

| 文件名 | 用途 |
|-------|------|
| `minidom_knowledge_map.md` | minidom 一页纸知识地图 |
| `mapper_knowledge_map.md` | mapper.py 知识地图（API、Prompt工程、JSON、Prompt Caching） |
| `test.py` | 测试 minidom 基本用法 |
| `test_of_minidom.py` | 详细的 minidom 演示代码 |
| `test_nodelist.py` | 测试 NodeList 和 Element 的区别 |
| `test_method_vs_attribute.py` | 测试 method 和 attribute 的区别 |

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
