# 数据流转文档：API 响应 → Applier 参数（批量处理模式）

> 本文档详细展示**批量处理模式**下，数据从 Anthropic API 原始响应到 `DiffBasedApplier.apply_mapped_revisions()` 参数的完整流转过程。
>
> 基于 `mapper2_from_codex.py`（BatchRevisionMapper）

---

## 总览流程图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        批量处理完整数据流转                                   │
└─────────────────────────────────────────────────────────────────────────────┘

extractor 输出
      │
      │ rows: List[Dict]
      ▼
┌───────────────────┐
│  _normalize_rows()│   标准化输入格式
└───────────────────┘
      │
      │ normalized: List[Dict]
      ▼
┌───────────────────┐
│  _build_batches() │   按输出预算动态分批
└───────────────────┘
      │
      │ batches: List[List[Dict]]
      ▼
┌───────────────────┐
│  _map_batch()     │   每批调用一次 API
└───────────────────┘
      │
      ├──────────────────────────────────────┐
      │                                      │
      ▼                                      ▼
┌───────────────────┐                 ┌───────────────────┐
│  API 原始响应      │                 │  stop_reason      │
│  (Message 对象)    │                 │  检查是否截断      │
└───────────────────┘                 └───────────────────┘
      │
      │ response.content[0].text
      ▼
┌───────────────────┐
│  LLM 输出文本      │   类型: str（JSON 数组字符串）
└───────────────────┘
      │
      │ _parse_batch_response()
      ▼
┌───────────────────┐
│  解析后的列表      │   类型: List[Dict]（多行结果）
└───────────────────┘
      │
      │ 识别失败行 → 精准重试
      ▼
┌───────────────────┐
│  map_rows() 返回   │   类型: List[Dict]
│  (mapped_results) │
└───────────────────┘
      │
      │ 传入 applier
      ▼
┌───────────────────┐
│  apply_mapped_    │
│  revisions()      │
└───────────────────┘
```

---

## 阶段 1：extractor 输出（输入数据）

### 数据来源
```python
# 来自 extractor.extract_row_pairs()
rows = extractor.extract_row_pairs()
```

### 数据类型
```
List[Dict[str, Any]]
```

### 数据结构示例
```python
[
    {
        'row_index': 0,
        'source_before': 'AI正在改变我们的生活。',
        'source_after': 'AI改变了我们的生活。',
        'target_current': 'AI is changing our life.'
    },
    {
        'row_index': 1,
        'source_before': '协议有效期为一年。',
        'source_after': '协议有效期为两年。',
        'target_current': 'The agreement is valid for one year.'
    },
    {
        'row_index': 2,
        'source_before': '甲方应当支付全部款项。',
        'source_after': '甲方须支付全部款项。',
        'target_current': 'Party A should pay the full amount.'
    }
]
```

---

## 阶段 2：`_normalize_rows()` 标准化

### 函数签名
```python
# mapper2_from_codex.py 第 174 行
def _normalize_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]
```

### 输入
| 参数 | 类型 | 说明 |
|------|------|------|
| `rows` | `List[Dict[str, Any]]` | extractor 原始输出 |

### 处理逻辑
```python
def _normalize_rows(self, rows):
    normalized = []
    for row in rows:
        # 兼容 row_index 或 row 字段名
        idx = row.get("row_index", row.get("row"))
        if idx is None:
            continue
        normalized.append({
            "row_index": int(idx),
            "source_before": row.get("source_before", ""),
            "source_after": row.get("source_after", ""),
            "target_current": row.get("target_current", ""),
        })
    return normalized
```

### 输出
| 返回值 | 类型 | 说明 |
|--------|------|------|
| `normalized` | `List[Dict[str, Any]]` | 标准化后的行列表 |

### 输出数据结构
```python
[
    {
        'row_index': 0,
        'source_before': 'AI正在改变我们的生活。',
        'source_after': 'AI改变了我们的生活。',
        'target_current': 'AI is changing our life.'
    },
    {
        'row_index': 1,
        'source_before': '协议有效期为一年。',
        'source_after': '协议有效期为两年。',
        'target_current': 'The agreement is valid for one year.'
    },
    # ... 更多行
]
```

---

## 阶段 3：`_build_batches()` 动态分批

### 函数签名
```python
# mapper2_from_codex.py 第 190 行
def _build_batches(
    self,
    rows: List[Dict[str, Any]],
    output_budget: int
) -> List[List[Dict[str, Any]]]
```

### 输入
| 参数 | 类型 | 说明 |
|------|------|------|
| `rows` | `List[Dict[str, Any]]` | 标准化后的行列表 |
| `output_budget` | `int` | 输出预算（tokens），默认 `max_output_tokens × 0.7` |

### 处理逻辑
```python
def _build_batches(self, rows, output_budget):
    batches = []
    current = []
    used = 0

    for row in rows:
        # 估算每行的输出 token 成本
        cost = self._estimate_row_output_tokens(row)

        # 如果超出预算，开始新批次
        if current and used + cost > output_budget:
            batches.append(current)
            current = []
            used = 0

        current.append(row)
        used += cost

    if current:
        batches.append(current)

    return batches

def _estimate_row_output_tokens(self, row):
    # 启发式估算：基础成本 + 每字符成本
    text_len = max(
        len(row.get("source_before", "")),
        len(row.get("source_after", "")),
        len(row.get("target_current", "")),
    )
    return int(self.row_base_tokens + self.row_per_char * text_len)
    # 默认：80 + 0.2 × 文本长度
```

### 输出
| 返回值 | 类型 | 说明 |
|--------|------|------|
| `batches` | `List[List[Dict[str, Any]]]` | 批次列表，每批包含多行 |

### 输出数据结构示例
假设有 100 行，按预算分成 5 批：
```python
[
    # 批次 0：第 0-19 行
    [
        {'row_index': 0, 'source_before': '...', 'source_after': '...', 'target_current': '...'},
        {'row_index': 1, 'source_before': '...', 'source_after': '...', 'target_current': '...'},
        # ... 共约 20 行
    ],
    # 批次 1：第 20-39 行
    [
        {'row_index': 20, ...},
        {'row_index': 21, ...},
        # ...
    ],
    # ... 更多批次
]
```

---

## 阶段 4：`_map_batch()` 单批次 API 调用

### 函数签名
```python
# mapper2_from_codex.py 第 128 行
def _map_batch(
    self,
    batch: List[Dict[str, Any]],
    source_lang: str,
    target_lang: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]
```

### 输入
| 参数 | 类型 | 说明 |
|------|------|------|
| `batch` | `List[Dict[str, Any]]` | 一个批次的行列表 |
| `source_lang` | `str` | 源语言 |
| `target_lang` | `str` | 目标语言 |

### 处理逻辑
```python
def _map_batch(self, batch, source_lang, target_lang):
    # 1. 构建 system prompt（带缓存）
    system_prompt = self._build_system_prompt(source_lang, target_lang)

    # 2. 构建 user message（JSON 格式）
    user_message = self._build_user_message(batch)

    # 3. 调用 API
    response = self.client.messages.create(
        model=self.model,
        max_tokens=self.max_output_tokens,
        temperature=0.0,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    # 4. 提取响应
    response_text = response.content[0].text
    stop_reason = response.stop_reason

    # 5. 解析响应
    parsed = self._parse_batch_response(response_text)

    # 6. 识别失败行
    parsed_ids = {item["row_index"] for item in parsed}
    batch_ids = {row["row_index"] for row in batch}
    failed_ids = batch_ids - parsed_ids

    # 7. 截断处理
    if stop_reason == "max_tokens":
        if parsed:
            last = parsed.pop()
            failed_ids.add(last.get("row_index"))
        failed_ids.add(batch[-1]["row_index"])

    # 8. 构建失败行列表
    failed_rows = [row for row in batch if row["row_index"] in failed_ids]

    return parsed, failed_rows
```

### 输出
| 返回值 | 类型 | 说明 |
|--------|------|------|
| `parsed` | `List[Dict[str, Any]]` | 成功解析的结果列表 |
| `failed_rows` | `List[Dict[str, Any]]` | 失败的行（需要重试） |

---

## 阶段 4.1：`_build_user_message()` 构建请求

### 函数签名
```python
# mapper2_from_codex.py 第 252 行
def _build_user_message(self, batch: List[Dict[str, Any]]) -> str
```

### 输入
| 参数 | 类型 | 说明 |
|------|------|------|
| `batch` | `List[Dict[str, Any]]` | 一个批次的行列表 |

### 输出
| 返回值 | 类型 | 说明 |
|--------|------|------|
| `user_message` | `str` | 发送给 LLM 的消息 |

### 输出示例
```
Process the following JSON array and return a JSON array of results.
Do not include any text outside the JSON array.

INPUT_JSON:
[{"row_index": 0, "source_before": "AI\u6b63\u5728\u6539\u53d8...", "source_after": "AI\u6539\u53d8\u4e86...", "target_current": "AI is changing our life."}, {"row_index": 1, "source_before": "...", "source_after": "...", "target_current": "..."}]
```

---

## 阶段 4.2：API 原始响应

### 数据类型
```
anthropic.types.Message
```

### 数据结构（正常完成）
```python
Message(
    id='msg_01ABC123...',
    type='message',
    role='assistant',
    model='claude-sonnet-4-20250514',

    content=[
        TextBlock(
            type='text',
            text='[\n  {\n    "row_index": 0,\n    "target_after": "AI has changed our life.",\n    "confidence": 0.95,\n    "explanation": "进行时→完成时"\n  },\n  {\n    "row_index": 1,\n    "target_after": "The agreement is valid for two years.",\n    "confidence": 0.98,\n    "explanation": "one year → two years"\n  }\n]'
        )
    ],

    stop_reason='end_turn',    # ← 正常完成
    stop_sequence=None,

    usage=Usage(
        input_tokens=1256,
        output_tokens=487,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=800
    )
)
```

### 数据结构（被截断）
```python
Message(
    # ... 其他字段相同 ...

    content=[
        TextBlock(
            type='text',
            text='[\n  {\n    "row_index": 0,\n    "target_after": "AI has changed our life.",\n    "confidence": 0.95\n  },\n  {\n    "row_index": 1,\n    "target_after": "The agreement is valid for two years.",\n    "confidence": 0.98\n  },\n  {\n    "row_index": 2,\n    "target_after": "Party A shall pay the ful'
            # ↑ 被截断，JSON 不完整
        )
    ],

    stop_reason='max_tokens',    # ← 被截断！

    usage=Usage(
        input_tokens=1256,
        output_tokens=2000,      # ← 达到上限
        ...
    )
)
```

---

## 阶段 4.3：提取 LLM 输出文本

### 代码
```python
# mapper2_from_codex.py 第 149 行
response_text = response.content[0].text
stop_reason = response.stop_reason
```

### 数据类型
| 变量 | 类型 | 说明 |
|------|------|------|
| `response_text` | `str` | LLM 输出的文本（JSON 数组） |
| `stop_reason` | `str` | `"end_turn"` 或 `"max_tokens"` |

### response_text 示例（正常完成）
```json
[
  {
    "row_index": 0,
    "target_after": "AI has changed our life.",
    "confidence": 0.95,
    "explanation": "进行时→完成时"
  },
  {
    "row_index": 1,
    "target_after": "The agreement is valid for two years.",
    "confidence": 0.98,
    "explanation": "one year → two years"
  },
  {
    "row_index": 2,
    "target_after": "Party A shall pay the full amount.",
    "confidence": 0.92,
    "explanation": "should → shall"
  }
]
```

### response_text 示例（被截断）
```json
[
  {
    "row_index": 0,
    "target_after": "AI has changed our life.",
    "confidence": 0.95
  },
  {
    "row_index": 1,
    "target_after": "The agreement is valid for two years.",
    "confidence": 0.98
  },
  {
    "row_index": 2,
    "target_after": "Party A shall pay the ful
```
**注意**：被截断时 JSON 不完整，无法直接解析。

---

## 阶段 5：`_parse_batch_response()` 解析批量响应

### 函数签名
```python
# mapper2_from_codex.py 第 270 行
def _parse_batch_response(self, response_text: str) -> List[Dict[str, Any]]
```

### 输入
| 参数 | 类型 | 说明 |
|------|------|------|
| `response_text` | `str` | LLM 输出的原始文本 |

### 处理逻辑
```python
def _parse_batch_response(self, response_text):
    # 1. 去掉 ``` 代码块包装
    text = self._strip_code_fence(response_text)

    # 2. 尝试完整 JSON 解析
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "results" in data:
            data = data["results"]
        return self._normalize_results(data)
    except Exception:
        pass

    # 3. 完整解析失败 → salvage 抢救
    salvaged = self._salvage_objects(text)
    return self._normalize_results(salvaged)
```

### `_salvage_objects()` 抢救逻辑
```python
def _salvage_objects(self, text):
    """从损坏的 JSON 中抢救完整的对象"""
    # 用正则找所有包含 row_index 的完整对象
    pattern = re.compile(r"\{[^{}]*\"row_index\"\s*:\s*\d+[^{}]*\}")

    results = []
    for match in pattern.finditer(text):
        chunk = match.group(0)
        try:
            results.append(json.loads(chunk))
        except Exception:
            continue
    return results
```

### `_normalize_results()` 标准化结果
```python
def _normalize_results(self, data):
    if not isinstance(data, list):
        return []

    normalized = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if "row_index" not in item:
            continue
        if "target_after" not in item:
            continue

        # 设置默认值
        if "confidence" not in item:
            item["confidence"] = 0.8
        if "explanation" not in item:
            item["explanation"] = ""

        normalized.append(item)

    return normalized
```

### 输出
| 返回值 | 类型 | 说明 |
|--------|------|------|
| `parsed` | `List[Dict[str, Any]]` | 解析成功的结果列表 |

### 输出数据结构
```python
[
    {
        'row_index': 0,
        'target_after': 'AI has changed our life.',
        'confidence': 0.95,
        'explanation': '进行时→完成时'
    },
    {
        'row_index': 1,
        'target_after': 'The agreement is valid for two years.',
        'confidence': 0.98,
        'explanation': 'one year → two years'
    },
    {
        'row_index': 2,
        'target_after': 'Party A shall pay the full amount.',
        'confidence': 0.92,
        'explanation': 'should → shall'
    }
]
```

---

## 阶段 6：失败行识别与精准重试

### 代码
```python
# mapper2_from_codex.py 第 152-168 行

# 识别失败行
parsed_ids = {item["row_index"] for item in parsed}
batch_ids = {row["row_index"] for row in batch}
failed_ids = batch_ids - parsed_ids    # 集合差运算

# 截断特殊处理
if stop_reason == "max_tokens":
    if parsed:
        last = parsed.pop()                      # 丢弃最后一个（可能不完整）
        failed_ids.add(last.get("row_index"))
    failed_ids.add(batch[-1]["row_index"])       # 最后一行也标记失败

# 构建失败行列表
failed_rows = [row for row in batch if row["row_index"] in failed_ids]
```

### 示例
```
批次包含：row 0, 1, 2, 3, 4
解析成功：row 0, 1, 2
失败行：  row 3, 4  ← 只重试这两行
```

---

## 阶段 7：`map_rows()` 主入口汇总

### 函数签名
```python
# mapper2_from_codex.py 第 80 行
def map_rows(
    self,
    rows: List[Dict[str, Any]],
    source_lang: str = "Chinese",
    target_lang: str = "English",
) -> List[Dict[str, Any]]
```

### 完整处理逻辑
```python
def map_rows(self, rows, source_lang, target_lang):
    # 1. 标准化输入
    normalized = self._normalize_rows(rows)

    results_by_row = {}       # 存储成功结果
    pending_rows = normalized  # 待处理行

    # 计算初始输出预算
    batch_output_limit = int(self.max_output_tokens * self.output_safety_ratio)

    # 2. 重试循环
    for attempt in range(self.max_retries + 1):
        if not pending_rows:
            break

        # 3. 分批
        batches = self._build_batches(pending_rows, batch_output_limit)
        failed_rows = []

        # 4. 处理每批
        for batch in batches:
            batch_results, batch_failed = self._map_batch(
                batch, source_lang, target_lang
            )

            # 收集成功结果
            for item in batch_results:
                results_by_row[item["row_index"]] = item

            # 收集失败行
            failed_rows.extend(batch_failed)

        # 5. 更新待处理行为失败行
        pending_rows = failed_rows

        # 6. 收缩预算（重试时更保守）
        batch_output_limit = int(batch_output_limit * self.retry_shrink_ratio)
        if batch_output_limit < 200:
            batch_output_limit = 200

    # 7. 按原始顺序返回结果
    ordered = []
    for row in normalized:
        idx = row["row_index"]
        if idx in results_by_row:
            ordered.append(results_by_row[idx])

    return ordered
```

### 输出
| 返回值 | 类型 | 说明 |
|--------|------|------|
| `ordered` | `List[Dict[str, Any]]` | 完整映射结果（即 `mapped_results`） |

### 输出数据结构
```python
[
    {
        'row_index': 0,
        'target_after': 'AI has changed our life.',
        'confidence': 0.95,
        'explanation': '进行时→完成时'
    },
    {
        'row_index': 1,
        'target_after': 'The agreement is valid for two years.',
        'confidence': 0.98,
        'explanation': 'one year → two years'
    },
    {
        'row_index': 2,
        'target_after': 'Party A shall pay the full amount.',
        'confidence': 0.92,
        'explanation': 'should → shall'
    }
]
```

---

## 阶段 8：`apply_mapped_revisions()` 接收

### 函数签名
```python
# applier.py 第 429 行
def apply_mapped_revisions(
    self,
    mapped_results: List[Dict],
    column_index: int = 1
) -> int
```

### 输入
| 参数 | 类型 | 说明 |
|------|------|------|
| `mapped_results` | `List[Dict]` | `map_rows()` 返回的完整映射结果 |
| `column_index` | `int` | 目标列索引 |

### 处理逻辑
```python
def apply_mapped_revisions(self, mapped_results, column_index=1):
    success_count = 0

    for result in mapped_results:
        row_idx = result.get('row_index')
        current = result.get('target_current', '')   # 注意：批量模式没有这个字段！
        after = result.get('target_after', '')

        success = self.apply_diff_to_row(
            row_index=row_idx,
            column_index=column_index,
            current_text=current,
            target_after=after
        )

        if success:
            success_count += 1

    return success_count
```

### ⚠️ 重要：数据字段差异

| 字段 | 单行模式 (mapper.py) | 批量模式 (mapper2_from_codex.py) |
|------|---------------------|--------------------------------|
| `row_index` | ✅ 有 | ✅ 有 |
| `target_after` | ✅ 有 | ✅ 有 |
| `confidence` | ✅ 有 | ✅ 有 |
| `explanation` | ✅ 有 | ✅ 有 |
| `target_current` | ✅ 有（手动补充） | ❌ 没有！ |

**批量模式需要补充 `target_current`** 才能与 applier 对接：

```python
# 补充 target_current
for i, result in enumerate(mapped_results):
    result['target_current'] = normalized[i]['target_current']
```

---

## 完整数据类型汇总

| 阶段 | 函数/操作 | 输出类型 |
|------|----------|---------|
| 1 | extractor 输出 | `List[Dict]` |
| 2 | `_normalize_rows()` | `List[Dict]` |
| 3 | `_build_batches()` | `List[List[Dict]]` |
| 4 | API 调用 | `anthropic.types.Message` |
| 4.3 | `response.content[0].text` | `str` |
| 5 | `_parse_batch_response()` | `List[Dict]` |
| 6 | 失败行识别 | `Set[int]` (failed_ids) |
| 7 | `map_rows()` | `List[Dict]` |
| 8 | `apply_mapped_revisions()` 接收 | `List[Dict]` |

---

## 批量处理 vs 单行处理对比

| 维度 | 单行处理 (mapper.py) | 批量处理 (mapper2_from_codex.py) |
|------|---------------------|--------------------------------|
| **一次 API 返回** | 1 个 Dict | N 个 Dict（List） |
| **处理 100 行** | 100 次 API 调用 | ~5-10 次 API 调用 |
| **result 类型** | `Dict` | `List[Dict]` |
| **错误处理** | 单行失败不影响其他 | 精准重试失败行 |
| **截断处理** | 无 | 有（丢弃最后行重试） |

---

## 使用示例

```python
from src.extractor import RevisionExtractor
from src.mapper2_from_codex import BatchRevisionMapper
from src.applier import DiffBasedApplier

# 1. 提取
extractor = RevisionExtractor(unpacked_dir)
row_pairs = extractor.extract_row_pairs()
# 类型: List[Dict]

# 2. 批量映射
mapper = BatchRevisionMapper(api_key)
mapped_results = mapper.map_rows(row_pairs)
# 类型: List[Dict]

# 3. 补充 target_current（批量模式需要）
for i, result in enumerate(mapped_results):
    result['target_current'] = row_pairs[i]['target_current']

# 4. 应用
applier = DiffBasedApplier(unpacked_dir)
success_count = applier.apply_mapped_revisions(mapped_results)
# 类型: int

applier.save()
```

---

## 文档信息

- **创建日期**：2026-01-22
- **更新日期**：2026-01-22
- **模式**：批量处理（BatchRevisionMapper）
- **相关文件**：
  - `src/mapper2_from_codex.py`
  - `src/applier.py`
  - `src/extractor.py`
