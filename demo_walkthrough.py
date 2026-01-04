"""
双语同步引擎演示脚本 - 展示核心工作流程

这个脚本演示了引擎的工作原理，不需要实际的文档和API
"""

import sys
import os

# 添加src到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def demo_overview():
    """演示1: 系统概览"""
    print("=" * 80)
    print("双语Word文档Track Changes同步引擎 - 系统概览")
    print("=" * 80)

    print("\n这个引擎解决的问题:")
    print("  在双语法律文档中，当一种语言被修订（track changes）时，")
    print("  需要将相应的修订同步到另一种语言，保持两个版本的一致性。")

    print("\n核心工作流程:")
    print("  1. [提取] 从源语言列提取所有track changes")
    print("  2. [映射] 使用Claude AI将修订翻译到目标语言")
    print("  3. [应用] 在目标语言列添加对应的track changes")

    print("\n技术栈:")
    print("  • Python 3.9+")
    print("  • defusedxml (安全的XML解析)")
    print("  • Anthropic Claude API (语义映射)")
    print("  • OOXML标准 (Word文档格式)")

    input("\n按Enter继续...")


def demo_extraction():
    """演示2: 修订提取"""
    print("\n" + "=" * 80)
    print("步骤1: 修订提取 (RevisionExtractor)")
    print("=" * 80)

    print("\n模拟场景: 从中文列提取修订")
    print("-" * 60)

    # 模拟XML结构
    print("\n原始XML结构示例:")
    print("""
    <w:tc>  <!-- 表格单元格 -->
      <w:p>  <!-- 段落 -->
        <w:r><w:t>你好！今天</w:t></w:r>
        <w:del w:id="0">  <!-- 删除标记 -->
          <w:r><w:delText>天气</w:delText></w:r>
        </w:del>
        <w:ins w:id="1">  <!-- 插入标记 -->
          <w:r><w:t>空气质量</w:t></w:r>
        </w:ins>
        <w:r><w:t>怎么样？</w:t></w:r>
      </w:p>
    </w:tc>
    """)

    # 模拟提取结果
    print("\n提取器提取出的修订:")
    revision = {
        'row_index': 0,
        'deletion': '天气',
        'insertion': '空气质量',
        'context_before': '你好！今天',
        'context_after': '怎么样？',
        'del_id': '0',
        'ins_id': '1'
    }

    for key, value in revision.items():
        print(f"  • {key}: '{value}'")

    input("\n按Enter继续...")


def demo_mapping():
    """演示3: LLM映射"""
    print("\n" + "=" * 80)
    print("步骤2: LLM映射 (RevisionMapper)")
    print("=" * 80)

    print("\n模拟场景: 将中文修订映射到英文")
    print("-" * 60)

    # 输入数据
    print("\n输入数据:")
    print("  源语言修订:")
    print("    删除: '天气'")
    print("    插入: '空气质量'")
    print("    上下文: '你好！今天...怎么样？'")
    print("  目标语言文本:")
    print("    'Hello! How's the weather today?'")

    # LLM提示词
    print("\n发送给Claude的提示词:")
    print("""
    你是双语法律文档翻译专家。

    源语言(中文)的修订:
    - 删除: "天气"
    - 插入: "空气质量"
    - 上下文: "你好！今天...怎么样？"

    目标语言(英文)当前文本:
    "Hello! How's the weather today?"

    任务: 找到对应位置并提供应该进行的修订。
    返回JSON格式: {"deletion": "...", "insertion": "...", "confidence": 0.95}
    """)

    # 模拟LLM响应
    print("\nClaude返回的映射结果:")
    mapped = {
        "deletion": "weather",
        "insertion": "air quality",
        "explanation": "将'天气'对应到'weather'，'空气质量'对应到'air quality'",
        "confidence": 0.95
    }

    for key, value in mapped.items():
        print(f"  • {key}: '{value}'")

    input("\n按Enter继续...")


def demo_application():
    """演示4: 修订应用"""
    print("\n" + "=" * 80)
    print("步骤3: 修订应用 (SmartRevisionApplier)")
    print("=" * 80)

    print("\n模拟场景: 在英文列应用修订")
    print("-" * 60)

    print("\n原始英文文本:")
    print("  'Hello! How's the weather today?'")

    print("\n需要应用的修订:")
    print("  删除: 'weather'")
    print("  插入: 'air quality'")

    print("\n应用器的处理步骤:")
    print("  1. 在文本中定位 'weather'")
    print("  2. 分析文本结构:")
    print("     - text_before: \"Hello! How's the \"")
    print("     - deletion: \"weather\"")
    print("     - insertion: \"air quality\"")
    print("     - text_after: \" today?\"")

    print("\n  3. 生成新的XML结构:")
    print("""
    <w:p>
      <w:r><w:t>Hello! How's the </w:t></w:r>
      <w:del w:id="2" w:author="Claude">
        <w:r><w:delText>weather</w:delText></w:r>
      </w:del>
      <w:ins w:id="3" w:author="Claude">
        <w:r><w:t>air quality</w:t></w:r>
      </w:ins>
      <w:r><w:t> today?</w:t></w:r>
    </w:p>
    """)

    print("\n最终效果:")
    print("  在Word中打开文档时，英文列会显示:")
    print("  'Hello! How's the [weather](删除) [air quality](插入) today?'")
    print("  (带有track changes标记)")

    input("\n按Enter继续...")


def demo_complete_workflow():
    """演示5: 完整工作流程"""
    print("\n" + "=" * 80)
    print("完整工作流程总结")
    print("=" * 80)

    print("\n一个完整的同步过程:")
    print("-" * 60)

    steps = [
        ("1. 解包文档", "将.docx文件解压为XML文件"),
        ("2. 提取修订", "从源语言列找到所有<w:del>和<w:ins>标记"),
        ("3. 提取上下文", "记录修订前后的文本以帮助定位"),
        ("4. 调用LLM", "将修订翻译到目标语言"),
        ("5. 定位文本", "在目标语言列中找到对应位置"),
        ("6. 插入XML", "添加新的<w:del>和<w:ins>标记"),
        ("7. 打包文档", "将XML文件重新打包为.docx")
    ]

    for step, description in steps:
        print(f"\n{step}")
        print(f"  → {description}")

    print("\n" + "=" * 60)
    print("结果: 双语文档的两列修订保持同步！")
    print("=" * 60)

    input("\n按Enter继续...")


def demo_code_structure():
    """演示6: 代码结构"""
    print("\n" + "=" * 80)
    print("代码结构一览")
    print("=" * 80)

    print("\n核心模块:")

    modules = [
        ("src/config.py", "配置管理", [
            "API密钥、模型选择",
            "语言设置、列索引",
            "作者信息、路径配置"
        ]),
        ("src/extractor.py", "修订提取器 (254行)", [
            "RevisionExtractor类",
            "extract_revisions_from_column()",
            "_pair_deletions_insertions()",
            "解析XML、提取上下文"
        ]),
        ("src/mapper.py", "LLM映射器 (215行)", [
            "RevisionMapper类",
            "map_revision()",
            "构建提示词",
            "调用Claude API"
        ]),
        ("src/applier.py", "修订应用器 (326行)", [
            "SmartRevisionApplier类",
            "apply_revision_to_row()",
            "定位文本、插入XML",
            "管理修订ID"
        ]),
        ("src/engine.py", "主引擎 (325行)", [
            "BilingualSyncEngine类",
            "sync() - 完整流程",
            "整合所有模块",
            "错误处理、日志"
        ])
    ]

    for filename, description, features in modules:
        print(f"\n{filename}")
        print(f"  功能: {description}")
        print("  核心特性:")
        for feature in features:
            print(f"    • {feature}")

    input("\n按Enter继续...")


def demo_usage_example():
    """演示7: 实际使用示例"""
    print("\n" + "=" * 80)
    print("实际使用示例")
    print("=" * 80)

    print("\n如何使用这个引擎（伪代码）:")
    print("-" * 60)

    code = """
# 1. 导入引擎
from src.engine import BilingualSyncEngine

# 2. 创建引擎实例
engine = BilingualSyncEngine(
    docx_path="your-document.docx",
    api_key="your-anthropic-api-key",
    source_column=0,      # 左列（中文）
    target_column=1,      # 右列（英文）
    source_lang="中文",
    target_lang="英文"
)

# 3. 执行同步（一行代码！）
output = engine.sync(
    output_path="synced-document.docx"
)

# 完成！
print(f"同步完成: {output}")
    """

    print(code)

    print("\n运行要求:")
    print("  • Python 3.9+")
    print("  • Anthropic API密钥")
    print("  • 双语Word文档（.docx格式）")
    print("  • 文档中包含track changes")

    input("\n按Enter继续...")


def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "双语Word文档Track Changes同步引擎" + " " * 15 + "║")
    print("║" + " " * 28 + "交互式演示" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")

    print("\n这个演示将展示引擎的工作原理和代码结构")
    print("不需要API密钥或实际文档")

    input("\n按Enter开始...")

    # 运行所有演示
    demo_overview()
    demo_extraction()
    demo_mapping()
    demo_application()
    demo_complete_workflow()
    demo_code_structure()
    demo_usage_example()

    # 总结
    print("\n" + "=" * 80)
    print("演示完成！")
    print("=" * 80)

    print("\n下一步:")
    print("  1. 如果你有Anthropic API密钥，可以运行实际示例")
    print("  2. 阅读源代码以深入理解实现细节")
    print("  3. 准备一个双语Word文档进行测试")

    print("\n要运行实际示例，需要:")
    print("  • 设置环境变量: export ANTHROPIC_API_KEY='your-key'")
    print("  • 准备测试文档")
    print("  • 运行: python examples/example_usage.py")

    print("\n感谢观看！")
    print()


if __name__ == "__main__":
    main()
