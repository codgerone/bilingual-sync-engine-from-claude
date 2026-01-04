"""
快速演示 - 同步引擎的实际效果
不需要真实文档，直接展示核心逻辑
"""

print("=" * 70)
print("双语Word文档Track Changes同步引擎 - 快速演示")
print("=" * 70)

# 场景设置
print("\n【场景】你有一个中英双语的法律合同文档")
print("=" * 70)

print("\n中文列（左侧）:")
print("  原文: 你好！今天天气怎么样？")
print("  修订后: 你好！今天[删除:天气][插入:空气质量]怎么样？")

print("\n英文列（右侧）:")
print("  原文: Hello! How's the weather today?")
print("  ❌ 问题: 英文列没有修订标记！两列不一致！")

print("\n" + "=" * 70)
print("【解决方案】使用同步引擎")
print("=" * 70)

# 步骤1: 提取
print("\n步骤1️⃣  提取修订 (Extractor)")
print("-" * 70)
print("  从中文列的XML中提取:")
revision = {
    'deletion': '天气',
    'insertion': '空气质量',
    'context_before': '你好！今天',
    'context_after': '怎么样？'
}
for key, value in revision.items():
    print(f"    • {key}: '{value}'")

# 步骤2: 映射
print("\n步骤2️⃣  LLM映射 (Mapper)")
print("-" * 70)
print("  发送给Claude AI:")
print("    '请将中文修订翻译到英文'")
print("    '删除: 天气  →  ?'")
print("    '插入: 空气质量  →  ?'")
print("\n  Claude返回:")
mapped = {
    'deletion': 'weather',
    'insertion': 'air quality'
}
for key, value in mapped.items():
    print(f"    • {key}: '{value}'")

# 步骤3: 应用
print("\n步骤3️⃣  应用修订 (Applier)")
print("-" * 70)
print("  在英文列的XML中插入:")
print("    Hello! How's the [删除:weather][插入:air quality] today?")

# 结果
print("\n" + "=" * 70)
print("【结果】两列修订保持同步！")
print("=" * 70)

print("\n✅ 中文列: 你好！今天[删除:天气][插入:空气质量]怎么样？")
print("✅ 英文列: Hello! How's the [删除:weather][插入:air quality] today?")

print("\n" + "=" * 70)
print("这就是这个引擎的核心价值！")
print("自动同步双语文档的修订，保持一致性")
print("=" * 70)

# 代码示例
print("\n【使用方法】")
print("-" * 70)
print("""
from src.engine import BilingualSyncEngine

# 一行创建
engine = BilingualSyncEngine(
    docx_path="your-document.docx",
    api_key="your-api-key"
)

# 一行执行
engine.sync(output_path="synced.docx")

# 完成！
""")

print("\n" + "=" * 70)
print("演示完成！")
print("=" * 70)
