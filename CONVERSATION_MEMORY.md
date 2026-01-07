# 对话记忆文件

> **用途**：跨设备、跨对话保持连贯性。新对话开始时，告诉 Claude "请先阅读 CONVERSATION_MEMORY.md"

---

## 📅 最近更新：2026-01-07

### 当前学习进度

**阶段**：V2 重塑完成，准备测试

**已完成**：
- ✅ 理解 minidom 的基本概念
- ✅ 理解 extractor.py 各函数的输入输出
- ✅ 讨论并确定了 V2 重塑方案（语义驱动）
- ✅ **重塑 extractor.py** - 输出 before_text/after_text
- ✅ **重塑 mapper.py** - 新 prompt 让 LLM 理解语义差异
- ✅ **重塑 applier.py** - 词级别 diff（jieba 分词）
- ✅ **调整 engine.py** - 新增 sync_v2() 方法
- ✅ **添加 jieba 依赖** 到 requirements.txt

**进行中**：
- 🔄 等待实际文档测试验证

---

### 🎯 V2 重塑核心思想

**Meiqi 的洞察**：翻译是语义对应，不是词汇对应！

```
中文：AI [正在] 改变 → AI 改变 [了]
英文：AI [is changing] → AI [has changed]

- 中文删除"正在"，英文删除"is"（词性不同）
- 中文插入"了"，英文无直接对应（语法不同）
- "改变"不变，但"change"要变时态
```

**V2 方案**：
1. **extractor** 输出 `{before_text, after_text}` 而非 `{deletion, insertion}`
2. **mapper** 让 LLM 看完整句子，理解语义差异，输出 `target_after`
3. **applier** 用词级别 diff（英文空格分词，中文 jieba 分词）生成 track changes

---

### 📁 V2 改动的文件

| 文件 | 改动 |
|------|------|
| `src/extractor.py` | 新增 `extract_text_versions_from_column()`, `extract_clean_text_from_column()` |
| `src/mapper.py` | 新增 `map_text_revision()`, 新 prompt 强调语义对应 |
| `src/applier.py` | 新增 `DiffBasedApplier`, `word_diff()`, `tokenize()` |
| `src/engine.py` | 新增 `sync_v2()` 方法 |
| `requirements.txt` | 添加 `jieba>=0.42.1` |

**使用 V2**：
```bash
python -m src.engine input.docx --v2
```

---

### 📝 第一版约束（待后续迭代）

1. **目标语言列是纯净文本**（无 track changes）
2. **词级别 diff**（非字符级别）

后续迭代时可考虑：
- 目标语言列也有 track changes 的情况
- 更细粒度的 diff（字符级别）

---

### 📁 学习过程中创建的文件

| 文件名 | 用途 |
|-------|------|
| `minidom_knowledge_map.md` | minidom 一页纸知识地图 |
| `test.py` | 测试 minidom 基本用法 |
| `test_of_minidom.py` | 详细的 minidom 演示代码 |
| `test_nodelist.py` | 测试 NodeList 和 Element 的区别 |
| `test_method_vs_attribute.py` | 测试 method 和 attribute 的区别 |

---

### 📝 学习方法约定

根据 CLAUDE.md 中的约定：
1. **先全局后局部**：对于新知识点，先生成一页纸知识地图，再逐个深入
2. **文字优先**：能用文字解释的不要生成测试代码，除非代码效果明显更好
3. **聚焦提问**：一次最多围绕一个知识点提 1-3 个问题

---

### ⏭️ 下次对话继续的内容

1. 安装 jieba 依赖：`pip install jieba`
2. 测试 V2 的 diff 功能：运行 `python src/applier.py`
3. 用真实双语 Word 文档测试完整流程

---

## 📜 历史记录归档

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

## 如何使用这个文件

**开始新对话时**，发送：
```
请先阅读 CONVERSATION_MEMORY.md，了解我们之前的讨论进展，然后我们继续
```

**结束对话前**，让我更新这个文件：
```
请更新 CONVERSATION_MEMORY.md，记录今天的讨论进展
```
