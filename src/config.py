"""
================================================================================
Configuration Module - Multi-LLM Provider Settings
================================================================================

Architecture
------------
Config (class)
    |-- API Settings (per provider)
    |-- Language Settings
    |-- Document Processing Settings
    +-- Logging Settings

LANGUAGE_PRESETS (dict)
    +-- Predefined language pair configurations

LLM_PROVIDERS (dict)
    +-- Provider-specific configurations (API endpoints, models, env vars)

================================================================================
"""

import os
from typing import Dict, Any


# ================================================================================
# LLM Provider Configurations
# ================================================================================

LLM_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "anthropic": {
        "name": "Anthropic Claude",
        "env_key": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-20250514",
        "api_type": "native",
        "base_url": None,
        "supports_caching": True,
        "models": [
            "claude-sonnet-4-20250514",
            "claude-opus-4-20250514",
            "claude-3-5-haiku-20241022",
        ],
    },
    "deepseek": {
        "name": "DeepSeek",
        "env_key": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
        "api_type": "openai_compatible",
        "base_url": "https://api.deepseek.com",
        "supports_caching": False,
        "models": [
            "deepseek-chat",
            "deepseek-reasoner",
        ],
    },
    "qwen": {
        "name": "Alibaba Qwen",
        "env_key": "QWEN_API_KEY",
        "default_model": "qwen-plus",
        "api_type": "openai_compatible",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "supports_caching": False,
        "models": [
            "qwen-turbo",
            "qwen-plus",
            "qwen-max",
        ],
    },
    "wenxin": {
        "name": "Baidu Wenxin (ERNIE)",
        "env_key": "WENXIN_API_KEY",
        "secret_env_key": "WENXIN_SECRET_KEY",
        "default_model": "ernie-4.0",
        "api_type": "native",
        "base_url": "https://aip.baidubce.com",
        "supports_caching": False,
        "models": [
            "ernie-4.0",
            "ernie-3.5",
        ],
    },
    "doubao": {
        "name": "ByteDance Doubao",
        "env_key": "DOUBAO_API_KEY",
        "default_model": "doubao-pro-32k",
        "api_type": "openai_compatible",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "supports_caching": False,
        "models": [
            "doubao-lite-32k",
            "doubao-pro-32k",
            "doubao-pro-128k",
        ],
    },
    "zhipu": {
        "name": "Zhipu GLM",
        "env_key": "ZHIPU_API_KEY",
        "default_model": "glm-4",
        "api_type": "openai_compatible",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "supports_caching": False,
        "models": [
            "glm-4",
            "glm-4-flash",
            "glm-4-plus",
        ],
    },
    "openai": {
        "name": "OpenAI",
        "env_key": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
        "api_type": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
        "supports_caching": False,
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
        ],
    },
}


# ================================================================================
# Language Presets
# ================================================================================

LANGUAGE_PRESETS: Dict[str, Dict[str, Any]] = {
    "zh-en": {
        "source_lang": "Chinese",
        "target_lang": "English",
        "source_column": 0,
        "target_column": 1,
    },
    "en-zh": {
        "source_lang": "English",
        "target_lang": "Chinese",
        "source_column": 1,
        "target_column": 0,
    },
    "zh-es": {
        "source_lang": "Chinese",
        "target_lang": "Spanish",
        "source_column": 0,
        "target_column": 1,
    },
    "es-en": {
        "source_lang": "Spanish",
        "target_lang": "English",
        "source_column": 0,
        "target_column": 1,
    },
    "zh-ja": {
        "source_lang": "Chinese",
        "target_lang": "Japanese",
        "source_column": 0,
        "target_column": 1,
    },
    "ja-en": {
        "source_lang": "Japanese",
        "target_lang": "English",
        "source_column": 0,
        "target_column": 1,
    },
}


# ================================================================================
# Main Configuration Class
# ================================================================================

class Config:
    """
    Central configuration class for the bilingual sync engine.

    All settings can be overridden via environment variables.
    """

    # --------------------------------------------------------------------------
    # LLM Settings
    # --------------------------------------------------------------------------

    # Default provider
    DEFAULT_PROVIDER: str = os.getenv("BILINGUAL_SYNC_PROVIDER", "anthropic")

    # Default strategy: "max_tokens" or "batch"
    DEFAULT_STRATEGY: str = os.getenv("BILINGUAL_SYNC_STRATEGY", "max_tokens")

    # API keys (from environment)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
    WENXIN_API_KEY: str = os.getenv("WENXIN_API_KEY", "")
    WENXIN_SECRET_KEY: str = os.getenv("WENXIN_SECRET_KEY", "")
    DOUBAO_API_KEY: str = os.getenv("DOUBAO_API_KEY", "")
    ZHIPU_API_KEY: str = os.getenv("ZHIPU_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # LLM parameters
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.0"))

    # Batch strategy parameters
    BATCH_OUTPUT_SAFETY_RATIO: float = 0.7
    BATCH_ROW_BASE_TOKENS: int = 80
    BATCH_ROW_PER_CHAR: float = 0.2
    BATCH_MAX_RETRIES: int = 2
    BATCH_RETRY_SHRINK_RATIO: float = 0.6

    # --------------------------------------------------------------------------
    # Language Settings
    # --------------------------------------------------------------------------

    DEFAULT_SOURCE_LANG: str = "Chinese"
    DEFAULT_TARGET_LANG: str = "English"
    DEFAULT_SOURCE_COLUMN: int = 0
    DEFAULT_TARGET_COLUMN: int = 1

    # --------------------------------------------------------------------------
    # Document Processing Settings
    # --------------------------------------------------------------------------

    DEFAULT_AUTHOR: str = "Claude"
    DEFAULT_INITIALS: str = "CL"

    # External tool paths (for Docker/Linux environments)
    DOCX_SKILL_PATH: str = "/mnt/skills/public/docx"
    UNPACK_SCRIPT: str = f"{DOCX_SKILL_PATH}/ooxml/scripts/unpack.py"
    PACK_SCRIPT: str = f"{DOCX_SKILL_PATH}/ooxml/scripts/pack.py"

    # Context window for text extraction
    CONTEXT_BEFORE_CHARS: int = 30
    CONTEXT_AFTER_CHARS: int = 30

    # --------------------------------------------------------------------------
    # Logging Settings
    # --------------------------------------------------------------------------

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "{time} | {level} | {message}"

    # --------------------------------------------------------------------------
    # Verification Settings
    # --------------------------------------------------------------------------

    ENABLE_VERIFICATION: bool = True
    VERIFICATION_TOOL: str = "pandoc"

    # --------------------------------------------------------------------------
    # Helper Methods
    # --------------------------------------------------------------------------

    @classmethod
    def get_api_key(cls, provider: str) -> str:
        """
        Get API key for a provider.

        Args:
            provider: Provider name (anthropic, deepseek, etc.)

        Returns:
            API key string (may be empty if not set)
        """
        provider_config = LLM_PROVIDERS.get(provider.lower(), {})
        env_key = provider_config.get("env_key", "")
        return os.getenv(env_key, "")

    @classmethod
    def get_provider_config(cls, provider: str) -> Dict[str, Any]:
        """
        Get full configuration for a provider.

        Args:
            provider: Provider name

        Returns:
            Provider configuration dict
        """
        return LLM_PROVIDERS.get(provider.lower(), {})

    @classmethod
    def get_all_config(cls) -> Dict[str, Any]:
        """Get all configuration values as a dictionary."""
        return {
            key: getattr(cls, key)
            for key in dir(cls)
            if not key.startswith('_') and key.isupper()
        }

    @classmethod
    def print_config(cls):
        """Print current configuration (hiding sensitive values)."""
        config = cls.get_all_config()

        print("Current Configuration:")
        print("-" * 50)

        for key, value in sorted(config.items()):
            # Hide API keys
            if "API_KEY" in key and value:
                if len(value) > 12:
                    display_value = value[:4] + "..." + value[-4:]
                else:
                    display_value = "****"
            elif "SECRET" in key and value:
                display_value = "****"
            else:
                display_value = value

            print(f"  {key}: {display_value}")

        print("-" * 50)

    @classmethod
    def list_available_providers(cls) -> None:
        """Print available LLM providers and their status."""
        print("\nAvailable LLM Providers:")
        print("-" * 50)

        for provider, config in LLM_PROVIDERS.items():
            api_key = cls.get_api_key(provider)
            status = "configured" if api_key else "not configured"

            print(f"\n  {provider}:")
            print(f"    Name: {config['name']}")
            print(f"    Status: {status}")
            print(f"    Default Model: {config['default_model']}")
            print(f"    Env Variable: {config['env_key']}")

        print("-" * 50)


def get_language_preset(preset_name: str) -> Dict[str, Any]:
    """
    Get language preset configuration.

    Args:
        preset_name: Preset name (e.g., "zh-en", "en-zh")

    Returns:
        Preset configuration dict

    Raises:
        ValueError: If preset not found
    """
    if preset_name not in LANGUAGE_PRESETS:
        available = ", ".join(LANGUAGE_PRESETS.keys())
        raise ValueError(f"Unknown preset: {preset_name}. Available: {available}")

    return LANGUAGE_PRESETS[preset_name]


# ================================================================================
# Usage Example
# ================================================================================

if __name__ == "__main__":
    # Print configuration
    Config.print_config()

    # List providers
    Config.list_available_providers()

    # Show language presets
    print("\nLanguage Presets:")
    print("-" * 50)
    for preset_name, preset in LANGUAGE_PRESETS.items():
        print(f"  {preset_name}: {preset['source_lang']} -> {preset['target_lang']}")
    print("-" * 50)
