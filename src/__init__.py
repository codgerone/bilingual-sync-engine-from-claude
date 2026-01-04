"""
双语Word文档Track Changes同步引擎

一个自动化工具，用于同步双语Word文档中的track changes。
"""

__version__ = "1.0.0"
__author__ = "Meiqi Jiang"

from .extractor import RevisionExtractor
from .mapper import RevisionMapper
from .applier import RevisionApplier, SmartRevisionApplier
from .engine import BilingualSyncEngine

__all__ = [
    'RevisionExtractor',
    'RevisionMapper',
    'RevisionApplier',
    'SmartRevisionApplier',
    'BilingualSyncEngine',
]
