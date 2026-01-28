# Data Flow Documentation

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        BilingualSyncEngine (engine.py)                       │
│                              Main Orchestrator                                │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
          ▼                           ▼                           ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│    Extractor     │ ───> │      Mapper      │ ───> │     Applier      │
│  (extractor.py)  │      │   (mapper.py)    │      │   (applier.py)   │
└──────────────────┘      └──────────────────┘      └──────────────────┘
         │                         │                         │
         ▼                         ▼                         ▼
    document.xml            LLM API Call              document.xml
    (parse OOXML)           (Claude/etc)              (write OOXML)
```

## Complete Pipeline

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   input.docx│ ──> │   Unpack    │ ──> │  XML Files  │ ──> │  Extractor  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                                                                   ▼
                                                         ┌─────────────────┐
                                                         │   row_pairs     │
                                                         │ List[Dict]:     │
                                                         │ - row_index     │
                                                         │ - source_before │
                                                         │ - source_after  │
                                                         │ - target_current│
                                                         └─────────────────┘
                                                                   │
                                                                   ▼
                                                         ┌─────────────────┐
                                                         │     Mapper      │
                                                         │   (LLM Call)    │
                                                         └─────────────────┘
                                                                   │
                                                                   ▼
                                                         ┌─────────────────┐
                                                         │ mapped_results  │
                                                         │ List[Dict]:     │
                                                         │ - row_index     │
                                                         │ - target_current│
                                                         │ - target_after  │
                                                         │ - explanation   │
                                                         │ - confidence    │
                                                         └─────────────────┘
                                                                   │
                                                                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ output.docx │ <── │    Pack     │ <── │  XML Files  │ <── │   Applier   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

## Module Details

### 1. Extractor (extractor.py)

**Purpose**: Parse OOXML and extract track changes from source column

**Input**: `document.xml` file path

**Output**: `List[Dict]` with structure:
```python
{
    'row_index': int,          # Row number in table
    'source_before': str,      # Text before revision (includes deletions)
    'source_after': str,       # Text after revision (includes insertions)
    'target_current': str      # Current text in target column
}
```

**Key Functions**:
```
extract_row_pairs()
    ├── _has_revisions()                 # Check for <w:del>/<w:ins>
    ├── _extract_text_versions_from_cell()
    │       └── _extract_text_from_node()
    └── _extract_all_text_from_cell()
```

**OOXML Parsing Logic**:
- `<w:r>` (normal run) → both before and after
- `<w:del>` (deletion) → before only
- `<w:ins>` (insertion) → after only

---

### 2. Mapper (mapper.py)

**Purpose**: Use LLM to translate revisions to target language

**Input**: `row_pairs` from Extractor

**Output**: `List[Dict]` with structure:
```python
{
    'row_index': int,
    'target_current': str,     # Original target text
    'target_after': str,       # LLM-generated revised text
    'explanation': str,        # LLM reasoning
    'confidence': float        # 0.0 - 1.0
}
```

**Strategies**:

| Strategy | Description | Best For |
|----------|-------------|----------|
| `max_tokens` | 每次调用顶格输出到 token 上限，正则抢救，剩余行继续下次调用 | 速度优先 |
| `batch` | Pre-estimated batches, json.loads parsing, retry with shrink | Structured output, cost optimization |

**Provider Support**:

| Provider | API Type | Caching Support |
|----------|----------|-----------------|
| Anthropic | Native | Yes |
| DeepSeek | OpenAI Compatible | No |
| Qwen | OpenAI Compatible | No |
| Wenxin | Native | No |
| Doubao | OpenAI Compatible | No |
| Zhipu | OpenAI Compatible | No |
| OpenAI | OpenAI Compatible | No |

**Key Functions**:
```
map_row_pairs()                        # Main entry
    ├── _map_max_tokens_strategy()     # 每次调用顶格输出，正则抢救
    │       └── _salvage_objects()
    └── _map_batch_strategy()          # Pre-estimated batches
            ├── _build_batches()
            ├── _map_single_batch()
            └── _parse_batch_response()
```

---

### 3. Applier (applier.py)

**Purpose**: Generate track changes XML and apply to document

**Input**: `mapped_results` from Mapper

**Output**: Modified `document.xml` with track changes

**Process**:
```
apply_mapped_revisions()
    └── apply_diff_to_row()
            ├── word_diff()            # Calculate differences
            │       ├── tokenize()
            │       └── detect_language()
            └── _build_diff_xml()      # Generate OOXML
```

**Word Diff Operations**:
- `('equal', text)` → No change
- `('delete', text)` → Create `<w:del>` element
- `('insert', text)` → Create `<w:ins>` element

**OOXML Output Format**:
```xml
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
```

---

## Configuration (config.py)

**LLM Settings**:
```python
DEFAULT_PROVIDER = "anthropic"
DEFAULT_STRATEGY = "max_tokens"
LLM_MAX_TOKENS = 4096
LLM_TEMPERATURE = 0.0
```

**Language Presets**:
```python
LANGUAGE_PRESETS = {
    "zh-en": {"source_lang": "Chinese", "target_lang": "English", ...},
    "en-zh": {"source_lang": "English", "target_lang": "Chinese", ...},
    # ... more presets
}
```

**Provider Configuration**:
```python
LLM_PROVIDERS = {
    "anthropic": {"env_key": "ANTHROPIC_API_KEY", "default_model": "claude-sonnet-4-20250514"},
    "deepseek": {"env_key": "DEEPSEEK_API_KEY", "default_model": "deepseek-chat"},
    # ... more providers
}
```

---

## Data Formats

### Extractor Output / Mapper Input

```json
[
    {
        "row_index": 0,
        "source_before": "协议有效期为一年",
        "source_after": "协议有效期为两年",
        "target_current": "The agreement is valid for one year"
    },
    {
        "row_index": 1,
        "source_before": "甲方应当支付",
        "source_after": "甲方须支付",
        "target_current": "Party A should pay"
    }
]
```

### Mapper Output / Applier Input

```json
[
    {
        "row_index": 0,
        "target_current": "The agreement is valid for one year",
        "target_after": "The agreement is valid for two years",
        "explanation": "Changed 'one year' to 'two years' to match the Chinese revision",
        "confidence": 0.95
    },
    {
        "row_index": 1,
        "target_current": "Party A should pay",
        "target_after": "Party A shall pay",
        "explanation": "Changed 'should' to 'shall' for stronger obligation",
        "confidence": 0.98
    }
]
```

---

## Error Handling

### Extractor
- Skips rows without track changes
- Handles missing columns gracefully
- Decodes HTML entities for non-ASCII

### Mapper
- **Max Tokens Strategy**: Regex salvage for truncated output, retry missing rows
- **Batch Strategy**: Retries failed rows with smaller batches
- **Truncation**: Drops last result if output truncated

### Applier
- Skips rows with empty `target_after`
- Logs errors but continues processing
- Handles XML escaping for special characters

---

## CLI Usage

```bash
# Basic usage
python -m src.engine input.docx -o output.docx

# With provider and strategy
python -m src.engine input.docx \
    --provider deepseek \
    --strategy batch \
    --preset zh-en

# Full options
python -m src.engine input.docx \
    --provider anthropic \
    --model claude-sonnet-4-20250514 \
    --strategy max_tokens \
    --source-column 0 \
    --target-column 1 \
    --source-lang Chinese \
    --target-lang English \
    --author "Translator"
```

---

## Performance Characteristics

| Document Size | Revisions | Estimated Time (Max Tokens) | Estimated Time (Batch) |
|--------------|-----------|---------------------------|----------------------|
| 1-5 pages | 1-10 | ~10 seconds | ~15 seconds |
| 10-20 pages | 10-30 | ~30 seconds | ~45 seconds |
| 50+ pages | 50+ | ~2 minutes | ~2 minutes |

**Bottleneck**: LLM API calls (latency + token processing)

**Optimizations**:
- Prompt caching (Anthropic only)
- Batch processing for multiple rows
- Retry with smaller batches on failure
