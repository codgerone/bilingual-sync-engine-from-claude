# minidom 知识地图（一页纸版本）

> **目标**：5分钟快速掌握 minidom 解析 XML 的全貌
> **用途**：理解 extractor.py 如何提取 Word 文档中的 track changes

---

## 1️⃣ minidom 是什么？（1句话）

**minidom = Python 内置的 XML 解析器，把 XML 文本转换成树状对象，可以遍历和查询**

```python
from defusedxml import minidom  # defusedxml 是安全版本的 minidom

# XML 字符串 → DOM 树对象
dom = minidom.parseString(xml_string)
```

---

## 2️⃣ 核心概念地图（只需记住3个）

```
┌─────────────────────────────────────────────────────────┐
│                    DOM 树                                │
│                                                         │
│  Document                    ← 整个文档（根节点）        │
│    └── Element               ← XML 标签 <w:p>           │
│         ├── Element          ← 子标签 <w:r>             │
│         │    └── Text        ← 文本内容 "你好"           │
│         └── Element          ← 兄弟标签 <w:del>         │
│              └── Element                                │
└─────────────────────────────────────────────────────────┘

3种对象：
1. Document  - 整个 XML 文档
2. Element   - XML 标签（最常用）
3. Text      - 标签里的文本内容
```

---

## 3️⃣ 常用方法速查表（只需记住5个）

| 方法 | 用途 | 示例 | 返回值 |
|------|------|------|--------|
| `parseString()` | 解析 XML 字符串 | `dom = minidom.parseString(xml)` | Document |
| `getElementsByTagName()` | 查找所有匹配标签 | `dom.getElementsByTagName('w:p')` | **NodeList** |
| `getAttribute()` | 获取标签属性 | `element.getAttribute('w:id')` | 字符串 |
| `childNodes` | 获取所有子节点 | `para.childNodes` | **NodeList** |
| `toxml()` | 转回 XML 字符串 | `element.toxml()` | 字符串 |

**关键：NodeList = 元素列表，用 `[0]` 取出单个元素**

---

## 4️⃣ 在 extractor.py 中的实际应用（对应代码行号）

### **Step 1: 解析 XML 文件**
```python
# extractor.py 第 50-54 行
with open(self.document_xml_path, 'r', encoding='utf-8') as f:
    content = f.read()
dom = minidom.parseString(content)  # ← 创建 DOM 树
```

### **Step 2: 查找目标元素**
```python
# 第 57 行 - 找到所有表格行
rows = dom.getElementsByTagName('w:tr')  # ← 返回 NodeList

# 第 67 行 - 找到单元格
cells = row.getElementsByTagName('w:tc')

# 第 88-89 行 - 找到删除和插入标记
deletions = para.getElementsByTagName('w:del')  # ← 核心！
insertions = para.getElementsByTagName('w:ins')
```

### **Step 3: 遍历和访问节点**
```python
# 第 122 行 - 获取段落的所有子节点
children = paragraph.childNodes  # ← 按顺序遍历

# 第 129 行 - 检查节点类型
if node.nodeType == node.ELEMENT_NODE and node.tagName == 'w:del':
    # ↑ 判断是不是 <w:del> 标签
```

### **Step 4: 提取属性和文本**
```python
# 第 131 行 - 提取属性
del_id = node.getAttribute('w:id')  # ← 获取 w:id="0"

# 第 167-173 行 - 提取文本内容
text_nodes = node.getElementsByTagName('w:t')
for t in text_nodes:
    if t.firstChild:  # ← Text 节点
        text_parts.append(t.firstChild.nodeValue)  # ← 文本值
```

---

## 5️⃣ 关键概念对比（扫清困惑）

| 对比项 | A | B | 区别 |
|--------|---|---|------|
| **返回值** | `getElementsByTagName()` | `childNodes` | 前者返回 NodeList，后者也是 NodeList |
| **查找范围** | `getElementsByTagName()` | `childNodes` | 前者查找**所有后代**，后者只返回**直接子节点** |
| **顺序** | `getElementsByTagName()` | `childNodes` | 前者**无序**（深度优先），后者**有序**（按出现顺序） |
| **对象类型** | Element | Text | Element 是标签，Text 是文本内容 |
| **访问方式** | `.tagName` | `.nodeValue` | Element 用 tagName，Text 用 nodeValue |

---

## 6️⃣ 核心流程图（extractor.py 做了什么）

```
XML 文件
   ↓
[parseString] → Document 对象
   ↓
[getElementsByTagName('w:tr')] → 找到所有行（NodeList）
   ↓
遍历每一行
   ↓
[getElementsByTagName('w:tc')] → 找到指定列的单元格
   ↓
[getElementsByTagName('w:p')] → 找到段落
   ↓
[getElementsByTagName('w:del')] → 找到删除标记 ← 目标！
[getElementsByTagName('w:ins')] → 找到插入标记 ← 目标！
   ↓
[getAttribute('w:id')] → 提取属性（ID、作者、日期）
   ↓
[getElementsByTagName('w:t')] → 提取文本内容
   ↓
[.firstChild.nodeValue] → 获取文本值
   ↓
组装成结构化数据（Python 字典）
```

---

## 7️⃣ 快速学习检查点（5个问题，能答对就算掌握）

1. ✅ **minidom.parseString() 返回什么？**
   - 答：Document 对象（DOM 树的根）

2. ✅ **getElementsByTagName() 返回什么？**
   - 答：NodeList（元素列表），不是单个元素

3. ✅ **如何从 NodeList 中取出第一个元素？**
   - 答：用索引 `[0]`

4. ✅ **如何获取标签的属性值（如 w:id="0"）？**
   - 答：`element.getAttribute('w:id')`

5. ✅ **如何获取标签里的文本内容（如 <w:t>你好</w:t>）？**
   - 答：`t_element.firstChild.nodeValue`

---

## 8️⃣ 实战建议（下一步做什么）

### **立即可做（5分钟）：**
1. 打开 `extractor.py`，找到上面标注的行号
2. 对照这个地图，看看能不能理解每一行在做什么

### **深入实践（30分钟）：**
1. 运行 `python src/extractor.py`（它有自己的测试代码）
2. 在关键位置加 `print()` 看中间结果：
   ```python
   rows = dom.getElementsByTagName('w:tr')
   print(f"找到 {len(rows)} 行")  # ← 加这种调试输出
   ```
3. 尝试修改代码，看会发生什么

### **遇到困惑时：**
- 回来看这个地图
- 对照 `test_of_minidom.py` 做实验
- 问我具体的问题（不要问太宽泛的）

---

## 9️⃣ 记忆口诀（快速回忆用）

```
parseString 变 DOM 树，
getElementsByTagName 找标签返列表，
childNodes 拿子节点按顺序，
getAttribute 取属性，
firstChild.nodeValue 拿文本，
toxml 转回字符串。
```

---

## 🔟 关键代码模板（直接复制用）

```python
from defusedxml import minidom

# 1. 解析
dom = minidom.parseString(xml_string)

# 2. 查找（返回 NodeList）
elements = dom.getElementsByTagName('w:del')

# 3. 遍历
for element in elements:
    # 4. 获取属性
    element_id = element.getAttribute('w:id')

    # 5. 获取文本
    text_nodes = element.getElementsByTagName('w:t')
    if text_nodes and text_nodes[0].firstChild:
        text = text_nodes[0].firstChild.nodeValue

    # 6. 访问子节点
    for child in element.childNodes:
        if child.nodeType == child.ELEMENT_NODE:
            print(f"子标签: {child.tagName}")
```

---

## 总结：只需记住这个公式

```
XML 字符串
  → [parseString]
  → Document
  → [getElementsByTagName]
  → NodeList
  → [索引 [0]]
  → Element
  → [getAttribute / firstChild.nodeValue]
  → 属性值 / 文本内容
```

**就这么简单！** 🎉

---

## 下一步

看完这个地图后，打开 `extractor.py`，试着用这个地图理解代码。

遇到具体不懂的地方，告诉我：
- "第 XX 行为什么要这样写？"
- "为什么这里用 childNodes 而不是 getElementsByTagName？"

我会针对性地解答！
