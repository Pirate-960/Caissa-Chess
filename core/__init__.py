"""
core/__init__.py

CAISSA core module initialization.
"""

from core.generator import CaissaGenerator, GameContext
from core.prompt_manager import PromptManager, GameEra, GameTheme
from core.match_analyzer import MatchAnalyzer, MatchAnalysis
from core.match_workflow import run_analyzed_match, run_match_series

__all__ = [
    "CaissaGenerator",
    "PromptManager",
    "GameContext",
    "GameEra",
    "GameTheme",
    "MatchAnalyzer",
    "MatchAnalysis",
    "run_analyzed_match",
    "run_match_series",
]
