# 快速开始 - 5分钟上手

## 最简单的使用方式

### 1. 准备工作（2分钟）

```bash
# 克隆或下载项目
cd bilingual-sync-engine

# 安装依赖
pip install anthropic defusedxml

# 设置API密钥
export ANTHROPIC_API_KEY='your-api-key-here'
```

### 2. 运行示例（3分钟）

```python
from src.engine import BilingualSyncEngine

# 创建引擎（一行代码）
engine = BilingualSyncEngine(
    docx_path="your-bilingual-document.docx"
)

# 执行同步（一行代码）
output = engine.sync(output_path="synced-document.docx")

print(f"完成！输出: {output}")
```

就这么简单！

## 完整示例

```python
from src.engine import BilingualSyncEngine

# 如果你的文档结构是：
# - 左列：中文（有track changes）
# - 右列：英文（需要同步）

engine = BilingualSyncEngine(
    docx_path="contract.docx",
    source_column=0,    # 左列
    target_column=1,    # 右列
    source_lang="中文",
    target_lang="英文",
    author="Legal Team"  # 修订者名称
)

# 执行同步
output = engine.sync(output_path="contract-synced.docx")

# 完成！
```

## 验证结果

打开 `contract-synced.docx`，你会看到：
1. 英文列有了对应的track changes
2. 所有修订都标记为作者 "Legal Team"
3. 修订内容与中文列的语义一致

## 下一步

- 查看 `USAGE_GUIDE.md` 了解更多功能
- 查看 `examples/example_usage.py` 了解高级用法
- 查看 `ARCHITECTURE.md` 了解技术细节

## 常见问题

**Q: 需要联网吗？**
A: 是的，需要调用Anthropic API进行翻译映射。

**Q: 支持哪些语言？**
A: 支持Claude API支持的所有语言对，包括中英、中西、英德等。

**Q: 会修改原文档吗？**
A: 不会，总是生成新文档。

**Q: 处理速度如何？**
A: 小文档（1-5页）约30秒，主要时间在LLM API调用。

**Q: 成本如何？**
A: 取决于文档大小和修订数量，通常每个修订约0.01-0.05美元。

## 需要帮助？

- 技术问题：查看 ARCHITECTURE.md
- 使用问题：查看 USAGE_GUIDE.md
- Bug报告：记录详细的错误信息和文档示例
