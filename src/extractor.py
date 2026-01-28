"""
================================================================================
Revision Extractor - Extract Track Changes from Word Documents
================================================================================

Architecture
------------
RevisionExtractor
    |
    +-- extract_row_pairs()          Main entry point
    |       |
    |       +-- _has_revisions()     Quick check for <w:del>/<w:ins>
    |       |
    |       +-- _extract_text_versions_from_cell()
    |       |       |
    |       |       +-- _extract_text_from_node()
    |       |
    |       +-- _extract_all_text_from_cell()

Data Flow
---------
Input:  document.xml (OOXML format)
Output: List[Dict] with keys:
        - row_index: int
        - source_before: str (text before revision)
        - source_after: str (text after revision)
        - target_current: str (current target text)

OOXML Structure
---------------
<w:tr>                      # Table row
  <w:tc>                    # Table cell (column 0 = source)
    <w:p>                   # Paragraph
      <w:r>                 # Normal text run
        <w:t>text</w:t>
      </w:r>
      <w:del>               # Deletion (track change)
        <w:r>
          <w:delText>deleted</w:delText>
        </w:r>
      </w:del>
      <w:ins>               # Insertion (track change)
        <w:r>
          <w:t>inserted</w:t>
        </w:r>
      </w:ins>
    </w:p>
  </w:tc>
  <w:tc>                    # Table cell (column 1 = target)
    ...
  </w:tc>
</w:tr>

================================================================================
"""

import re
from typing import List, Dict, Tuple
from defusedxml import minidom


class RevisionExtractor:
    """
    Extract track changes from Word document XML.

    Parses the OOXML structure and extracts:
    - Before text: Original text (normal runs + deletions)
    - After text: Revised text (normal runs + insertions)
    """

    def __init__(self, unpacked_dir: str):
        """
        Initialize the extractor.

        Args:
            unpacked_dir: Path to unpacked document directory
        """
        self.unpacked_dir = unpacked_dir
        self.document_xml_path = f"{unpacked_dir}/word/document.xml"

    def extract_row_pairs(
        self, source_column: int = 0, target_column: int = 1
    ) -> List[Dict]:
        """
        Extract row pairs with revisions.

        Only returns rows that have track changes in the source column.

        Args:
            source_column: Source language column index (default: 0 = left)
            target_column: Target language column index (default: 1 = right)

        Returns:
            List of dicts with:
            - row_index: Row number in document
            - source_before: Source text before revision
            - source_after: Source text after revision
            - target_current: Current target text
        """
        # Parse document
        with open(self.document_xml_path, "r", encoding="utf-8") as f:
            content = f.read()

        dom = minidom.parseString(content)
        rows = dom.getElementsByTagName("w:tr")

        results = []

        for row_idx, row in enumerate(rows):
            cells = row.getElementsByTagName("w:tc")

            # Check both columns exist
            if source_column >= len(cells) or target_column >= len(cells):
                continue

            source_cell = cells[source_column]

            # Skip rows without revisions
            if not self._has_revisions(source_cell):
                continue

            # Extract texts
            source_before, source_after = self._extract_text_versions_from_cell(source_cell)
            target_current = self._extract_all_text_from_cell(cells[target_column])

            results.append({
                "row_index": row_idx,
                "source_before": source_before,
                "source_after": source_after,
                "target_current": target_current,
            })

        return results

    def _has_revisions(self, cell) -> bool:
        """
        Quick check if cell contains track changes.

        Args:
            cell: w:tc element

        Returns:
            True if cell contains <w:del> or <w:ins>
        """
        return (
            len(cell.getElementsByTagName("w:del")) > 0 or
            len(cell.getElementsByTagName("w:ins")) > 0
        )

    def _extract_text_versions_from_cell(self, cell) -> Tuple[str, str]:
        """
        Extract before and after text versions from a cell.

        Traverses all nodes in order:
        - <w:r>: Normal text -> both before and after
        - <w:del>: Deleted text -> before only
        - <w:ins>: Inserted text -> after only

        Args:
            cell: w:tc element

        Returns:
            (before_text, after_text)
        """
        before_parts = []
        after_parts = []

        paragraphs = cell.getElementsByTagName("w:p")

        for para_idx, para in enumerate(paragraphs):
            # Add paragraph separator (except first)
            if para_idx > 0:
                before_parts.append("\n")
                after_parts.append("\n")

            # Process direct child nodes
            for child in para.childNodes:
                if child.nodeType != child.ELEMENT_NODE:
                    continue

                tag = child.tagName

                if tag == "w:r":
                    # Normal text -> both versions
                    text = self._extract_text_from_node(child)
                    before_parts.append(text)
                    after_parts.append(text)

                elif tag == "w:del":
                    # Deletion -> before only
                    text = self._extract_text_from_node(child)
                    before_parts.append(text)

                elif tag == "w:ins":
                    # Insertion -> after only
                    text = self._extract_text_from_node(child)
                    after_parts.append(text)

        return "".join(before_parts), "".join(after_parts)

    def _extract_all_text_from_cell(self, cell) -> str:
        """
        Extract all visible text from a cell.

        Used for target column which has no track changes.

        Args:
            cell: w:tc element

        Returns:
            All text content
        """
        text_parts = []
        paragraphs = cell.getElementsByTagName("w:p")

        for para_idx, para in enumerate(paragraphs):
            if para_idx > 0:
                text_parts.append("\n")

            # Get all w:t nodes
            text_nodes = para.getElementsByTagName("w:t")
            for t in text_nodes:
                if t.firstChild:
                    text_parts.append(t.firstChild.nodeValue)

        return "".join(text_parts)

    def _extract_text_from_node(self, node) -> str:
        """
        Extract text from an XML node.

        Handles both <w:t> (normal text) and <w:delText> (deleted text).

        Args:
            node: XML element

        Returns:
            Text content
        """
        text_parts = []

        # Normal text
        for t in node.getElementsByTagName("w:t"):
            if t.firstChild:
                text_parts.append(t.firstChild.nodeValue)

        # Deleted text
        for dt in node.getElementsByTagName("w:delText"):
            if dt.firstChild:
                text_parts.append(dt.firstChild.nodeValue)

        return "".join(text_parts)


def decode_html_entities(text: str) -> str:
    """
    Decode HTML entities to Unicode characters.

    Word XML sometimes uses numeric entities for non-ASCII:
    &#20320;&#22909; -> Chinese characters

    Args:
        text: Text possibly containing HTML entities

    Returns:
        Decoded text
    """
    import html

    # Decode numeric entities
    def decode_numeric(match):
        num = int(match.group(1))
        return chr(num)

    text = re.sub(r"&#(\d+);", decode_numeric, text)

    # Decode named entities
    text = html.unescape(text)

    return text


# ================================================================================
# Usage Example
# ================================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python extractor.py <unpacked_dir>")
        print("Example: python extractor.py ./test_work/unpacked")
        sys.exit(1)

    unpacked_dir = sys.argv[1]
    extractor = RevisionExtractor(unpacked_dir)

    print("=" * 50)
    print("Extracting rows with revisions...")
    print("=" * 50)

    row_pairs = extractor.extract_row_pairs(source_column=0, target_column=1)

    print(f"\nFound {len(row_pairs)} rows with revisions")

    for row in row_pairs:
        print(f"\nRow {row['row_index']}:")
        print(f"  Before: {decode_html_entities(row['source_before'])}")
        print(f"  After:  {decode_html_entities(row['source_after'])}")
        print(f"  Target: {decode_html_entities(row['target_current'])}")
