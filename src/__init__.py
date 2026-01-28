"""
Bilingual Word Document Track Changes Sync Engine

Automatically sync track changes from one language column to another
in bilingual Word documents.
"""

__version__ = "2.0.0"
__author__ = "Meiqi Jiang"

from .extractor import RevisionExtractor
from .mapper import RevisionMapper
from .applier import DiffBasedApplier
from .engine import BilingualSyncEngine

__all__ = [
    'RevisionExtractor',
    'RevisionMapper',
    'DiffBasedApplier',
    'BilingualSyncEngine',
]
