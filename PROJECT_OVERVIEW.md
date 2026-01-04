# 双语Word文档Track Changes同步引擎 - 项目概览

## 📦 项目结构

```
bilingual-sync-engine/
│
├── 📄 README.md              # 项目说明
├── 📄 QUICKSTART.md          # 5分钟快速上手指南
├── 📄 USAGE_GUIDE.md         # 详细使用指南
├── 📄 ARCHITECTURE.md        # 技术架构文档
├── 📄 requirements.txt       # Python依赖列表
│
├── 📁 src/                   # 源代码目录
│   ├── __init__.py          # 模块初始化
│   ├── extractor.py         # 修订提取器 (300行)
│   ├── mapper.py            # LLM映射器 (150行)
│   ├── applier.py           # 修订应用器 (250行)
│   ├── engine.py            # 主引擎 (300行)
│   └── config.py            # 配置管理 (100行)
│
└── 📁 examples/              # 使用示例
    └── example_usage.py     # 完整的使用示例集合
```

## 🎯 核心功能

1. **自动提取** - 从源语言列提取所有track changes
2. **智能映射** - 使用Claude AI将修订翻译到目标语言
3. **精确应用** - 在目标语言列添加对应的track changes
4. **格式保持** - 完整保留Word文档的所有格式和元数据

## 🚀 快速开始

```python
from src.engine import BilingualSyncEngine

# 一行创建引擎
engine = BilingualSyncEngine(docx_path="your-document.docx")

# 一行执行同步
output = engine.sync(output_path="synced-document.docx")
```

## 📚 文档导航

### 新手入门
1. **QUICKSTART.md** - 5分钟快速上手
2. **examples/example_usage.py** - 运行示例代码

### 日常使用
1. **USAGE_GUIDE.md** - 详细使用说明
   - 基础教程
   - 进阶用法
   - 常见问题

### 深入了解
1. **ARCHITECTURE.md** - 技术架构
   - 系统设计
   - 核心算法
   - 性能优化

## 🔧 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| XML解析 | defusedxml | 安全解析Word文档的XML |
| LLM API | Anthropic Claude | 语义映射和翻译 |
| 文档操作 | docx skill Document Library | OOXML标准操作 |
| 验证工具 | pandoc | 文档格式验证 |

## 💡 使用场景

### 1. 法律文档
- 合同协议（中英对照）
- NDA保密协议
- 服务条款

### 2. 商业文档
- 产品说明书
- 用户手册
- 技术规格

### 3. 学术文档
- 研究论文
- 学位论文
- 会议文章

## 🎓 学习路径

### Level 1: 基础使用（1小时）
1. 阅读 QUICKSTART.md
2. 运行 example_usage.py 中的示例1
3. 处理你的第一个双语文档

### Level 2: 熟练使用（2-3小时）
1. 阅读 USAGE_GUIDE.md 的基础教程部分
2. 尝试不同的语言对
3. 理解配置选项

### Level 3: 高级应用（1天）
1. 阅读完整的 USAGE_GUIDE.md
2. 学习分步执行和自定义
3. 处理复杂的文档结构

### Level 4: 深度掌握（2-3天）
1. 阅读 ARCHITECTURE.md
2. 理解XML结构和OOXML标准
3. 能够扩展和定制引擎

## 🔍 核心概念速查

### 修订（Revision）
- **删除（Deletion）**: 被标记为删除的文本
- **插入（Insertion）**: 被标记为插入的文本
- **上下文（Context）**: 修订前后的文本，用于帮助定位

### 列（Column）
- **源列（Source Column）**: 包含原始修订的列
- **目标列（Target Column）**: 需要同步修订的列

### 映射（Mapping）
- 将源语言的修订翻译到目标语言
- 保持语义一致性
- 考虑上下文和语言习惯

## 📊 性能参考

| 文档大小 | 修订数量 | 处理时间 | API成本 |
|---------|---------|---------|---------|
| 1-5页 | 1-10个 | ~30秒 | ~$0.10 |
| 10-20页 | 10-30个 | ~2分钟 | ~$0.50 |
| 50+页 | 50+个 | ~5分钟 | ~$2.00 |

*注：成本估算基于Claude Sonnet 4价格，实际成本可能有所不同*

## ⚠️ 重要提示

### 必需条件
- ✅ Python 3.9+
- ✅ Anthropic API密钥
- ✅ 网络连接（调用API）
- ✅ pandoc（用于验证）

### 文档要求
- ✅ Word文档格式 (.docx)
- ✅ 表格结构（双列或多列）
- ✅ 至少一列包含track changes

### 系统要求
- ✅ Linux/Mac/Windows
- ✅ 2GB+ 可用内存
- ✅ 足够的磁盘空间（文档大小的3倍）

## 🛠️ 故障排除速查

### 问题：找不到修订
- ✅ 检查源列索引是否正确
- ✅ 确认文档中确实有track changes
- ✅ 查看提取器的调试输出

### 问题：翻译不准确
- ✅ 增加上下文窗口大小
- ✅ 优化提示词
- ✅ 使用更强大的模型

### 问题：XML格式错误
- ✅ 使用Document Library的验证功能
- ✅ 检查OOXML标准合规性
- ✅ 查看详细错误信息

## 🔗 相关资源

### 官方文档
- [OOXML标准](http://www.ecma-international.org/publications/standards/Ecma-376.htm)
- [Anthropic API文档](https://docs.anthropic.com/)
- [pandoc文档](https://pandoc.org/MANUAL.html)

### 学习资源
- docx skill完整文档
- Python defusedxml教程
- Word VBA编程指南

## 📝 版本历史

### v1.0.0 (2026-01-03)
- ✅ 初始版本
- ✅ 基础提取、映射、应用功能
- ✅ 支持中英双语
- ✅ 智能上下文分析
- ✅ 完整的文档和示例

## 🤝 贡献指南

这个项目是为Meiqi的实际工作需求开发的工具。如果你想改进它：

1. 理解现有架构
2. 编写测试用例
3. 保持代码简洁
4. 更新相关文档

## 📜 许可证

MIT License - 可自由使用和修改

## 💬 支持

如果遇到问题：
1. 查看相关文档
2. 检查示例代码
3. 查看技术架构文档

---

**记住**: 这个工具的目标是让双语文档同步变得简单。如果你发现某个功能过于复杂，那可能意味着我们需要改进设计。

开始使用吧！ 🚀
