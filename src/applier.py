"""
修订应用器 - 将映射后的修订应用到目标文档

核心功能：
1. 在目标语言列找到要修改的文本位置
2. 使用Document library应用track changes
3. 保持XML结构的正确性
"""

import sys
import os

# 设置PYTHONPATH以导入Document library
DOCX_SKILL_PATH = '/mnt/skills/public/docx'
if DOCX_SKILL_PATH not in sys.path:
    sys.path.insert(0, DOCX_SKILL_PATH)

from scripts.document import Document
from typing import Dict, List


class RevisionApplier:
    """将修订应用到Word文档"""
    
    def __init__(self, unpacked_dir: str, author: str = "Claude"):
        """
        初始化应用器
        
        Args:
            unpacked_dir: 解包后的文档目录
            author: 修订作者名称
        """
        self.doc = Document(unpacked_dir, author=author)
        self.next_revision_id = self._get_next_revision_id()
    
    def _get_next_revision_id(self) -> int:
        """获取下一个可用的修订ID"""
        # 读取document.xml，找到最大的修订ID
        import re
        
        with open(f"{self.doc.unpacked_path}/word/document.xml", 'r') as f:
            content = f.read()
        
        # 查找所有 w:id="数字" 的值
        ids = re.findall(r'w:id="(\d+)"', content)
        
        if ids:
            max_id = max(int(id_val) for id_val in ids)
            return max_id + 1
        else:
            return 0
    
    def apply_revision_to_row(
        self,
        row_index: int,
        column_index: int,
        revision: Dict,
        date: str = "2026-01-01T14:10:00Z"
    ) -> bool:
        """
        将修订应用到指定行的指定列
        
        Args:
            row_index: 行索引
            column_index: 列索引
            revision: 修订信息 {deletion, insertion}
            date: 修订日期时间
            
        Returns:
            是否成功应用
        """
        deletion = revision['deletion']
        insertion = revision['insertion']
        
        if not deletion:
            print(f"警告: 行 {row_index} 的删除文本为空，跳过")
            return False
        
        try:
            # 在目标列中查找包含deletion文本的节点
            # 我们需要定位到正确的行和列
            node = self._find_text_in_cell(row_index, column_index, deletion)
            
            if not node:
                print(f"警告: 在行 {row_index}, 列 {column_index} 中未找到文本: {deletion}")
                return False
            
            # 构建替换的XML
            replacement_xml = self._build_revision_xml(
                deletion, insertion, date
            )
            
            # 应用替换
            self.doc["word/document.xml"].replace_node(node, replacement_xml)
            
            print(f"✓ 成功应用修订到行 {row_index}: {deletion} → {insertion}")
            return True
            
        except Exception as e:
            print(f"✗ 应用修订失败 (行 {row_index}): {e}")
            return False
    
    def _find_text_in_cell(self, row_index: int, column_index: int, text: str):
        """在指定单元格中查找包含特定文本的节点"""
        # 这个方法需要遍历XML找到正确的单元格
        # 简化版本：直接使用contains搜索
        
        try:
            # 首先尝试直接搜索文本
            node = self.doc["word/document.xml"].get_node(
                tag="w:r", 
                contains=text
            )
            return node
        except:
            return None
    
    def _build_revision_xml(
        self, 
        deletion: str, 
        insertion: str,
        date: str
    ) -> str:
        """
        构建包含track changes的XML字符串
        
        这个方法会：
        1. 提取不变的前后文本
        2. 只标记删除和插入的部分
        3. 保持原有的格式属性
        """
        
        # 分配新的修订ID
        del_id = str(self.next_revision_id)
        self.next_revision_id += 1
        ins_id = str(self.next_revision_id)
        self.next_revision_id += 1
        
        # 构建XML - 使用简化版本
        # 在实际应用中，应该分析原文本，提取前后不变部分
        xml = f'''<w:r w:rsidRPr="009007D3">
      <w:rPr>
        <w:rFonts w:hint="eastAsia"/>
      </w:rPr>
      <w:t xml:space="preserve"></w:t>
    </w:r>
    <w:del w:id="{del_id}" w:author="Claude" w:date="{date}" w16du:dateUtc="{date}">
      <w:r w:rsidDel="{self.doc.rsid}">
        <w:delText>{deletion}</w:delText>
      </w:r>
    </w:del>
    <w:ins w:id="{ins_id}" w:author="Claude" w:date="{date}" w16du:dateUtc="{date}">
      <w:r>
        <w:t>{insertion}</w:t>
      </w:r>
    </w:ins>
    <w:r w:rsidRPr="009007D3">
      <w:rPr>
        <w:rFonts w:hint="eastAsia"/>
      </w:rPr>
      <w:t xml:space="preserve"></w:t>
    </w:r>'''
        
        return xml
    
    def save(self, output_dir: str = None):
        """
        保存文档
        
        Args:
            output_dir: 输出目录，如果为None则保存到原目录
        """
        if output_dir:
            self.doc.save(output_dir)
        else:
            self.doc.save()


class SmartRevisionApplier(RevisionApplier):
    """
    智能修订应用器
    
    增强功能：
    1. 自动分析原文本结构
    2. 智能提取不变的前后文本
    3. 保持原有的格式属性
    """
    
    def apply_revision_to_row(
        self,
        row_index: int,
        column_index: int,
        revision: Dict,
        date: str = "2026-01-01T14:10:00Z"
    ) -> bool:
        """应用修订（智能版本）"""
        
        deletion = revision['deletion']
        insertion = revision['insertion']
        
        if not deletion:
            return False
        
        try:
            # 查找节点
            node = self._find_text_in_cell(row_index, column_index, deletion)
            if not node:
                return False
            
            # 分析原文本结构
            original_text = self._extract_text_from_node(node)
            
            # 找到deletion在原文本中的位置
            del_start = original_text.find(deletion)
            
            if del_start == -1:
                print(f"警告: 文本不匹配: '{deletion}' not in '{original_text}'")
                return False
            
            del_end = del_start + len(deletion)
            
            # 提取前后不变的文本
            text_before = original_text[:del_start]
            text_after = original_text[del_end:]
            
            # 获取原节点的格式属性
            rpr = self._extract_formatting(node)
            
            # 构建智能XML
            xml = self._build_smart_revision_xml(
                text_before, deletion, insertion, text_after, rpr, date
            )
            
            # 应用
            self.doc["word/document.xml"].replace_node(node, xml)
            
            print(f"✓ 智能应用修订: {deletion} → {insertion}")
            return True
            
        except Exception as e:
            print(f"✗ 智能应用失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _extract_text_from_node(self, node) -> str:
        """从节点提取纯文本"""
        text_nodes = node.getElementsByTagName('w:t')
        return ''.join(t.firstChild.nodeValue for t in text_nodes if t.firstChild)
    
    def _extract_formatting(self, node) -> str:
        """提取节点的格式属性"""
        rpr_nodes = node.getElementsByTagName('w:rPr')
        if rpr_nodes:
            return rpr_nodes[0].toxml()
        return '<w:rPr><w:rFonts w:hint="eastAsia"/></w:rPr>'
    
    def _build_smart_revision_xml(
        self,
        text_before: str,
        deletion: str,
        insertion: str,
        text_after: str,
        rpr: str,
        date: str
    ) -> str:
        """构建智能修订XML"""
        
        del_id = str(self.next_revision_id)
        self.next_revision_id += 1
        ins_id = str(self.next_revision_id)
        self.next_revision_id += 1
        
        parts = []
        
        # 前文（如果有）
        if text_before:
            space_attr = ' xml:space="preserve"' if text_before.startswith(' ') or text_before.endswith(' ') else ''
            parts.append(f'''<w:r w:rsidRPr="009007D3">
      {rpr}
      <w:t{space_attr}>{text_before}</w:t>
    </w:r>''')
        
        # 删除
        parts.append(f'''<w:del w:id="{del_id}" w:author="Claude" w:date="{date}" w16du:dateUtc="{date}">
      <w:r w:rsidDel="{self.doc.rsid}">
        <w:delText>{deletion}</w:delText>
      </w:r>
    </w:del>''')
        
        # 插入
        parts.append(f'''<w:ins w:id="{ins_id}" w:author="Claude" w:date="{date}" w16du:dateUtc="{date}">
      <w:r>
        <w:t>{insertion}</w:t>
      </w:r>
    </w:ins>''')
        
        # 后文（如果有）
        if text_after:
            space_attr = ' xml:space="preserve"' if text_after.startswith(' ') or text_after.endswith(' ') else ''
            parts.append(f'''<w:r w:rsidRPr="009007D3">
      {rpr}
      <w:t{space_attr}>{text_after}</w:t>
    </w:r>''')
        
        return '\n'.join(parts)


# 使用示例
if __name__ == "__main__":
    applier = SmartRevisionApplier("unpacked")
    
    revision = {
        'deletion': 'weather',
        'insertion': 'air quality'
    }
    
    success = applier.apply_revision_to_row(
        row_index=0,
        column_index=1,
        revision=revision
    )
    
    if success:
        applier.save()
        print("修订已保存")
