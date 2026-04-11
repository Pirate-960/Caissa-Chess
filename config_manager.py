"""
config_manager.py

Centralized configuration system for Caissa Chess Engine.
Loads settings from caissa_config.yaml, .env, and environment variables.
Provides typed, validated access to every configurable parameter.

Priority: CLI args > Environment vars (.env) > caissa_config.local.yaml > caissa_config.yaml

Usage:
    from config_manager import cfg
    print(cfg.llm.provider)
    print(cfg.stockfish.depth)
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try importing YAML — fallback to JSON if unavailable
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.resolve()


# =============================================================================
# VALIDATION
# =============================================================================

class ConfigValidationError(Exception):
    """Raised when configuration values are out of valid range."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        msg = "Configuration validation failed:\n  - " + "\n  - ".join(errors)
        super().__init__(msg)


def _check_range(errors: List[str], section: str, name: str, value, lo, hi):
    """Append an error if *value* is outside [lo, hi]."""
    if value < lo or value > hi:
        errors.append(f"{section}.{name} = {value!r} — must be between {lo} and {hi}")


def _check_positive(errors: List[str], section: str, name: str, value):
    """Append an error if *value* is not > 0."""
    if value <= 0:
        errors.append(f"{section}.{name} = {value!r} — must be > 0")


def _check_non_negative(errors: List[str], section: str, name: str, value):
    """Append an error if *value* is < 0."""
    if value < 0:
        errors.append(f"{section}.{name} = {value!r} — must be >= 0")


def _check_choice(errors: List[str], section: str, name: str, value, choices):
    """Append an error if *value* is not in *choices*."""
    if value not in choices:
        errors.append(f"{section}.{name} = {value!r} — must be one of {choices}")


SUPPORTED_PROVIDERS = {"openai", "anthropic", "gemini", "deepseek", "ollama", "azure", "mock"}
SUPPORTED_EXPORT_FORMATS = {"pgn", "pgn_strict", "json", "markdown", "html", "export_all"}
SUPPORTED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
SUPPORTED_EVAL_MODES = {"hybrid", "stockfish", "aesthetic", "llm"}
SUPPORTED_RETRY_STRATEGIES = {"exponential", "linear", "constant", "none"}
SUPPORTED_COMMENTARY_STYLES = {"analytical", "poetic", "dramatic", "educational", "humorous"}
SUPPORTED_DIFFICULTIES = {"beginner", "intermediate", "advanced", "master", "grandmaster"}
SUPPORTED_BIASES = {"white", "black", "draw", "random", "neutral"}


def validate_config(config: "CaissaConfig") -> None:
    """
    Validate all configuration values.

    Raises ``ConfigValidationError`` if any values are out of range.
    Warnings for non-critical issues are logged instead.
    """
    errors: List[str] = []

    # — LLM ------------------------------------------------------------------
    llm = config.llm
    _check_choice(errors, "llm", "provider", llm.provider, SUPPORTED_PROVIDERS)
    _check_range(errors, "llm", "temperature", llm.temperature, 0.0, 2.0)
    _check_positive(errors, "llm", "max_tokens", llm.max_tokens)
    _check_range(errors, "llm", "top_p", llm.top_p, 0.0, 1.0)

    # — Stockfish -------------------------------------------------------------
    sf = config.stockfish
    _check_range(errors, "stockfish", "depth", sf.depth, 1, 30)
    _check_range(errors, "stockfish", "threads", sf.threads, 1, 128)
    _check_range(errors, "stockfish", "hash_mb", sf.hash_mb, 1, 8192)
    _check_positive(errors, "stockfish", "time_limit", sf.time_limit)
    _check_positive(errors, "stockfish", "blunder_threshold", sf.blunder_threshold)
    _check_non_negative(errors, "stockfish", "sacrifice_margin", sf.sacrifice_margin)

    # — Generation ------------------------------------------------------------
    gen = config.generation
    _check_range(errors, "generation", "aggression", gen.aggression, 1, 10)
    _check_range(errors, "generation", "chaos", gen.chaos, 1, 10)
    _check_range(errors, "generation", "depth", gen.depth, 10, 500)
    _check_range(errors, "generation", "blunder_tolerance", gen.blunder_tolerance, 0.0, 10.0)
    _check_range(errors, "generation", "target_beauty_score", gen.target_beauty_score, 0.0, 100.0)
    _check_choice(errors, "generation", "bias", gen.bias, SUPPORTED_BIASES)
    _check_choice(errors, "generation", "difficulty", gen.difficulty, SUPPORTED_DIFFICULTIES)

    # — Aesthetics ------------------------------------------------------------
    aes = config.aesthetics
    for bonus_name in (
        "sacrifice_bonus", "quiet_killer_bonus", "forcing_move_bonus",
        "tension_multiplier", "draw_penalty", "zwischenzug_bonus",
        "queen_sacrifice_bonus", "king_hunt_bonus", "windmill_bonus",
        "smothered_mate_bonus", "exchange_sacrifice_bonus", "prophylaxis_bonus",
        "defensive_resource_bonus", "pawn_breakthrough_bonus", "mysterious_rook_bonus",
    ):
        _check_non_negative(errors, "aesthetics", bonus_name, getattr(aes, bonus_name))
    _check_choice(errors, "aesthetics", "evaluation_mode", aes.evaluation_mode, SUPPORTED_EVAL_MODES)

    # — Prompts ---------------------------------------------------------------
    p = config.prompts
    _check_choice(errors, "prompts", "commentary_style", p.commentary_style, SUPPORTED_COMMENTARY_STYLES)
    _check_range(errors, "prompts", "opening_book_depth", p.opening_book_depth, 1, 30)

    # — Export ----------------------------------------------------------------
    exp = config.export
    _check_choice(errors, "export", "format", exp.format, SUPPORTED_EXPORT_FORMATS)
    _check_positive(errors, "export", "max_line_width", exp.max_line_width)

    # — Benchmarks ------------------------------------------------------------
    bm = config.benchmarks
    _check_positive(errors, "benchmarks", "default_runs", bm.default_runs)
    _check_range(errors, "benchmarks", "regression_threshold", bm.regression_threshold, 0.0, 1.0)
    # Quality weights should sum to ~1.0
    qw = bm.quality_weights
    weight_sum = qw.legality + qw.tactical + qw.aesthetic + qw.structural
    if abs(weight_sum - 1.0) > 0.05:
        errors.append(
            f"benchmarks.quality_weights sum = {weight_sum:.2f} — should be ~1.0"
        )

    # — Logging ---------------------------------------------------------------
    _check_choice(errors, "logging", "level", config.logging.level.upper(), SUPPORTED_LOG_LEVELS)

    # — Advanced / Retry ------------------------------------------------------
    adv = config.advanced
    _check_choice(errors, "advanced.retry", "strategy", adv.retry.strategy, SUPPORTED_RETRY_STRATEGIES)
    _check_range(errors, "advanced.retry", "max_retries", adv.retry.max_retries, 0, 20)
    _check_positive(errors, "advanced.retry", "base_delay", adv.retry.base_delay)
    _check_positive(errors, "advanced.retry", "max_delay", adv.retry.max_delay)
    _check_range(errors, "advanced.retry", "jitter", adv.retry.jitter, 0.0, 1.0)

    # — Advanced / Parallel ---------------------------------------------------
    _check_range(errors, "advanced.parallel", "max_workers", adv.parallel.max_workers, 1, 64)

    if errors:
        raise ConfigValidationError(errors)


# =============================================================================
# CONFIG SECTION DATACLASSES
# =============================================================================

@dataclass
class LLMConfig:
    """LLM provider configuration."""
    provider: str = "gemini"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    gemini_model: str = "gemini-2.5-pro"
    deepseek_model: str = "deepseek-chat"
    ollama_model: str = "llama2"
    temperature: float = 0.8
    max_tokens: int = 4096
    top_p: float = 1.0
    ollama_base_url: str = "http://localhost:11434"
    azure_endpoint: Optional[str] = None
    azure_deployment: Optional[str] = None
    azure_api_version: str = "2024-02-01"


@dataclass
class StockfishConfig:
    """Stockfish engine configuration."""
    path: str = "engines/stockfish-windows-x86-64-avx2.exe"
    depth: int = 15
    threads: int = 1
    hash_mb: int = 64
    time_limit: float = 0.1
    blunder_threshold: int = 300
    sacrifice_margin: int = 100
    enabled: bool = True


@dataclass
class GenerationConfig:
    """Game generation configuration."""
    style: str = "tal"
    theme: Optional[str] = None
    era: str = "romantic"
    aggression: int = 7
    chaos: int = 5
    depth: int = 40
    white_player: str = "Caissa White"
    black_player: str = "Caissa Black"
    bias: str = "neutral"
    blunder_tolerance: float = 1.5
    difficulty: str = "intermediate"
    narrative_arc: Optional[str] = None
    target_beauty_score: float = 70.0
    include_annotations: bool = True
    include_commentary: bool = False


@dataclass
class AestheticsConfig:
    """Beauty evaluation and style configuration."""
    sacrifice_bonus: float = 15.0
    quiet_killer_bonus: float = 20.0
    forcing_move_bonus: float = 5.0
    tension_multiplier: float = 0.5
    draw_penalty: float = 5.0
    zwischenzug_bonus: float = 18.0
    queen_sacrifice_bonus: float = 35.0
    king_hunt_bonus: float = 22.0
    windmill_bonus: float = 30.0
    smothered_mate_bonus: float = 25.0
    exchange_sacrifice_bonus: float = 12.0
    prophylaxis_bonus: float = 10.0
    defensive_resource_bonus: float = 14.0
    pawn_breakthrough_bonus: float = 16.0
    mysterious_rook_bonus: float = 8.0
    evaluation_mode: str = "hybrid"
    enable_style_blending: bool = False
    blend_styles: Dict[str, float] = field(default_factory=dict)


@dataclass
class PromptsConfig:
    """Prompt engineering configuration."""
    enable_personalities: bool = True
    multi_stage: bool = False
    commentary_style: str = "analytical"
    commentary_depth: str = "moderate"
    use_opening_book: bool = False
    opening_book_depth: int = 6
    custom_constraints: List[str] = field(default_factory=list)


@dataclass
class ExportConfig:
    """Export and output configuration."""
    format: str = "pgn"
    output_path: str = "game.pgn"
    batch_output_dir: str = "./games"
    batch_filename_pattern: str = "game_{n:03d}.pgn"
    pretty_pgn: bool = True
    max_line_width: int = 80
    include_headers: bool = True
    use_nag_symbols: bool = True
    enable_visualization: bool = True


@dataclass
class BenchmarkQualityWeights:
    """Quality analysis dimension weights."""
    legality: float = 0.30
    tactical: float = 0.25
    aesthetic: float = 0.25
    structural: float = 0.20


@dataclass
class BenchmarksConfig:
    """Benchmarking configuration."""
    default_runs: int = 5
    quality_weights: BenchmarkQualityWeights = field(default_factory=BenchmarkQualityWeights)
    save_history: bool = True
    history_file: str = "benchmarks/history.json"
    regression_threshold: float = 0.15
    report_format: str = "html"


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    log_dir: str = "logs"
    format: str = "%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s"
    log_llm_prompts: bool = True
    max_bytes: int = 10_485_760        # 10 MB — applies to ALL log files
    backup_count: int = 3
    console_logs: bool = True
    verbosity: str = "normal"


@dataclass
class RetryConfig:
    """Retry strategy configuration."""
    strategy: str = "exponential"
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    jitter: float = 0.1


@dataclass
class ParallelConfig:
    """Parallel processing configuration."""
    enabled: bool = False
    max_workers: int = 4
    fail_fast: bool = False


@dataclass
class BatchDefaults:
    """Default values for the batch generation wizard."""
    count: int = 5
    style_variation: str = "round_robin"   # fixed | round_robin | random
    default_styles: List[str] = field(default_factory=lambda: ["tal", "morphy", "capablanca"])
    default_eras: List[str] = field(default_factory=lambda: ["romantic"])
    default_themes: List[str] = field(default_factory=list)
    depth: int = 40
    min_quality: str = "acceptable"        # poor | acceptable | good | excellent
    quality_retries: int = 3
    mode: str = "sequential"               # sequential | parallel
    workers: int = 4
    filename_pattern: str = "game_{n:03d}"
    export_formats: List[str] = field(default_factory=lambda: ["pgn"])
    pretty_pgn: bool = True
    resume: bool = True
    generate_summary: bool = True


@dataclass
class AdvancedConfig:
    """Advanced internal configuration."""
    retry: RetryConfig = field(default_factory=RetryConfig)
    enable_move_cache: bool = True
    parallel: ParallelConfig = field(default_factory=ParallelConfig)
    track_stats: bool = True
    stats_file: str = ".caissa_stats.json"


# =============================================================================
# TOURNAMENT CONFIGURATION (v0.5.0)
# =============================================================================

@dataclass
class TournamentEloConfig:
    """ELO rating system configuration for tournaments."""
    initial_rating: int = 1500
    k_factor_strategy: str = "fide"  # fixed | fide | uscf | dynamic | provisional
    k_factor: int = 32
    k_factor_new: int = 40
    k_factor_established: int = 20
    k_factor_master: int = 10
    rating_floor: int = 100
    rating_ceiling: int = 3500
    persist_ratings: bool = True
    ratings_file: str = "tournaments/elo_ratings.json"


@dataclass
class TournamentMatchConfig:
    """Match engine settings for tournaments."""
    max_moves: int = 500
    max_retries: int = 3
    allow_draws: bool = True
    shuffle_colors: bool = True
    detect_opening: bool = True
    timeout_fallback_enabled: bool = True
    timeout_fallback_max_consecutive: int = 3
    timeout_fallback_cooldown_moves: int = 2
    include_time_control_in_prompt: bool = True


@dataclass
class TournamentCommentaryConfig:
    """Live commentary settings for tournaments."""
    enabled: bool = False
    style: str = "grandmaster"
    depth: str = "key_moments"
    multi_panel: bool = False
    panel_styles: List[str] = field(default_factory=lambda: ["grandmaster", "enthusiastic"])


@dataclass
class TournamentOutputConfig:
    """Tournament output and export settings."""
    output_dir: str = "tournaments"
    auto_export: List[str] = field(default_factory=lambda: ["markdown", "json", "pgn"])
    include_crosstable: bool = True
    include_elo_changes: bool = True
    html_report: bool = True


@dataclass
class TournamentArenaConfig:
    """Arena mode tournament settings."""
    duration_minutes: int = 60
    arena_win_points: int = 2
    arena_draw_points: int = 1
    allow_berserk: bool = False
    berserk_bonus: int = 1


@dataclass
class TournamentAnalyticsConfig:
    """Tournament analytics settings."""
    style_fingerprinting: bool = True
    provider_metrics: bool = True
    decision_quality: bool = True
    pattern_detection: bool = True


@dataclass
class TournamentConfig:
    """LLM vs LLM Tournament Configuration (v0.5.0)."""
    # Default settings
    default_format: str = "round_robin"
    default_rounds: int = 0
    default_time_control: str = "rapid"
    
    # Time per move for each control type
    time_per_move: Dict[str, int] = field(default_factory=lambda: {
        "bullet": 5,
        "blitz": 15,
        "rapid": 30,
        "classical": 60,
        "correspondence": 3600,
        "unlimited": 0
    })
    
    # Scoring system
    win_points: float = 1.0
    draw_points: float = 0.5
    loss_points: float = 0.0
    bye_points: float = 1.0
    
    # Tiebreak methods
    tiebreak_methods: List[str] = field(default_factory=lambda: ["h2h", "sb", "wins"])
    
    # Player personas
    enable_personas: bool = True
    default_persona: Optional[str] = None
    
    # Nested configs
    elo: TournamentEloConfig = field(default_factory=TournamentEloConfig)
    match: TournamentMatchConfig = field(default_factory=TournamentMatchConfig)
    commentary: TournamentCommentaryConfig = field(default_factory=TournamentCommentaryConfig)
    output: TournamentOutputConfig = field(default_factory=TournamentOutputConfig)
    arena: TournamentArenaConfig = field(default_factory=TournamentArenaConfig)
    analytics: TournamentAnalyticsConfig = field(default_factory=TournamentAnalyticsConfig)


# =============================================================================
# MASTER CONFIG
# =============================================================================

@dataclass
class CaissaConfig:
    """Master configuration containing all subsections."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    stockfish: StockfishConfig = field(default_factory=StockfishConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    aesthetics: AestheticsConfig = field(default_factory=AestheticsConfig)
    prompts: PromptsConfig = field(default_factory=PromptsConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    benchmarks: BenchmarksConfig = field(default_factory=BenchmarksConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    advanced: AdvancedConfig = field(default_factory=AdvancedConfig)
    batch: BatchDefaults = field(default_factory=BatchDefaults)
    tournament: TournamentConfig = field(default_factory=TournamentConfig)

    # Computed paths
    project_root: Path = field(default_factory=lambda: PROJECT_ROOT)
    data_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data")
    engines_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "engines")
    export_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "export")


# =============================================================================
# LOADING LOGIC
# =============================================================================

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_yaml_file(path: Path) -> dict:
    """Load a YAML or JSON config file."""
    if not path.exists():
        return {}
    
    text = path.read_text(encoding="utf-8")
    
    if path.suffix in (".yaml", ".yml"):
        if HAS_YAML:
            return yaml.safe_load(text) or {}
        else:
            logger.warning(f"PyYAML not installed. Cannot load {path}. Install with: pip install pyyaml")
            return {}
    elif path.suffix == ".json":
        return json.loads(text) if text.strip() else {}
    else:
        # Try YAML first, then JSON
        if HAS_YAML:
            try:
                return yaml.safe_load(text) or {}
            except Exception:
                pass
        try:
            return json.loads(text) if text.strip() else {}
        except Exception:
            return {}


def _apply_env_overrides(data: dict) -> dict:
    """Apply environment variable overrides to the config dict."""
    env_map = {
        # LLM
        "LLM_PROVIDER": ("llm", "provider"),
        "OPENAI_API_KEY": ("llm", "openai_api_key"),
        "ANTHROPIC_API_KEY": ("llm", "anthropic_api_key"),
        "GOOGLE_API_KEY": ("llm", "google_api_key"),
        "DEEPSEEK_API_KEY": ("llm", "deepseek_api_key"),
        "OPENAI_MODEL": ("llm", "openai_model"),
        "ANTHROPIC_MODEL": ("llm", "anthropic_model"),
        "GEMINI_MODEL": ("llm", "gemini_model"),
        "LLM_TEMPERATURE": ("llm", "temperature"),
        "LLM_MAX_TOKENS": ("llm", "max_tokens"),
        # Stockfish
        "STOCKFISH_PATH": ("stockfish", "path"),
        "STOCKFISH_DEPTH": ("stockfish", "depth"),
        "STOCKFISH_THREADS": ("stockfish", "threads"),
        "STOCKFISH_HASH_MB": ("stockfish", "hash_mb"),
        "STOCKFISH_ENABLED": ("stockfish", "enabled"),
        # Generation
        "DEFAULT_STYLE": ("generation", "style"),
        "DEFAULT_THEME": ("generation", "theme"),
        "DEFAULT_ERA": ("generation", "era"),
        "DEFAULT_AGGRESSION": ("generation", "aggression"),
        "DEFAULT_CHAOS": ("generation", "chaos"),
        "DEFAULT_GAME_LENGTH": ("generation", "depth"),
        "DEFAULT_WHITE": ("generation", "white_player"),
        "DEFAULT_BLACK": ("generation", "black_player"),
        # Export
        "EXPORT_FORMAT": ("export", "format"),
        "OUTPUT_PATH": ("export", "output_path"),
        "ENABLE_VISUALIZATION": ("export", "enable_visualization"),
        # Logging
        "LOG_LEVEL": ("logging", "level"),
        "LOG_FILE": ("logging", "file"),
    }
    
    for env_var, (section, key) in env_map.items():
        value = os.getenv(env_var)
        if value is not None:
            if section not in data:
                data[section] = {}
            # Type coercion for known numeric/boolean fields
            if key in ("depth", "threads", "hash_mb", "max_tokens", "aggression",
                        "chaos", "blunder_threshold", "max_retries", "max_workers",
                        "default_runs"):
                try:
                    value = int(value)
                except ValueError:
                    pass
            elif key in ("temperature", "time_limit", "base_delay", "max_delay",
                          "jitter", "blunder_tolerance", "target_beauty_score",
                          "regression_threshold", "top_p"):
                try:
                    value = float(value)
                except ValueError:
                    pass
            elif key in ("enabled", "enable_visualization", "pretty_pgn",
                          "enable_move_cache", "save_history", "track_stats",
                          "multi_stage", "use_opening_book", "fail_fast",
                          "log_llm_prompts", "include_annotations",
                          "include_commentary", "enable_personalities"):
                value = value.lower() in ("true", "1", "yes")
            
            data[section][key] = value
    
    return data


def _populate_dataclass(dc_class, data: dict):
    """Recursively populate a dataclass from a dict, ignoring unknown keys."""
    import dataclasses
    
    if not isinstance(data, dict):
        return dc_class()
    
    kwargs = {}
    
    for f in dataclasses.fields(dc_class):
        if f.name not in data:
            continue
        value = data[f.name]
        
        # Check if the field type is itself a dataclass
        if dataclasses.is_dataclass(f.type):
            kwargs[f.name] = _populate_dataclass(f.type, value if isinstance(value, dict) else {})
        elif hasattr(f.type, '__origin__'):
            # Generic types like Dict, List — pass through
            kwargs[f.name] = value
        else:
            # Handle field default_factory that produces dataclasses
            if isinstance(f.default_factory, type) if callable(getattr(f, 'default_factory', None)) else False:
                pass
            # Try to get the actual type for dataclass fields with default_factory
            field_type = f.type
            if isinstance(field_type, str):
                # Forward reference — skip complex resolution
                kwargs[f.name] = value
            else:
                try:
                    if dataclasses.is_dataclass(field_type):
                        kwargs[f.name] = _populate_dataclass(field_type, value if isinstance(value, dict) else {})
                    else:
                        kwargs[f.name] = value
                except TypeError:
                    kwargs[f.name] = value
    
    return dc_class(**kwargs)


def _build_config_from_dict(data: dict) -> CaissaConfig:
    """Build a CaissaConfig from a raw dictionary."""
    import dataclasses
    
    config = CaissaConfig()
    
    section_map = {
        "llm": ("llm", LLMConfig),
        "stockfish": ("stockfish", StockfishConfig),
        "generation": ("generation", GenerationConfig),
        "aesthetics": ("aesthetics", AestheticsConfig),
        "prompts": ("prompts", PromptsConfig),
        "export": ("export", ExportConfig),
        "benchmarks": ("benchmarks", BenchmarksConfig),
        "logging": ("logging", LoggingConfig),
        "advanced": ("advanced", AdvancedConfig),
        "batch": ("batch", BatchDefaults),
        "tournament": ("tournament", TournamentConfig),
    }
    
    for yaml_key, (attr_name, dc_class) in section_map.items():
        section_data = data.get(yaml_key, {})
        if isinstance(section_data, dict):
            # Special handling for nested dataclasses
            if dc_class == BenchmarksConfig and "quality_weights" in section_data:
                qw = section_data.get("quality_weights", {})
                if isinstance(qw, dict):
                    section_data = dict(section_data)
                    section_data["quality_weights"] = BenchmarkQualityWeights(**{
                        k: v for k, v in qw.items() 
                        if k in ("legality", "tactical", "aesthetic", "structural")
                    })
            
            if dc_class == AdvancedConfig:
                section_data = dict(section_data)
                if "retry" in section_data and isinstance(section_data["retry"], dict):
                    section_data["retry"] = RetryConfig(**{
                        k: v for k, v in section_data["retry"].items()
                        if k in ("strategy", "max_retries", "base_delay", "max_delay", "jitter")
                    })
                if "parallel" in section_data and isinstance(section_data["parallel"], dict):
                    section_data["parallel"] = ParallelConfig(**{
                        k: v for k, v in section_data["parallel"].items()
                        if k in ("enabled", "max_workers", "fail_fast")
                    })
            
            # Filter to only known fields
            known_fields = {f.name for f in dataclasses.fields(dc_class)}
            filtered = {k: v for k, v in section_data.items() if k in known_fields}
            
            try:
                setattr(config, attr_name, dc_class(**filtered))
            except TypeError as e:
                logger.warning(f"Error loading config section '{yaml_key}': {e}")
                setattr(config, attr_name, dc_class())
    
    return config


def load_config(
    config_path: Optional[str] = None,
    local_path: Optional[str] = None,
    cli_overrides: Optional[Dict[str, Any]] = None,
) -> CaissaConfig:
    """
    Load configuration with full priority chain:
    CLI args > env vars > local config > default config
    
    Args:
        config_path: Path to main config file (default: caissa_config.yaml)
        local_path: Path to local override file (default: caissa_config.local.yaml)
        cli_overrides: Dict of CLI overrides in nested format, e.g. {"llm": {"provider": "openai"}}
    
    Returns:
        Fully resolved CaissaConfig
    """
    # 1. Load base config
    if config_path is None:
        config_path = str(PROJECT_ROOT / "caissa_config.yaml")
    base_data = _load_yaml_file(Path(config_path))
    
    # 2. Load local overrides
    if local_path is None:
        local_path = str(PROJECT_ROOT / "caissa_config.local.yaml")
    local_data = _load_yaml_file(Path(local_path))
    
    # 3. Merge: base <- local
    merged = _deep_merge(base_data, local_data)
    
    # 4. Apply environment variable overrides
    merged = _apply_env_overrides(merged)
    
    # 5. Apply CLI overrides
    if cli_overrides:
        merged = _deep_merge(merged, cli_overrides)
    
    # 6. Build typed config
    config = _build_config_from_dict(merged)
    
    # 7. Validate
    validate_config(config)
    
    return config


def config_to_dict(config: CaissaConfig) -> dict:
    """Convert a CaissaConfig to a serializable dict (for display/export)."""
    import dataclasses
    
    def _dc_to_dict(obj):
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            result = {}
            for f in dataclasses.fields(obj):
                val = getattr(obj, f.name)
                if isinstance(val, Path):
                    result[f.name] = str(val)
                else:
                    result[f.name] = _dc_to_dict(val)
            return result
        elif isinstance(obj, dict):
            return {k: _dc_to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [_dc_to_dict(v) for v in obj]
        else:
            return obj
    
    return _dc_to_dict(config)


# =============================================================================
# GLOBAL SINGLETON
# =============================================================================

# Load config once on import. Modules can import `cfg` directly.
try:
    cfg: CaissaConfig = load_config()
except ConfigValidationError as _e:
    logger.warning("Config validation failed on startup — using defaults: %s", _e)
    cfg = CaissaConfig()


def reload_config(**kwargs) -> CaissaConfig:
    """Reload configuration (e.g., after changing the config file)."""
    global cfg
    cfg = load_config(**kwargs)
    return cfg
