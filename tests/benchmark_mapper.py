"""
================================================================================
Mapper Benchmark - Compare LLM Providers and Strategies
================================================================================

This script benchmarks the RevisionMapper across:
- Different LLM providers (Anthropic, DeepSeek, Qwen, etc.)
- Different strategies (max_tokens vs batch)

Usage:
    python tests/benchmark_mapper.py

Requires at least one API key to be set in environment.

================================================================================
"""

import os
import sys
import time
import json
from typing import Dict, List, Any

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.mapper import RevisionMapper, create_llm_client
from src.config import Config, LLM_PROVIDERS


# ================================================================================
# Test Data
# ================================================================================

TEST_ROW_PAIRS = [
    {
        "row_index": 0,
        "source_before": "AI is changing our life.",
        "source_after": "AI has changed our life.",
        "target_current": "AI is changing our life."
    },
    {
        "row_index": 1,
        "source_before": "The agreement is valid for one year.",
        "source_after": "The agreement is valid for two years.",
        "target_current": "The agreement is valid for one year."
    },
    {
        "row_index": 2,
        "source_before": "Party A should pay the amount.",
        "source_after": "Party A shall pay the amount.",
        "target_current": "Party A should pay the amount."
    },
    {
        "row_index": 3,
        "source_before": "This clause may be amended.",
        "source_after": "This clause cannot be amended.",
        "target_current": "This clause may be amended."
    },
    {
        "row_index": 4,
        "source_before": "Payment is due within 30 days.",
        "source_after": "Payment is due within 14 days.",
        "target_current": "Payment is due within 30 days."
    },
]

# Expected results for validation
EXPECTED_RESULTS = {
    0: {"contains": ["changed", "has changed"]},
    1: {"contains": ["two years"]},
    2: {"contains": ["shall"]},
    3: {"contains": ["cannot"]},
    4: {"contains": ["14 days"]},
}


# ================================================================================
# Benchmark Functions
# ================================================================================

def get_available_providers() -> List[str]:
    """Get list of providers with configured API keys."""
    available = []
    for provider in LLM_PROVIDERS:
        api_key = Config.get_api_key(provider)
        if api_key:
            available.append(provider)
    return available


def validate_result(result: Dict, expected: Dict) -> bool:
    """Check if result contains expected text."""
    target_after = result.get("target_after", "").lower()
    for keyword in expected.get("contains", []):
        if keyword.lower() in target_after:
            return True
    return False


def benchmark_single_provider(
    provider: str,
    strategy: str,
    row_pairs: List[Dict]
) -> Dict[str, Any]:
    """
    Benchmark a single provider/strategy combination.

    Returns:
        {
            "provider": str,
            "strategy": str,
            "total_time": float,
            "avg_time_per_row": float,
            "success_count": int,
            "total_rows": int,
            "results": List[Dict],
            "error": str (if failed)
        }
    """
    result = {
        "provider": provider,
        "strategy": strategy,
        "total_rows": len(row_pairs),
    }

    try:
        # Create mapper
        mapper = RevisionMapper(
            provider=provider,
            strategy=strategy
        )

        # Run benchmark
        start_time = time.time()

        mapped_results = mapper.map_row_pairs(
            row_pairs,
            source_lang="English",
            target_lang="English"
        )

        end_time = time.time()

        # Calculate metrics
        total_time = end_time - start_time
        result["total_time"] = round(total_time, 2)
        result["avg_time_per_row"] = round(total_time / len(row_pairs), 2)

        # Validate results
        success_count = 0
        for mapped in mapped_results:
            row_idx = mapped.get("row_index")
            if row_idx in EXPECTED_RESULTS:
                if validate_result(mapped, EXPECTED_RESULTS[row_idx]):
                    success_count += 1

        result["success_count"] = success_count
        result["results"] = mapped_results

    except Exception as e:
        result["error"] = str(e)
        result["success_count"] = 0
        result["total_time"] = 0
        result["avg_time_per_row"] = 0

    return result


def run_benchmarks(
    providers: List[str] = None,
    strategies: List[str] = None,
    num_rows: int = None
) -> List[Dict]:
    """
    Run benchmarks across providers and strategies.

    Args:
        providers: List of providers to test (defaults to all available)
        strategies: List of strategies to test (defaults to both)
        num_rows: Number of test rows to use (defaults to all)

    Returns:
        List of benchmark results
    """
    if providers is None:
        providers = get_available_providers()

    if strategies is None:
        strategies = ["max_tokens", "batch"]

    if num_rows is None:
        row_pairs = TEST_ROW_PAIRS
    else:
        row_pairs = TEST_ROW_PAIRS[:num_rows]

    results = []

    for provider in providers:
        for strategy in strategies:
            print(f"\nBenchmarking: {provider} / {strategy}...")

            result = benchmark_single_provider(provider, strategy, row_pairs)
            results.append(result)

            if "error" in result:
                print(f"  Error: {result['error']}")
            else:
                print(f"  Time: {result['total_time']}s ({result['avg_time_per_row']}s/row)")
                print(f"  Success: {result['success_count']}/{result['total_rows']}")

    return results


def print_summary(results: List[Dict]):
    """Print benchmark summary table."""
    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)

    print(f"\n{'Provider':<12} {'Strategy':<8} {'Time':<10} {'Avg/Row':<10} {'Success':<10}")
    print("-" * 50)

    for r in results:
        if "error" in r:
            status = f"ERROR: {r['error'][:20]}..."
        else:
            status = f"{r['success_count']}/{r['total_rows']}"

        print(f"{r['provider']:<12} {r['strategy']:<8} {r.get('total_time', 0):<10.2f} "
              f"{r.get('avg_time_per_row', 0):<10.2f} {status}")

    print("-" * 50)

    # Find best performer
    valid_results = [r for r in results if "error" not in r]
    if valid_results:
        fastest = min(valid_results, key=lambda x: x["total_time"])
        print(f"\nFastest: {fastest['provider']} / {fastest['strategy']} "
              f"({fastest['total_time']}s)")


def save_results(results: List[Dict], filename: str = "benchmark_results.json"):
    """Save benchmark results to JSON file."""
    output_path = os.path.join(
        os.path.dirname(__file__),
        filename
    )

    # Remove large results for storage
    for r in results:
        if "results" in r:
            r["results"] = [
                {k: v for k, v in item.items() if k != "explanation"}
                for item in r["results"]
            ]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_path}")


# ================================================================================
# Main Entry
# ================================================================================

def main():
    """Main entry point."""
    print("=" * 70)
    print("Mapper Benchmark Tool")
    print("=" * 70)

    # Check available providers
    available = get_available_providers()

    if not available:
        print("\nNo API keys configured. Please set one of:")
        for provider, config in LLM_PROVIDERS.items():
            print(f"  - {config['env_key']} for {provider}")
        sys.exit(1)

    print(f"\nAvailable providers: {', '.join(available)}")
    print(f"Test rows: {len(TEST_ROW_PAIRS)}")

    # Run benchmarks
    results = run_benchmarks(
        providers=available,
        strategies=["max_tokens", "batch"]
    )

    # Print summary
    print_summary(results)

    # Save results
    save_results(results)


if __name__ == "__main__":
    main()
