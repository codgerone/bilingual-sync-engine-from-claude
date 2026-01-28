# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Bilingual Word Document Track Changes Synchronization Engine** that automatically syncs track changes (revisions) from one language column to another in bilingual Word documents. It's designed for legal documents where changes in one language need to be accurately reflected in the translation.

**Core workflow**: Extract track changes from source column → Use LLM to map revisions to target language → Apply track changes to target column

**Key feature**: Supports multiple LLM providers (Anthropic, DeepSeek, Qwen, Wenxin, Doubao, Zhipu, OpenAI) with two mapping strategies (max_tokens and batch).

## Essential Commands

### Environment Setup
```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Set API key (choose one provider)
export ANTHROPIC_API_KEY='your-key-here'  # Linux/Mac
set ANTHROPIC_API_KEY=your-key-here  # Windows

# Or use other providers
set DEEPSEEK_API_KEY=your-key-here
set QWEN_API_KEY=your-key-here
```

### Running the Engine

**Basic usage**:
```bash
python -m src.engine input.docx -o output.docx
```

**With LLM provider and strategy**:
```bash
python -m src.engine input.docx \
  --provider deepseek \
  --strategy batch \
  --preset zh-en
```

**Full options**:
```bash
python -m src.engine input.docx \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --strategy max_tokens \
  --source-column 0 \
  --target-column 1 \
  --source-lang "Chinese" \
  --target-lang "English" \
  --author "Claude"
```

**Run benchmark**:
```bash
python tests/benchmark_mapper.py
```

### Development Commands
```bash
# No build process - pure Python project

# Debug mode (view extraction details)
python src/extractor.py  # Run extractor standalone
python src/mapper.py     # Run mapper standalone
python src/applier.py    # Run applier standalone (word diff demo)
```

## Architecture Overview

### Three-Module Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    BilingualSyncEngine                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        v                   v                   v
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Extractor   │ ─> │    Mapper    │ ─> │   Applier    │
│  (XML parse) │    │  (LLM call)  │    │ (word diff)  │
└──────────────┘    └──────────────┘    └──────────────┘
```

1. **RevisionExtractor** (`src/extractor.py`)
   - Parses OOXML (Word's XML format) using defusedxml
   - Navigates table structure: `<w:tbl>` → `<w:tr>` → `<w:tc>`
   - Identifies track changes: `<w:del>` (deletions) and `<w:ins>` (insertions)
   - Extracts before/after text versions from source column

2. **RevisionMapper** (`src/mapper.py`)
   - Unified multi-LLM mapper supporting 7 providers
   - Two strategies: "max_tokens" (每次调用顶格输出，正则抢救) and "batch" (预估批次，json.loads)
   - LLM Client abstraction layer: `LLMClient` → `AnthropicClient`, `OpenAICompatibleClient`, `WenxinClient`
   - Factory function `create_llm_client()` for easy provider switching
   - Temperature 0.0 for deterministic output

3. **DiffBasedApplier** (`src/applier.py`)
   - Uses word-level diff (difflib.SequenceMatcher) to find changes
   - Supports both Chinese (jieba) and English tokenization
   - Generates OOXML-compliant track change XML
   - Auto-manages revision IDs (finds max ID in document, increments)
   - Uses Document Library from `/mnt/skills/public/docx`

### Main Engine (`src/engine.py`)
Orchestrates the pipeline:
1. Unpacks .docx (ZIP) to XML files
2. Initializes three modules
3. Extracts source revisions
4. Maps revisions via LLM (max_tokens or batch strategy)
5. Applies word-level diff to target column
6. Repacks to .docx
7. Verifies with pandoc (optional)

### Key Design Patterns

**Multi-LLM Architecture**:
- Abstract `LLMClient` base class with `call()` and `call_with_cache()` methods
- `AnthropicClient`: Native Anthropic API with prompt caching support
- `OpenAICompatibleClient`: Works with DeepSeek, Qwen, Doubao, Zhipu, OpenAI
- `WenxinClient`: Baidu Wenxin native API with OAuth token management

**Dual Strategy Pattern**:
- `strategy="max_tokens"`: 每次调用顶格输出到 token 上限，正则抢救解析，剩余行继续下次调用
- `strategy="batch"`: Pre-estimated batches, json.loads parsing, retry with shrinking batches

**Unpack/Pack workflow**:
- Word .docx files are ZIP archives containing XML
- Uses docx skill scripts: `/mnt/skills/public/docx/ooxml/scripts/unpack.py` and `pack.py`
- Working directory: `{docx_path}_work/unpacked/`

**Revision ID management**:
- Each track change needs unique `w:id` attribute
- Applier scans existing IDs with regex `w:id="(\d+)"`
- New revisions use `max_id + 1`, `max_id + 2`, etc.

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

### Multi-LLM Provider Settings (`src/config.py`)

| Provider | Environment Variable | Default Model | API Type |
|----------|---------------------|---------------|----------|
| Anthropic | `ANTHROPIC_API_KEY` | claude-sonnet-4-20250514 | Native |
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat | OpenAI Compatible |
| Qwen | `QWEN_API_KEY` | qwen-plus | OpenAI Compatible |
| Wenxin | `WENXIN_API_KEY` + `WENXIN_SECRET_KEY` | ernie-4.0 | Native |
| Doubao | `DOUBAO_API_KEY` | doubao-pro-32k | OpenAI Compatible |
| Zhipu | `ZHIPU_API_KEY` | glm-4 | OpenAI Compatible |
| OpenAI | `OPENAI_API_KEY` | gpt-4o | OpenAI Compatible |

### Language Presets
```python
LANGUAGE_PRESETS = {
    "zh-en": {"source_lang": "Chinese", "target_lang": "English", "source_column": 0, "target_column": 1},
    "en-zh": {"source_lang": "English", "target_lang": "Chinese", "source_column": 1, "target_column": 0},
    # ... more presets
}
```

### Key Config Constants
- `LLM_TEMPERATURE`: 0.0 (deterministic)
- `LLM_MAX_TOKENS`: 4096
- `DEFAULT_PROVIDER`: "anthropic"
- `DEFAULT_STRATEGY`: "max_tokens"

## Common Issues and Solutions

### Issue: Revision not found in target text
**Cause**: LLM returned text that doesn't match target column
**Solution**:
- Check word_diff() tokenization in applier.py
- May need fuzzy matching for edge cases
- Try different LLM provider for better translation quality

### Issue: XML format errors after packing
**Cause**: Generated XML doesn't conform to OOXML schema
**Solution**:
- Ensure proper element nesting in `_build_diff_xml()`
- Use `xml:space="preserve"` for text with leading/trailing spaces
- Verify all required attributes are present

### Issue: Batch strategy losing rows
**Cause**: Output truncated mid-JSON or LLM didn't process all rows
**Solution**:
- Retry logic automatically re-processes failed rows
- Consider reducing `output_safety_ratio` for more conservative batching
- Switch to "max_tokens" strategy for speed-critical documents

## Development Guidelines

### When modifying extraction logic (extractor.py):
- Test with various document structures (nested tables, merged cells)
- Verify HTML entity decoding for non-ASCII languages
- Check that before/after text extraction handles all node types

### When modifying LLM prompts (mapper.py):
- Keep temperature at 0.0 for consistency
- Always request JSON output format
- Include confidence score in response schema
- Test with edge cases (empty strings, special characters)
- Test across multiple providers (prompt behavior varies)

### When modifying XML generation (applier.py):
- Always preserve original text formatting (rPr nodes)
- Test with Word 2016+ for compatibility
- Verify revision IDs are truly unique
- Use Document Library's validation if available

### When adding new LLM providers:
- If OpenAI-compatible: Add to `PROVIDERS` dict in `create_llm_client()`
- If native API: Create new `LLMClient` subclass
- Add provider config to `LLM_PROVIDERS` in config.py
- Test with benchmark_mapper.py

### Testing approach:
- Run `python tests/benchmark_mapper.py` to test mapper
- Create minimal test documents with known revisions
- Compare output with manually created track changes
- Use pandoc to convert to markdown and verify visually
- Check revision metadata (author, date) in Word

## File Organization

```
bilingual-sync-engine/
├── src/                    # Core source code
│   ├── __init__.py        # Package exports (v2.0.0)
│   ├── config.py          # Multi-LLM config, language presets
│   ├── extractor.py       # XML parsing, revision extraction
│   ├── mapper.py          # Multi-LLM mapping (7 providers, 2 strategies)
│   ├── applier.py         # Word-level diff, track changes generation
│   └── engine.py          # Orchestration, CLI, unpack/pack
│
├── tests/
│   └── benchmark_mapper.py # Provider/strategy benchmarks
│
├── docs/
│   ├── DATA_FLOW.md       # Complete pipeline documentation
│   └── KNOWLEDGE_MAP.md   # Technical concepts for beginners
│
├── examples/
│   └── example_usage.py   # Interactive usage examples
│
├── CLAUDE.md              # This file
├── CONVERSATION_MEMORY.md # Learning progress tracking
├── README.md              # Project readme
└── requirements.txt       # Python dependencies
```

**Module independence**:
- extractor.py has no dependencies on mapper.py or applier.py
- mapper.py is pure API wrapper, no document manipulation
- applier.py requires Document Library but not extractor/mapper
- engine.py imports and coordinates all three

## External Dependencies

**Python packages** (requirements.txt):
- `anthropic>=0.18.0` - Claude API client
- `openai>=1.0.0` - OpenAI-compatible API client (DeepSeek, Qwen, etc.)
- `defusedxml>=0.7.1` - Safe XML parsing (security)
- `jieba>=0.42.1` - Chinese word segmentation
- `requests>=2.28.0` - HTTP client (for Wenxin API)
- `tqdm>=4.65.0` - Progress bars (optional)
- `loguru>=0.7.0` - Logging (optional)

**System dependencies**:
- `pandoc` - Document verification (converts .docx to markdown)
- docx skill - Document Library for OOXML operations

**API requirements**:
- At least one LLM provider API key
- Internet connection for API calls

## Notes for Future Developers

1. **Windows paths**: Code uses forward slashes for docx skill paths (`/mnt/skills/`), but works on Windows too. Don't change these.

2. **RSID values**: Random IDs used by Word for tracking. Get from `doc.rsid` (Document Library) - don't hardcode.

3. **Date format**: Use ISO 8601 with timezone: `2026-01-01T14:10:00Z`

4. **Author field**: Can be customized by user, defaults to "Claude"

5. **Verification step**: Uses pandoc with `--track-changes=all` to export markdown for visual inspection

6. **Error handling**: Current implementation logs errors but continues processing remaining revisions

7. **Language support**: Works with any language pair that the chosen LLM provider supports

8. **Provider switching**: To switch providers, just set the corresponding environment variable and use `--provider` flag


## Meiqi添加的项目记忆

1. 你好Claude，这个项目文件夹是我在claude网页端请求你帮我生成的。因为我在工作中碰到了双语word文档中track changes需要手动同步的问题，我觉得这是个很好的实际切入点，让我可以在实际问题中学习如何coding，如何使用AI，如何开发AI产品。我的目标是最终开发一款能够面市的AI产品，其核心功能是能够实现双语word文档中track changes的自动同步。

在coding，AI和产品开发方面，我都是初学者。我有一点点的python基础知识，但不多。我之所以请求你生成这个双语word文档track changes同步引擎，就是希望能够通过这个实例，深入学习coding、python、AI和AI产品开发。接下来我将深入该项目的每一个细节，深度掌握项目全貌。请你作为我的指导老师，为我提供学习指导和帮助。可以多向我追问，检查我的掌握是否到位。

2. 2026.1.6，我和你尝试了一些学习该项目的方法。我根据引擎处理文档的数据流走向来逐个学习项目中的文件，我首先学习的是`extractor.py`，我向你提问文件中我看不懂的概念或内容。在对话了几个轮次后，我发现这种学习方式速度极慢，因为每次对话，针对一个小小的概念，你就会为我生成一个专门的测试文件来讲解。而对于我这个初学者来说，单个文件中我没接触过的概念实在太多了。以`extractor.py`为例，我不知道minidom是如何解析XML文件的，不知道其中涉及哪些概念和方法，我对此没有一个全局性的认识，自底而上的学习方式让我学习的速度非常缓慢。所以我们切换了学习模式，对于一个文件中涉及到的多个知识点，你会为我先生成一个一页纸的全局性知识文档，让我能够自上而下先快速了解整块内容的全貌，对于不懂的具体概念，再逐个深入讨论。后续我们将沿用这种学习方式来学习这个项目。

3. 对于可以用文字解释明白的概念或内容，请先尽量用文字解释，而不是生成一个测试代码文件来演示。除非你觉得用跑测试代码的方法来解释这个概念或问题的效果比文字解释要好的多，你可以向我提出运行测试代码的建议，我会根据情况选择是否要执行。

4. **更新 CONVERSATION_MEMORY.md 的规则**：在更新对话记忆时，不要删除历史记忆！应该：
   - 保留历史对话记忆（可以精简浓缩，保留最重要的点）
   - 将旧的内容归档到"历史记录归档"部分
   - 在最新部分更新本轮对话的进展
   - 这样可以保持跨对话的连贯性和完整性
