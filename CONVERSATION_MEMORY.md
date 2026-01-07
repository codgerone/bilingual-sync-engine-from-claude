# 对话记忆文件

> **用途**：跨设备、跨对话保持连贯性。新对话开始时，告诉 Claude "请先阅读 CONVERSATION_MEMORY.md"

---

## 📅 最近更新：2026-01-07

### 当前学习进度

**阶段**：学习 extractor.py，理解 minidom 解析 XML

**已完成**：
- ✅ 理解 minidom 的基本概念（Document, Element, Text, NodeList）
- ✅ 创建了 `minidom_knowledge_map.md` 知识地图
- ✅ 理解了"空白字符也是文本节点"这个陷阱
- ✅ 理解了 `firstChild`, `childNodes`, `getElementsByTagName` 的区别
- ✅ 理解了 `extractor.py` 各函数的输入输出

**进行中**：
- 🔄 讨论 extractor.py 的设计缺陷和重塑方案

---

### 🚨 重要讨论：extractor.py 重塑

**问题**：当前 `_pair_deletions_insertions()` 方法假设"删除+插入必须配对"，这是错误的。

**Meiqi 的观点**：
1. 删除就是删除，插入就是插入，它们可以独立存在，不需要配对
2. context_before/after 无法用来"定位"另一种语言中的对应词，因为语序不同
3. LLM 应该靠"语义理解"来找到对应的翻译，而不是靠位置

**示例**：
```
中文：人工智能技术 [深刻] 改变了我们的生活方式
英文：... has changed our way of life [profoundly]
↑ 中文的"深刻"在句中，英文的"profoundly"在句末，位置完全不对应！
```

**待讨论**：
- extractor 到底需要提取哪些信息？
- 最简方案：只需要 `{type, text, row_index}` 吗？
- context 的真正作用是什么？

**计划文件**：`C:\Users\80017794\.claude\plans\fluffy-waddling-cook.md`

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

1. 继续讨论 extractor.py 的重塑方案
2. 确定 extractor 应该提取哪些信息
3. 实施重塑

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
