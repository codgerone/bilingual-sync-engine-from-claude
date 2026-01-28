# Knowledge Map - Technical Concepts Reference

> This document explains key technical concepts used in the bilingual sync engine.
> For beginners learning Python, XML, and LLM APIs.

---

## Table of Contents

1. [XML Parsing with minidom](#1-xml-parsing-with-minidom)
2. [LLM API Concepts](#2-llm-api-concepts)
3. [JSON Parsing](#3-json-parsing)
4. [Word Document Structure (OOXML)](#4-word-document-structure-ooxml)

---

## 1. XML Parsing with minidom

### What is minidom?

**minidom = Python's built-in XML parser that converts XML text into a tree of objects**

```python
from defusedxml import minidom  # defusedxml is the secure version

# XML string → DOM tree object
dom = minidom.parseString(xml_string)
```

### Core Concepts (Only 3 to Remember)

```
                    DOM Tree

  Document                    ← Root node (entire document)
    └── Element               ← XML tag like <w:p>
         ├── Element          ← Child tag like <w:r>
         │    └── Text        ← Text content "Hello"
         └── Element          ← Sibling tag like <w:del>
              └── Element
```

**3 Object Types:**
1. **Document** - The entire XML document
2. **Element** - XML tags (most commonly used)
3. **Text** - Text content inside tags

### Quick Reference Table

| Method | Purpose | Example | Returns |
|--------|---------|---------|---------|
| `parseString()` | Parse XML string | `dom = minidom.parseString(xml)` | Document |
| `getElementsByTagName()` | Find all matching tags | `dom.getElementsByTagName('w:p')` | NodeList |
| `getAttribute()` | Get tag attribute | `element.getAttribute('w:id')` | String |
| `childNodes` | Get all child nodes | `para.childNodes` | NodeList |
| `toxml()` | Convert back to XML string | `element.toxml()` | String |

**Important: NodeList = list of elements. Use `[0]` to get a single element.**

### Common Pitfall: Whitespace Text Nodes

**Problem:** Why is `element.firstChild` often not what you expect?

```xml
<!-- Formatted XML with newlines -->
<w:p>
    <w:r>Hello</w:r>
</w:p>

Actual DOM tree:
<w:p>
  ├─ Text node: "\n    "     ← firstChild is THIS!
  ├─ Element: <w:r>          ← Not this
  └─ Text node: "\n"
```

**Reason:** minidom treats all characters between tags (including newlines, spaces, indentation) as text nodes!

**Solution:**
```python
# ❌ Wrong: directly use firstChild
element.firstChild.toxml()  # Might be whitespace!

# ✅ Correct: check node type
for child in element.childNodes:
    if child.nodeType == child.ELEMENT_NODE:  # Skip text nodes
        print(child.toxml())

# ✅ Or: use getElementsByTagName directly
first_r = element.getElementsByTagName('w:r')[0]
```

### Code Template

```python
from defusedxml import minidom

# 1. Parse
dom = minidom.parseString(xml_string)

# 2. Find (returns NodeList)
elements = dom.getElementsByTagName('w:del')

# 3. Iterate
for element in elements:
    # 4. Get attribute
    element_id = element.getAttribute('w:id')

    # 5. Get text
    text_nodes = element.getElementsByTagName('w:t')
    if text_nodes and text_nodes[0].firstChild:
        text = text_nodes[0].firstChild.nodeValue

    # 6. Access children
    for child in element.childNodes:
        if child.nodeType == child.ELEMENT_NODE:
            print(f"Child tag: {child.tagName}")
```

---

## 2. LLM API Concepts

### What is an API?

**API = How programs communicate with each other**

Think of a restaurant:
- You (program) can't go into the kitchen yourself
- You need a **waiter (API)** to order food
- The waiter communicates your request to the kitchen
- The kitchen prepares the food, and the waiter brings it to you

The API defines:
- What dishes you can order (available functions)
- How to order (request format)
- How the food will be served (response format)

### Anthropic API

Anthropic developed Claude. Their API allows you to:
- Send text to Claude
- Receive Claude's response
- Control various parameters

**Why use an API?**
- Claude's "brain" (model) runs on Anthropic's servers
- Your computer can't run such a large model
- Through the API, your program can "borrow" Anthropic's servers to think

### API Key

**API Key = Your ID + Payment credential**

```
ANTHROPIC_API_KEY = "sk-ant-api03-xxxxx..."
```

- Every API call requires the key
- Anthropic identifies who's calling via the key
- Charges based on usage (per token)

**Security reminder:** The key is like a bank password. Never:
- Commit to GitHub
- Share with others
- Hardcode in your code

Correct way - use environment variables:
```bash
# Windows
set ANTHROPIC_API_KEY=your-key

# Mac/Linux
export ANTHROPIC_API_KEY='your-key'
```

### Core API Usage

```python
import anthropic

# 1. Create client
client = anthropic.Anthropic(api_key="your-key")

# 2. Send message
response = client.messages.create(
    model="claude-sonnet-4-20250514",  # Which model to use
    max_tokens=2000,                     # Max response length
    temperature=0.0,                     # Randomness (0 = deterministic)
    messages=[
        {"role": "user", "content": "Hello, Claude!"}
    ]
)

# 3. Get reply
reply = response.content[0].text
print(reply)
```

### Key Parameters

| Parameter | Purpose | Our Value |
|-----------|---------|-----------|
| `model` | Which Claude model to use | `claude-sonnet-4-20250514` |
| `max_tokens` | Maximum response length | `2000` |
| `temperature` | Output randomness | `0.0` |
| `messages` | Conversation history | User message |

**About temperature:**
- `0.0` → Deterministic output (same input always gives same output)
- `1.0` → Higher randomness (same input may give different outputs)

We use 0.0 because legal documents need **consistency**.

### What are Tokens?

**Token ≈ Word or part of a word**

Claude charges by tokens, not characters:
- English: ~1 token = 0.75 words
- Chinese: ~1 token = 0.5-1 characters

Example:
```
"Hello, world!" → 4 tokens
"你好世界" → 4-5 tokens
```

---

## 3. JSON Parsing

### What is JSON?

**JSON = Structured data format**

```json
{
  "name": "Alice",
  "age": 25,
  "skills": ["Python", "Java"]
}
```

Features:
- Objects wrapped in curly braces `{}`
- Key-value pairs separated by colons `:`
- Multiple pairs separated by commas `,`
- Can nest (objects inside arrays, arrays inside objects)

### Why Use JSON?

AI returns natural language text like:
```
Okay, let me analyze this revision...
The revised English should be "AI changed our life."
My confidence is 95%.
```

This is human-friendly but program-unfriendly—hard to extract the data we need.

So we ask AI to return JSON:
```json
{
  "target_after": "AI changed our life.",
  "confidence": 0.95
}
```

Programs can directly use `result['target_after']` to get the value.

### Parsing JSON from LLM Responses

```python
import json

def parse_response(response_text: str) -> dict:
    # AI might return:
    # "Here's the result:
    # ```json
    # {"target_after": "...", "confidence": 0.95}
    # ```
    # "

    # Step 1: Find JSON code block
    if "```json" in response_text:
        start = response_text.find("```json") + 7
        end = response_text.find("```", start)
        json_str = response_text[start:end].strip()

    # Step 2: Parse JSON string
    result = json.loads(json_str)

    # Step 3: Validate required fields
    if 'target_after' not in result:
        raise ValueError("Missing target_after field")

    return result
```

---

## 4. Word Document Structure (OOXML)

### What is OOXML?

**OOXML = Office Open XML, the format used by Word (.docx)**

A .docx file is actually a ZIP archive containing XML files:

```
document.docx (ZIP file)
├── [Content_Types].xml
├── _rels/
│   └── .rels
├── word/
│   ├── document.xml      ← Main content
│   ├── styles.xml
│   └── ...
└── docProps/
    └── core.xml
```

### Table Structure

```xml
<w:tbl>                      <!-- Table -->
  <w:tr>                     <!-- Table Row -->
    <w:tc>                   <!-- Table Cell (column 0 = source) -->
      <w:p>                  <!-- Paragraph -->
        <w:r>                <!-- Normal text run -->
          <w:t>text</w:t>
        </w:r>
        <w:del>              <!-- Deletion (track change) -->
          <w:r>
            <w:delText>deleted</w:delText>
          </w:r>
        </w:del>
        <w:ins>              <!-- Insertion (track change) -->
          <w:r>
            <w:t>inserted</w:t>
          </w:r>
        </w:ins>
      </w:p>
    </w:tc>
    <w:tc>                   <!-- Table Cell (column 1 = target) -->
      ...
    </w:tc>
  </w:tr>
</w:tbl>
```

### Track Changes Elements

| Element | Purpose | Contains |
|---------|---------|----------|
| `<w:del>` | Marks deleted text | `<w:delText>` |
| `<w:ins>` | Marks inserted text | `<w:t>` |

### Required Attributes for Track Changes

```xml
<w:del w:id="0" w:author="Claude" w:date="2026-01-01T00:00:00Z" w16du:dateUtc="...">
  <w:r w:rsidDel="...">
    <w:delText>deleted text</w:delText>
  </w:r>
</w:del>

<w:ins w:id="1" w:author="Claude" w:date="2026-01-01T00:00:00Z" w16du:dateUtc="...">
  <w:r>
    <w:t>inserted text</w:t>
  </w:r>
</w:ins>
```

| Attribute | Purpose |
|-----------|---------|
| `w:id` | Unique numeric ID for each change |
| `w:author` | Who made the change |
| `w:date` | When the change was made (ISO 8601) |
| `w16du:dateUtc` | UTC timestamp |
| `w:rsidDel/w:rsidR` | Random session ID (from Document Library) |

### Extracting Text

**Before revision (original):** Normal runs + deletions
**After revision (current):** Normal runs + insertions

```
<w:p>
  <w:r><w:t>Hello </w:t></w:r>        → before: "Hello ", after: "Hello "
  <w:del><w:r><w:delText>old</w:delText></w:r></w:del>  → before: "old", after: ""
  <w:ins><w:r><w:t>new</w:t></w:r></w:ins>              → before: "", after: "new"
  <w:r><w:t> world</w:t></w:r>        → before: " world", after: " world"
</w:p>

Result:
  before_text = "Hello old world"
  after_text = "Hello new world"
```

---

## Quick Reference Card

### minidom
```python
dom = minidom.parseString(xml)
elements = dom.getElementsByTagName('tag')
for el in elements:
    attr = el.getAttribute('name')
    text = el.firstChild.nodeValue
```

### Anthropic API
```python
client = anthropic.Anthropic(api_key=key)
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=2000,
    temperature=0.0,
    messages=[{"role": "user", "content": "..."}]
)
text = response.content[0].text
```

### JSON
```python
import json
data = json.loads(json_string)
value = data['key']
```

### OOXML
- `<w:tr>` = table row
- `<w:tc>` = table cell
- `<w:p>` = paragraph
- `<w:r>` = text run
- `<w:t>` = text
- `<w:del>` = deletion
- `<w:ins>` = insertion

---

*Last updated: 2026-01-26*
