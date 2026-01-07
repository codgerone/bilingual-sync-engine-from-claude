"""
修订应用器 - 将映射后的修订应用到目标文档

核心功能：
1. 使用词级别 diff 比较 current_text 和 target_after
2. 生成 track changes XML 结构
3. 应用到目标文档

V2 重塑说明：
- 新增词级别 diff 函数（英文按空格，中文用 jieba）
- 接收 current_text 和 target_after，自动计算差异
- 支持一个单元格多处修订
"""

import sys
import os
import re
import difflib
from datetime import datetime
from typing import Dict, List, Tuple

# 尝试导入 jieba（中文分词）
try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    print("警告: jieba 未安装，中文将按字符分词。请运行: pip install jieba")

# 设置PYTHONPATH以导入Document library
DOCX_SKILL_PATH = '/mnt/skills/public/docx'
if DOCX_SKILL_PATH not in sys.path:
    sys.path.insert(0, DOCX_SKILL_PATH)

from scripts.document import Document


# ========== 分词和 Diff 工具函数 ==========

def detect_language(text: str) -> str:
    """
    简单检测文本主要语言

    Returns:
        'zh' 如果主要是中文
        'en' 如果主要是英文/其他
    """
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(text.replace(' ', ''))

    if total_chars == 0:
        return 'en'

    if chinese_chars / total_chars > 0.3:
        return 'zh'
    return 'en'


def tokenize(text: str) -> List[str]:
    """
    将文本分词

    - 中文：使用 jieba 分词
    - 英文：按空格分词，保留标点
    """
    lang = detect_language(text)

    if lang == 'zh':
        if JIEBA_AVAILABLE:
            # jieba 分词
            tokens = list(jieba.cut(text))
            # 过滤空字符串
            return [t for t in tokens if t]
        else:
            # 没有 jieba，按字符分
            return list(text)
    else:
        # 英文：按空格分词，保留标点
        # 使用正则表达式分割，保留分隔符（空格）
        tokens = re.split(r'(\s+)', text)
        return [t for t in tokens if t]


def word_diff(current_text: str, target_after: str) -> List[Tuple[str, str]]:
    """
    词级别 diff

    Args:
        current_text: 当前文本
        target_after: 目标文本

    Returns:
        操作列表，每项为 (op, text)：
        - ('equal', '...') 不变的文本
        - ('delete', '...') 要删除的文本
        - ('insert', '...') 要插入的文本
    """
    # 分词
    current_tokens = tokenize(current_text)
    target_tokens = tokenize(target_after)

    # 使用 SequenceMatcher 计算差异
    matcher = difflib.SequenceMatcher(None, current_tokens, target_tokens)

    operations = []

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == 'equal':
            text = ''.join(current_tokens[i1:i2])
            operations.append(('equal', text))

        elif op == 'delete':
            text = ''.join(current_tokens[i1:i2])
            operations.append(('delete', text))

        elif op == 'insert':
            text = ''.join(target_tokens[j1:j2])
            operations.append(('insert', text))

        elif op == 'replace':
            # replace = delete + insert
            del_text = ''.join(current_tokens[i1:i2])
            ins_text = ''.join(target_tokens[j1:j2])
            operations.append(('delete', del_text))
            operations.append(('insert', ins_text))

    return operations


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


# ========== V2 新类：基于 Diff 的修订应用器 ==========

class DiffBasedApplier(RevisionApplier):
    """
    基于 Diff 的修订应用器（V2 新实现）

    使用词级别 diff 比较 current_text 和 target_after，
    自动生成多个 track changes。
    """

    def apply_diff_to_row(
        self,
        row_index: int,
        column_index: int,
        current_text: str,
        target_after: str,
        date: str = None
    ) -> bool:
        """
        将 diff 结果应用到指定行的指定列

        Args:
            row_index: 行索引
            column_index: 列索引
            current_text: 当前文本
            target_after: 目标文本
            date: 修订日期时间（默认为当前时间）

        Returns:
            是否成功应用
        """
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        # 如果文本相同，无需修订
        if current_text == target_after:
            print(f"行 {row_index}: 文本无变化，跳过")
            return True

        try:
            # 计算 diff
            operations = word_diff(current_text, target_after)

            # 检查是否有实际变化
            has_changes = any(op[0] in ('delete', 'insert') for op in operations)
            if not has_changes:
                print(f"行 {row_index}: diff 无变化，跳过")
                return True

            # 在目标列中找到单元格
            node = self._find_cell_content_node(row_index, column_index)
            if not node:
                print(f"警告: 行 {row_index}, 列 {column_index} 未找到内容节点")
                return False

            # 构建替换 XML
            replacement_xml = self._build_diff_xml(operations, date)

            # 应用替换
            self.doc["word/document.xml"].replace_node(node, replacement_xml)

            print(f"✓ 行 {row_index}: 应用了 {sum(1 for op in operations if op[0] in ('delete', 'insert'))} 处修订")
            return True

        except Exception as e:
            print(f"✗ 行 {row_index} 应用失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _find_cell_content_node(self, row_index: int, column_index: int):
        """找到指定单元格的内容节点"""
        try:
            # 这里简化处理：找到第一个包含文本的 w:r 节点
            # 实际应用中可能需要更精确的定位
            node = self.doc["word/document.xml"].get_node(
                tag="w:r",
                contains=""  # 匹配任意内容
            )
            return node
        except Exception:
            return None

    def _build_diff_xml(self, operations: List[Tuple[str, str]], date: str) -> str:
        """
        根据 diff 操作列表构建 XML

        Args:
            operations: [('equal', text), ('delete', text), ('insert', text), ...]
            date: 修订日期

        Returns:
            XML 字符串
        """
        parts = []

        for op, text in operations:
            if not text:
                continue

            # 处理空格
            space_attr = ' xml:space="preserve"' if text.startswith(' ') or text.endswith(' ') else ''

            if op == 'equal':
                # 普通文本
                parts.append(f'''<w:r>
      <w:t{space_attr}>{self._escape_xml(text)}</w:t>
    </w:r>''')

            elif op == 'delete':
                # 删除标记
                del_id = str(self.next_revision_id)
                self.next_revision_id += 1

                parts.append(f'''<w:del w:id="{del_id}" w:author="Claude" w:date="{date}" w16du:dateUtc="{date}">
      <w:r w:rsidDel="{self.doc.rsid}">
        <w:delText{space_attr}>{self._escape_xml(text)}</w:delText>
      </w:r>
    </w:del>''')

            elif op == 'insert':
                # 插入标记
                ins_id = str(self.next_revision_id)
                self.next_revision_id += 1

                parts.append(f'''<w:ins w:id="{ins_id}" w:author="Claude" w:date="{date}" w16du:dateUtc="{date}">
      <w:r>
        <w:t{space_attr}>{self._escape_xml(text)}</w:t>
      </w:r>
    </w:ins>''')

        return '\n'.join(parts)

    def _escape_xml(self, text: str) -> str:
        """转义 XML 特殊字符"""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))

    def apply_mapped_revisions(
        self,
        mapped_results: List[Dict],
        column_index: int = 1
    ) -> int:
        """
        批量应用映射结果

        Args:
            mapped_results: mapper 返回的结果列表，每项含
                           {row_index, target_current, target_after, ...}
            column_index: 目标列索引

        Returns:
            成功应用的修订数
        """
        success_count = 0

        for result in mapped_results:
            row_idx = result.get('row_index')
            current = result.get('target_current', '')
            after = result.get('target_after', '')

            if not after:
                print(f"行 {row_idx}: target_after 为空，跳过")
                continue

            success = self.apply_diff_to_row(
                row_index=row_idx,
                column_index=column_index,
                current_text=current,
                target_after=after
            )

            if success:
                success_count += 1

        return success_count


# ========== V1 旧类（保留以便对比） ==========

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
    print("=" * 50)
    print("V2 新功能：词级别 Diff 演示")
    print("=" * 50)

    # 测试英文 diff
    current_en = "AI is changing our life."
    target_en = "AI has changed our life."

    print(f"\n英文 Diff:")
    print(f"  当前: {current_en}")
    print(f"  目标: {target_en}")
    print(f"  操作:")
    for op, text in word_diff(current_en, target_en):
        print(f"    {op}: '{text}'")

    # 测试中文 diff
    current_zh = "AI正在改变我们的生活。"
    target_zh = "AI改变了我们的生活。"

    print(f"\n中文 Diff:")
    print(f"  当前: {current_zh}")
    print(f"  目标: {target_zh}")
    print(f"  操作:")
    for op, text in word_diff(current_zh, target_zh):
        print(f"    {op}: '{text}'")

    # 测试多处修订
    current_multi = "The quick brown fox jumps over the lazy dog."
    target_multi = "A fast brown cat leaps over the sleepy dog."

    print(f"\n多处修订 Diff:")
    print(f"  当前: {current_multi}")
    print(f"  目标: {target_multi}")
    print(f"  操作:")
    for op, text in word_diff(current_multi, target_multi):
        print(f"    {op}: '{text}'")

    print("\n" + "=" * 50)
    print("V1 旧方法（需要 Document Library）")
    print("=" * 50)

    try:
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
    except Exception as e:
        print(f"V1 方法需要 Document Library: {e}")
