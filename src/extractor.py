"""
修订提取器 - 从Word文档中提取track changes

核心功能：
1. 解析文档XML结构
2. 识别<w:del>和<w:ins>标签
3. 提取修订前后的完整文本
4. 组织成结构化数据

V2 重塑说明：
- 新增 extract_text_versions_from_column() 方法
- 输出 before_text（修订前）和 after_text（修订后）
- 删除 deletion/insertion 配对逻辑，让 LLM 理解语义差异
"""

import re
from typing import List, Dict, Tuple
from defusedxml import minidom


class RevisionExtractor:
    """从Word文档中提取track changes信息"""

    def __init__(self, unpacked_dir: str):
        """
        初始化提取器

        Args:
            unpacked_dir: 解包后的文档目录路径
        """
        self.unpacked_dir = unpacked_dir
        self.document_xml_path = f"{unpacked_dir}/word/document.xml"
        
    def extract_revisions_from_column(self, column_index: int = 0) -> List[Dict]:
        """
        从指定列提取所有修订
        
        Args:
            column_index: 列索引 (0=左列, 1=右列)
            
        Returns:
            修订列表，每个修订包含：
            {
                'row_index': 行索引,
                'deletion': 删除的文本,
                'insertion': 插入的文本,
                'context_before': 修订前的上下文,
                'context_after': 修订后的上下文,
                'del_id': 删除标记ID,
                'ins_id': 插入标记ID,
                'line_number': XML中的行号范围
            }
        """
        # 读取document.xml
        with open(self.document_xml_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析XML
        dom = minidom.parseString(content)
        
        # 找到所有表格行
        rows = dom.getElementsByTagName('w:tr')
        
        revisions = []
        
        for row_idx, row in enumerate(rows):
            # 获取指定列的单元格
            cells = row.getElementsByTagName('w:tc')
            if column_index >= len(cells):
                continue
                
            cell = cells[column_index]
            
            # 在这个单元格中查找所有修订对
            cell_revisions = self._extract_revisions_from_cell(
                cell, row_idx, content
            )
            revisions.extend(cell_revisions)
        
        return revisions

    # ========== V2 新方法：提取修订前后完整文本 ==========

    def extract_text_versions_from_column(self, column_index: int = 0) -> List[Dict]:
        """
        从指定列提取每行的修订前后文本（V2 新方法）

        Args:
            column_index: 列索引 (0=左列, 1=右列)

        Returns:
            文本版本列表，每项包含：
            {
                'row_index': 行索引,
                'before_text': 修订前完整文本（正常文本 + 删除文本）,
                'after_text': 修订后完整文本（正常文本 + 插入文本）,
                'has_revisions': 是否包含修订
            }
        """
        with open(self.document_xml_path, 'r', encoding='utf-8') as f:
            content = f.read()

        dom = minidom.parseString(content)
        rows = dom.getElementsByTagName('w:tr')

        results = []

        for row_idx, row in enumerate(rows):
            cells = row.getElementsByTagName('w:tc')
            if column_index >= len(cells):
                continue

            cell = cells[column_index]
            before_text, after_text, has_revisions = self._extract_text_versions_from_cell(cell)

            results.append({
                'row_index': row_idx,
                'before_text': before_text,
                'after_text': after_text,
                'has_revisions': has_revisions,
            })

        return results

    def extract_clean_text_from_column(self, column_index: int = 0) -> List[Dict]:
        """
        从指定列提取纯净文本（用于目标语言列，假设无 track changes）

        Args:
            column_index: 列索引 (0=左列, 1=右列)

        Returns:
            文本列表，每项包含：
            {
                'row_index': 行索引,
                'current_text': 当前纯净文本
            }
        """
        with open(self.document_xml_path, 'r', encoding='utf-8') as f:
            content = f.read()

        dom = minidom.parseString(content)
        rows = dom.getElementsByTagName('w:tr')

        results = []

        for row_idx, row in enumerate(rows):
            cells = row.getElementsByTagName('w:tc')
            if column_index >= len(cells):
                continue

            cell = cells[column_index]
            current_text = self._extract_all_text_from_cell(cell)

            results.append({
                'row_index': row_idx,
                'current_text': current_text,
            })

        return results

    def _extract_text_versions_from_cell(self, cell) -> Tuple[str, str, bool]:
        """
        从单元格提取修订前后的完整文本

        遍历单元格内所有节点，按顺序收集：
        - <w:r> 普通文本 → before 和 after 都包含
        - <w:del> 删除文本 → 只在 before 中
        - <w:ins> 插入文本 → 只在 after 中

        Returns:
            (before_text, after_text, has_revisions)
        """
        before_parts = []
        after_parts = []
        has_revisions = False

        paragraphs = cell.getElementsByTagName('w:p')

        for para_idx, para in enumerate(paragraphs):
            # 添加段落分隔（除了第一个段落）
            if para_idx > 0:
                before_parts.append('\n')
                after_parts.append('\n')

            # 遍历段落的直接子节点
            for child in para.childNodes:
                if child.nodeType != child.ELEMENT_NODE:
                    continue

                tag = child.tagName

                if tag == 'w:r':
                    # 普通文本节点 → 两个版本都包含
                    text = self._extract_text_from_node(child)
                    before_parts.append(text)
                    after_parts.append(text)

                elif tag == 'w:del':
                    # 删除节点 → 只在 before 中
                    text = self._extract_text_from_node(child)
                    before_parts.append(text)
                    has_revisions = True

                elif tag == 'w:ins':
                    # 插入节点 → 只在 after 中
                    text = self._extract_text_from_node(child)
                    after_parts.append(text)
                    has_revisions = True

        before_text = ''.join(before_parts)
        after_text = ''.join(after_parts)

        return before_text, after_text, has_revisions

    def _extract_all_text_from_cell(self, cell) -> str:
        """
        从单元格提取所有可见文本（用于纯净文本列）

        对于无 track changes 的列，直接提取所有 <w:t> 文本
        """
        text_parts = []
        paragraphs = cell.getElementsByTagName('w:p')

        for para_idx, para in enumerate(paragraphs):
            if para_idx > 0:
                text_parts.append('\n')

            # 获取所有 w:t 节点
            text_nodes = para.getElementsByTagName('w:t')
            for t in text_nodes:
                if t.firstChild:
                    text_parts.append(t.firstChild.nodeValue)

        return ''.join(text_parts)

    # ========== V1 旧方法（保留以便对比和测试） ==========

    def _extract_revisions_from_cell(
        self, cell, row_idx: int, full_content: str
    ) -> List[Dict]:
        """从单个单元格提取修订"""
        revisions = []
        
        # 获取单元格内的段落
        paragraphs = cell.getElementsByTagName('w:p')
        
        for para in paragraphs:
            # 查找删除和插入标记
            deletions = para.getElementsByTagName('w:del')
            insertions = para.getElementsByTagName('w:ins')
            
            # 通常删除和插入是成对出现的
            # 我们需要找到配对关系
            paired_revisions = self._pair_deletions_insertions(
                deletions, insertions, para
            )
            
            for pair in paired_revisions:
                revision = {
                    'row_index': row_idx,
                    'deletion': pair['deletion_text'],
                    'insertion': pair['insertion_text'],
                    'context_before': pair['context_before'],
                    'context_after': pair['context_after'],
                    'del_id': pair.get('del_id'),
                    'ins_id': pair.get('ins_id'),
                }
                revisions.append(revision)
        
        return revisions
    
    def _pair_deletions_insertions(
        self, deletions, insertions, paragraph
    ) -> List[Dict]:
        """
        配对删除和插入标记
        
        策略：在同一段落中，删除后紧跟的插入通常是配对的
        """
        pairs = []
        
        # 获取段落中所有子节点
        children = paragraph.childNodes
        
        i = 0
        while i < len(children):
            node = children[i]
            
            # 检查是否是删除节点
            if node.nodeType == node.ELEMENT_NODE and node.tagName == 'w:del':
                deletion_text = self._extract_text_from_node(node)
                del_id = node.getAttribute('w:id')
                
                # 提取前文
                context_before = self._get_context_before(children[:i])
                
                # 查找后续的插入节点
                insertion_text = ""
                ins_id = None
                context_after = ""
                
                if i + 1 < len(children):
                    next_node = children[i + 1]
                    if (next_node.nodeType == node.ELEMENT_NODE and 
                        next_node.tagName == 'w:ins'):
                        insertion_text = self._extract_text_from_node(next_node)
                        ins_id = next_node.getAttribute('w:id')
                        
                        # 提取后文
                        context_after = self._get_context_after(children[i+2:])
                        i += 1  # 跳过已处理的插入节点
                
                pairs.append({
                    'deletion_text': deletion_text,
                    'insertion_text': insertion_text,
                    'context_before': context_before,
                    'context_after': context_after,
                    'del_id': del_id,
                    'ins_id': ins_id,
                })
            
            i += 1
        
        return pairs
    
    def _extract_text_from_node(self, node) -> str:
        """从XML节点中提取纯文本"""
        text_nodes = node.getElementsByTagName('w:t')
        del_text_nodes = node.getElementsByTagName('w:delText')
        
        text_parts = []
        for t in text_nodes:
            if t.firstChild:
                text_parts.append(t.firstChild.nodeValue)
        
        for dt in del_text_nodes:
            if dt.firstChild:
                text_parts.append(dt.firstChild.nodeValue)
        
        return ''.join(text_parts)
    
    def _get_context_before(self, nodes, max_chars: int = 30) -> str:
        """获取修订前的上下文"""
        text_parts = []
        
        for node in reversed(nodes):
            if node.nodeType == node.ELEMENT_NODE and node.tagName == 'w:r':
                text = self._extract_text_from_node(node)
                text_parts.insert(0, text)
                
                if len(''.join(text_parts)) > max_chars:
                    break
        
        context = ''.join(text_parts)
        if len(context) > max_chars:
            context = '...' + context[-max_chars:]
        
        return context
    
    def _get_context_after(self, nodes, max_chars: int = 30) -> str:
        """获取修订后的上下文"""
        text_parts = []
        
        for node in nodes:
            if node.nodeType == node.ELEMENT_NODE and node.tagName == 'w:r':
                text = self._extract_text_from_node(node)
                text_parts.append(text)
                
                if len(''.join(text_parts)) > max_chars:
                    break
        
        context = ''.join(text_parts)
        if len(context) > max_chars:
            context = context[:max_chars] + '...'
        
        return context


def decode_html_entities(text: str) -> str:
    """
    将HTML实体解码为Unicode字符
    
    例如: &#20320;&#22909; -> 你好
    """
    import html
    
    # 处理数字实体
    def decode_numeric(match):
        num = int(match.group(1))
        return chr(num)
    
    text = re.sub(r'&#(\d+);', decode_numeric, text)
    
    # 处理命名实体
    text = html.unescape(text)
    
    return text


# 使用示例
if __name__ == "__main__":
    extractor = RevisionExtractor("unpacked")

    print("=" * 50)
    print("V2 新方法：提取修订前后完整文本")
    print("=" * 50)

    # 从源语言列（中文列）提取修订前后文本
    source_texts = extractor.extract_text_versions_from_column(column_index=0)

    for item in source_texts:
        if item['has_revisions']:
            print(f"\n行 {item['row_index']}:")
            print(f"  修订前: {decode_html_entities(item['before_text'])}")
            print(f"  修订后: {decode_html_entities(item['after_text'])}")

    # 从目标语言列（英文列）提取纯净文本
    print("\n" + "=" * 50)
    print("目标语言列纯净文本")
    print("=" * 50)

    target_texts = extractor.extract_clean_text_from_column(column_index=1)

    for item in target_texts:
        print(f"\n行 {item['row_index']}:")
        print(f"  当前文本: {decode_html_entities(item['current_text'])}")

    print("\n" + "=" * 50)
    print("V1 旧方法（保留以便对比）")
    print("=" * 50)

    # V1 旧方法
    chinese_revisions = extractor.extract_revisions_from_column(column_index=0)

    print(f"找到 {len(chinese_revisions)} 个修订")

    for i, rev in enumerate(chinese_revisions, 1):
        print(f"\n修订 {i}:")
        print(f"  行: {rev['row_index']}")
        print(f"  删除: {decode_html_entities(rev['deletion'])}")
        print(f"  插入: {decode_html_entities(rev['insertion'])}")
        print(f"  前文: {decode_html_entities(rev['context_before'])}")
        print(f"  后文: {decode_html_entities(rev['context_after'])}")
