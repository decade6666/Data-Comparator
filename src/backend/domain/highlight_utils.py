"""Highlight helper exports for backend-domain callers."""

from .excel_utils import apply_highlight_to_worksheet
from .highlight_optimizer import HighlightOptimizer

highlight_optimizer = HighlightOptimizer()

__all__ = ["HighlightOptimizer", "apply_highlight_to_worksheet", "highlight_optimizer"]
