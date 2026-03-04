"""
Central configuration module for Caissa Chess Engine.
All system, engine, LLM, and generation parameters are loaded and managed here.

This is a backward-compatible bridge to the new config_manager system.
All parameters are now driven by caissa_config.yaml + .env + env vars.

Usage:
    from configuration import config
    print(config.LLM_PROVIDER)
    print(config.STOCKFISH_PATH)

For the new typed config interface, use:
    from config_manager import cfg
    print(cfg.llm.provider)
    print(cfg.stockfish.depth)
"""
import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import the new config system
from config_manager import cfg as _cfg


class Config:
    """
    Legacy configuration class — delegates to config_manager.cfg.
    
    Reads live from the new config system so that any changes are picked up.
    All the SCREAMING_CASE attributes are preserved for backward compatibility.
    """
    
    # --- LLM Provider ---
    @property
    def LLM_PROVIDER(self) -> str:
        return _cfg.llm.provider
    
    @property
    def OPENAI_API_KEY(self) -> Optional[str]:
        return os.getenv("OPENAI_API_KEY") or _cfg.llm.openai_api_key
    
    @property
    def ANTHROPIC_API_KEY(self) -> Optional[str]:
        return os.getenv("ANTHROPIC_API_KEY") or _cfg.llm.anthropic_api_key
    
    @property
    def GOOGLE_API_KEY(self) -> Optional[str]:
        return os.getenv("GOOGLE_API_KEY") or _cfg.llm.google_api_key
    
    @property
    def DEEPSEEK_API_KEY(self) -> Optional[str]:
        return os.getenv("DEEPSEEK_API_KEY") or _cfg.llm.deepseek_api_key
    
    @property
    def GEMINI_MODEL(self) -> str:
        return _cfg.llm.gemini_model
    
    @property
    def OPENAI_MODEL(self) -> str:
        return _cfg.llm.openai_model
    
    @property
    def ANTHROPIC_MODEL(self) -> str:
        return _cfg.llm.anthropic_model
    
    # --- Stockfish ---
    @property
    def STOCKFISH_PATH(self) -> str:
        return _cfg.stockfish.path
    
    @property
    def STOCKFISH_DEPTH(self) -> int:
        return _cfg.stockfish.depth
    
    @property
    def STOCKFISH_THREADS(self) -> int:
        return _cfg.stockfish.threads
    
    @property
    def STOCKFISH_HASH_MB(self) -> int:
        return _cfg.stockfish.hash_mb
    
    # --- Generation ---
    @property
    def DEFAULT_STYLE(self) -> str:
        return _cfg.generation.style
    
    @property
    def DEFAULT_THEME(self) -> Optional[str]:
        return _cfg.generation.theme
    
    @property
    def DEFAULT_AGGRESSION(self) -> int:
        return _cfg.generation.aggression
    
    @property
    def DEFAULT_CHAOS(self) -> int:
        return _cfg.generation.chaos
    
    @property
    def DEFAULT_GAME_LENGTH(self) -> int:
        return _cfg.generation.depth
    
    @property
    def DEFAULT_ERA(self) -> str:
        return _cfg.generation.era
    
    @property
    def DEFAULT_WHITE(self) -> str:
        return _cfg.generation.white_player
    
    @property
    def DEFAULT_BLACK(self) -> str:
        return _cfg.generation.black_player
    
    # --- Output ---
    @property
    def EXPORT_FORMAT(self) -> str:
        return _cfg.export.format
    
    @property
    def ENABLE_VISUALIZATION(self) -> bool:
        return _cfg.export.enable_visualization
    
    @property
    def OUTPUT_PATH(self) -> str:
        return _cfg.export.output_path
    
    # --- Logging ---
    @property
    def LOG_LEVEL(self) -> str:
        return _cfg.logging.level
    
    @property
    def LOG_FILE(self) -> Optional[str]:
        return getattr(_cfg.logging, 'file', None)
    
    # --- Paths ---
    @property
    def PROJECT_ROOT(self) -> Path:
        return _cfg.project_root
    
    @property
    def DATA_DIR(self) -> Path:
        return _cfg.data_dir
    
    @property
    def ENGINES_DIR(self) -> Path:
        return _cfg.engines_dir
    
    @property
    def EXPORT_DIR(self) -> Path:
        return _cfg.export_dir


config = Config()
