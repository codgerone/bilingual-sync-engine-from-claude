"""
================================================================================
LLM Mapper - Multi-Provider Revision Mapping with Dual Strategies
================================================================================

Architecture Overview
---------------------

                    +-----------------------+
                    |    RevisionMapper     |  <-- Main Entry Point
                    |   (strategy switch)   |
                    +-----------+-----------+
                                |
          +---------------------+---------------------+
          |                                           |
          v                                           v
    +-------------+                           +-------------+
    | "max_tokens"|                           |   "batch"   |
    |  Strategy   |                           |   Strategy  |
    +-------------+                           +-------------+
    每次调用顶格输出                          预估批次大小
    直到 token 上限                           控制在预算内
    正则抢救解析                              json.loads 解析
    剩余行继续下次调用                        失败时缩小批次重试
          |                                           |
          +---------------------+---------------------+
                                |
                                v
                    +-----------------------+
                    |      LLMClient        |  <-- Abstract Base
                    |  (provider agnostic)  |
                    +-----------------------+
                                |
     +-----------+-------+------+------+------+------+
     |           |       |      |      |      |      |
     v           v       v      v      v      v      v
  Anthropic  DeepSeek  Qwen  Wenxin Doubao  Zhipu  OpenAI
   Client     Client  Client Client Client Client Client

Data Flow
---------
Input (from extractor):
    {
        'row_index': int,
        'source_before': str,
        'source_after': str,
        'target_current': str
    }

Output (to applier):
    {
        'row_index': int,
        'target_current': str,
        'target_after': str,
        'explanation': str,
        'confidence': float
    }

Strategies
----------
1. "max_tokens" - 每次调用顶格输出到 token 上限
   - 特点: 速度最快，每次调用都用满输出配额
   - 解析: 正则抢救 (从截断输出中提取完整 JSON 对象)
   - 重试: 剩余未完成的行进入下一次调用

2. "batch" - 预估批次大小，控制在输出预算内
   - 特点: 解析可靠，行为可预测
   - 解析: json.loads (批次大小确保输出不会截断)
   - 重试: 缩小预算重新分批

================================================================================
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
import json
import re
import os


# ================================================================================
# LLM Client Abstraction Layer
# ================================================================================

class LLMClient(ABC):
    """
    Abstract base class for LLM API clients.

    Provides a unified interface for different LLM providers.
    All providers must implement the call() method.
    """

    @abstractmethod
    def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2000,
        temperature: float = 0.0
    ) -> Tuple[str, str]:
        """
        Make an API call to the LLM.

        Args:
            system_prompt: System/instruction prompt
            user_message: User message content
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 = deterministic)

        Returns:
            (response_text, stop_reason)
        """
        pass

    @abstractmethod
    def call_with_cache(
        self,
        system_prompt_parts: List[Dict],
        user_message: str,
        max_tokens: int = 2000,
        temperature: float = 0.0
    ) -> Tuple[str, str]:
        """
        Make an API call with prompt caching support.

        Args:
            system_prompt_parts: List of prompt parts with cache_control
            user_message: User message content
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            (response_text, stop_reason)
        """
        pass


class AnthropicClient(LLMClient):
    """Anthropic Claude API client."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2000,
        temperature: float = 0.0
    ) -> Tuple[str, str]:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text, response.stop_reason

    def call_with_cache(
        self,
        system_prompt_parts: List[Dict],
        user_message: str,
        max_tokens: int = 2000,
        temperature: float = 0.0
    ) -> Tuple[str, str]:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt_parts,
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text, response.stop_reason


class OpenAICompatibleClient(LLMClient):
    """
    OpenAI-compatible API client.

    Works with: DeepSeek, Qwen, Doubao, Zhipu, and other OpenAI-compatible APIs.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        provider_name: str = "OpenAI-Compatible"
    ):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.provider_name = provider_name

    def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2000,
        temperature: float = 0.0
    ) -> Tuple[str, str]:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )
        return response.choices[0].message.content, response.choices[0].finish_reason

    def call_with_cache(
        self,
        system_prompt_parts: List[Dict],
        user_message: str,
        max_tokens: int = 2000,
        temperature: float = 0.0
    ) -> Tuple[str, str]:
        # OpenAI-compatible APIs don't support cache_control
        # Combine parts into single system prompt
        system_text = "".join(part.get("text", "") for part in system_prompt_parts)
        return self.call(system_text, user_message, max_tokens, temperature)


class WenxinClient(LLMClient):
    """
    Baidu Wenxin (ERNIE) API client.

    Uses native Wenxin API format.
    """

    def __init__(self, api_key: str, secret_key: str, model: str = "ernie-4.0"):
        self.api_key = api_key
        self.secret_key = secret_key
        self.model = model
        self._access_token = None

    def _get_access_token(self) -> str:
        """Get or refresh access token."""
        if self._access_token:
            return self._access_token

        import requests
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }
        response = requests.post(url, params=params)
        self._access_token = response.json().get("access_token")
        return self._access_token

    def call(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2000,
        temperature: float = 0.0
    ) -> Tuple[str, str]:
        import requests

        access_token = self._get_access_token()
        url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{self.model}?access_token={access_token}"

        payload = {
            "messages": [
                {"role": "user", "content": f"{system_prompt}\n\n{user_message}"}
            ],
            "temperature": max(temperature, 0.01),  # Wenxin minimum is 0.01
            "max_output_tokens": max_tokens
        }

        response = requests.post(url, json=payload)
        result = response.json()

        return result.get("result", ""), "stop"

    def call_with_cache(
        self,
        system_prompt_parts: List[Dict],
        user_message: str,
        max_tokens: int = 2000,
        temperature: float = 0.0
    ) -> Tuple[str, str]:
        system_text = "".join(part.get("text", "") for part in system_prompt_parts)
        return self.call(system_text, user_message, max_tokens, temperature)


# ================================================================================
# LLM Client Factory
# ================================================================================

def create_llm_client(
    provider: str,
    api_key: str = None,
    model: str = None,
    **kwargs
) -> LLMClient:
    """
    Factory function to create LLM clients.

    Args:
        provider: Provider name (anthropic, deepseek, qwen, wenxin, doubao, zhipu, openai)
        api_key: API key (defaults to environment variable)
        model: Model name (defaults to provider's recommended model)
        **kwargs: Additional provider-specific arguments

    Returns:
        LLMClient instance
    """
    provider = provider.lower()

    # Provider configurations
    PROVIDERS = {
        "anthropic": {
            "env_key": "ANTHROPIC_API_KEY",
            "default_model": "claude-sonnet-4-20250514",
            "client_class": AnthropicClient,
        },
        "deepseek": {
            "env_key": "DEEPSEEK_API_KEY",
            "default_model": "deepseek-chat",
            "base_url": "https://api.deepseek.com",
            "client_class": OpenAICompatibleClient,
        },
        "qwen": {
            "env_key": "QWEN_API_KEY",
            "default_model": "qwen-plus",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "client_class": OpenAICompatibleClient,
        },
        "doubao": {
            "env_key": "DOUBAO_API_KEY",
            "default_model": "doubao-pro-32k",
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "client_class": OpenAICompatibleClient,
        },
        "zhipu": {
            "env_key": "ZHIPU_API_KEY",
            "default_model": "glm-4",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "client_class": OpenAICompatibleClient,
        },
        "openai": {
            "env_key": "OPENAI_API_KEY",
            "default_model": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
            "client_class": OpenAICompatibleClient,
        },
    }

    if provider not in PROVIDERS:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(f"Unknown provider: {provider}. Available: {available}")

    config = PROVIDERS[provider]

    # Get API key from parameter or environment
    if api_key is None:
        api_key = os.getenv(config["env_key"], "")
        if not api_key:
            raise ValueError(
                f"API key required. Set {config['env_key']} environment variable "
                f"or pass api_key parameter."
            )

    # Get model
    if model is None:
        model = config["default_model"]

    # Special handling for Wenxin (needs secret_key)
    if provider == "wenxin":
        secret_key = kwargs.get("secret_key") or os.getenv("WENXIN_SECRET_KEY", "")
        if not secret_key:
            raise ValueError("Wenxin requires secret_key (set WENXIN_SECRET_KEY)")
        return WenxinClient(api_key, secret_key, model)

    # Create client
    if config["client_class"] == AnthropicClient:
        return AnthropicClient(api_key, model)
    else:
        return OpenAICompatibleClient(
            api_key=api_key,
            base_url=config["base_url"],
            model=model,
            provider_name=provider.capitalize()
        )


# ================================================================================
# Revision Mapper - Main Class
# ================================================================================

class RevisionMapper:
    """
    Unified revision mapper with multi-LLM support and dual strategies.

    Strategies:
        - "max_tokens": 每次调用顶格输出到 token 上限，正则抢救解析，剩余行继续下次调用
        - "batch": 预估批次大小，json.loads 解析，失败时缩小批次重试

    Usage:
        mapper = RevisionMapper(provider="deepseek", strategy="max_tokens")
        results = mapper.map_row_pairs(row_pairs, source_lang="Chinese", target_lang="English")
    """

    def __init__(
        self,
        provider: str = "anthropic",
        api_key: str = None,
        model: str = None,
        strategy: str = "max_tokens",
        max_output_tokens: int = 4096,
        # batch strategy parameters
        output_safety_ratio: float = 0.7,
        row_base_tokens: int = 80,
        row_per_char: float = 0.2,
        # shared retry parameters
        max_retries: int = 2,
        retry_shrink_ratio: float = 0.6,
        **kwargs
    ):
        """
        Initialize the mapper.

        Args:
            provider: LLM provider (anthropic, deepseek, qwen, etc.)
            api_key: API key (or use environment variable)
            model: Model name (or use provider default)
            strategy: "max_tokens" or "batch"
            max_output_tokens: Max tokens for API call output
            output_safety_ratio: Safety margin for batch output budgeting
            row_base_tokens: Base token cost per row estimate (batch strategy)
            row_per_char: Token cost per character estimate (batch strategy)
            max_retries: Max retry attempts for failed/missing rows
            retry_shrink_ratio: Budget shrink ratio for retries
        """
        # Create LLM client
        self.client = create_llm_client(provider, api_key, model, **kwargs)
        self.provider = provider
        self.strategy = strategy

        # Output parameters
        self.max_output_tokens = max_output_tokens

        # Batch strategy parameters
        self.output_safety_ratio = output_safety_ratio
        self.row_base_tokens = row_base_tokens
        self.row_per_char = row_per_char

        # Shared retry parameters
        self.max_retries = max_retries
        self.retry_shrink_ratio = retry_shrink_ratio

    # --------------------------------------------------------------------------
    # Public API
    # --------------------------------------------------------------------------

    def map_row_pairs(
        self,
        row_pairs: List[Dict[str, Any]],
        source_lang: str = "Chinese",
        target_lang: str = "English"
    ) -> List[Dict[str, Any]]:
        """
        Main entry point: Map revisions for all rows.

        Args:
            row_pairs: List from extractor.extract_row_pairs()
                      Each item: {row_index, source_before, source_after, target_current}
            source_lang: Source language name
            target_lang: Target language name

        Returns:
            List of mapping results:
            {row_index, target_current, target_after, explanation, confidence}
        """
        if self.strategy == "batch":
            return self._map_batch_strategy(row_pairs, source_lang, target_lang)
        else:
            # Default: max_tokens strategy
            return self._map_max_tokens_strategy(row_pairs, source_lang, target_lang)

    def map_text_revision(
        self,
        source_before: str,
        source_after: str,
        target_current: str,
        source_lang: str = "Chinese",
        target_lang: str = "English"
    ) -> Dict[str, Any]:
        """
        Convenience method: Map a single revision.

        Wraps in a one-element list and calls map_row_pairs.

        Args:
            source_before: Source text before revision
            source_after: Source text after revision
            target_current: Current target text
            source_lang: Source language name
            target_lang: Target language name

        Returns:
            {target_after, explanation, confidence}
        """
        row_pairs = [{
            "row_index": 0,
            "source_before": source_before,
            "source_after": source_after,
            "target_current": target_current,
        }]
        results = self.map_row_pairs(row_pairs, source_lang, target_lang)
        if results:
            return results[0]
        return {"target_after": "", "confidence": 0.0, "explanation": "", "error": "no result"}

    # --------------------------------------------------------------------------
    # max_tokens Strategy: 每次调用顶格输出，正则抢救，剩余行继续下次调用
    # --------------------------------------------------------------------------

    def _map_max_tokens_strategy(
        self,
        row_pairs: List[Dict],
        source_lang: str,
        target_lang: str
    ) -> List[Dict]:
        """
        每次调用 API 都顶格输出到 max_tokens 上限，用正则抢救解析结果。
        剩余未完成的行进入下一次调用，重复直到所有行都完成。

        对于短文档可能一次调用就够；对于长文档会自动分多次调用完成。
        """
        results_by_row: Dict[int, Dict] = {}
        pending_rows = row_pairs.copy()
        target_by_row = {row["row_index"]: row["target_current"] for row in row_pairs}

        for attempt in range(self.max_retries + 1):
            if not pending_rows:
                break

            print(f"  [max_tokens] 第 {attempt + 1} 次调用: 发送 {len(pending_rows)} 行，顶格输出...")

            # Build and send
            system_parts = self._build_batch_system_prompt(source_lang, target_lang)
            user_message = self._build_batch_user_message(pending_rows)

            response_text, stop_reason = self.client.call_with_cache(
                system_parts, user_message,
                max_tokens=self.max_output_tokens, temperature=0.0
            )

            if stop_reason in ("max_tokens", "length"):
                print(f"  [max_tokens] 达到输出上限，正则抢救已输出内容...")

            # Parse: always use regex salvage (works for both complete and truncated)
            parsed = self._salvage_objects(response_text)
            parsed = self._normalize_batch_results(parsed)

            # Drop last object if truncated (likely incomplete)
            if stop_reason in ("max_tokens", "length") and parsed:
                dropped = parsed.pop()
                print(f"  [max_tokens] 丢弃最后一个对象 (row {dropped.get('row_index')})，截断不可信")

            # Collect results
            for item in parsed:
                item["target_current"] = target_by_row.get(item["row_index"], "")
                results_by_row[item["row_index"]] = item

            print(f"  [max_tokens] 本轮拿到 {len(parsed)} 个有效结果")

            # Find missing rows
            done_ids = set(results_by_row.keys())
            pending_rows = [row for row in pending_rows if row["row_index"] not in done_ids]

            if pending_rows:
                print(f"  [max_tokens] 还剩 {len(pending_rows)} 行未完成，继续下一次调用...")

        # Return results in input order
        return [
            results_by_row[pair["row_index"]]
            for pair in row_pairs
            if pair["row_index"] in results_by_row
        ]

    # --------------------------------------------------------------------------
    # batch Strategy: Pre-estimated batches, json.loads parsing
    # --------------------------------------------------------------------------

    def _map_batch_strategy(
        self,
        row_pairs: List[Dict],
        source_lang: str,
        target_lang: str
    ) -> List[Dict]:
        """
        Split rows into pre-estimated batches sized to fit output budget.
        Each batch should complete without truncation, parsed with json.loads.
        """
        results_by_row: Dict[int, Dict] = {}
        pending_rows = row_pairs.copy()
        target_by_row = {row["row_index"]: row["target_current"] for row in row_pairs}

        batch_output_limit = int(self.max_output_tokens * self.output_safety_ratio)

        for attempt in range(self.max_retries + 1):
            if not pending_rows:
                break

            batches = self._build_batches(pending_rows, batch_output_limit)
            print(f"  [batch] Attempt {attempt + 1}: {len(pending_rows)} rows in {len(batches)} batches")

            failed_rows: List[Dict] = []

            for batch_idx, batch in enumerate(batches):
                print(f"  [batch] Batch {batch_idx + 1}/{len(batches)}: {len(batch)} rows")

                batch_results, batch_failed = self._map_single_batch(
                    batch, source_lang, target_lang
                )

                for item in batch_results:
                    item["target_current"] = target_by_row.get(item["row_index"], "")
                    results_by_row[item["row_index"]] = item

                failed_rows.extend(batch_failed)

            pending_rows = failed_rows

            # Shrink budget for retries (more conservative batching)
            batch_output_limit = max(
                200,
                int(batch_output_limit * self.retry_shrink_ratio)
            )

            if pending_rows:
                print(f"  [batch] {len(pending_rows)} rows failed, retrying with smaller batches...")

        # Return results in input order
        return [
            results_by_row[pair["row_index"]]
            for pair in row_pairs
            if pair["row_index"] in results_by_row
        ]

    def _map_single_batch(
        self,
        batch: List[Dict],
        source_lang: str,
        target_lang: str
    ) -> Tuple[List[Dict], List[Dict]]:
        """Map a single batch, return (results, failed_rows)."""
        if not batch:
            return [], []

        system_parts = self._build_batch_system_prompt(source_lang, target_lang)
        user_message = self._build_batch_user_message(batch)

        response_text, stop_reason = self.client.call_with_cache(
            system_parts, user_message, max_tokens=self.max_output_tokens, temperature=0.0
        )

        # Batch strategy: try json.loads first (should work if budget estimate is correct)
        parsed = self._parse_batch_response(response_text)

        parsed_ids = {item["row_index"] for item in parsed}
        batch_ids = {row["row_index"] for row in batch}
        failed_ids = batch_ids - parsed_ids

        # If truncated, drop last result and mark it as failed
        if stop_reason in ("max_tokens", "length"):
            if parsed:
                last = parsed.pop()
                parsed_ids.discard(last.get("row_index"))
                failed_ids.add(last.get("row_index"))

        failed_rows = [row for row in batch if row["row_index"] in failed_ids]
        return parsed, failed_rows

    def _build_batches(
        self,
        rows: List[Dict],
        output_budget: int
    ) -> List[List[Dict]]:
        """Split rows into batches based on estimated output tokens."""
        batches: List[List[Dict]] = []
        current: List[Dict] = []
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

    def _estimate_row_output_tokens(self, row: Dict) -> int:
        """Estimate output token cost for a row."""
        text_len = max(
            len(row.get("source_before", "")),
            len(row.get("source_after", "")),
            len(row.get("target_current", ""))
        )
        return int(self.row_base_tokens + self.row_per_char * text_len)

    # --------------------------------------------------------------------------
    # Prompt Building (shared by both strategies)
    # --------------------------------------------------------------------------

    def _build_batch_system_prompt(self, source_lang: str, target_lang: str) -> List[Dict]:
        """Build system prompt for multi-row mapping."""
        system_text = f"""You are a professional bilingual legal translator.

Task
- Understand semantic changes from source_before to source_after in {source_lang}
- Apply minimal necessary changes to target_current in {target_lang}
- Return the full target_after text

Output format (JSON array only, no extra text)
Each item must include:
- row_index (int)
- target_after (string)
- confidence (0-1, float)
- explanation (string, optional)"""

        return [
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"}
            }
        ]

    def _build_batch_user_message(self, batch: List[Dict]) -> str:
        """Build user message for multi-row mapping."""
        payload = [
            {
                "row_index": row["row_index"],
                "source_before": row["source_before"],
                "source_after": row["source_after"],
                "target_current": row["target_current"]
            }
            for row in batch
        ]

        json_text = json.dumps(payload, ensure_ascii=False)
        return (
            "Process the following JSON array and return a JSON array of results.\n"
            "Do not include any text outside the JSON array.\n\n"
            f"INPUT_JSON:\n{json_text}\n"
        )

    # --------------------------------------------------------------------------
    # Response Parsing
    # --------------------------------------------------------------------------

    def _parse_batch_response(self, response_text: str) -> List[Dict]:
        """Parse batch response: try json.loads first, fall back to regex salvage."""
        text = self._strip_code_fence(response_text)

        # Try full JSON parse
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "results" in data:
                data = data["results"]
            return self._normalize_batch_results(data)
        except Exception:
            pass

        # Fall back to regex salvage
        salvaged = self._salvage_objects(text)
        return self._normalize_batch_results(salvaged)

    def _strip_code_fence(self, text: str) -> str:
        """Remove code fences from response."""
        if "```" not in text:
            return text.strip()
        start = text.find("```")
        # Skip language identifier (e.g., ```json)
        newline = text.find("\n", start)
        if newline != -1:
            start = newline + 1
        else:
            start = start + 3
        end = text.find("```", start)
        if end == -1:
            return text[start:].strip()
        return text[start:end].strip()

    def _salvage_objects(self, text: str) -> List[Dict]:
        """
        Regex salvage: extract all complete JSON objects containing row_index.
        Works on both complete and truncated responses.
        """
        # Strip code fences first
        text = self._strip_code_fence(text)

        pattern = re.compile(r"\{[^{}]*\"row_index\"\s*:\s*\d+[^{}]*\}")
        results = []
        for match in pattern.finditer(text):
            chunk = match.group(0)
            try:
                results.append(json.loads(chunk))
            except Exception:
                continue
        return results

    def _normalize_batch_results(self, data: Any) -> List[Dict]:
        """Normalize and validate batch results."""
        if not isinstance(data, list):
            return []

        normalized = []
        for item in data:
            if not isinstance(item, dict):
                continue
            if "row_index" not in item or "target_after" not in item:
                continue
            item.setdefault("confidence", 0.8)
            item.setdefault("explanation", "")
            normalized.append(item)

        return normalized


# ================================================================================
# Convenience Functions
# ================================================================================

def quick_map(
    source_before: str,
    source_after: str,
    target_current: str,
    provider: str = "anthropic",
    source_lang: str = "Chinese",
    target_lang: str = "English"
) -> str:
    """
    Quick one-liner for single revision mapping.

    Returns the target_after text directly.
    """
    mapper = RevisionMapper(provider=provider, strategy="max_tokens")
    result = mapper.map_text_revision(
        source_before, source_after, target_current,
        source_lang, target_lang
    )
    return result.get("target_after", "")


# ================================================================================
# Usage Example
# ================================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Unified RevisionMapper Demo")
    print("=" * 60)

    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("\nNo ANTHROPIC_API_KEY found. Set it to run the demo:")
        print("  Windows: set ANTHROPIC_API_KEY=your-key-here")
        print("  Linux/Mac: export ANTHROPIC_API_KEY='your-key-here'")
        print("\nAvailable providers:")
        for provider in ["anthropic", "deepseek", "qwen", "doubao", "zhipu", "openai"]:
            print(f"  - {provider}")
        print("\nStrategies:")
        print("  - max_tokens: 每次调用顶格输出，正则抢救 (最快)")
        print("  - batch: 预估批次大小，json.loads 解析 (最稳定)")
        exit(0)

    # Example: max_tokens strategy
    print("\n--- max_tokens strategy: 每次调用顶格输出 ---")
    mapper = RevisionMapper(provider="anthropic", strategy="max_tokens")

    row_pairs = [
        {
            "row_index": 0,
            "source_before": "The agreement is valid for one year.",
            "source_after": "The agreement is valid for two years.",
            "target_current": "The agreement is valid for one year."
        },
        {
            "row_index": 1,
            "source_before": "Party A should pay.",
            "source_after": "Party A shall pay.",
            "target_current": "Party A should pay."
        },
        {
            "row_index": 2,
            "source_before": "This clause may be amended.",
            "source_after": "This clause cannot be amended.",
            "target_current": "This clause may be amended."
        }
    ]

    results = mapper.map_row_pairs(row_pairs, source_lang="English", target_lang="English")

    for r in results:
        print(f"\nRow {r['row_index']}:")
        print(f"  Current: {r['target_current']}")
        print(f"  After:   {r['target_after']}")
        print(f"  Confidence: {r['confidence']}")
