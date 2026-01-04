# 同步引擎工作原理详解

## 🎯 核心问题

**场景**：你有一个双语法律文档（中英对照）
- 左列：中文
- 右列：英文

**问题**：当你在中文列修改内容时（使用Word的Track Changes），英文列没有对应的修订标记，两列不同步！

**解决方案**：自动将中文列的修订同步到英文列

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────┐
│             BilingualSyncEngine (主引擎)                │
│                                                         │
│  sync() 方法协调整个流程                                 │
└────────────┬────────────┬────────────┬──────────────────┘
             │            │            │
             ▼            ▼            ▼
    ┌────────────┐ ┌─────────────┐ ┌──────────────┐
    │ Extractor  │ │   Mapper    │ │   Applier    │
    │  提取器    │ │   映射器    │ │   应用器      │
    └────────────┘ └─────────────┘ └──────────────┘
         │              │               │
         │              │               │
    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
    │XML解析  │    │Claude AI│    │Document │
    │defusedxml│   │  API    │    │ Library │
    └─────────┘    └─────────┘    └─────────┘
```

---

## 🔄 完整工作流程（8个步骤）

### **步骤1: 解包Word文档**
```python
# Word文档其实是一个ZIP文件
input.docx  →  解压  →  word/document.xml (主要内容)
                     →  word/_rels/ (关系文件)
                     →  [Content_Types].xml (内容类型)
```

**作用**：将.docx转换为可编辑的XML文件

---

### **步骤2: 初始化组件**
```python
self.extractor = RevisionExtractor(unpacked_dir)
self.mapper = RevisionMapper(api_key)
self.applier = SmartRevisionApplier(unpacked_dir)
```

**作用**：准备三个核心工具

---

### **步骤3: 提取源语言修订 (Extractor)**

#### 输入: 中文列的XML
```xml
<w:tc>  <!-- 表格单元格 -->
  <w:p>  <!-- 段落 -->
    <w:r><w:t>你好！今天</w:t></w:r>

    <w:del w:id="0" w:author="User">  <!-- 删除标记 -->
      <w:r><w:delText>天气</w:delText></w:r>
    </w:del>

    <w:ins w:id="1" w:author="User">  <!-- 插入标记 -->
      <w:r><w:t>空气质量</w:t></w:r>
    </w:ins>

    <w:r><w:t>怎么样？</w:t></w:r>
  </w:p>
</w:tc>
```

#### 提取器做什么：
1. 遍历XML，找到所有 `<w:del>` (删除) 和 `<w:ins>` (插入) 标签
2. 配对相邻的删除和插入
3. 提取上下文（前后文本）

#### 输出: 结构化的修订数据
```python
{
    'row_index': 0,           # 第0行
    'deletion': '天气',       # 删除的文本
    'insertion': '空气质量',   # 插入的文本
    'context_before': '你好！今天',  # 修订前的上下文
    'context_after': '怎么样？',     # 修订后的上下文
    'del_id': '0',           # 删除标记ID
    'ins_id': '1'            # 插入标记ID
}
```

---

### **步骤4: 提取目标语言文本**

从英文列提取当前文本，为映射做准备：
```python
target_texts = [
    "Hello! How's the weather today?",  # 第0行
    "Nice to meet you!",                # 第1行
    ...
]
```

**作用**：给LLM提供上下文，知道在哪里应用修订

---

### **步骤5: LLM映射 (Mapper) ⭐核心步骤⭐**

#### 构建提示词发送给Claude
```python
prompt = f"""
你是专业的双语法律文档翻译专家。

源语言(中文)的修订:
- 删除: "天气"
- 插入: "空气质量"
- 上下文: "你好！今天...怎么样？"

目标语言(英文)当前文本:
"Hello! How's the weather today?"

任务:
1. 找到英文文本中对应"天气"的词
2. 找到"空气质量"的准确英文翻译
3. 只标记实际改变的部分

返回JSON格式:
{{
    "deletion": "应该删除的英文词",
    "insertion": "应该插入的英文词",
    "explanation": "解释",
    "confidence": 0.95
}}
"""
```

#### Claude AI 返回
```json
{
    "deletion": "weather",
    "insertion": "air quality",
    "explanation": "将'天气'对应到'weather'，'空气质量'翻译为'air quality'",
    "confidence": 0.95
}
```

**为什么需要LLM？**
- 不是简单的逐字翻译
- 需要理解上下文
- 需要保持语言习惯
- 处理同义词和语序变化

---

### **步骤6: 应用修订 (Applier)**

#### 输入: 映射后的修订
```python
{
    'deletion': 'weather',
    'insertion': 'air quality'
}
```

#### Applier做什么：

**6.1 在英文文本中定位要删除的词**
```python
text = "Hello! How's the weather today?"
deletion = "weather"

# 找到位置
position = text.find("weather")  # 位置17
```

**6.2 分析文本结构**
```python
text_before = "Hello! How's the "     # 不变部分（前）
deletion = "weather"                   # 要删除的部分
insertion = "air quality"              # 要插入的部分
text_after = " today?"                 # 不变部分（后）
```

**6.3 生成新的XML结构**
```xml
<w:p>
  <!-- 保留前面不变的文本 -->
  <w:r>
    <w:t xml:space="preserve">Hello! How's the </w:t>
  </w:r>

  <!-- 添加删除标记 -->
  <w:del w:id="2" w:author="Claude" w:date="2026-01-04T12:00:00Z">
    <w:r w:rsidDel="00000000">
      <w:delText>weather</w:delText>
    </w:r>
  </w:del>

  <!-- 添加插入标记 -->
  <w:ins w:id="3" w:author="Claude" w:date="2026-01-04T12:00:00Z">
    <w:r>
      <w:t>air quality</w:t>
    </w:r>
  </w:ins>

  <!-- 保留后面不变的文本 -->
  <w:r>
    <w:t xml:space="preserve"> today?</w:t>
  </w:r>
</w:p>
```

**6.4 管理修订ID**
```python
def _get_next_revision_id():
    # 扫描整个文档，找到最大的w:id值
    max_id = 找到最大ID  # 比如当前最大是1
    return max_id + 1    # 返回2，用于新的删除标记
                         # 下一个是3，用于插入标记
```

---

### **步骤7: 保存并打包**

**7.1 保存XML修改**
```python
self.applier.save()  # 将修改写回document.xml
```

**7.2 打包回.docx**
```python
# 将所有XML文件重新打包为ZIP
unpacked/  →  压缩  →  output_synced.docx
```

---

### **步骤8: 验证（可选）**
```python
# 使用pandoc或其他工具验证文档格式
pandoc output.docx -o test.md
```

---

## 📊 数据流示例

### 完整的数据转换过程：

```
输入文档 (input.docx)
    │
    ▼
解包
    │
    ▼
XML文件 (document.xml)
    │
    ▼
中文列XML:
  "你好！今天<del>天气</del><ins>空气质量</ins>怎么样？"
    │
    ▼
Extractor提取
    │
    ▼
结构化数据:
  {deletion: '天气', insertion: '空气质量', ...}
    │
    ▼
Mapper映射 (调用Claude API)
    │
    ▼
映射结果:
  {deletion: 'weather', insertion: 'air quality'}
    │
    ▼
Applier应用
    │
    ▼
英文列新XML:
  "Hello! How's the <del>weather</del><ins>air quality</ins> today?"
    │
    ▼
保存并打包
    │
    ▼
输出文档 (output_synced.docx)
```

---

## 🔑 关键技术点

### 1. XML解析安全性
```python
from defusedxml import minidom  # 使用安全的XML解析器
dom = minidom.parseString(content)
```

### 2. Track Changes的XML标准（OOXML）
- `<w:del>` - 删除标记
- `<w:ins>` - 插入标记
- `w:id` - 唯一标识符
- `w:author` - 作者
- `w:date` - 时间戳

### 3. LLM提示词工程
- 包含足够的上下文
- 明确任务要求
- 指定输出格式（JSON）
- 要求置信度评估

### 4. 智能文本定位
```python
# 不是简单的字符串替换
# 需要考虑：
# - 大小写
# - 标点符号
# - 多次出现
# - 部分匹配
```

---

## 💡 实际运行示例

### 使用代码
```python
from src.engine import BilingualSyncEngine

# 创建引擎
engine = BilingualSyncEngine(
    docx_path="contract.docx",
    api_key="sk-ant-...",
    source_column=0,      # 左列（中文）
    target_column=1,      # 右列（英文）
    source_lang="中文",
    target_lang="英文"
)

# 执行同步（一行代码！）
output = engine.sync(output_path="contract_synced.docx")
```

### 控制台输出
```
============================================================
双语Word文档Track Changes同步引擎
============================================================

[1/6] 解包Word文档...
  文档已解包到: /tmp/contract_work/unpacked

[2/6] 初始化组件...

[3/6] 从中文列提取修订...
  找到 3 个修订

[4/6] 提取英文文本...

[5/6] 使用LLM映射修订到英文...

  映射修订 1/3:
    中文: 天气 → 空气质量
    英文: weather → air quality
    置信度: 0.95

  映射修订 2/3:
    中文: 合同 → 协议
    英文: contract → agreement
    置信度: 0.92

  映射修订 3/3:
    中文: 五天 → 七天
    英文: five days → seven days
    置信度: 0.98

[6/6] 应用修订到英文列...

成功应用 3/3 个修订

保存修改...
打包文档到: contract_synced.docx

验证结果...

============================================================
同步完成！
输出文件: contract_synced.docx
============================================================
```

---

## 🎯 总结

### 核心价值
- 🚀 **自动化**: 消除手动复制粘贴
- 🎯 **准确性**: AI理解语义，不是机械翻译
- 📝 **可追溯**: 保留完整的track changes历史
- ✅ **标准化**: 符合OOXML标准

### 适用场景
- 法律合同（中英对照）
- 产品手册
- 技术文档
- 学术论文

### 技术亮点
- 安全的XML解析
- 智能的LLM集成
- 符合Word标准的XML生成
- 完整的错误处理
