# 双语Word文档Track Changes同步引擎 - 完整使用指南

## 目录
1. [快速开始](#快速开始)
2. [核心概念](#核心概念)
3. [详细教程](#详细教程)
4. [进阶用法](#进阶用法)
5. [常见问题](#常见问题)
6. [技术细节](#技术细节)

---

## 快速开始

### 1. 安装依赖

```bash
# 安装Python依赖
pip install -r requirements.txt

# 安装系统依赖
sudo apt-get install pandoc  # 用于文档验证
```

### 2. 设置API密钥

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

### 3. 运行示例

```python
from src.engine import BilingualSyncEngine

# 创建引擎
engine = BilingualSyncEngine(
    docx_path="your-document.docx",
    source_column=0,  # 左列
    target_column=1,  # 右列
    source_lang="中文",
    target_lang="英文"
)

# 执行同步
output_path = engine.sync(output_path="output.docx")
```

---

## 核心概念

### 工作流程

```
[Word文档] 
    ↓
[解包] → XML文件
    ↓
[提取] → 源语言的Track Changes
    ↓
[映射] → 使用LLM翻译到目标语言
    ↓
[应用] → 在目标语言列添加Track Changes
    ↓
[打包] → 新的Word文档
```

### 关键组件

1. **RevisionExtractor** (提取器)
   - 从XML中解析track changes
   - 识别<w:del>和<w:ins>标签
   - 提取上下文信息

2. **RevisionMapper** (映射器)
   - 调用LLM API
   - 将修订翻译到目标语言
   - 保持语义一致性

3. **RevisionApplier** (应用器)
   - 在目标文本中定位对应位置
   - 生成正确的XML标记
   - 应用track changes

---

## 详细教程

### 教程1: 基础双语同步

**场景**: 你有一个中英双列的NDA文档，律师在中文列做了修改，你需要将这些修改同步到英文列。

```python
from src.engine import BilingualSyncEngine

engine = BilingualSyncEngine(
    docx_path="NDA-bilingual.docx",
    source_column=0,  # 中文在左列
    target_column=1,  # 英文在右列
    source_lang="中文",
    target_lang="英文",
    author="Legal Team"  # 设置修订作者
)

output = engine.sync(output_path="NDA-synced.docx")
print(f"完成！输出: {output}")
```

### 教程2: 分步执行（适合调试）

如果你想更精细地控制每个步骤：

```python
from src.extractor import RevisionExtractor
from src.mapper import RevisionMapper
from src.applier import SmartRevisionApplier
import subprocess

# 步骤1: 解包
subprocess.run([
    "python3",
    "/mnt/skills/public/docx/ooxml/scripts/unpack.py",
    "input.docx",
    "unpacked"
])

# 步骤2: 提取修订
extractor = RevisionExtractor("unpacked")
revisions = extractor.extract_revisions_from_column(0)

print(f"找到 {len(revisions)} 个修订")
for rev in revisions:
    print(f"  删除: {rev['deletion']}")
    print(f"  插入: {rev['insertion']}")

# 步骤3: 映射修订
mapper = RevisionMapper(api_key="your-key")

for i, rev in enumerate(revisions):
    # 获取目标文本（你需要自己提取）
    target_text = "..."  
    
    mapped = mapper.map_revision(rev, target_text)
    print(f"映射 {i+1}: {mapped}")

# 步骤4: 应用修订
applier = SmartRevisionApplier("unpacked")

for i, mapped in enumerate(mapped_revisions):
    applier.apply_revision_to_row(
        row_index=i,
        column_index=1,
        revision=mapped
    )

applier.save()

# 步骤5: 打包
subprocess.run([
    "python3",
    "/mnt/skills/public/docx/ooxml/scripts/pack.py",
    "unpacked",
    "output.docx"
])
```

### 教程3: 批量处理多个文档

```python
import os
from src.engine import BilingualSyncEngine

def process_directory(input_dir, output_dir):
    """批量处理目录中的所有文档"""
    
    os.makedirs(output_dir, exist_ok=True)
    
    for filename in os.listdir(input_dir):
        if not filename.endswith('.docx'):
            continue
        
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, f"synced_{filename}")
        
        print(f"\n处理: {filename}")
        
        try:
            engine = BilingualSyncEngine(
                docx_path=input_path,
                source_column=0,
                target_column=1
            )
            
            engine.sync(output_path=output_path)
            print(f"✓ 完成: {output_path}")
            
        except Exception as e:
            print(f"✗ 失败: {e}")

# 使用
process_directory("input_docs", "output_docs")
```

---

## 进阶用法

### 1. 自定义LLM提示

你可以修改`mapper.py`中的提示词来优化翻译质量：

```python
class CustomRevisionMapper(RevisionMapper):
    def _build_mapping_prompt(self, source_revision, target_text, 
                              source_lang, target_lang):
        # 自定义你的提示词
        prompt = f"""
        专业法律翻译任务...
        
        额外要求：
        - 使用正式的法律术语
        - 保持条款编号一致
        - 注意日期格式
        
        ...
        """
        return prompt
```

### 2. 添加验证步骤

```python
def verify_sync(original_path, synced_path):
    """验证同步结果"""
    
    # 转换为markdown比较
    import subprocess
    
    subprocess.run([
        "pandoc", "--track-changes=all",
        original_path, "-o", "original.md"
    ])
    
    subprocess.run([
        "pandoc", "--track-changes=all",
        synced_path, "-o", "synced.md"
    ])
    
    # 读取并比较
    with open("original.md") as f:
        original = f.read()
    
    with open("synced.md") as f:
        synced = f.read()
    
    # 检查新增的修订
    print("验证报告:")
    print(f"原文档行数: {len(original.splitlines())}")
    print(f"新文档行数: {len(synced.splitlines())}")
    
    # 更详细的比较...
```

### 3. 处理复杂文档结构

对于包含多个表格或复杂结构的文档：

```python
from src.extractor import RevisionExtractor

class AdvancedExtractor(RevisionExtractor):
    def extract_all_tables(self):
        """提取所有表格的修订"""
        
        tables = self.dom.getElementsByTagName('w:tbl')
        
        all_revisions = []
        
        for table_idx, table in enumerate(tables):
            print(f"处理表格 {table_idx + 1}")
            
            rows = table.getElementsByTagName('w:tr')
            
            for row_idx, row in enumerate(rows):
                # 处理每一行...
                pass
        
        return all_revisions
```

---

## 常见问题

### Q1: 为什么有些修订没有被同步？

**原因**:
1. LLM无法准确定位目标文本
2. 源文本和目标文本差异太大
3. 修订的文本在XML中被分割成多个节点

**解决方案**:
```python
# 检查提取的修订
revisions = extractor.extract_revisions_from_column(0)
for rev in revisions:
    print(f"删除: '{rev['deletion']}'")
    print(f"插入: '{rev['insertion']}'")
    print(f"上下文: '{rev['context_before']}...{rev['context_after']}'")
    print()

# 如果修订提取不完整，可能需要调整提取逻辑
```

### Q2: 如何处理特殊字符？

```python
from src.extractor import decode_html_entities

# HTML实体会自动解码
text = "&#20320;&#22909;"  # 你好
decoded = decode_html_entities(text)
print(decoded)  # 输出: 你好
```

### Q3: 如何调整LLM的准确性？

```python
# 方法1: 提供更多上下文
class BetterExtractor(RevisionExtractor):
    def _get_context_before(self, nodes, max_chars=50):  # 增加上下文
        # ...
        pass

# 方法2: 使用不同的模型
mapper = RevisionMapper(
    api_key="...",
    model="claude-opus-4-20250514"  # 使用更强大的模型
)

# 方法3: 调整提示词温度
# 在mapper.py中修改API调用
response = self.client.messages.create(
    model=self.model,
    max_tokens=1000,
    temperature=0.0,  # 更确定的输出
    messages=[...]
)
```

---

## 技术细节

### XML结构解析

Word文档的track changes在XML中的表示：

```xml
<!-- 删除 -->
<w:del w:id="0" w:author="作者" w:date="2026-01-01T14:10:00Z">
  <w:r w:rsidDel="009007D3">
    <w:delText>被删除的文本</w:delText>
  </w:r>
</w:del>

<!-- 插入 -->
<w:ins w:id="1" w:author="作者" w:date="2026-01-01T14:10:00Z">
  <w:r>
    <w:t>插入的文本</w:t>
  </w:r>
</w:ins>
```

### 关键属性说明

- `w:id`: 修订的唯一标识符（必须唯一）
- `w:author`: 修订作者
- `w:date`: 修订日期时间
- `w:rsidDel`: 删除修订的RSID
- `w:rsidR`: 运行的RSID

### 修订ID管理

```python
# 自动获取下一个可用ID
def _get_next_revision_id(self):
    import re
    
    with open(f"{self.doc.unpacked_path}/word/document.xml") as f:
        content = f.read()
    
    ids = re.findall(r'w:id="(\d+)"', content)
    
    if ids:
        return max(int(id) for id in ids) + 1
    else:
        return 0
```

### 性能优化

对于大型文档：

```python
# 使用批量处理
def batch_map_revisions(revisions, batch_size=10):
    """批量映射修订以减少API调用"""
    
    for i in range(0, len(revisions), batch_size):
        batch = revisions[i:i+batch_size]
        
        # 构建批量提示
        prompt = build_batch_prompt(batch)
        
        # 一次API调用处理多个修订
        results = call_api(prompt)
        
        # 解析批量结果
        yield from parse_batch_results(results)
```

---

## 故障排除

### 调试模式

```python
# 启用详细日志
import logging

logging.basicConfig(level=logging.DEBUG)

# 或使用loguru
from loguru import logger

logger.add("debug.log", level="DEBUG")
```

### 验证文档完整性

```python
def validate_document(docx_path):
    """验证文档是否有效"""
    
    import zipfile
    
    try:
        with zipfile.ZipFile(docx_path, 'r') as zip_file:
            # 检查必要文件
            required_files = [
                'word/document.xml',
                '[Content_Types].xml',
                'word/_rels/document.xml.rels'
            ]
            
            for file in required_files:
                if file not in zip_file.namelist():
                    print(f"缺少文件: {file}")
                    return False
        
        print("文档结构有效")
        return True
        
    except zipfile.BadZipFile:
        print("无效的ZIP文件")
        return False
```

---

## 扩展功能建议

### 1. Web界面

使用Flask创建简单的Web界面：

```python
from flask import Flask, request, send_file
from src.engine import BilingualSyncEngine

app = Flask(__name__)

@app.route('/sync', methods=['POST'])
def sync_document():
    file = request.files['document']
    file.save('temp.docx')
    
    engine = BilingualSyncEngine(docx_path='temp.docx')
    output = engine.sync(output_path='output.docx')
    
    return send_file(output, as_attachment=True)

if __name__ == '__main__':
    app.run(port=5000)
```

### 2. 命令行工具

```bash
# 安装为命令行工具
pip install -e .

# 使用
bilingual-sync input.docx -o output.docx --source-lang 中文 --target-lang 英文
```

### 3. 集成到现有工作流

```python
# Git hooks示例
# .git/hooks/pre-commit

#!/usr/bin/env python3
from src.engine import BilingualSyncEngine

# 自动同步所有修改的双语文档
# ...
```

---

## 总结

这个引擎的核心优势：

1. **自动化**: 无需手动复制粘贴修订
2. **准确性**: 使用LLM确保翻译质量
3. **可追溯**: 保留完整的track changes历史
4. **灵活性**: 支持多种语言对和文档结构

下一步建议：

1. 针对你的具体文档类型优化提取逻辑
2. 调整LLM提示词以提高翻译质量
3. 添加自动化测试
4. 考虑性能优化（缓存、批处理等）

祝使用愉快！
