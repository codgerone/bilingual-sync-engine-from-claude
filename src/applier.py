"""
================================================================================
Revision Applier - Apply Track Changes to Word Documents
================================================================================

Architecture
------------
DiffBasedApplier
    |
    +-- apply_mapped_revisions()     Main entry: process all results
    |       |
    |       +-- apply_diff_to_row()  Process single row
    |               |
    |               +-- word_diff()  Calculate word-level diff
    |               |
    |               +-- _build_diff_xml()  Generate OOXML
    |
    +-- save()                       Write changes to document.xml

Helper Functions
    |
    +-- word_diff()      Compare two texts, return operations
    +-- tokenize()       Split text into words/tokens
    +-- detect_language() Detect if text is Chinese or English

Data Flow
---------
Input (from mapper):
    {
        'row_index': int,
        'target_current': str,
        'target_after': str,
        ...
    }

Output:
    Modified document.xml with <w:del> and <w:ins> elements

OOXML Track Changes Format
--------------------------
<w:del w:id="0" w:author="Claude" w:date="2026-01-01T00:00:00Z">
    <w:r w:rsidDel="...">
        <w:delText>deleted text</w:delText>
    </w:r>
</w:del>
<w:ins w:id="1" w:author="Claude" w:date="2026-01-01T00:00:00Z">
    <w:r>
        <w:t>inserted text</w:t>
    </w:r>
</w:ins>

================================================================================
"""

import sys
import os
import re
import difflib
from datetime import datetime
from typing import Dict, List, Tuple

# Optional: jieba for Chinese tokenization
try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False

# Document Library for OOXML operations (only available in Docker/Linux runtime)
DOCX_SKILL_PATH = "/mnt/skills/public/docx"
if DOCX_SKILL_PATH not in sys.path:
    sys.path.insert(0, DOCX_SKILL_PATH)

try:
    from scripts.document import Document
    DOCUMENT_LIB_AVAILABLE = True
except ImportError:
    Document = None
    DOCUMENT_LIB_AVAILABLE = False


# ================================================================================
# Tokenization and Diff Functions
# ================================================================================

def detect_language(text: str) -> str:
    """
    Detect primary language of text.

    Args:
        text: Input text

    Returns:
        'zh' for Chinese, 'en' for English/other
    """
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    total_chars = len(text.replace(" ", ""))

    if total_chars == 0:
        return "en"

    return "zh" if chinese_chars / total_chars > 0.3 else "en"


def tokenize(text: str) -> List[str]:
    """
    Tokenize text for diff comparison.

    - Chinese: Use jieba segmentation (or character-level fallback)
    - English: Split by whitespace, preserve punctuation

    Args:
        text: Input text

    Returns:
        List of tokens
    """
    lang = detect_language(text)

    if lang == "zh":
        if JIEBA_AVAILABLE:
            tokens = list(jieba.cut(text))
            return [t for t in tokens if t]
        else:
            return list(text)
    else:
        # English: split by whitespace, keep separators
        tokens = re.split(r"(\s+)", text)
        return [t for t in tokens if t]


def word_diff(current_text: str, target_after: str) -> List[Tuple[str, str]]:
    """
    Calculate word-level diff between two texts.

    Args:
        current_text: Original text
        target_after: Target text

    Returns:
        List of (operation, text) tuples:
        - ('equal', 'unchanged text')
        - ('delete', 'removed text')
        - ('insert', 'added text')
    """
    current_tokens = tokenize(current_text)
    target_tokens = tokenize(target_after)

    matcher = difflib.SequenceMatcher(None, current_tokens, target_tokens)
    operations = []

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            text = "".join(current_tokens[i1:i2])
            operations.append(("equal", text))

        elif op == "delete":
            text = "".join(current_tokens[i1:i2])
            operations.append(("delete", text))

        elif op == "insert":
            text = "".join(target_tokens[j1:j2])
            operations.append(("insert", text))

        elif op == "replace":
            # Replace = delete + insert
            del_text = "".join(current_tokens[i1:i2])
            ins_text = "".join(target_tokens[j1:j2])
            operations.append(("delete", del_text))
            operations.append(("insert", ins_text))

    return operations


# ================================================================================
# Diff-Based Applier
# ================================================================================

class DiffBasedApplier:
    """
    Apply revisions using word-level diff.

    Compares target_current with target_after and generates
    track changes XML for the differences.
    """

    def __init__(self, unpacked_dir: str, author: str = "Claude"):
        """
        Initialize the applier.

        Args:
            unpacked_dir: Path to unpacked document directory
            author: Author name for track changes
        """
        self.doc = Document(unpacked_dir, author=author)
        self.author = author
        self.next_revision_id = self._get_next_revision_id()

    def _get_next_revision_id(self) -> int:
        """Find the next available revision ID in the document."""
        doc_path = f"{self.doc.unpacked_path}/word/document.xml"

        with open(doc_path, "r", encoding="utf-8") as f:
            content = f.read()

        ids = re.findall(r'w:id="(\d+)"', content)

        if ids:
            return max(int(id_val) for id_val in ids) + 1
        return 0

    def apply_mapped_revisions(
        self,
        mapped_results: List[Dict],
        column_index: int = 1
    ) -> int:
        """
        Apply all mapped revisions to the document.

        Args:
            mapped_results: List from mapper with:
                - row_index: int
                - target_current: str
                - target_after: str
            column_index: Target column index

        Returns:
            Number of successfully applied revisions
        """
        success_count = 0

        for result in mapped_results:
            row_idx = result.get("row_index")
            current = result.get("target_current", "")
            after = result.get("target_after", "")

            if not after:
                print(f"Row {row_idx}: target_after is empty, skipping")
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

    def apply_diff_to_row(
        self,
        row_index: int,
        column_index: int,
        current_text: str,
        target_after: str,
        date: str = None
    ) -> bool:
        """
        Apply diff to a specific row.

        Args:
            row_index: Row index in document
            column_index: Column index
            current_text: Current text in cell
            target_after: Target text after revision
            date: Revision timestamp (defaults to now)

        Returns:
            True if successful
        """
        if date is None:
            date = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        # Skip if texts are identical
        if current_text == target_after:
            print(f"Row {row_index}: No changes needed")
            return True

        try:
            # Calculate diff
            operations = word_diff(current_text, target_after)

            # Check for actual changes
            has_changes = any(op[0] in ("delete", "insert") for op in operations)
            if not has_changes:
                print(f"Row {row_index}: Diff shows no changes")
                return True

            # Find the cell content node
            node = self._find_cell_content_node(row_index, column_index)
            if not node:
                print(f"Row {row_index}: Could not find content node")
                return False

            # Build replacement XML
            replacement_xml = self._build_diff_xml(operations, date)

            # Apply replacement
            self.doc["word/document.xml"].replace_node(node, replacement_xml)

            change_count = sum(1 for op in operations if op[0] in ("delete", "insert"))
            print(f"Row {row_index}: Applied {change_count} changes")
            return True

        except Exception as e:
            print(f"Row {row_index}: Failed - {e}")
            return False

    def _find_cell_content_node(self, row_index: int, column_index: int):
        """Find the content node for a specific cell."""
        try:
            node = self.doc["word/document.xml"].get_node(
                tag="w:r",
                contains=""
            )
            return node
        except Exception:
            return None

    def _build_diff_xml(self, operations: List[Tuple[str, str]], date: str) -> str:
        """
        Build OOXML from diff operations.

        Args:
            operations: List of (op, text) tuples
            date: Revision timestamp

        Returns:
            XML string with track changes
        """
        parts = []

        for op, text in operations:
            if not text:
                continue

            # Handle whitespace preservation
            space_attr = ""
            if text.startswith(" ") or text.endswith(" "):
                space_attr = ' xml:space="preserve"'

            escaped_text = self._escape_xml(text)

            if op == "equal":
                parts.append(
                    f'<w:r><w:t{space_attr}>{escaped_text}</w:t></w:r>'
                )

            elif op == "delete":
                del_id = str(self.next_revision_id)
                self.next_revision_id += 1

                parts.append(
                    f'<w:del w:id="{del_id}" w:author="{self.author}" '
                    f'w:date="{date}" w16du:dateUtc="{date}">'
                    f'<w:r w:rsidDel="{self.doc.rsid}">'
                    f'<w:delText{space_attr}>{escaped_text}</w:delText>'
                    f'</w:r></w:del>'
                )

            elif op == "insert":
                ins_id = str(self.next_revision_id)
                self.next_revision_id += 1

                parts.append(
                    f'<w:ins w:id="{ins_id}" w:author="{self.author}" '
                    f'w:date="{date}" w16du:dateUtc="{date}">'
                    f'<w:r><w:t{space_attr}>{escaped_text}</w:t></w:r>'
                    f'</w:ins>'
                )

        return "".join(parts)

    def _escape_xml(self, text: str) -> str:
        """Escape XML special characters."""
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def save(self, output_dir: str = None):
        """
        Save the document.

        Args:
            output_dir: Optional output directory (defaults to original location)
        """
        if output_dir:
            self.doc.save(output_dir)
        else:
            self.doc.save()


# ================================================================================
# Usage Example
# ================================================================================

if __name__ == "__main__":
    print("=" * 50)
    print("Word-Level Diff Demo")
    print("=" * 50)

    # English example
    current_en = "AI is changing our life."
    target_en = "AI has changed our life."

    print(f"\nEnglish Diff:")
    print(f"  Current: {current_en}")
    print(f"  Target:  {target_en}")
    print(f"  Operations:")
    for op, text in word_diff(current_en, target_en):
        print(f"    {op}: '{text}'")

    # Chinese example
    current_zh = "AI正在改变我们的生活。"
    target_zh = "AI改变了我们的生活。"

    print(f"\nChinese Diff:")
    print(f"  Current: {current_zh}")
    print(f"  Target:  {target_zh}")
    print(f"  Operations:")
    for op, text in word_diff(current_zh, target_zh):
        print(f"    {op}: '{text}'")

    # Multiple changes example
    current = "The quick brown fox jumps over the lazy dog."
    target = "A fast brown cat leaps over the sleepy dog."

    print(f"\nMultiple Changes:")
    print(f"  Current: {current}")
    print(f"  Target:  {target}")
    print(f"  Operations:")
    for op, text in word_diff(current, target):
        print(f"    {op}: '{text}'")
