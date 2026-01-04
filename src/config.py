"""
配置文件 - 双语Word文档Track Changes同步引擎
"""

import os
from typing import Dict, Any


class Config:
    """配置类"""
    
    # API配置
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    
    # 默认语言设置
    DEFAULT_SOURCE_LANG: str = "中文"
    DEFAULT_TARGET_LANG: str = "英文"
    
    # 默认列设置
    DEFAULT_SOURCE_COLUMN: int = 0  # 左列
    DEFAULT_TARGET_COLUMN: int = 1  # 右列
    
    # 作者设置
    DEFAULT_AUTHOR: str = "Claude"
    DEFAULT_INITIALS: str = "CL"
    
    # 文件路径
    DOCX_SKILL_PATH: str = "/mnt/skills/public/docx"
    UNPACK_SCRIPT: str = f"{DOCX_SKILL_PATH}/ooxml/scripts/unpack.py"
    PACK_SCRIPT: str = f"{DOCX_SKILL_PATH}/ooxml/scripts/pack.py"
    
    # LLM配置
    LLM_MAX_TOKENS: int = 1000
    LLM_TEMPERATURE: float = 0.0  # 使用确定性输出
    
    # 上下文窗口大小
    CONTEXT_BEFORE_CHARS: int = 30
    CONTEXT_AFTER_CHARS: int = 30
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "{time} | {level} | {message}"
    
    # 验证配置
    ENABLE_VERIFICATION: bool = True
    VERIFICATION_TOOL: str = "pandoc"
    
    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """获取所有配置项"""
        return {
            key: getattr(cls, key)
            for key in dir(cls)
            if not key.startswith('_') and key.isupper()
        }
    
    @classmethod
    def print_config(cls):
        """打印当前配置"""
        config = cls.get_config()
        
        print("当前配置:")
        print("-" * 50)
        
        for key, value in config.items():
            # 隐藏API密钥的敏感部分
            if "API_KEY" in key and value:
                display_value = value[:8] + "..." + value[-4:]
            else:
                display_value = value
            
            print(f"  {key}: {display_value}")
        
        print("-" * 50)


# 语言配置预设
LANGUAGE_PRESETS = {
    "zh-en": {
        "source_lang": "中文",
        "target_lang": "英文",
        "source_column": 0,
        "target_column": 1,
    },
    "en-zh": {
        "source_lang": "英文",
        "target_lang": "中文",
        "source_column": 1,
        "target_column": 0,
    },
    "zh-es": {
        "source_lang": "中文",
        "target_lang": "西班牙语",
        "source_column": 0,
        "target_column": 1,
    },
    "es-en": {
        "source_lang": "西班牙语",
        "target_lang": "英文",
        "source_column": 0,
        "target_column": 1,
    },
}


def get_language_preset(preset_name: str) -> Dict[str, Any]:
    """
    获取语言预设配置
    
    Args:
        preset_name: 预设名称，如 "zh-en", "en-zh"
        
    Returns:
        预设配置字典
    """
    if preset_name not in LANGUAGE_PRESETS:
        available = ", ".join(LANGUAGE_PRESETS.keys())
        raise ValueError(f"未知的预设: {preset_name}. 可用预设: {available}")
    
    return LANGUAGE_PRESETS[preset_name]


# 使用示例
if __name__ == "__main__":
    # 打印配置
    Config.print_config()
    
    # 获取语言预设
    print("\n可用的语言预设:")
    for preset_name in LANGUAGE_PRESETS:
        preset = LANGUAGE_PRESETS[preset_name]
        print(f"  {preset_name}: {preset['source_lang']} → {preset['target_lang']}")
