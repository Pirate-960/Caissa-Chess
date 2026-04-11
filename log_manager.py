"""
log_manager.py

Centralized logging infrastructure for the Caissa Chess Engine.

Organises logs into a structured directory hierarchy::

    logs/
    ├── master.log              — Aggregated log of ALL events
    ├── llm/
    │   ├── calls.log           — Full LLM prompt / response pairs
    │   └── errors.log          — LLM errors (retryable and fatal)
    ├── generation/
    │   └── generation.log      — Game generation pipeline (retries, timing)
    ├── validation/
    │   └── validation.log      — Move-by-move legality checks
    ├── engine/
    │   └── stockfish.log       — Stockfish evaluations
    ├── export/
    │   └── export.log          — Export pipeline events
    ├── cli/
    │   └── activity.log        — CLI user interactions
    ├── prompts/
    │   └── prompts.log         — Prompt construction details
    ├── aesthetic/
    │   └── aesthetic.log       — Beauty & style evaluation
    ├── config/
    │   └── config.log          — Configuration loading events
    └── benchmark/
        └── benchmark.log       — Benchmark execution

Usage
-----
At application startup (``main.py``)::

    from log_manager import setup_logging, get_logger, SESSION_ID
    setup_logging()          # reads settings from config_manager.cfg

In any module::

    from log_manager import get_logger
    logger = get_logger("generation")  # → logging.getLogger("caissa.generation")
"""

import logging
import uuid
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Dict


# ─── Process-wide session ID ────────────────────────────────────────────────
SESSION_ID: str = uuid.uuid4().hex[:8]


# ─── Module state ───────────────────────────────────────────────────────────
_setup_done = False
_setup_lock = threading.Lock()
_log_dir: Optional[Path] = None
_llm_prompts_enabled: bool = True
_console_handler: Optional[logging.StreamHandler] = None


# ─── Formatters ─────────────────────────────────────────────────────────────
_MASTER_FMT = "%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s"
_MASTER_DATE_FMT = "%Y-%m-%d %H:%M:%S"
_LLM_FMT = "%(asctime)s\n%(message)s\n"
_CONSOLE_FMT = "%(levelname)-8s | %(message)s"

# Map verbosity strings to the minimum level shown on the console.
_VERBOSITY_LEVELS: Dict[str, int] = {
    "quiet":   logging.CRITICAL,   # effectively silent
    "normal":  logging.INFO,       # key progress messages
    "verbose": logging.DEBUG,      # everything
    "debug":   logging.DEBUG,
}


# ─── Log category definitions ───────────────────────────────────────────────
# Each category maps to a subdirectory and filename inside the log root.

LOG_CATEGORIES: Dict[str, Dict[str, str]] = {
    "cli":        {"dir": "cli",        "file": "activity.log"},
    "config":     {"dir": "config",     "file": "config.log"},
    "generation": {"dir": "generation", "file": "generation.log"},
    "llm.calls":  {"dir": "llm",        "file": "calls.log"},
    "llm.errors": {"dir": "llm",        "file": "errors.log"},
    "prompts":    {"dir": "prompts",    "file": "prompts.log"},
    "validation": {"dir": "validation", "file": "validation.log"},
    "engine":     {"dir": "engine",     "file": "stockfish.log"},
    "export":     {"dir": "export",     "file": "export.log"},
    "aesthetic":  {"dir": "aesthetic",   "file": "aesthetic.log"},
    "benchmark":  {"dir": "benchmark",  "file": "benchmark.log"},
}


# Map existing ``logging.getLogger(__name__)`` names → log categories so that
# pre-existing module-level loggers are automatically routed to the correct
# per-category files without changing their declarations.

_LEGACY_MODULE_MAP: Dict[str, str] = {
    "core.generator":                   "generation",
    "core.llm_provider":                "generation",
    "core.match_engine":                "validation",  # LLM vs LLM match validation
    "core.tournament":                  "generation",  # Tournament orchestration
    "core.match_analyzer":              "engine",      # Post-match analysis
    "core.prompt_manager":              "prompts",
    "core.board_state":                 "validation",
    "core.provider_factory":            "config",
    "engine.legality":                  "validation",
    "engine.stockfish_client":          "engine",
    "export.pgn_builder":               "export",
    "export.game_exporter":             "export",
    "export.annotation_parser":         "export",
    "export.tournament_exporter":       "export",      # Tournament exports
    "aesthetic.beauty_eval":            "aesthetic",
    "aesthetic.style_slider":           "aesthetic",
    "config_manager":                   "config",
    "benchmarks.provider_benchmark":    "benchmark",
    "benchmarks.quality_analyzer":      "benchmark",
    "benchmarks.report_generator":      "benchmark",
    "benchmarks.benchmark_history":     "benchmark",
    "benchmarks.rich_console":          "benchmark",
}


# ─── Helpers ────────────────────────────────────────────────────────────────

def _make_handler(
    file_path: Path,
    fmt: str,
    date_fmt: str,
    max_bytes: int,
    backup_count: int,
    level: int = logging.DEBUG,
) -> RotatingFileHandler:
    """Create a :class:`RotatingFileHandler` with the given settings."""
    handler = RotatingFileHandler(
        str(file_path),
        mode="a",
        encoding="utf-8",
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(fmt, datefmt=date_fmt))
    return handler


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═════════════════════════════════════════════════════════════════════════════

def setup_logging(
    log_dir: str = "logs",
    level: str = "INFO",
    log_format: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 3,
    log_llm_prompts: bool = True,
    verbosity: str = "normal",
    console_logs: bool = True,
) -> None:
    """
    Initialise the entire logging infrastructure.

    Creates the directory tree, wires :class:`RotatingFileHandler` instances
    for every category, and configures the root logger with a master
    aggregation log.

    **Call once** at application startup before any logging occurs.
    Subsequent calls are safe no-ops.
    """
    global _setup_done, _log_dir, _llm_prompts_enabled, _console_handler

    with _setup_lock:
        if _setup_done:
            return

        project_root = Path(__file__).parent.resolve()
        _log_dir = project_root / log_dir
        _llm_prompts_enabled = log_llm_prompts
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        fmt = log_format or _MASTER_FMT

        # ── Create directory tree ────────────────────────────────────
        _log_dir.mkdir(parents=True, exist_ok=True)
        seen_dirs: set = set()
        for cat_info in LOG_CATEGORIES.values():
            d = cat_info["dir"]
            if d not in seen_dirs:
                (_log_dir / d).mkdir(parents=True, exist_ok=True)
                seen_dirs.add(d)

        # ── 1. Root logger → master.log ──────────────────────────────
        root = logging.getLogger()
        root.handlers.clear()               # remove stale basicConfig handlers
        root.setLevel(logging.DEBUG)         # let individual handlers filter

        master_handler = _make_handler(
            _log_dir / "master.log",
            fmt, _MASTER_DATE_FMT,
            max_bytes, backup_count,
            numeric_level,
        )
        root.addHandler(master_handler)

        # ── 1b. Root logger → console (stderr) ──────────────────────
        _console_handler = None
        if console_logs:
            console_level = _VERBOSITY_LEVELS.get(verbosity.lower(), logging.INFO)
            if console_level < logging.CRITICAL:      # "quiet" → no handler
                console = logging.StreamHandler()     # defaults to stderr
                console.setLevel(console_level)
                console.setFormatter(logging.Formatter(_CONSOLE_FMT))
                root.addHandler(console)
                _console_handler = console

        # ── 2. Category loggers (caissa.*) ───────────────────────────
        for category, cat_info in LOG_CATEGORIES.items():
            logger_name = f"caissa.{category}"
            cat_logger = logging.getLogger(logger_name)
            cat_logger.setLevel(logging.DEBUG)
            cat_logger.handlers.clear()

            # LLM call / error logs are too verbose for master.log
            if category.startswith("llm."):
                cat_logger.propagate = False

                if category == "llm.calls" and not log_llm_prompts:
                    cat_logger.addHandler(logging.NullHandler())
                    continue

                handler = _make_handler(
                    _log_dir / cat_info["dir"] / cat_info["file"],
                    _LLM_FMT, _MASTER_DATE_FMT,
                    max_bytes, backup_count,
                )
                cat_logger.addHandler(handler)
            else:
                # Normal categories: own file + propagate to master
                cat_logger.propagate = True
                handler = _make_handler(
                    _log_dir / cat_info["dir"] / cat_info["file"],
                    fmt, _MASTER_DATE_FMT,
                    max_bytes, backup_count,
                )
                cat_logger.addHandler(handler)

        # ── 3. Legacy module loggers → category files ────────────────
        #    So that existing `logger = logging.getLogger(__name__)`
        #    declarations automatically go to the right category file
        #    (plus master.log via root propagation).
        for module_name, category in _LEGACY_MODULE_MAP.items():
            cat_info = LOG_CATEGORIES.get(category)
            if not cat_info:
                continue

            mod_logger = logging.getLogger(module_name)

            # Avoid duplicating if the handler already exists
            target_filename = cat_info["file"]
            already_has = any(
                isinstance(h, RotatingFileHandler)
                and getattr(h, "baseFilename", "").replace("\\", "/").endswith(target_filename)
                for h in mod_logger.handlers
            )
            if already_has:
                continue

            handler = _make_handler(
                _log_dir / cat_info["dir"] / cat_info["file"],
                fmt, _MASTER_DATE_FMT,
                max_bytes, backup_count,
            )
            mod_logger.addHandler(handler)

        # ── 4. Session banner ────────────────────────────────────────
        startup_logger = logging.getLogger("caissa.cli")
        startup_logger.info(
            "Session %s started — log_dir=%s, level=%s, verbosity=%s",
            SESSION_ID, _log_dir, level, verbosity,
        )

        _setup_done = True


def get_logger(category: str) -> logging.Logger:
    """
    Return a named logger under the ``caissa.*`` hierarchy.

    If :func:`setup_logging` has not been called yet it is invoked
    automatically with settings from ``config_manager.cfg`` (or defaults).

    Args:
        category: Known category (e.g. ``"generation"``, ``"validation"``,
                  ``"cli"``, ``"llm.calls"``) or any custom sub-name.

    Returns:
        :class:`logging.Logger` instance.
    """
    if not _setup_done:
        _auto_setup()
    return logging.getLogger(f"caissa.{category}")


def get_session_id() -> str:
    """Return the process-wide session identifier (8 hex chars)."""
    return SESSION_ID


def is_llm_logging_enabled() -> bool:
    """Whether full LLM prompt/response logging is active."""
    if not _setup_done:
        _auto_setup()
    return _llm_prompts_enabled


def get_log_dir() -> Optional[Path]:
    """Return the resolved log directory path, or ``None`` if not set up."""
    return _log_dir


def get_console_handler() -> Optional[logging.StreamHandler]:
    """Return the console StreamHandler managed by setup_logging(), if any."""
    return _console_handler


# ─── Private auto-setup ────────────────────────────────────────────────────

def _auto_setup() -> None:
    """Auto-initialise from ``config_manager`` if available, else defaults."""
    try:
        from config_manager import cfg
        setup_logging(
            log_dir=getattr(cfg.logging, "log_dir", "logs"),
            level=cfg.logging.level,
            log_format=cfg.logging.format,
            max_bytes=getattr(cfg.logging, "max_bytes", 10_485_760),
            backup_count=getattr(cfg.logging, "backup_count", 3),
            log_llm_prompts=cfg.logging.log_llm_prompts,
            verbosity=cfg.logging.verbosity,
        )
    except Exception:
        setup_logging()
