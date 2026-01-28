"""
================================================================================
Bilingual Sync Engine - Main Orchestration Module
================================================================================

Architecture
------------
                       ┌─────────────────┐
                       │BilingualSyncEngine│
                       └────────┬────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        v                       v                       v
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  Extractor   │ ───> │   Mapper     │ ───> │   Applier    │
│(extract rows)│      │(LLM mapping) │      │(apply diffs) │
└──────────────┘      └──────────────┘      └──────────────┘
        │                       │                       │
        v                       v                       v
   row_pairs              mapped_results          document.xml

Data Flow
---------
1. Unpack .docx (ZIP) -> XML files
2. Extract revisions from source column
3. Map revisions via LLM (max_tokens or batch strategy)
4. Apply changes to target column using word-level diff
5. Pack XML files -> .docx

================================================================================
"""

import os
import subprocess
from typing import List, Dict, Optional

from .extractor import RevisionExtractor, decode_html_entities
from .mapper import RevisionMapper
from .applier import DiffBasedApplier
from .config import Config


class BilingualSyncEngine:
    """
    Bilingual Word Document Track Changes Sync Engine.

    Orchestrates the three-module pipeline:
    1. Extractor: Parse OOXML, extract revisions
    2. Mapper: Use LLM to map revisions to target language
    3. Applier: Generate track changes in target column
    """

    def __init__(
        self,
        docx_path: str,
        provider: str = None,
        api_key: str = None,
        model: str = None,
        strategy: str = None,
        source_column: int = 0,
        target_column: int = 1,
        source_lang: str = "Chinese",
        target_lang: str = "English",
        author: str = "Claude"
    ):
        """
        Initialize the sync engine.

        Args:
            docx_path: Path to Word document
            provider: LLM provider (anthropic, deepseek, qwen, etc.)
            api_key: API key (or use environment variable)
            model: Model name (or use provider default)
            strategy: "max_tokens" or "batch" (max_tokens = 每次调用顶格输出)
            source_column: Source language column index (0 = left)
            target_column: Target language column index (1 = right)
            source_lang: Source language name
            target_lang: Target language name
            author: Author name for track changes
        """
        self.docx_path = docx_path
        self.source_column = source_column
        self.target_column = target_column
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.author = author

        # Set up working directory
        self.work_dir = os.path.splitext(docx_path)[0] + "_work"
        self.unpacked_dir = os.path.join(self.work_dir, "unpacked")

        # Use defaults from config if not specified
        self.provider = provider or Config.DEFAULT_PROVIDER
        self.strategy = strategy or Config.DEFAULT_STRATEGY

        # Get API key from environment if not provided
        if api_key is None:
            api_key = Config.get_api_key(self.provider)

        if not api_key:
            raise ValueError(
                f"API key required for {self.provider}. "
                f"Set environment variable or pass api_key parameter."
            )

        # Initialize mapper with the new unified interface
        self.mapper = RevisionMapper(
            provider=self.provider,
            api_key=api_key,
            model=model,
            strategy=self.strategy
        )

        # These will be initialized after unpacking
        self.extractor: Optional[RevisionExtractor] = None
        self.applier: Optional[DiffBasedApplier] = None

    def sync(self, output_path: str = None) -> str:
        """
        Execute the full sync pipeline.

        Args:
            output_path: Output document path (auto-generated if None)

        Returns:
            Path to output document
        """
        print("=" * 60)
        print("Bilingual Word Document Track Changes Sync Engine")
        print(f"Provider: {self.provider} | Strategy: {self.strategy}")
        print("=" * 60)

        # Step 1: Unpack document
        print("\n[1/6] Unpacking Word document...")
        self._unpack_document()

        # Step 2: Initialize components
        print("[2/6] Initializing components...")
        self.extractor = RevisionExtractor(self.unpacked_dir)
        self.applier = DiffBasedApplier(self.unpacked_dir, author=self.author)

        # Step 3: Extract row pairs
        print(f"[3/6] Extracting revisions from {self.source_lang} column...")
        row_pairs = self.extractor.extract_row_pairs(
            source_column=self.source_column,
            target_column=self.target_column
        )

        print(f"  Found {len(row_pairs)} rows with revisions")

        if not row_pairs:
            print("  No revisions found, exiting")
            return None

        # Step 4: Map revisions via LLM
        print(f"[4/6] Mapping revisions to {self.target_lang} via LLM...")

        mapped_results = self.mapper.map_row_pairs(
            row_pairs,
            source_lang=self.source_lang,
            target_lang=self.target_lang
        )

        # Display mapping results
        for result in mapped_results:
            row_idx = result.get("row_index")
            current = result.get("target_current", "")[:50]
            after = result.get("target_after", "")[:50]
            confidence = result.get("confidence", "N/A")

            print(f"\n  Row {row_idx}:")
            print(f"    Current: {current}...")
            print(f"    After: {after}...")
            print(f"    Confidence: {confidence}")

        # Step 5: Apply revisions
        print(f"\n[5/6] Applying revisions to {self.target_lang} column...")

        success_count = self.applier.apply_mapped_revisions(
            mapped_results=mapped_results,
            column_index=self.target_column
        )

        print(f"\n  Successfully applied {success_count}/{len(mapped_results)} revisions")

        # Step 6: Save and pack
        print("\n[6/6] Saving changes...")
        self.applier.save()

        if output_path is None:
            base, ext = os.path.splitext(self.docx_path)
            output_path = f"{base}_synced{ext}"

        print(f"  Packing document to: {output_path}")
        self._pack_document(output_path)

        # Verify if enabled
        if Config.ENABLE_VERIFICATION:
            print("\n  Verifying output...")
            self._verify_output(output_path)

        print("\n" + "=" * 60)
        print("Sync complete!")
        print(f"Output: {output_path}")
        print("=" * 60)

        return output_path

    def _unpack_document(self):
        """Unpack Word document to XML files."""
        os.makedirs(self.work_dir, exist_ok=True)

        cmd = [
            "python3",
            Config.UNPACK_SCRIPT,
            self.docx_path,
            self.unpacked_dir
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Unpack failed: {result.stderr}")

        print(f"  Unpacked to: {self.unpacked_dir}")

    def _pack_document(self, output_path: str):
        """Pack XML files back to Word document."""
        cmd = [
            "python3",
            Config.PACK_SCRIPT,
            self.unpacked_dir,
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Pack failed: {result.stderr}")

    def _verify_output(self, output_path: str):
        """Verify output document using pandoc."""
        md_path = output_path.replace(".docx", "_verify.md")

        cmd = [
            "pandoc",
            "--track-changes=all",
            output_path,
            "-o",
            md_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"    Verification file: {md_path}")

            # Show preview
            try:
                with open(md_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()[:10]

                print("\n    Preview (first 10 lines):")
                for line in lines:
                    print(f"      {line.rstrip()}")
            except Exception:
                pass
        else:
            print(f"    Verification failed: {result.stderr}")


# ================================================================================
# Command Line Interface
# ================================================================================

def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Bilingual Word Document Track Changes Sync Engine"
    )

    parser.add_argument(
        "input",
        help="Input bilingual Word document path"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output document path (optional)"
    )
    parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic", "deepseek", "qwen", "wenxin", "doubao", "zhipu", "openai"],
        help="LLM provider (default: anthropic)"
    )
    parser.add_argument(
        "--strategy",
        default="max_tokens",
        choices=["max_tokens", "batch"],
        help="Mapping strategy: max_tokens (顶格输出) or batch (预估批次) (default: max_tokens)"
    )
    parser.add_argument(
        "--model",
        help="Model name (uses provider default if not specified)"
    )
    parser.add_argument(
        "--api-key",
        help="API key (or use environment variable)"
    )
    parser.add_argument(
        "--source-column",
        type=int,
        default=0,
        help="Source language column index (default: 0)"
    )
    parser.add_argument(
        "--target-column",
        type=int,
        default=1,
        help="Target language column index (default: 1)"
    )
    parser.add_argument(
        "--source-lang",
        default="Chinese",
        help="Source language name (default: Chinese)"
    )
    parser.add_argument(
        "--target-lang",
        default="English",
        help="Target language name (default: English)"
    )
    parser.add_argument(
        "--author",
        default="Claude",
        help="Track changes author name (default: Claude)"
    )
    parser.add_argument(
        "--preset",
        choices=["zh-en", "en-zh", "zh-es", "es-en", "zh-ja", "ja-en"],
        help="Language preset (overrides column and language settings)"
    )

    args = parser.parse_args()

    # Apply preset if specified
    if args.preset:
        from .config import get_language_preset
        preset = get_language_preset(args.preset)
        args.source_column = preset["source_column"]
        args.target_column = preset["target_column"]
        args.source_lang = preset["source_lang"]
        args.target_lang = preset["target_lang"]

    # Create and run engine
    engine = BilingualSyncEngine(
        docx_path=args.input,
        provider=args.provider,
        api_key=args.api_key,
        model=args.model,
        strategy=args.strategy,
        source_column=args.source_column,
        target_column=args.target_column,
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        author=args.author
    )

    output_path = engine.sync(args.output)
    return output_path


if __name__ == "__main__":
    main()
