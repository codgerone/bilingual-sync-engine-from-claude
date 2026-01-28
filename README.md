# Bilingual Word Document Track Changes Sync Engine

Automatically synchronize track changes (revisions) from one language column to another in bilingual Word documents. Designed for legal documents where changes in one language need to be accurately reflected in the translation.

## Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Set API Key

```bash
# Windows
set ANTHROPIC_API_KEY=your-key-here

# Linux/Mac
export ANTHROPIC_API_KEY='your-key-here'
```

### 3. Run

```bash
# Basic usage
python -m src.engine input.docx -o output.docx

# With language preset
python -m src.engine input.docx --preset zh-en

# With different LLM provider
python -m src.engine input.docx --provider deepseek --strategy batch
```

## Project Structure

```
bilingual-sync-engine/
├── src/                    # Core source code
│   ├── __init__.py
│   ├── config.py          # Configuration and LLM provider settings
│   ├── extractor.py       # Extract track changes from Word XML
│   ├── mapper.py          # Multi-LLM revision mapping
│   ├── applier.py         # Apply revisions using word-level diff
│   └── engine.py          # Main orchestration engine
│
├── tests/                  # Test files
│   └── benchmark_mapper.py # LLM provider benchmarks
│
├── docs/                   # Documentation
│   ├── DATA_FLOW.md       # Complete data flow documentation
│   └── KNOWLEDGE_MAP.md   # Technical concepts reference
│
├── examples/               # Usage examples
│   └── example_usage.py
│
├── CLAUDE.md              # Claude Code AI instructions
├── README.md              # This file
└── requirements.txt       # Python dependencies
```

## Architecture

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

## Supported LLM Providers

| Provider | Environment Variable | Default Model |
|----------|---------------------|---------------|
| Anthropic | `ANTHROPIC_API_KEY` | claude-sonnet-4-20250514 |
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat |
| Qwen | `QWEN_API_KEY` | qwen-plus |
| Wenxin | `WENXIN_API_KEY` + `WENXIN_SECRET_KEY` | ernie-4.0 |
| Doubao | `DOUBAO_API_KEY` | doubao-pro-32k |
| Zhipu | `ZHIPU_API_KEY` | glm-4 |
| OpenAI | `OPENAI_API_KEY` | gpt-4o |

## CLI Options

```
python -m src.engine input.docx [options]

Options:
  -o, --output PATH        Output document path
  --provider PROVIDER      LLM provider (anthropic, deepseek, qwen, etc.)
  --strategy STRATEGY      max_tokens (顶格输出) or batch (预估批次)
  --model MODEL            Specific model name
  --preset PRESET          Language preset (zh-en, en-zh, etc.)
  --source-column INT      Source column index (default: 0)
  --target-column INT      Target column index (default: 1)
  --source-lang LANG       Source language name (default: Chinese)
  --target-lang LANG       Target language name (default: English)
  --author NAME            Track changes author (default: Claude)
```

## Language Presets

| Preset | Source | Target |
|--------|--------|--------|
| `zh-en` | Chinese (column 0) | English (column 1) |
| `en-zh` | English (column 1) | Chinese (column 0) |
| `zh-es` | Chinese (column 0) | Spanish (column 1) |
| `zh-ja` | Chinese (column 0) | Japanese (column 1) |

## How It Works

1. **Unpack** - Extract .docx (ZIP) to XML files
2. **Extract** - Parse OOXML, find `<w:del>` and `<w:ins>` elements
3. **Map** - Send source revision to LLM, get target language revision
4. **Apply** - Calculate word-level diff, generate track changes XML
5. **Pack** - Repack XML files to .docx

## Requirements

- Python 3.8+
- anthropic (or openai for other providers)
- defusedxml
- jieba (optional, for Chinese word segmentation)
- pandoc (optional, for verification)

## Documentation

- [Data Flow](docs/DATA_FLOW.md) - Complete pipeline documentation
- [Knowledge Map](docs/KNOWLEDGE_MAP.md) - Technical concepts for beginners
- [CLAUDE.md](CLAUDE.md) - AI assistant instructions

## License

MIT
