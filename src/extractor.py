"""
修订提取器 - 从Word文档中提取track changes

================================================================================
文件结构（按调用关系）
================================================================================

RevisionExtractor 类
├── __init__(unpacked_dir)                  # 初始化，设置文档路径
└── extract_row_pairs()                     # 主入口：打包提取有修订的行
    ├── _has_revisions()                    # 快速检查单元格是否有修订
    ├── _extract_text_versions_from_cell()  # 提取源语言修订前后文本
    │   └── _extract_text_from_node()       # 从节点提取纯文本
    └── _extract_all_text_from_cell()       # 提取目标语言纯净文本

独立函数
└── decode_html_entities()                  # HTML实体 → Unicode字符，用于显示提取的文本

使用示例 (if __name__ == "__main__")
└── 演示 extract_row_pairs() 的调用方式和输出格式

================================================================================
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

    def extract_row_pairs(
        self, source_column: int = 0, target_column: int = 1
    ) -> List[Dict]:
        """
        打包提取有修订的行的源语言和目标语言文本

        Args:
            source_column: 源语言列索引 (默认 0 = 左列)
            target_column: 目标语言列索引 (默认 1 = 右列)

        Returns:
            行数据列表（只包含有修订的行），每项包含：
            {
                'row_index': 行索引,
                'source_before': 源语言修订前文本,
                'source_after': 源语言修订后文本,
                'target_current': 目标语言当前文本
            }
        """
        with open(self.document_xml_path, 'r', encoding='utf-8') as f:
            content = f.read()

        dom = minidom.parseString(content)
        rows = dom.getElementsByTagName('w:tr')

        results = []

        for row_idx, row in enumerate(rows):
            cells = row.getElementsByTagName('w:tc')

            # 确保两列都存在
            if source_column >= len(cells) or target_column >= len(cells):
                continue

            source_cell = cells[source_column]

            # 快速检查：跳过无修订的行
            if not self._has_revisions(source_cell):
                continue

            # 有修订才提取文本
            source_before, source_after = self._extract_text_versions_from_cell(source_cell)
            target_current = self._extract_all_text_from_cell(cells[target_column])

            results.append({
                'row_index': row_idx,
                'source_before': source_before,
                'source_after': source_after,
                'target_current': target_current,
            })

        return results

    def _has_revisions(self, cell) -> bool:
        """快速检查单元格是否包含修订"""
        return (len(cell.getElementsByTagName('w:del')) > 0 or
                len(cell.getElementsByTagName('w:ins')) > 0)

    def _extract_text_versions_from_cell(self, cell) -> Tuple[str, str]:
        """
        从单元格提取修订前后的完整文本

        遍历单元格内所有节点，按顺序收集：
        - <w:r> 普通文本 → before 和 after 都包含
        - <w:del> 删除文本 → 只在 before 中
        - <w:ins> 插入文本 → 只在 after 中

        Returns:
            (before_text, after_text)
        """
        before_parts = []
        after_parts = []

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

                elif tag == 'w:ins':
                    # 插入节点 → 只在 after 中
                    text = self._extract_text_from_node(child)
                    after_parts.append(text)

        return ''.join(before_parts), ''.join(after_parts)

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
    print("打包提取：只提取有修订的行")
    print("=" * 50)

    # 打包提取有修订的行
    row_pairs = extractor.extract_row_pairs(source_column=0, target_column=1)

    print(f"\n共找到 {len(row_pairs)} 个有修订的行")

    for row in row_pairs:
        print(f"\n行 {row['row_index']}:")
        print(f"  源语言修订前: {decode_html_entities(row['source_before'])}")
        print(f"  源语言修订后: {decode_html_entities(row['source_after'])}")
        print(f"  目标语言当前: {decode_html_entities(row['target_current'])}")
