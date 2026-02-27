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
        temperature: float = 0.0
    ) -> Tuple[str, str]:
        """
        Make an API call to the LLM.

        Args:
            system_prompt: System/instruction prompt
            user_message: User message content
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
        temperature: float = 0.0
    ) -> Tuple[str, str]:
        """
        Make an API call with prompt caching support.

        Args:
            system_prompt_parts: List of prompt parts with cache_control
            user_message: User message content
            temperature: Sampling temperature

        Returns:
            (response_text, stop_reason)
        """
        pass


class AnthropicClient(LLMClient):
    """Anthropic Claude API client."""

    # Anthropic API requires max_tokens, so we use model's max output limit
    # Source: https://docs.anthropic.com/en/docs/about-claude/models/overview
    MODEL_MAX_TOKENS = {
        "claude-opus-4-6": 128000,
        "claude-sonnet-4-6": 64000,
        "claude-haiku-4-5-20251001": 64000,
        "claude-sonnet-4-5-20250929": 64000,
        "claude-opus-4-5-20251101": 64000,
        "claude-opus-4-1-20250805": 32000,
        "claude-sonnet-4-20250514": 64000,
        "claude-opus-4-20250514": 32000,
    }
    DEFAULT_MAX_TOKENS = 64000

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = self.MODEL_MAX_TOKENS.get(model, self.DEFAULT_MAX_TOKENS)

    def call(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.0
    ) -> Tuple[str, str]:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text, response.stop_reason

    def call_with_cache(
        self,
        system_prompt_parts: List[Dict],
        user_message: str,
        temperature: float = 0.0
    ) -> Tuple[str, str]:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
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
        temperature: float = 0.0
    ) -> Tuple[str, str]:
        response = self.client.chat.completions.create(
            model=self.model,
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
        temperature: float = 0.0
    ) -> Tuple[str, str]:
        # OpenAI-compatible APIs don't support cache_control
        # Combine parts into single system prompt
        system_text = "".join(part.get("text", "") for part in system_prompt_parts)
        return self.call(system_text, user_message, temperature)


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
        }

        response = requests.post(url, json=payload)
        result = response.json()

        return result.get("result", ""), "stop"

    def call_with_cache(
        self,
        system_prompt_parts: List[Dict],
        user_message: str,
        temperature: float = 0.0
    ) -> Tuple[str, str]:
        system_text = "".join(part.get("text", "") for part in system_prompt_parts)
        return self.call(system_text, user_message, temperature)


# ================================================================================
# LLM Client Factory
# ================================================================================

def create_llm_client(provider: str, api_key: str = None, model: str = None) -> LLMClient:
    """
    Factory function to create LLM clients.

    Args:
        provider: Provider name (anthropic, deepseek, qwen, wenxin, doubao, zhipu, openai)
        api_key: API key (read from environment variable)
        model: Model name (defaults to provider's recommended model)

    Returns:
        LLMClient instance
    """
    provider = provider.lower()

    PROVIDER_ENV_KEYS = {
        "anthropic": "ANTHROPIC_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "qwen": "QWEN_API_KEY",
        "wenxin": "WENXIN_API_KEY",
        "doubao": "DOUBAO_API_KEY",
        "zhipu": "ZHIPU_API_KEY",
        "openai": "OPENAI_API_KEY",
    }

    # Provider configurations
    PROVIDERS = {
        "anthropic": {
            "default_model": "claude-sonnet-4-20250514",
            "client_class": AnthropicClient,
        },
        "deepseek": {
            "default_model": "deepseek-chat",
            "base_url": "https://api.deepseek.com",
            "client_class": OpenAICompatibleClient,
        },
        "qwen": {
            "default_model": "qwen-plus",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "client_class": OpenAICompatibleClient,
        },
        "wenxin": {
            "default_model": "ernie-4.0",
            "client_class": WenxinClient,
        },
        "doubao": {
            "default_model": "doubao-pro-32k",
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "client_class": OpenAICompatibleClient,
        },
        "zhipu": {
            "default_model": "glm-4",
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "client_class": OpenAICompatibleClient,
        },
        "openai": {
            "default_model": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
            "client_class": OpenAICompatibleClient,
        },
    }

    if provider not in PROVIDERS:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(f"Unknown provider: {provider}. Available: {available}")

    # Read API key from environment variable
    env_key = PROVIDER_ENV_KEYS[provider]
    api_key = os.getenv(env_key, "")
    if not api_key:
        raise ValueError(f"API key required. Set {env_key} environment variable.")

    config = PROVIDERS[provider]
    model = model or config["default_model"]

    # Create client based on client_class
    if config["client_class"] == WenxinClient:
        secret_key = os.getenv("WENXIN_SECRET_KEY", "")
        if not secret_key:
            raise ValueError("Wenxin requires WENXIN_SECRET_KEY environment variable.")
        return WenxinClient(api_key, secret_key, model)
    elif config["client_class"] == AnthropicClient:
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
        model: str = None,
        strategy: str = "max_tokens",
        output_safety_ratio: float = 0.7,
        row_base_tokens: int = 80,
        row_per_char: float = 0.2,
        retry_shrink_ratio: float = 0.6,
    ):
        """
        Initialize the mapper.

        Args:
            provider: LLM provider (anthropic, deepseek, qwen, wenxin, doubao, zhipu, openai)
            model: Model name (or use provider default)
            strategy: "max_tokens" or "batch"
            output_safety_ratio: Safety margin for batch output budgeting
            row_base_tokens: Base token cost per row estimate (batch strategy)
            row_per_char: Token cost per character estimate (batch strategy)
            retry_shrink_ratio: Budget shrink ratio for batch retries
        """
        self.provider = provider.lower()
        self.strategy = strategy

        # Create LLM client
        self.client = create_llm_client(self.provider, model)

        # Batch strategy parameters
        self.output_safety_ratio = output_safety_ratio
        self.row_base_tokens = row_base_tokens
        self.row_per_char = row_per_char
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
        使用"无进展检测"代替固定重试次数，避免长文档数据丢失。
        """
        results = []
        done_ids = set()
        pending_rows = row_pairs.copy()
        target_by_row = {row["row_index"]: row["target_current"] for row in row_pairs}

        no_progress_count = 0
        max_no_progress = 3  # 连续 3 次无进展才停止
        call_count = 0

        while pending_rows:
            call_count += 1
            previous_pending_count = len(pending_rows)

            print(f"  [max_tokens] 第 {call_count} 次调用: 发送 {len(pending_rows)} 行，顶格输出...")

            # Build and send
            system_parts = self._build_batch_system_prompt(source_lang, target_lang)
            user_message = self._build_batch_user_message(pending_rows)

            response_text, stop_reason = self.client.call_with_cache(
                system_parts, user_message, temperature=0.0
            )

            if stop_reason in ("max_tokens", "length"):
                print(f"  [max_tokens] 达到输出上限，正则抢救已输出内容...")

            # Parse with regex salvage
            parsed = self._salvage_valid_results(response_text)

            # Collect results
            for item in parsed:
                item["target_current"] = target_by_row.get(item["row_index"], "")
                results.append(item)
                done_ids.add(item["row_index"])

            print(f"  [max_tokens] 本轮拿到 {len(parsed)} 个有效结果")

            # Find missing rows
            pending_rows = [row for row in pending_rows if row["row_index"] not in done_ids]

            # 检测是否有进展
            if len(pending_rows) == previous_pending_count:
                no_progress_count += 1
                print(f"  [max_tokens] 警告: 本轮无进展 ({no_progress_count}/{max_no_progress})")
                if no_progress_count >= max_no_progress:
                    print(f"  [max_tokens] 错误: 连续 {max_no_progress} 次无进展，停止。剩余 {len(pending_rows)} 行未处理")
                    break
            else:
                no_progress_count = 0  # 有进展，重置计数

            if pending_rows:
                print(f"  [max_tokens] 还剩 {len(pending_rows)} 行未完成，继续下一次调用...")

        return results

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
        使用"无进展检测"避免无限循环。
        """
        results_by_row: Dict[int, Dict] = {}
        pending_rows = row_pairs.copy()
        target_by_row = {row["row_index"]: row["target_current"] for row in row_pairs}

        batch_output_limit = int(self.max_output_tokens * self.output_safety_ratio)

        no_progress_count = 0
        max_no_progress = 3
        round_count = 0

        while pending_rows:
            round_count += 1
            previous_pending_count = len(pending_rows)

            batches = self._build_batches(pending_rows, batch_output_limit)
            print(f"  [batch] Round {round_count}: {len(pending_rows)} rows in {len(batches)} batches")

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

            # 检测是否有进展
            if len(pending_rows) == previous_pending_count:
                no_progress_count += 1
                print(f"  [batch] 警告: 本轮无进展 ({no_progress_count}/{max_no_progress})")
                if no_progress_count >= max_no_progress:
                    print(f"  [batch] 错误: 连续 {max_no_progress} 次无进展，停止。剩余 {len(pending_rows)} 行未处理")
                    break
            else:
                no_progress_count = 0

            # Shrink budget for retries (more conservative batching)
            if pending_rows:
                batch_output_limit = max(
                    200,
                    int(batch_output_limit * self.retry_shrink_ratio)
                )
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
            system_parts, user_message, temperature=0.0
        )

        # 先尝试 json.loads 直接解析（batch 策略预期输出完整）
        parsed = self._parse_json_response(response_text)
        if not parsed:
            # 解析失败，用正则抢救
            parsed = self._salvage_valid_results(response_text)

        parsed_ids = {item["row_index"] for item in parsed}
        batch_ids = {row["row_index"] for row in batch}
        failed_ids = batch_ids - parsed_ids

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
        system_text = f"""You are a bilingual legal translator.

TASK: Apply source text changes to target text.
- Understand semantic changes from source_before to source_after in {source_lang}
- Apply minimal necessary changes to target_current in {target_lang}

OUTPUT FORMAT - STRICTLY FOLLOW:
1. Output a JSON array ONLY
2. NO markdown code fences (no ```)
3. NO explanatory text before or after the JSON
4. Each object has exactly 4 fields in this EXACT order:
   row_index, target_after, confidence, explanation

EXAMPLE OUTPUT:
[{{"row_index": 0, "target_after": "translated text", "confidence": 0.95, "explanation": "reason"}}]

FIELD RULES:
- row_index: integer, must match input row_index
- target_after: string, the translated result
- confidence: float between 0 and 1
- explanation: string, brief reason (use "" if none)

STRING ESCAPING (CRITICAL):
- Quotes inside strings: use \\"
- Backslashes inside strings: use \\\\
- Newlines inside strings: use \\n
- Output must be valid JSON"""

        return [
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"}
            }
        ]

    def _build_batch_user_message(self, batch: List[Dict]) -> str:
        """Build user message for multi-row mapping."""
        json_text = json.dumps(batch, ensure_ascii=False)
        return f"INPUT:\n{json_text}"

    # --------------------------------------------------------------------------
    # Response Parsing
    # --------------------------------------------------------------------------

    def _parse_json_response(self, response_text: str) -> List[Dict]:
        """
        尝试直接用 json.loads 解析完整响应。
        用于 batch 策略（预期输出完整不截断）。
        """
        text = response_text.strip()
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [
                    item for item in data
                    if self._is_valid_result(item)
                ]
        except Exception:
            pass
        return []

    def _salvage_valid_results(self, text: str) -> List[Dict]:
        """
        从响应中提取所有完整有效的结果对象。
        用于 max_tokens 策略（输出可能被截断）。

        正则精确匹配 prompt 规定的格式：
        {"row_index": int, "target_after": str, "confidence": float, "explanation": str}
        """
        # 精确匹配 prompt 规定的格式：字段顺序固定
        pattern = re.compile(
            r'\{\s*"row_index"\s*:\s*\d+\s*,\s*'
            r'"target_after"\s*:\s*"(?:[^"\\]|\\.)*"\s*,\s*'
            r'"confidence"\s*:\s*[\d.]+\s*,\s*'
            r'"explanation"\s*:\s*"(?:[^"\\]|\\.)*"\s*\}'
        )

        results = []
        for match in pattern.finditer(text):
            try:
                obj = json.loads(match.group(0))
                if self._is_valid_result(obj):
                    results.append(obj)
            except Exception:
                continue

        return results

    def _is_valid_result(self, obj: Any) -> bool:
        """验证对象是否包含所有必要字段且类型正确"""
        return (
            isinstance(obj, dict) and
            isinstance(obj.get("row_index"), int) and
            isinstance(obj.get("target_after"), str) and
            isinstance(obj.get("confidence"), (int, float)) and
            isinstance(obj.get("explanation"), str)
        )


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
