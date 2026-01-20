"""
Mapper V2 (batch, JSON-in/JSON-out) for bilingual revision mapping.

Architecture
------------
Input rows (extractor JSON)
    |
    v
[Normalize + Estimate Output Budget]
    |
    v
[Batch Builder: fit rows into output token budget]
    |
    v
[LLM Call (prompt caching)]
    |
    v
[Parse JSON -> Salvage objects -> Identify failed rows]
    |
    v
[Retry failed rows only (smaller batches)]
    |
    v
Output: list of {row_index, target_after, confidence, explanation}

Design notes
------------
- Speed-first: batch requests to reduce API calls.
- Output-length is not controllable; max_tokens is an upper bound, so we
  estimate output cost and keep batches safely below the limit.
- JSON-in/JSON-out to avoid extra preprocessing.
- Fault tolerance: if full JSON parsing fails, salvage valid objects; retry
  only failed rows.
- Truncation safety: if stop_reason == "max_tokens", drop the last result and
  retry that row.
- ASCII-only source file; runtime JSON can include escaped Unicode.
"""

from __future__ import annotations

from typing import Dict, List, Tuple, Any
import json
import re

import anthropic


class BatchRevisionMapper:
    """Batch mapper with output-budgeted chunking and precise retries."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_output_tokens: int = 2000,
        output_safety_ratio: float = 0.7,
        row_base_tokens: int = 80,
        row_per_char: float = 0.2,
        max_retries: int = 2,
        retry_shrink_ratio: float = 0.6,
    ) -> None:
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        self.max_output_tokens = max_output_tokens
        self.output_safety_ratio = output_safety_ratio
        self.row_base_tokens = row_base_tokens
        self.row_per_char = row_per_char
        self.max_retries = max_retries
        self.retry_shrink_ratio = retry_shrink_ratio

        self._cached_system_prompt = None
        self._cached_source_lang = None
        self._cached_target_lang = None

    # -----------------------------
    # Public API
    # -----------------------------

    def map_rows(
        self,
        rows: List[Dict[str, Any]],
        source_lang: str = "Chinese",
        target_lang: str = "English",
    ) -> List[Dict[str, Any]]:
        """Map revisions for all rows with batch processing and retries."""
        normalized = self._normalize_rows(rows)

        results_by_row: Dict[int, Dict[str, Any]] = {}
        pending_rows = normalized

        batch_output_limit = int(self.max_output_tokens * self.output_safety_ratio)

        for attempt in range(self.max_retries + 1):
            if not pending_rows:
                break

            batches = self._build_batches(pending_rows, batch_output_limit)
            failed_rows: List[Dict[str, Any]] = []

            for batch in batches:
                batch_results, batch_failed = self._map_batch(
                    batch, source_lang, target_lang
                )
                for item in batch_results:
                    results_by_row[item["row_index"]] = item
                failed_rows.extend(batch_failed)

            pending_rows = failed_rows

            # Shrink budget for retries to reduce truncation risk.
            batch_output_limit = int(batch_output_limit * self.retry_shrink_ratio)
            if batch_output_limit < 200:
                batch_output_limit = 200

        # Return results in input order where possible.
        ordered = []
        for row in normalized:
            idx = row["row_index"]
            if idx in results_by_row:
                ordered.append(results_by_row[idx])
        return ordered

    # -----------------------------
    # Batch mapping
    # -----------------------------

    def _map_batch(
        self,
        batch: List[Dict[str, Any]],
        source_lang: str,
        target_lang: str,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Call the LLM for a batch and return (results, failed_rows)."""
        if not batch:
            return [], []

        system_prompt = self._build_system_prompt(source_lang, target_lang)
        user_message = self._build_user_message(batch)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_output_tokens,
            temperature=0.0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        response_text = response.content[0].text
        stop_reason = response.stop_reason

        parsed = self._parse_batch_response(response_text)
        parsed_ids = {item["row_index"] for item in parsed}
        batch_ids = {row["row_index"] for row in batch}
        failed_ids = batch_ids - parsed_ids

        # If truncated, treat the last row as failed and drop last parsed item.
        if stop_reason == "max_tokens":
            if parsed:
                last = parsed.pop()
                parsed_ids.discard(last.get("row_index"))
                failed_ids.add(last.get("row_index"))
            failed_ids.add(batch[-1]["row_index"])

        # Build failure list
        failed_rows = [row for row in batch if row["row_index"] in failed_ids]

        return parsed, failed_rows

    # -----------------------------
    # Helpers
    # -----------------------------

    def _normalize_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        for row in rows:
            idx = row.get("row_index", row.get("row"))
            if idx is None:
                continue
            normalized.append(
                {
                    "row_index": int(idx),
                    "source_before": row.get("source_before", ""),
                    "source_after": row.get("source_after", ""),
                    "target_current": row.get("target_current", ""),
                }
            )
        return normalized

    def _build_batches(
        self, rows: List[Dict[str, Any]], output_budget: int
    ) -> List[List[Dict[str, Any]]]:
        batches: List[List[Dict[str, Any]]] = []
        current: List[Dict[str, Any]] = []
        used = 0

        for row in rows:
            cost = self._estimate_row_output_tokens(row)
            if current and used + cost > output_budget:
                batches.append(current)
                current = []
                used = 0
            current.append(row)
            used += cost

        if current:
            batches.append(current)

        return batches

    def _estimate_row_output_tokens(self, row: Dict[str, Any]) -> int:
        # Heuristic: output size scales with text length and a base cost.
        text_len = max(
            len(row.get("source_before", "")),
            len(row.get("source_after", "")),
            len(row.get("target_current", "")),
        )
        return int(self.row_base_tokens + self.row_per_char * text_len)

    def _build_system_prompt(self, source_lang: str, target_lang: str) -> List[Dict]:
        if (
            self._cached_system_prompt is None
            or self._cached_source_lang != source_lang
            or self._cached_target_lang != target_lang
        ):
            system_text = f"""You are a professional bilingual legal translator.

Task
- Understand semantic changes from source_before to source_after in {source_lang}.
- Apply the minimal necessary changes to target_current in {target_lang}.
- Return the full target_after text.

Output format (JSON array only, no extra text)
Each item must include:
- row_index (int)
- target_after (string)
- confidence (0-1, float)
- explanation (string, optional)
"""
            self._cached_system_prompt = [
                {
                    "type": "text",
                    "text": system_text,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
            self._cached_source_lang = source_lang
            self._cached_target_lang = target_lang

        return self._cached_system_prompt

    def _build_user_message(self, batch: List[Dict[str, Any]]) -> str:
        payload = [
            {
                "row_index": row["row_index"],
                "source_before": row["source_before"],
                "source_after": row["source_after"],
                "target_current": row["target_current"],
            }
            for row in batch
        ]

        json_text = json.dumps(payload, ensure_ascii=True)
        return (
            "Process the following JSON array and return a JSON array of results.\n"
            "Do not include any text outside the JSON array.\n\n"
            f"INPUT_JSON:\n{json_text}\n"
        )

    def _parse_batch_response(self, response_text: str) -> List[Dict[str, Any]]:
        text = self._strip_code_fence(response_text)

        # Try full JSON parse first.
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "results" in data:
                data = data["results"]
            return self._normalize_results(data)
        except Exception:
            pass

        # Salvage partial objects if full parse fails.
        salvaged = self._salvage_objects(text)
        return self._normalize_results(salvaged)

    def _strip_code_fence(self, text: str) -> str:
        if "```" not in text:
            return text.strip()
        start = text.find("```")
        end = text.find("```", start + 3)
        if end == -1:
            return text[start + 3 :].strip()
        return text[start + 3 : end].strip()

    def _salvage_objects(self, text: str) -> List[Dict[str, Any]]:
        # Extract JSON objects that contain row_index. This is best-effort.
        pattern = re.compile(r"\{[^{}]*\"row_index\"\s*:\s*\d+[^{}]*\}")
        results = []
        for match in pattern.finditer(text):
            chunk = match.group(0)
            try:
                results.append(json.loads(chunk))
            except Exception:
                continue
        return results

    def _normalize_results(self, data: Any) -> List[Dict[str, Any]]:
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
            if "confidence" not in item:
                item["confidence"] = 0.8
            if "explanation" not in item:
                item["explanation"] = ""
            normalized.append(item)
        return normalized


# Example usage (optional)
if __name__ == "__main__":
    import os

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise SystemExit("Missing ANTHROPIC_API_KEY")

    mapper = BatchRevisionMapper(api_key)
    sample_rows = [
        {
            "row_index": 0,
            "source_before": "AI is changing our life.",
            "source_after": "AI has changed our life.",
            "target_current": "AI is changing our life.",
        }
    ]

    results = mapper.map_rows(sample_rows, source_lang="English", target_lang="English")
    print(results)
