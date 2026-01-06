# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Bilingual Word Document Track Changes Synchronization Engine** that automatically syncs track changes (revisions) from one language column to another in bilingual Word documents. It's designed for legal documents where changes in one language need to be accurately reflected in the translation.

**Core workflow**: Extract track changes from source column → Use LLM to map revisions to target language → Apply track changes to target column

## Essential Commands

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Set API key
export ANTHROPIC_API_KEY='your-key-here'  # Linux/Mac
set ANTHROPIC_API_KEY=your-key-here  # Windows
```

### Running the Engine

**Basic usage (as library)**:
```bash
python -m src.engine input.docx -o output.docx
```

**With custom parameters**:
```bash
python -m src.engine input.docx \
  --source-column 0 \
  --target-column 1 \
  --source-lang "中文" \
  --target-lang "英文" \
  --author "Claude"
```

**Run examples**:
```bash
python examples/example_usage.py
```

### Development Commands
```bash
# No build process - pure Python project

# Manual testing with specific document
python -c "from src.engine import BilingualSyncEngine; BilingualSyncEngine('test.docx').sync()"

# Debug mode (view extraction details)
python src/extractor.py  # Run extractor standalone
python src/mapper.py     # Run mapper standalone
python src/applier.py    # Run applier standalone
```

## Architecture Overview

### Three-Module Pipeline

1. **RevisionExtractor** (`src/extractor.py`)
   - Parses OOXML (Word's XML format) using defusedxml
   - Navigates table structure: `<w:tbl>` → `<w:tr>` → `<w:tc>`
   - Identifies track changes: `<w:del>` (deletions) and `<w:ins>` (insertions)
   - Pairs consecutive deletions/insertions as revisions
   - Extracts context (30 chars before/after) for LLM mapping

2. **RevisionMapper** (`src/mapper.py`)
   - Uses Anthropic Claude API (default: claude-sonnet-4-20250514)
   - Sends revision + context + target text to LLM
   - Returns JSON with target language deletion/insertion/confidence
   - Temperature set to 0.0 for deterministic output

3. **SmartRevisionApplier** (`src/applier.py`)
   - Uses Document Library from `/mnt/skills/public/docx` (docx skill dependency)
   - Finds deletion text in target column XML
   - Intelligently splits text into: before + deletion + insertion + after
   - Generates OOXML-compliant track change XML
   - Auto-manages revision IDs (finds max ID in document, increments from there)

### Main Engine (`src/engine.py`)
Orchestrates the pipeline:
1. Unpacks .docx (ZIP) to XML files
2. Initializes three modules
3. Extracts source revisions
4. Maps each revision via LLM
5. Applies to target column
6. Repacks to .docx
7. Verifies with pandoc (optional)

### Key Design Patterns

**Unpack/Pack workflow**:
- Word .docx files are ZIP archives containing XML
- Uses docx skill scripts: `/mnt/skills/public/docx/ooxml/scripts/unpack.py` and `pack.py`
- Working directory: `{docx_path}_work/unpacked/`

**XML manipulation**:
- Read: defusedxml minidom for safe parsing
- Write: Document Library (from docx skill) for OOXML compliance
- Critical: maintain proper element order and attributes for Word compatibility

**Revision ID management**:
- Each track change needs unique `w:id` attribute
- Engine scans existing IDs with regex `w:id="(\d+)"`
- New revisions use `max_id + 1`, `max_id + 2`, etc.

**Context-aware mapping**:
- Extractor provides 30-char context before/after each revision
- Helps LLM locate correct position in target language text
- LLM prompt emphasizes semantic equivalence, not literal translation

## Critical Implementation Details

### OOXML Track Changes Structure
```xml
<!-- Deletion -->
<w:del w:id="0" w:author="Claude" w:date="2026-01-01T14:10:00Z" w16du:dateUtc="...">
  <w:r w:rsidDel="B7D9F225">
    <w:delText>deleted text</w:delText>
  </w:r>
</w:del>

<!-- Insertion -->
<w:ins w:id="1" w:author="Claude" w:date="2026-01-01T14:10:00Z" w16du:dateUtc="...">
  <w:r>
    <w:t>inserted text</w:t>
  </w:r>
</w:ins>
```

**Required attributes**:
- `w:id`: unique numeric string
- `w:author`: revision author name
- `w:date`: ISO 8601 timestamp
- `w16du:dateUtc`: UTC timestamp (can match w:date)
- `w:rsidDel`, `w:rsidR`: RSID values (use doc.rsid from Document Library)

### HTML Entity Handling
Word XML often uses HTML entities for non-ASCII characters:
- `&#20320;&#22909;` → 你好
- Use `decode_html_entities()` function from extractor.py
- Apply to all extracted text before displaying or processing

### Document Library Dependency
This project requires the docx skill's Document Library:
- Path: `/mnt/skills/public/docx`
- Must be in PYTHONPATH (applier.py adds it)
- Provides: Document class, node manipulation, OOXML validation
- Used only in applier.py, not in extractor.py or mapper.py

## Configuration

### Language Presets (`src/config.py`)
```python
LANGUAGE_PRESETS = {
    "zh-en": {"source_lang": "中文", "target_lang": "英文", "source_column": 0, "target_column": 1},
    "en-zh": {"source_lang": "英文", "target_lang": "中文", "source_column": 1, "target_column": 0},
    # ... more presets
}
```

### Key Config Constants
- `ANTHROPIC_MODEL`: "claude-sonnet-4-20250514"
- `LLM_TEMPERATURE`: 0.0 (deterministic)
- `LLM_MAX_TOKENS`: 1000
- `CONTEXT_BEFORE_CHARS`: 30
- `CONTEXT_AFTER_CHARS`: 30

## Common Issues and Solutions

### Issue: Revision not found in target text
**Cause**: LLM returned deletion text that doesn't exist in target column
**Solution**:
- Check `_extract_text_from_node()` in applier.py
- May need fuzzy matching or better context
- Consider increasing context window size

### Issue: XML format errors after packing
**Cause**: Generated XML doesn't conform to OOXML schema
**Solution**:
- Ensure proper element nesting in `_build_smart_revision_xml()`
- Use `xml:space="preserve"` for text with leading/trailing spaces
- Verify all required attributes are present

### Issue: Incorrect revision pairing
**Cause**: `_pair_deletions_insertions()` logic assumes adjacent del/ins
**Solution**:
- Some documents have non-adjacent revisions
- May need to enhance pairing logic with position tracking
- Check paragraph structure in document.xml

### Issue: Missing modifications after sync
**Cause**: Extractor couldn't pair deletion with insertion
**Solution**:
- Standalone deletions or insertions might be skipped
- Enhance `_pair_deletions_insertions()` to handle unpaired revisions
- Log extraction details for debugging

## Development Guidelines

### When modifying extraction logic (extractor.py):
- Test with various document structures (nested tables, merged cells)
- Verify HTML entity decoding for non-ASCII languages
- Check context extraction doesn't truncate mid-character

### When modifying LLM prompts (mapper.py):
- Keep temperature at 0.0 for consistency
- Always request JSON output format
- Include confidence score in response schema
- Test with edge cases (empty strings, special characters)

### When modifying XML generation (applier.py):
- Always preserve original text formatting (rPr nodes)
- Test with Word 2016+ for compatibility
- Verify revision IDs are truly unique
- Use Document Library's validation if available

### Testing approach:
- Create minimal test documents with known revisions
- Compare output with manually created track changes
- Use pandoc to convert to markdown and verify visually
- Check revision metadata (author, date) in Word

## File Organization

```
src/
├── extractor.py    # XML parsing, revision extraction (no external API calls)
├── mapper.py       # LLM API integration (only module that calls Anthropic)
├── applier.py      # XML generation, Document Library usage
├── engine.py       # Orchestration, unpack/pack, CLI
└── config.py       # Constants, presets, environment vars

examples/
└── example_usage.py  # Interactive examples (useful for testing)
```

**Module independence**:
- extractor.py has no dependencies on mapper.py or applier.py
- mapper.py is pure API wrapper, no document manipulation
- applier.py requires Document Library but not extractor/mapper
- engine.py imports and coordinates all three

## External Dependencies

**Python packages** (requirements.txt):
- `anthropic>=0.18.0` - Claude API client
- `defusedxml>=0.7.1` - Safe XML parsing (security)
- `tqdm>=4.65.0` - Progress bars (optional)
- `loguru>=0.7.0` - Logging (optional)

**System dependencies**:
- `pandoc` - Document verification (converts .docx to markdown)
- docx skill - Document Library for OOXML operations

**API requirements**:
- Anthropic API key (set ANTHROPIC_API_KEY environment variable)
- Internet connection for API calls

## Performance Characteristics

- **Small docs (1-5 pages, 1-10 revisions)**: ~30 seconds
- **Medium docs (10-20 pages, 10-30 revisions)**: ~2 minutes
- **Large docs (50+ pages, 50+ revisions)**: ~5 minutes

**Bottleneck**: LLM API calls (one per revision, sequential)

**Optimization opportunities**:
- Batch multiple revisions in single LLM call
- Cache identical revisions
- Parallel processing for multiple documents
- Only process new revisions (incremental mode)

## Notes for Future Developers

1. **Windows paths**: Code uses forward slashes for docx skill paths (`/mnt/skills/`), but works on Windows too. Don't change these.

2. **RSID values**: Random IDs used by Word for tracking. Get from `doc.rsid` (Document Library) - don't hardcode.

3. **Date format**: Use ISO 8601 with timezone: `2026-01-01T14:10:00Z`

4. **Author field**: Can be customized by user, defaults to "Claude"

5. **Verification step**: Uses pandoc with `--track-changes=all` to export markdown for visual inspection

6. **Error handling**: Current implementation logs errors but continues processing remaining revisions

7. **Language support**: Works with any language pair Claude API supports, not limited to Chinese/English


## Meiqi添加的项目记忆

你好Claude，这个项目文件夹是我在claude网页端请求你帮我生成的。因为我在工作中碰到了双语word文档中track changes需要手动同步的问题，我觉得这是个很好的实际切入点，让我可以在实际问题中学习如何coding，如何使用AI，如何开发AI产品。我的目标是最终开发一款能够面市的AI产品，其核心功能是能够实现双语word文档中track changes的自动同步。

在coding，AI和产品开发方面，我都是初学者。我有一点点的python基础知识，但不多。我之所以请求你生成这个双语word文档track changes同步引擎，就是希望能够通过这个实例，深入学习coding、AI和AI产品开发。接下来我将深入该项目的每一个细节，深度掌握项目全貌。请你作为我的指导老师，为我提供学习指导和帮助。可以多向我追问，检查我的掌握是否到位。