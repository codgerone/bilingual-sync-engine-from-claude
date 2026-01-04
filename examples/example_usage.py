"""
双语Word文档Track Changes同步引擎 - 使用示例
"""

import os
import sys

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from engine import BilingualSyncEngine


def example_basic_usage():
    """基础使用示例"""
    
    print("=" * 60)
    print("示例1: 基础使用")
    print("=" * 60)
    
    # 设置API密钥（从环境变量或直接提供）
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key:
        print("错误: 请设置ANTHROPIC_API_KEY环境变量")
        return
    
    # 创建引擎实例
    engine = BilingualSyncEngine(
        docx_path="/mnt/user-data/uploads/test-bilingual-document.docx",
        api_key=api_key,
        source_column=0,  # 左列是中文（源语言）
        target_column=1,  # 右列是英文（目标语言）
        source_lang="中文",
        target_lang="英文"
    )
    
    # 执行同步
    output_path = engine.sync(
        output_path="/mnt/user-data/outputs/synced_example_basic.docx"
    )
    
    print(f"\n完成! 输出文件: {output_path}")


def example_reverse_direction():
    """反向同步示例：英文→中文"""
    
    print("\n" + "=" * 60)
    print("示例2: 反向同步（英文修订→中文）")
    print("=" * 60)
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    if not api_key:
        print("错误: 请设置ANTHROPIC_API_KEY环境变量")
        return
    
    # 反向设置：右列（英文）是源，左列（中文）是目标
    engine = BilingualSyncEngine(
        docx_path="/mnt/user-data/uploads/test-bilingual-document.docx",
        api_key=api_key,
        source_column=1,  # 右列是英文（源语言）
        target_column=0,  # 左列是中文（目标语言）
        source_lang="English",
        target_lang="Chinese"
    )
    
    output_path = engine.sync(
        output_path="/mnt/user-data/outputs/synced_example_reverse.docx"
    )
    
    print(f"\n完成! 输出文件: {output_path}")


def example_step_by_step():
    """分步执行示例：展示每个阶段"""
    
    print("\n" + "=" * 60)
    print("示例3: 分步执行（详细展示）")
    print("=" * 60)
    
    from extractor import RevisionExtractor, decode_html_entities
    from mapper import RevisionMapper
    from applier import SmartRevisionApplier
    import subprocess
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("错误: 请设置ANTHROPIC_API_KEY环境变量")
        return
    
    docx_path = "/mnt/user-data/uploads/test-bilingual-document.docx"
    unpacked_dir = "/home/claude/manual_unpacked"
    
    # 步骤1: 解包
    print("\n步骤1: 解包文档")
    subprocess.run([
        "python3",
        "/mnt/skills/public/docx/ooxml/scripts/unpack.py",
        docx_path,
        unpacked_dir
    ])
    print("  ✓ 解包完成")
    
    # 步骤2: 提取修订
    print("\n步骤2: 提取中文列的修订")
    extractor = RevisionExtractor(unpacked_dir)
    revisions = extractor.extract_revisions_from_column(column_index=0)
    
    print(f"  ✓ 找到 {len(revisions)} 个修订:")
    for i, rev in enumerate(revisions, 1):
        print(f"\n  修订 {i}:")
        print(f"    行: {rev['row_index']}")
        print(f"    删除: {decode_html_entities(rev['deletion'])}")
        print(f"    插入: {decode_html_entities(rev['insertion'])}")
    
    # 步骤3: 映射修订
    print("\n步骤3: 使用LLM映射到英文")
    mapper = RevisionMapper(api_key)
    
    # 简单示例：只映射第一个修订
    if revisions:
        first_rev = revisions[0]
        target_text = "Hello! How's the weather today?"
        
        mapped = mapper.map_revision(
            first_rev,
            target_text,
            source_lang="中文",
            target_lang="英文"
        )
        
        print(f"  ✓ 映射结果:")
        print(f"    删除: {mapped['deletion']}")
        print(f"    插入: {mapped['insertion']}")
        print(f"    置信度: {mapped.get('confidence')}")
    
    # 步骤4: 应用修订
    print("\n步骤4: 应用修订到英文列")
    applier = SmartRevisionApplier(unpacked_dir)
    
    if revisions and mapped:
        success = applier.apply_revision_to_row(
            row_index=0,
            column_index=1,
            revision=mapped
        )
        
        if success:
            print("  ✓ 修订应用成功")
            applier.save()
            print("  ✓ 已保存")
    
    # 步骤5: 打包
    print("\n步骤5: 打包文档")
    output_path = "/mnt/user-data/outputs/synced_example_manual.docx"
    subprocess.run([
        "python3",
        "/mnt/skills/public/docx/ooxml/scripts/pack.py",
        unpacked_dir,
        output_path
    ])
    print(f"  ✓ 已打包到: {output_path}")


def example_custom_configuration():
    """自定义配置示例"""
    
    print("\n" + "=" * 60)
    print("示例4: 自定义配置")
    print("=" * 60)
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("错误: 请设置ANTHROPIC_API_KEY环境变量")
        return
    
    # 使用自定义配置
    engine = BilingualSyncEngine(
        docx_path="/mnt/user-data/uploads/test-bilingual-document.docx",
        api_key=api_key,
        source_column=0,
        target_column=1,
        source_lang="简体中文",  # 自定义语言名称
        target_lang="美式英语",
        author="Meiqi Jiang"  # 自定义作者名
    )
    
    output_path = engine.sync(
        output_path="/mnt/user-data/outputs/synced_example_custom.docx"
    )
    
    print(f"\n完成! 输出文件: {output_path}")


def main():
    """运行所有示例"""
    
    print("\n" + "=" * 80)
    print(" 双语Word文档Track Changes同步引擎 - 使用示例集合")
    print("=" * 80)
    
    # 检查API密钥
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("\n错误: 请先设置ANTHROPIC_API_KEY环境变量")
        print("示例: export ANTHROPIC_API_KEY='your-api-key-here'")
        return
    
    print("\n请选择要运行的示例:")
    print("  1. 基础使用（中文→英文）")
    print("  2. 反向同步（英文→中文）")
    print("  3. 分步执行（详细展示每个步骤）")
    print("  4. 自定义配置")
    print("  5. 运行所有示例")
    print("  0. 退出")
    
    choice = input("\n请输入选项 (0-5): ").strip()
    
    if choice == '1':
        example_basic_usage()
    elif choice == '2':
        example_reverse_direction()
    elif choice == '3':
        example_step_by_step()
    elif choice == '4':
        example_custom_configuration()
    elif choice == '5':
        example_basic_usage()
        example_reverse_direction()
        example_step_by_step()
        example_custom_configuration()
    elif choice == '0':
        print("退出")
    else:
        print("无效选项")


if __name__ == "__main__":
    main()
