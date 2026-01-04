"""
双语同步引擎主模块

整合提取、映射、应用三个核心功能
"""

import os
import subprocess
from typing import List, Dict, Tuple
from .extractor import RevisionExtractor, decode_html_entities
from .mapper import RevisionMapper
from .applier import SmartRevisionApplier


class BilingualSyncEngine:
    """双语Word文档Track Changes同步引擎"""
    
    def __init__(
        self,
        docx_path: str,
        api_key: str = None,
        source_column: int = 0,
        target_column: int = 1,
        source_lang: str = "中文",
        target_lang: str = "英文",
        author: str = "Claude"
    ):
        """
        初始化同步引擎
        
        Args:
            docx_path: Word文档路径
            api_key: Anthropic API密钥
            source_column: 源语言列索引（0=左，1=右）
            target_column: 目标语言列索引
            source_lang: 源语言名称
            target_lang: 目标语言名称
            author: 修订作者名称
        """
        self.docx_path = docx_path
        self.source_column = source_column
        self.target_column = target_column
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.author = author
        
        # 设置工作目录
        self.work_dir = os.path.splitext(docx_path)[0] + "_work"
        self.unpacked_dir = os.path.join(self.work_dir, "unpacked")
        
        # 初始化API密钥
        if api_key is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
        
        if not api_key:
            raise ValueError("需要提供API密钥或设置ANTHROPIC_API_KEY环境变量")
        
        # 初始化各个组件
        self.extractor = None
        self.mapper = RevisionMapper(api_key)
        self.applier = None
    
    def sync(self, output_path: str = None) -> str:
        """
        执行完整的同步流程
        
        Args:
            output_path: 输出文档路径，如果为None则自动生成
            
        Returns:
            输出文档的路径
        """
        print("=" * 60)
        print("双语Word文档Track Changes同步引擎")
        print("=" * 60)
        
        # 1. 解包文档
        print("\n[1/6] 解包Word文档...")
        self._unpack_document()
        
        # 2. 初始化组件
        print("[2/6] 初始化组件...")
        self.extractor = RevisionExtractor(self.unpacked_dir)
        self.applier = SmartRevisionApplier(self.unpacked_dir, author=self.author)
        
        # 3. 提取源语言修订
        print(f"[3/6] 从{self.source_lang}列提取修订...")
        source_revisions = self.extractor.extract_revisions_from_column(
            self.source_column
        )
        
        print(f"  找到 {len(source_revisions)} 个修订")
        
        if not source_revisions:
            print("  没有发现修订，退出")
            return None
        
        # 4. 提取目标语言文本
        print(f"[4/6] 提取{self.target_lang}文本...")
        target_texts = self._extract_target_texts()
        
        # 5. 使用LLM映射修订
        print(f"[5/6] 使用LLM映射修订到{self.target_lang}...")
        mapped_revisions = []
        
        for i, source_rev in enumerate(source_revisions):
            row_idx = source_rev['row_index']
            target_text = target_texts[row_idx] if row_idx < len(target_texts) else ""
            
            print(f"\n  映射修订 {i+1}/{len(source_revisions)}:")
            print(f"    {self.source_lang}: {decode_html_entities(source_rev['deletion'])} → {decode_html_entities(source_rev['insertion'])}")
            
            mapped = self.mapper.map_revision(
                source_rev,
                target_text,
                self.source_lang,
                self.target_lang
            )
            
            print(f"    {self.target_lang}: {mapped['deletion']} → {mapped['insertion']}")
            print(f"    置信度: {mapped.get('confidence', 'N/A')}")
            
            mapped_revisions.append({
                'row_index': row_idx,
                'revision': mapped
            })
        
        # 6. 应用修订到目标语言列
        print(f"\n[6/6] 应用修订到{self.target_lang}列...")
        
        success_count = 0
        for item in mapped_revisions:
            if self.applier.apply_revision_to_row(
                row_index=item['row_index'],
                column_index=self.target_column,
                revision=item['revision']
            ):
                success_count += 1
        
        print(f"\n成功应用 {success_count}/{len(mapped_revisions)} 个修订")
        
        # 7. 保存文档
        print("\n保存修改...")
        self.applier.save()
        
        # 8. 打包文档
        if output_path is None:
            base, ext = os.path.splitext(self.docx_path)
            output_path = f"{base}_synced{ext}"
        
        print(f"打包文档到: {output_path}")
        self._pack_document(output_path)
        
        # 9. 验证
        print("\n验证结果...")
        self._verify_output(output_path)
        
        print("\n" + "=" * 60)
        print("同步完成！")
        print(f"输出文件: {output_path}")
        print("=" * 60)
        
        return output_path
    
    def _unpack_document(self):
        """解包Word文档"""
        os.makedirs(self.work_dir, exist_ok=True)
        
        cmd = [
            "python3",
            "/mnt/skills/public/docx/ooxml/scripts/unpack.py",
            self.docx_path,
            self.unpacked_dir
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"解包失败: {result.stderr}")
        
        print(f"  文档已解包到: {self.unpacked_dir}")
    
    def _extract_target_texts(self) -> List[str]:
        """提取目标语言列的所有文本"""
        from defusedxml import minidom
        
        doc_xml_path = f"{self.unpacked_dir}/word/document.xml"
        
        with open(doc_xml_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        dom = minidom.parseString(content)
        rows = dom.getElementsByTagName('w:tr')
        
        texts = []
        
        for row in rows:
            cells = row.getElementsByTagName('w:tc')
            if self.target_column < len(cells):
                cell = cells[self.target_column]
                
                # 提取所有文本节点
                text_parts = []
                for t_node in cell.getElementsByTagName('w:t'):
                    if t_node.firstChild:
                        text_parts.append(t_node.firstChild.nodeValue)
                
                text = ''.join(text_parts)
                texts.append(decode_html_entities(text))
            else:
                texts.append("")
        
        return texts
    
    def _pack_document(self, output_path: str):
        """打包Word文档"""
        cmd = [
            "python3",
            "/mnt/skills/public/docx/ooxml/scripts/pack.py",
            self.unpacked_dir,
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"打包失败: {result.stderr}")
    
    def _verify_output(self, output_path: str):
        """验证输出文档"""
        # 使用pandoc转换为markdown以验证
        md_path = output_path.replace('.docx', '_verify.md')
        
        cmd = [
            "pandoc",
            "--track-changes=all",
            output_path,
            "-o",
            md_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"  验证文件已生成: {md_path}")
            
            # 显示前几行
            with open(md_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()[:10]
            
            print("\n  预览前10行:")
            for line in lines:
                print(f"    {line.rstrip()}")
        else:
            print(f"  验证失败: {result.stderr}")


# 命令行接口
def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="双语Word文档Track Changes同步引擎"
    )
    parser.add_argument(
        "input",
        help="输入的双语Word文档路径"
    )
    parser.add_argument(
        "-o", "--output",
        help="输出文档路径（可选）"
    )
    parser.add_argument(
        "--source-column",
        type=int,
        default=0,
        help="源语言列索引（默认: 0）"
    )
    parser.add_argument(
        "--target-column",
        type=int,
        default=1,
        help="目标语言列索引（默认: 1）"
    )
    parser.add_argument(
        "--source-lang",
        default="中文",
        help="源语言名称（默认: 中文）"
    )
    parser.add_argument(
        "--target-lang",
        default="英文",
        help="目标语言名称（默认: 英文）"
    )
    parser.add_argument(
        "--author",
        default="Claude",
        help="修订作者名称（默认: Claude）"
    )
    parser.add_argument(
        "--api-key",
        help="Anthropic API密钥（可选，也可通过环境变量设置）"
    )
    
    args = parser.parse_args()
    
    # 创建引擎
    engine = BilingualSyncEngine(
        docx_path=args.input,
        api_key=args.api_key,
        source_column=args.source_column,
        target_column=args.target_column,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        author=args.author
    )
    
    # 执行同步
    output_path = engine.sync(args.output)
    
    return output_path


if __name__ == "__main__":
    main()
