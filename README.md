# 双语Word文档Track Changes同步引擎

## 项目结构

```
bilingual-sync-engine/
├── README.md                    # 项目说明
├── requirements.txt             # Python依赖
├── config.py                    # 配置文件
├── src/
│   ├── __init__.py
│   ├── extractor.py            # 提取track changes
│   ├── mapper.py               # LLM映射翻译
│   ├── applier.py              # 应用修订到目标语言
│   └── utils.py                # 工具函数
├── tests/
│   └── test_basic.py           # 基础测试
└── examples/
    └── example_usage.py        # 使用示例

```

## 核心依赖

1. **OOXML处理**：使用docx skill中的Document library
2. **LLM API**：Anthropic Claude API
3. **文档转换**：pandoc (用于调试和验证)

## 工作流程

1. 解包Word文档 (unpack .docx → XML files)
2. 提取源语言的所有track changes
3. 使用LLM将每个修订映射到目标语言
4. 在目标语言列应用对应的track changes
5. 打包并验证最终文档
