"""
main.py

Unified interactive entry point for CAISSA Chess Engine.
Run: python main.py

Guides users through all features with an interactive CLI menu.
All functionality is accessible from this single file.
"""

import sys
import os
import time
import datetime
import logging
import threading
import uuid
import json
import re
from pathlib import Path
from typing import Optional, List, Any, Tuple, Dict

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# Force UTF-8 on Windows (skip when imported under pytest to preserve
# pytest's capture file descriptors — conftest.py sets CAISSA_TEST_MODE).
if sys.platform == "win32" and not os.environ.get("CAISSA_TEST_MODE"):
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception:
        pass

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config_manager import cfg, reload_config, config_to_dict
from log_manager import setup_logging, get_logger
from core.prompt_studio_cli import interactive_prompt_studio as _interactive_prompt_studio_impl

# Initialize structured logging from config — must happen before first log.
# Skip when running under pytest (CAISSA_TEST_MODE) so tests control their
# own log setup via a temp directory.
if not os.environ.get("CAISSA_TEST_MODE"):
    setup_logging(
        log_dir=getattr(cfg.logging, "log_dir", "logs"),
        level=cfg.logging.level,
        log_format=cfg.logging.format,
        max_bytes=getattr(cfg.logging, "max_bytes", 10_485_760),
        backup_count=getattr(cfg.logging, "backup_count", 3),
        log_llm_prompts=cfg.logging.log_llm_prompts,
        verbosity=cfg.logging.verbosity,
        console_logs=getattr(cfg.logging, "console_logs", True),
    )

cli_logger = get_logger("cli")


# =============================================================================
# ANSI COLOR HELPERS
# =============================================================================

class C:
    """ANSI color codes for terminal output."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    
    @staticmethod
    def disable():
        """Disable colors (e.g. when piping to file)."""
        for attr in ("RESET", "BOLD", "DIM", "RED", "GREEN", "YELLOW",
                      "BLUE", "MAGENTA", "CYAN", "WHITE"):
            setattr(C, attr, "")

# Disable colors if not a TTY
if not sys.stdout.isatty():
    C.disable()


# =============================================================================
# UI HELPERS
# =============================================================================

UI = {
    "prompt": "❯",
    "ok": "✓",
    "error": "✖",
    "warn": "⚠",
    "info": "•",
}


def _soft_rule(width: int = 60):
    """Render a subtle divider line."""
    print(f"{C.DIM}{'─' * width}{C.RESET}")

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    """Print the CAISSA banner."""
    banner = f"""
{C.CYAN}{C.BOLD}
    ===========================================================
                  ___    _    ___ ____ ____    _    
                 / __|  /_\\  |_ _/ ___/ ___|  /_\\   
                | |    / _ \\  | |\\___ \\___ \\ / _ \\  
                | |__ / ___ \\ | | ___) |__) / ___ \\ 
                 \\___/_/   \\_\\___|____/____/_/   \\_\\
                                                     
              The Aesthetic Chess Game Generator
    ===========================================================
{C.RESET}
{C.DIM}    "We don't generate chess games. We generate immortality."{C.RESET}
"""
    print(banner)


def print_header(title: str, width: int = 60):
    """Print a section header."""
    print()
    print(f"{C.CYAN}{C.DIM}{'╭' + '─' * (width - 2) + '╮'}{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}│ {title.ljust(width - 4)} │{C.RESET}")
    print(f"{C.CYAN}{C.DIM}{'╰' + '─' * (width - 2) + '╯'}{C.RESET}")
    print()


def print_success(msg: str):
    print(f"  {C.GREEN}{UI['ok']}{C.RESET} {msg}")


def print_error(msg: str):
    print(f"  {C.RED}{UI['error']}{C.RESET} {msg}")


def print_warning(msg: str):
    print(f"  {C.YELLOW}{UI['warn']}{C.RESET} {msg}")


def print_info(msg: str):
    print(f"  {C.BLUE}{UI['info']}{C.RESET} {msg}")


def _new_run_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _mode_validation_policy(mode: str) -> str:
    if mode == "single":
        return "Single-LLM finalization: terminal result required (1-0/0-1/1/2-1/2), no '*'."
    if mode == "match":
        return "LLM-vs-LLM: forfeit/in-progress semantics allowed per match engine termination rules."
    if mode == "tournament":
        return "Tournament: match-level termination semantics allowed; aggregate outputs may include unfinished matches."
    if mode == "batch":
        return "Batch single-LLM: each game must pass legality; non-terminal results are treated as failures by generator policy."
    return "Mode-specific validation applies."


def _announce_validation_policy(mode: str):
    print_info(f"Validation policy: {_mode_validation_policy(mode)}")


def _read_multiline_input(prompt_title: str) -> str:
    print_info(f"{prompt_title}")
    print(f"  {C.DIM}Paste lines, then type EOF on its own line to finish.{C.RESET}")
    lines = []
    while True:
        line = input("")
        if line.strip() == "EOF":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _read_text_if_exists(path: Path) -> Optional[str]:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        return None
    return None


def _extract_summary_from_pgn_text(text: str) -> dict:
    if not text:
        return {}
    result = "*"
    m = re.search(r'\[Result\s+"([^"]+)"\]', text)
    if m:
        result = m.group(1).strip()
    ann = None
    am = re.search(r"Annotated moves:\s*(\d+)\s*/\s*(\d+)", text)
    if am:
        ann = (int(am.group(1)), int(am.group(2)))
    return {"result": result, "annotated": ann}


def _extract_summary_from_json_text(text: str) -> dict:
    if not text:
        return {}
    try:
        data = json.loads(text)
    except Exception:
        return {}
    meta = data.get("metadata", {})
    summ = data.get("summary", {})
    return {
        "result": meta.get("result"),
        "moves": summ.get("total_moves") or meta.get("move_count"),
        "annotations": summ.get("annotations_count"),
    }


def _warn_export_guardrail(output_paths: List[Path], mode: str, run_id: str):
    """
    Warning-only export consistency checks. Never raises.
    """
    try:
        pgn_path = next((p for p in output_paths if p.suffix.lower() == ".pgn"), None)
        json_path = next((p for p in output_paths if p.suffix.lower() == ".json"), None)
        if not pgn_path and not json_path:
            return

        pgn_summary = _extract_summary_from_pgn_text(_read_text_if_exists(pgn_path) or "") if pgn_path else {}
        json_summary = _extract_summary_from_json_text(_read_text_if_exists(json_path) or "") if json_path else {}

        issues = []
        pgn_result = pgn_summary.get("result")
        json_result = json_summary.get("result")
        if pgn_result and json_result and pgn_result != json_result:
            issues.append(f"result mismatch: PGN={pgn_result}, JSON={json_result}")

        if issues:
            print_warning("Export guardrail: potential consistency issues detected (warning-only).")
            for issue in issues:
                print_warning(f"  - {issue}")
            cli_logger.warning("run_id=%s mode=%s export_guardrail_issues=%s", run_id, mode, issues)
        else:
            cli_logger.info("run_id=%s mode=%s export_guardrail=ok", run_id, mode)
    except Exception as exc:
        cli_logger.warning("run_id=%s mode=%s export_guardrail_error=%s", run_id, mode, exc)


def interactive_prompt_studio():
    """Prompt Studio: inspect and safely override prompts."""
    _interactive_prompt_studio_impl(
        io={
            "C": C,
            "UI": UI,
            "GO_BACK": GO_BACK,
            "project_root": PROJECT_ROOT,
            "prompt_choice": prompt_choice,
            "prompt_input": prompt_input,
            "prompt_int": prompt_int,
            "prompt_yes_no": prompt_yes_no,
            "print_header": print_header,
            "print_info": print_info,
            "print_warning": print_warning,
            "print_error": print_error,
            "print_success": print_success,
            "read_multiline_input": _read_multiline_input,
            "soft_rule": _soft_rule,
        }
    )


class _BufferingHandler(logging.Handler):
    """Stores log records in memory so they can be replayed later."""

    def __init__(self):
        super().__init__()
        self.buffer: List[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord):
        self.buffer.append(record)


class Spinner:
    """Animated spinner shown during long-running blocking operations.

    Usage::

        with Spinner("Calling LLM"):
            result = slow_function()

    The spinner runs on a background daemon thread and clears its line
    when the ``with`` block exits (success or exception).

    While active the console ``StreamHandler`` is temporarily muted and
    its records are buffered.  When the spinner stops, buffered messages
    are flushed cleanly below the cleared spinner line so they never
    collide with the animation.
    """

    _FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Working", interval: float = 0.1):
        self._msg = message
        self._interval = interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_time: float = 0.0
        # Log-buffering state
        self._console_handler: Optional[logging.StreamHandler] = None
        self._saved_level: int = logging.NOTSET
        self._buf_handler: Optional[_BufferingHandler] = None

    # --- context manager ---------------------------------------------------
    def __enter__(self):
        self._start_time = time.time()
        self._stop.clear()
        self._mute_console()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        # clear spinner line
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()
        self._restore_console()

    # --- log buffering ------------------------------------------------------
    def _mute_console(self):
        """Find the root logger's console StreamHandler, mute it, add buffer."""
        root = logging.getLogger()
        for h in root.handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(
                h, logging.FileHandler
            ):
                self._console_handler = h
                self._saved_level = h.level
                # Suppress all console output while spinner is active
                h.setLevel(logging.CRITICAL + 1)
                break
        # Attach a buffering handler to capture what would have gone to console
        self._buf_handler = _BufferingHandler()
        self._buf_handler.setLevel(self._saved_level)
        root.addHandler(self._buf_handler)

    def _restore_console(self):
        """Restore original console handler level and flush buffered records."""
        root = logging.getLogger()
        # Remove buffer handler
        if self._buf_handler:
            root.removeHandler(self._buf_handler)
        # Restore console handler
        if self._console_handler:
            self._console_handler.setLevel(self._saved_level)
            # Flush buffered records through the real console handler
            if self._buf_handler:
                for record in self._buf_handler.buffer:
                    if record.levelno >= self._saved_level:
                        self._console_handler.emit(record)
        self._console_handler = None
        self._buf_handler = None

    # --- internal -----------------------------------------------------------
    def _spin(self):
        idx = 0
        while not self._stop.is_set():
            elapsed = time.time() - self._start_time
            frame = self._FRAMES[idx % len(self._FRAMES)]
            line = f"\r  {C.CYAN}{frame}{C.RESET} {self._msg}... {C.DIM}({elapsed:.0f}s){C.RESET}"
            sys.stdout.write(line)
            sys.stdout.flush()
            idx += 1
            self._stop.wait(self._interval)


# ─────────────────────────────────────────────────────────────────────────────
# BATCH SPINNER — animated per-job progress for batch generation
# ─────────────────────────────────────────────────────────────────────────────

class BatchSpinner:
    """A rich animated spinner that shows real-time batch generation progress.

    Displays a continuously-animated spinner line while a job is RUNNING,
    then overwrites it with a final status (OK / FAIL / SKIP) when completed.

    Usage::

        bs = BatchSpinner(total=10)
        bs.start()
        ...
        bs.update(job_index, total, status, msg)
        ...
        bs.stop()
    """

    _CHESS_FRAMES = ["♔ ", "♕ ", "♗ ", "♘ ", "♖ ", "♙ ", "♚ ", "♛ ", "♝ ", "♞ ", "♜ ", "♟ "]
    _BAR_WIDTH = 120

    def __init__(self, total: int):
        self._total = total
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_time: float = 0.0
        # Current running job info
        self._current_index: int = 0
        self._current_msg: str = ""
        self._is_running: bool = False
        self._completed: int = 0
        self._failed: int = 0
        # Log-buffering state (same pattern as Spinner)
        self._console_handler: Optional[logging.StreamHandler] = None
        self._saved_level: int = logging.NOTSET
        self._buf_handler: Optional[_BufferingHandler] = None

    def start(self):
        self._start_time = time.time()
        self._stop.clear()
        self._mute_console()
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        # Clear the spinner line
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()
        self._restore_console()

    # --- log buffering ------------------------------------------------------
    def _mute_console(self):
        """Suppress console log output while spinner is active."""
        root = logging.getLogger()
        for h in root.handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(
                h, logging.FileHandler
            ):
                self._console_handler = h
                self._saved_level = h.level
                h.setLevel(logging.CRITICAL + 1)
                break
        self._buf_handler = _BufferingHandler()
        self._buf_handler.setLevel(self._saved_level)
        root.addHandler(self._buf_handler)

    def _restore_console(self):
        """Restore console handler and flush buffered log records."""
        root = logging.getLogger()
        if self._buf_handler:
            root.removeHandler(self._buf_handler)
        if self._console_handler:
            self._console_handler.setLevel(self._saved_level)
            if self._buf_handler:
                for record in self._buf_handler.buffer:
                    if record.levelno >= self._saved_level:
                        self._console_handler.emit(record)
        self._console_handler = None
        self._buf_handler = None

    def update(self, job_index: int, total: int, status, msg: str):
        """Called by the batch engine's progress callback."""
        # Import here to avoid circular import at module level
        from core.batch_engine import BatchJobStatus

        with self._lock:
            if status == BatchJobStatus.RUNNING:
                self._current_index = job_index
                self._current_msg = msg
                self._is_running = True
            else:
                self._is_running = False
                # Clear spinner line, print final status, then let spinner resume
                sys.stdout.write("\r\033[K")
                tag = f"[{job_index}/{total}]"
                if status == BatchJobStatus.SKIPPED:
                    print(f"  {tag} {C.DIM}⏭  SKIP{C.RESET}  {msg}")
                elif status == BatchJobStatus.SUCCESS:
                    self._completed += 1
                    print(f"  {tag} {C.GREEN}✓  OK{C.RESET}    {msg}")
                elif status == BatchJobStatus.FAILED:
                    self._failed += 1
                    print(f"  {tag} {C.RED}✗  FAIL{C.RESET}  {msg}")

    def _progress_bar(self) -> str:
        """Build a mini progress bar.

        Counts completed + failed jobs as fully done, and adds the
        currently-running job as a partial contribution so the bar
        visually advances while a game is being generated.
        """
        done = self._completed + self._failed
        # Add a half-step for the job currently in-flight
        effective = done + (0.5 if self._is_running else 0)
        ratio = effective / self._total if self._total else 0
        ratio = min(ratio, 1.0)
        filled = int(self._BAR_WIDTH * ratio)
        bar = f"{C.GREEN}{'█' * filled}{C.DIM}{'░' * (self._BAR_WIDTH - filled)}{C.RESET}"
        pct = int(ratio * 100)
        return f"{bar} {pct}%"

    def _animate(self):
        idx = 0
        while not self._stop.is_set():
            with self._lock:
                if self._is_running:
                    elapsed = time.time() - self._start_time
                    frame = self._CHESS_FRAMES[idx % len(self._CHESS_FRAMES)]
                    tag = f"[{self._current_index}/{self._total}]"
                    bar = self._progress_bar()
                    line = (
                        f"\r  {tag} {C.CYAN}{frame}{C.RESET}"
                        f" {self._current_msg}"
                        f"  {bar}"
                        f"  {C.DIM}{elapsed:.0f}s{C.RESET}"
                    )
                    sys.stdout.write(f"\r\033[K{line}")
                    sys.stdout.flush()
            idx += 1
            self._stop.wait(0.15)


# Sentinel value returned by prompt helpers when the user chooses "Back".
GO_BACK = "__GO_BACK__"


def prompt_choice(
    prompt: str,
    options: List[str],
    default: Optional[int] = None,
    allow_back: bool = False,
) -> int:
    """
    Display numbered options and return the selected index (0-based).

    Args:
        prompt: The question to ask
        options: List of option labels
        default: Default selection (1-based) or None
        allow_back: If True, show a "0. ← Back" option and return GO_BACK
                    when the user selects it.

    Returns:
        Selected index (0-based), or GO_BACK sentinel string.
    """
    _soft_rule()
    print(f"  {C.BOLD}{prompt}{C.RESET}")
    for i, opt in enumerate(options, 1):
        marker = f" {C.GREEN}• default{C.RESET}" if default == i else ""
        print(f"    {C.CYAN}{i:>2}.{C.RESET} {opt}{marker}")
    if allow_back:
        print(f"    {C.DIM} 0. ← Back{C.RESET}")

    while True:
        suffix = f" [{default}]" if default else ""
        raw = input(f"\n  {C.YELLOW}{UI['prompt']}{C.RESET} Enter choice{suffix}: ").strip()

        if not raw and default is not None:
            return default - 1

        # "back" / "b" shorthand
        if allow_back and raw.lower() in ("0", "back", "b"):
            return GO_BACK

        try:
            choice = int(raw)
            if allow_back and choice == 0:
                return GO_BACK
            if 1 <= choice <= len(options):
                return choice - 1
        except ValueError:
            pass

        lo = "0" if allow_back else "1"
        print(f"  {C.RED}Invalid choice. Enter {lo}-{len(options)}.{C.RESET}")


def prompt_input(
    prompt: str,
    default: Optional[str] = None,
    allow_back: bool = False,
) -> str:
    """Prompt for text input with optional default. Returns GO_BACK on 'back'."""
    suffix = f" [{C.DIM}{default}{C.RESET}]" if default else ""
    if allow_back:
        suffix += f"  {C.DIM}(0 to go back){C.RESET}"
    raw = input(f"  {C.YELLOW}{UI['prompt']}{C.RESET} {prompt}{suffix}: ").strip()
    if allow_back and raw.lower() in ("0", "back", "b"):
        return GO_BACK
    return raw if raw else (default or "")


def prompt_int(
    prompt: str,
    default: int,
    min_val: int = 1,
    max_val: int = 100,
    allow_back: bool = False,
) -> int:
    """Prompt for an integer with validation. Returns GO_BACK on 'back'."""
    while True:
        raw = prompt_input(f"{prompt} ({min_val}-{max_val})", str(default), allow_back=allow_back)
        if raw is GO_BACK:
            return GO_BACK
        try:
            val = int(raw)
            if min_val <= val <= max_val:
                return val
        except (ValueError, TypeError):
            pass
        print(f"  {C.RED}Enter a number between {min_val} and {max_val}.{C.RESET}")


def prompt_yes_no(
    prompt: str,
    default: bool = True,
    allow_back: bool = False,
) -> bool:
    """Prompt for yes/no. Returns GO_BACK on 'back'."""
    hint = "Y/n" if default else "y/N"
    back_hint = f"  {C.DIM}(0 to go back){C.RESET}" if allow_back else ""
    raw = input(f"  {C.YELLOW}{UI['prompt']}{C.RESET} {prompt} [{hint}]{back_hint}: ").strip().lower()
    if allow_back and raw in ("0", "back", "b"):
        return GO_BACK
    if not raw:
        return default
    return raw in ("y", "yes", "1", "true")


def prompt_multi_choice(
    prompt: str,
    options: List[str],
    defaults: Optional[List[int]] = None,
    allow_back: bool = False,
) -> list:
    """
    Display numbered options and let the user pick multiple (comma-separated).

    Args:
        prompt: The question to ask
        options: List of option labels
        defaults: Default selections (1-based) — pre-selected if user presses Enter
        allow_back: If True, show a "0. ← Back" option

    Returns:
        List of 0-based indices, or GO_BACK sentinel.
    """
    _soft_rule()
    print(f"  {C.BOLD}{prompt}{C.RESET}")
    for i, opt in enumerate(options, 1):
        marker = ""
        if defaults and i in defaults:
            marker = f" {C.GREEN}• default{C.RESET}"
        print(f"    {C.CYAN}{i:>2}.{C.RESET} {opt}{marker}")
    if allow_back:
        print(f"    {C.DIM} 0. ← Back{C.RESET}")
    print(f"    {C.DIM}(Enter comma-separated numbers, e.g. 1,3,5 or 'all'){C.RESET}")

    while True:
        default_str = ",".join(str(d) for d in (defaults or []))
        suffix = f" [{default_str}]" if default_str else ""
        raw = input(f"\n  {C.YELLOW}{UI['prompt']}{C.RESET} Enter choices{suffix}: ").strip()

        if not raw and defaults:
            return [d - 1 for d in defaults]

        if allow_back and raw.lower() in ("0", "back", "b"):
            return GO_BACK

        if raw.lower() == "all":
            return list(range(len(options)))

        try:
            nums = [int(x.strip()) for x in raw.split(",") if x.strip()]
            if allow_back and 0 in nums:
                return GO_BACK
            if all(1 <= n <= len(options) for n in nums) and nums:
                return [n - 1 for n in nums]
        except ValueError:
            pass

        print(f"  {C.RED}Invalid. Enter numbers 1-{len(options)} separated by commas.{C.RESET}")


# =============================================================================
# FEATURE: GENERATE A GAME (interactive)
# =============================================================================

def interactive_generate():
    """Walk the user through generating a single chess game (with go-back)."""
    cli_logger.info("User selected: Generate a Chess Game")
    print_header("Generate a Chess Game")

    # Shared option lists ─────────────────────────────────────────────────────
    styles = [
        "Tal          - Intuitive, risky, attacking",
        "Capablanca   - Perfect, positional, clinical",
        "Morphy       - Classical, attacking, sound",
        "Coffee House - Gambits, tricks, complications",
        "Neural       - AlphaZero-like, alien logic",
        "Karpov       - Positional squeeze, silent strength",
    ]
    style_keys = ["tal", "capablanca", "morphy", "coffee_house", "neural", "karpov"]
    eras = [
        "Romantic     - 1850s, sacrifices and brilliance",
        "Classical    - 1880s-1920s, principled play",
        "Hypermodern  - 1920s-1930s, flank strategies",
        "Soviet       - 1920s-1970s, scientific approach",
        "Computer     - 1980s-2000s, precise calculation",
        "Neural       - 2010s+, AI-inspired play",
    ]
    era_keys = ["romantic", "classical", "hypermodern", "soviet", "computer", "neural"]
    themes = [
        "Queen Sacrifice", "Rook Sacrifice", "Windmill Attack",
        "Minority Attack", "Pawn Storm", "Quiet Killer Move",
        "Perpetual Check", "Stalemate Trap", "Back Rank Weakness",
        "Fianchetto Setup",
    ]
    theme_keys = [
        "QUEEN_SACRIFICE", "ROOK_SACRIFICE", "WINDMILL", "MINORITY_ATTACK",
        "PAWN_STORM", "QUIET_KILLER", "PERPETUAL_CHECK", "STALEMATE_TRAP",
        "BACK_RANK", "FIANCHETTO",
    ]
    formats = ["PGN", "Markdown", "HTML", "JSON", "All"]
    format_keys = ["pgn", "markdown", "html", "json", "all"]

    # Collected answers (populated step-by-step) ──────────────────────────────
    style = era = theme = None
    aggression = chaos = depth = None
    white = black = output_format = output_path = pretty = provider_name = None

    step = 0  # step counter; go-back decrements it

    while step <= 10:  # 0..10 = the steps, 11 → done
        # Step 0 ── Style
        if step == 0:
            style_default = style_keys.index(cfg.generation.style) + 1 if cfg.generation.style in style_keys else 1
            v = prompt_choice("Select playing style:", styles, default=style_default, allow_back=True)
            if v is GO_BACK:
                return  # back from first step → return to main menu
            style = style_keys[v]
            step += 1
            continue

        # Step 1 ── Era
        if step == 1:
            era_default = era_keys.index(cfg.generation.era) + 1 if cfg.generation.era in era_keys else 1
            v = prompt_choice("Select chess era:", eras, default=era_default, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            era = era_keys[v]
            step += 1
            continue

        # Step 2 ── Theme
        if step == 2:
            use_theme = prompt_yes_no("Apply a thematic concept?", default=False, allow_back=True)
            if use_theme is GO_BACK:
                step -= 1
                continue
            theme = None
            if use_theme:
                v = prompt_choice("Select theme:", themes, allow_back=True)
                if v is GO_BACK:
                    continue  # re-ask the theme yes/no
                theme = theme_keys[v]
            step += 1
            continue

        # Step 3 ── Aggression
        if step == 3:
            v = prompt_int("Aggression level", cfg.generation.aggression, 1, 10, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            aggression = v
            step += 1
            continue

        # Step 4 ── Chaos
        if step == 4:
            v = prompt_int("Chaos level", cfg.generation.chaos, 1, 10, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            chaos = v
            step += 1
            continue

        # Step 5 ── Depth
        if step == 5:
            v = prompt_int("Target game length (half-moves)", cfg.generation.depth, 10, 200, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            depth = v
            step += 1
            continue

        # Step 6 ── Player names
        if step == 6:
            w = prompt_input("White player name", cfg.generation.white_player, allow_back=True)
            if w is GO_BACK:
                step -= 1
                continue
            b = prompt_input("Black player name", cfg.generation.black_player, allow_back=True)
            if b is GO_BACK:
                continue  # re-ask white name
            white, black = w, b
            step += 1
            continue

        # Step 7 ── Output format
        if step == 7:
            v = prompt_choice("Output format:", formats, default=1, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            output_format = format_keys[v]
            step += 1
            continue

        # Step 8 ── Output path & pretty
        if step == 8:
            default_ext = {"pgn": ".pgn", "markdown": ".md", "html": ".html", "json": ".json", "all": ".pgn"}
            default_out = f"game{default_ext[output_format]}"
            v = prompt_input("Output file path", default_out, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            output_path = v
            v = prompt_yes_no("Enable pretty formatting?", default=True, allow_back=True)
            if v is GO_BACK:
                continue  # re-ask output path
            pretty = v
            step += 1
            continue

        # Step 9 ── LLM Provider
        if step == 9:
            providers = _get_available_providers()
            if not providers:
                print_error("No LLM provider configured. Set API keys in .env or caissa_config.yaml.")
                print_info("Supported providers: openai, anthropic, gemini, deepseek, ollama")
                return
            if len(providers) == 1:
                provider_name = providers[0]
                print_info(f"Using provider: {provider_name}")
            else:
                provider_labels = [_provider_display(p) for p in providers]
                v = prompt_choice("Select LLM provider:", provider_labels, default=1, allow_back=True)
                if v is GO_BACK:
                    step -= 1
                    continue
                provider_name = providers[v]
            step += 1
            continue

        # Step 10 ── Confirmation
        if step == 10:
            print(f"\n  {C.BOLD}Configuration Summary:{C.RESET}")
            print(f"    Style:       {C.CYAN}{style}{C.RESET}")
            print(f"    Era:         {C.CYAN}{era}{C.RESET}")
            print(f"    Theme:       {C.CYAN}{theme or 'None'}{C.RESET}")
            print(f"    Aggression:  {C.CYAN}{aggression}/10{C.RESET}")
            print(f"    Chaos:       {C.CYAN}{chaos}/10{C.RESET}")
            print(f"    Length:      {C.CYAN}{depth} half-moves{C.RESET}")
            print(f"    White:       {C.CYAN}{white}{C.RESET}")
            print(f"    Black:       {C.CYAN}{black}{C.RESET}")
            print(f"    Provider:    {C.CYAN}{provider_name}{C.RESET}")
            print(f"    Format:      {C.CYAN}{output_format}{C.RESET}")
            print(f"    Output:      {C.CYAN}{output_path}{C.RESET}")
            print(f"    Pretty:      {C.CYAN}{pretty}{C.RESET}")

            v = prompt_yes_no("\n  Proceed with generation?", default=True, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            if not v:
                print_info("Generation cancelled.")
                return
            break  # confirmed → execute

    # --- Execute ---
    _execute_generation(
        style=style,
        era=era,
        theme=theme,
        aggression=aggression,
        chaos=chaos,
        depth=depth,
        white=white,
        black=black,
        provider_name=provider_name,
        output_format=output_format,
        output_path=output_path,
        pretty=pretty,
    )


# =============================================================================
# FEATURE: BATCH GENERATE
# =============================================================================

def interactive_batch():
    """Walk the user through advanced batch game generation (with go-back)."""
    cli_logger.info("User selected: Batch Game Generation")
    print_header("Batch Game Generation")

    style_labels = ["Tal", "Capablanca", "Morphy", "Coffee House", "Neural", "Karpov"]
    style_keys = ["tal", "capablanca", "morphy", "coffee_house", "neural", "karpov"]
    variation_labels = ["Fixed (same style for every game)",
                        "Round-Robin (cycle through selected styles)",
                        "Random (random style each game)"]
    variation_keys = ["fixed", "round_robin", "random"]
    era_labels = ["Romantic 1850s", "Classical 1880s-1920s", "Hypermodern 1920s-1930s",
                  "Soviet School 1920s-1970s", "Computer Era 1980s-2000s", "Neural Network Era 2010s+"]
    era_keys = ["romantic", "classical", "hypermodern", "soviet", "computer", "neural"]
    theme_labels = [
        "Queen Sacrifice", "Rook Sacrifice", "Windmill Attack",
        "Minority Attack", "Pawn Storm", "Quiet Killer Move",
        "Perpetual Check", "Stalemate Trap", "Back Rank Weakness",
        "Fianchetto Setup",
    ]
    theme_keys = [
        "queen_sacrifice", "rook_sacrifice", "windmill", "minority_attack",
        "pawn_storm", "quiet_killer", "perpetual_check", "stalemate_trap",
        "back_rank", "fianchetto",
    ]
    quality_labels = ["Poor (accept anything)", "Acceptable (default)", "Good", "Excellent"]
    quality_keys = ["poor", "acceptable", "good", "excellent"]
    mode_labels = ["Sequential (one at a time)", "Parallel (multiple threads)"]
    mode_keys = ["sequential", "parallel"]
    format_labels = ["PGN", "Markdown", "HTML", "JSON"]
    format_keys = ["pgn", "markdown", "html", "json"]

    # Collected answers
    count = None
    selected_styles = None
    style_variation = None
    selected_eras = None
    use_themes = False
    selected_themes = None
    depth = None
    min_quality = None
    quality_retries = None
    gen_mode = None
    workers = None
    output_dir = None
    filename_pattern = None
    export_formats = None
    pretty = None
    resume = None
    generate_summary = None
    provider_name = None

    step = 0

    while step <= 13:
        # Step 0 ── Count
        if step == 0:
            v = prompt_int("Number of games to generate", cfg.batch.count, 1, 500, allow_back=True)
            if v is GO_BACK:
                return
            count = v
            step += 1
            continue

        # Step 1 ── Styles (multi-select)
        if step == 1:
            v = prompt_multi_choice("Select styles to include:", style_labels,
                                    defaults=[1], allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            selected_styles = [style_keys[i] for i in v]
            step += 1
            continue

        # Step 2 ── Style variation mode
        if step == 2:
            if len(selected_styles) == 1:
                style_variation = "fixed"
                step += 1
                continue
            v = prompt_choice("How should styles vary across games?",
                              variation_labels, default=2, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            style_variation = variation_keys[v]
            step += 1
            continue

        # Step 3 ── Eras (multi-select)
        if step == 3:
            v = prompt_multi_choice("Select chess eras to use:", era_labels,
                                    defaults=[1], allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            selected_eras = [era_keys[i] for i in v]
            step += 1
            continue

        # Step 4 ── Themes
        if step == 4:
            v = prompt_yes_no("Apply thematic concepts to games?", default=False,
                              allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            use_themes = v
            if use_themes:
                t = prompt_multi_choice("Select themes (will rotate across games):",
                                        theme_labels, allow_back=True)
                if t is GO_BACK:
                    continue  # re-ask themes yes/no
                selected_themes = [theme_keys[i] for i in t]
            else:
                selected_themes = []
            step += 1
            continue

        # Step 5 ── Game depth
        if step == 5:
            v = prompt_int("Target game length (half-moves)", cfg.generation.depth,
                           10, 200, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            depth = v
            step += 1
            continue

        # Step 6 ── Quality gate
        if step == 6:
            v = prompt_choice("Minimum quality threshold:", quality_labels,
                              default=2, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            min_quality = quality_keys[v]
            if min_quality in ("good", "excellent"):
                r = prompt_int("Max retries per game to meet quality",
                               cfg.batch.quality_retries, 1, 10,
                               allow_back=True)
                if r is GO_BACK:
                    continue  # re-ask quality
                quality_retries = r
            else:
                quality_retries = 1
            step += 1
            continue

        # Step 7 ── Generation mode
        if step == 7:
            v = prompt_choice("Generation mode:", mode_labels, default=1,
                              allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            gen_mode = mode_keys[v]
            if gen_mode == "parallel":
                w = prompt_int("Number of parallel workers",
                               cfg.advanced.parallel.max_workers, 2, 16,
                               allow_back=True)
                if w is GO_BACK:
                    continue  # re-ask mode
                workers = w
            else:
                workers = 1
            step += 1
            continue

        # Step 8 ── Output directory
        if step == 8:
            v = prompt_input("Output directory", cfg.export.batch_output_dir,
                             allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            output_dir = v
            step += 1
            continue

        # Step 9 ── Filename pattern
        if step == 9:
            print_info("Tokens: {n} = number, {style}, {era}, {theme}, {date}")
            v = prompt_input("Filename pattern (without extension)",
                             cfg.export.batch_filename_pattern.replace(".pgn", ""),
                             allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            filename_pattern = v
            step += 1
            continue

        # Step 10 ── Export formats (multi-select)
        if step == 10:
            v = prompt_multi_choice("Export formats:", format_labels,
                                    defaults=[1], allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            export_formats = [format_keys[i] for i in v]
            step += 1
            continue

        # Step 11 ── Pretty & resume & summary
        if step == 11:
            v = prompt_yes_no("Pretty PGN formatting?", default=True, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            pretty = v
            v = prompt_yes_no("Resume (skip games with existing files)?",
                              default=True, allow_back=True)
            if v is GO_BACK:
                continue
            resume = v
            v = prompt_yes_no("Generate batch summary report?",
                              default=True, allow_back=True)
            if v is GO_BACK:
                continue
            generate_summary = v
            step += 1
            continue

        # Step 12 ── Provider
        if step == 12:
            providers = _get_available_providers()
            if not providers:
                print_error("No LLM provider configured.")
                return
            if len(providers) == 1:
                provider_name = providers[0]
                print_info(f"Using provider: {provider_name}")
            else:
                v = prompt_choice("Select LLM provider:",
                                  [_provider_display(p) for p in providers],
                                  default=1, allow_back=True)
                if v is GO_BACK:
                    step -= 1
                    continue
                provider_name = providers[v]
            step += 1
            continue

        # Step 13 ── Confirm
        if step == 13:
            print(f"\n  {C.BOLD}Batch Configuration:{C.RESET}")
            print(f"    Games:        {C.CYAN}{count}{C.RESET}")
            styles_str = ", ".join(selected_styles)
            if len(selected_styles) > 1:
                styles_str += f" ({style_variation})"
            print(f"    Styles:       {C.CYAN}{styles_str}{C.RESET}")
            print(f"    Eras:         {C.CYAN}{', '.join(selected_eras)}{C.RESET}")
            if selected_themes:
                print(f"    Themes:       {C.CYAN}{', '.join(selected_themes)}{C.RESET}")
            print(f"    Depth:        {C.CYAN}{depth} half-moves{C.RESET}")
            print(f"    Quality:      {C.CYAN}{min_quality} (retries: {quality_retries}){C.RESET}")
            print(f"    Mode:         {C.CYAN}{gen_mode}"
                  f"{f' ({workers} workers)' if gen_mode == 'parallel' else ''}{C.RESET}")
            print(f"    Output:       {C.CYAN}{output_dir}{C.RESET}")
            print(f"    Pattern:      {C.CYAN}{filename_pattern}{C.RESET}")
            print(f"    Formats:      {C.CYAN}{', '.join(export_formats)}{C.RESET}")
            print(f"    Resume:       {C.CYAN}{resume}{C.RESET}")
            print(f"    Summary:      {C.CYAN}{generate_summary}{C.RESET}")
            print(f"    Provider:     {C.CYAN}{provider_name}{C.RESET}")

            v = prompt_yes_no("\n  Proceed?", default=True, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            if not v:
                return
            break

    _execute_batch(
        count=count,
        styles=selected_styles,
        style_variation=style_variation,
        eras=selected_eras,
        themes=selected_themes or [],
        depth=depth,
        min_quality=min_quality,
        quality_retries=quality_retries,
        mode=gen_mode,
        workers=workers,
        output_dir=output_dir,
        filename_pattern=filename_pattern,
        export_formats=export_formats,
        pretty=pretty,
        resume=resume,
        generate_summary=generate_summary,
        provider_name=provider_name,
    )


# =============================================================================
# FEATURE: HISTORICAL MATCHUP
# =============================================================================

def interactive_matchup():
    """Generate a game between two historical players (with go-back)."""
    cli_logger.info("User selected: Historical Player Matchup")
    print_header("Historical Player Matchup")

    players = [
        "Mikhail Tal", "Jose Raul Capablanca", "Paul Morphy",
        "Bobby Fischer", "Garry Kasparov", "Anatoly Karpov",
        "Magnus Carlsen", "Alexander Alekhine", "Tigran Petrosian",
        "Boris Spassky", "Emanuel Lasker", "Wilhelm Steinitz",
    ]

    white_name = black_name = output = provider_name = None
    step = 0

    while step <= 4:
        # Step 0 ── White player
        if step == 0:
            print_info("Select White player:")
            v = prompt_choice("White player:", players, default=1, allow_back=True)
            if v is GO_BACK:
                return
            white_name = players[v]
            step += 1
            continue

        # Step 1 ── Black player
        if step == 1:
            print_info("Select Black player:")
            v = prompt_choice("Black player:", players, default=6, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            black_name = players[v]
            step += 1
            continue

        # Step 2 ── Output file
        if step == 2:
            v = prompt_input("Output file", "matchup.pgn", allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            output = v
            step += 1
            continue

        # Step 3 ── Provider
        if step == 3:
            providers = _get_available_providers()
            if not providers:
                print_error("No LLM provider configured.")
                return
            if len(providers) == 1:
                provider_name = providers[0]
            else:
                v = prompt_choice("Provider:", [_provider_display(p) for p in providers], default=1, allow_back=True)
                if v is GO_BACK:
                    step -= 1
                    continue
                provider_name = providers[v]
            step += 1
            continue

        # Step 4 ── Confirm
        if step == 4:
            print(f"\n  {C.BOLD}Matchup:{C.RESET}")
            print(f"    {C.WHITE}{white_name}{C.RESET} (White) vs {C.WHITE}{black_name}{C.RESET} (Black)")

            v = prompt_yes_no("\n  Proceed?", default=True, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            if not v:
                return
            break

    _execute_matchup(white_name, black_name, output, provider_name)


# =============================================================================
# FEATURE: ANALYZE PGN
# =============================================================================

def interactive_analyze():
    """Analyze an existing PGN file (with go-back)."""
    cli_logger.info("User selected: Analyze a PGN File")
    print_header("Analyze a PGN File")

    filepath = analysis_depth = beauty = None
    step = 0

    while step <= 2:
        # Step 0 ── File path
        if step == 0:
            v = prompt_input("Path to PGN file", "game.pgn", allow_back=True)
            if v is GO_BACK:
                return
            if not Path(v).exists():
                print_error(f"File not found: {v}")
                continue  # re-ask
            filepath = v
            step += 1
            continue

        # Step 1 ── Depth
        if step == 1:
            v = prompt_int("Analysis depth", cfg.stockfish.depth, 1, 30, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            analysis_depth = v
            step += 1
            continue

        # Step 2 ── Beauty
        if step == 2:
            v = prompt_yes_no("Include beauty score analysis?", default=True, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            beauty = v
            break

    _execute_analysis(filepath, analysis_depth, beauty)


# =============================================================================
# FEATURE: VIEW / EDIT CONFIGURATION
# =============================================================================

def _reload_environment():
    """Re-read the .env file and reload configuration so new values take effect."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        print_warning(f"No .env file found at {env_path}")
        return

    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=str(env_path), override=True)
        print_success(f"Environment reloaded from {env_path}")
    except ImportError:
        print_warning("python-dotenv not installed — reading .env manually.")
        # Minimal fallback: parse KEY=VALUE lines into os.environ
        with open(env_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    os.environ[key] = value
        print_success(f"Environment reloaded from {env_path} (manual parse)")

    # Also reload config so the new env vars propagate into cfg
    global cfg
    cfg = reload_config()
    print_success("Configuration refreshed with new environment values.")


def interactive_config():
    """View and optionally edit the current configuration (with go-back)."""
    print_header("Configuration Manager")

    actions = [
        "View current configuration",
        "View a specific section",
        "Open config file location",
        "Reload configuration",
        "Reload environment (.env)",
        "Browse & select model",
    ]
    action = prompt_choice("What would you like to do?", actions, default=1, allow_back=True)
    if action is GO_BACK:
        return

    if action == 0:
        _display_full_config()
    elif action == 1:
        sections = ["llm", "stockfish", "generation", "aesthetics", "prompts",
                     "export", "benchmarks", "logging", "advanced", "batch", "tournament"]
        sec_idx = prompt_choice("Select section:", sections, default=1, allow_back=True)
        if sec_idx is GO_BACK:
            return
        _display_config_section(sections[sec_idx])
    elif action == 2:
        config_path = PROJECT_ROOT / "caissa_config.yaml"
        print_info(f"Config file: {config_path}")
        print_info(f"Local overrides: {PROJECT_ROOT / 'caissa_config.local.yaml'}")
        print_info(f"Environment: {PROJECT_ROOT / '.env'}")
    elif action == 3:
        global cfg
        cfg = reload_config()
        print_success("Configuration reloaded from disk.")
    elif action == 4:
        _reload_environment()
    elif action == 5:
        _browse_and_select_model()


def _browse_and_select_model():
    """Interactively discover models for a provider and let the user pick one."""
    global cfg
    from core.model_discovery import (
        discover_models, format_model_table, format_model_verbose,
        GEMINI_OLD_SDK_OK, GEMINI_SDK_NOT_INSTALLED, GEMINI_SDK_ERROR,
    )

    # Step 0 ── Choose provider
    providers = _get_available_providers()
    if not providers:
        print_error("No providers configured. Set API keys in .env first.")
        return

    display = [_provider_display(p) for p in providers]
    pidx = prompt_choice("Select a provider to browse models:", display,
                         default=1, allow_back=True)
    if pidx is GO_BACK:
        return

    provider_name = providers[pidx]

    # Step 1 ── Include preview / experimental?
    include_preview = prompt_yes_no(
        "Include preview & experimental models?", default=False, allow_back=True
    )
    if include_preview is GO_BACK:
        return _browse_and_select_model()  # re-ask provider

    # Step 1b ── Verbose mode?
    verbose = prompt_yes_no(
        "Show verbose model details?", default=False, allow_back=True
    )
    if verbose is GO_BACK:
        return _browse_and_select_model()  # re-ask preview

    # Step 2 ── Fetch models with spinner
    print()
    with Spinner(f"Querying {provider_name} for available models"):
        result = discover_models(
            provider_name, include_preview=include_preview, cfg=cfg,
        )

    if result.error:
        print_error(result.error)
        return

    # Gemini SDK status feedback
    if provider_name == "gemini" and result.sdk_status:
        if result.sdk_status == GEMINI_SDK_NOT_INSTALLED:
            print()
            print_warning("No Gemini SDK installed — using REST API.")
            print_info("  To install the recommended SDK:")
            print_info(f"    {C.BOLD}pip install google-genai{C.RESET}")
            _answer = prompt_yes_no("Install SDK now?", default=False, allow_back=True)
            if _answer is GO_BACK:
                return _browse_and_select_model()
            if _answer:
                import subprocess as _sp
                print()
                with Spinner("Installing google-genai SDK"):
                    proc = _sp.run(
                        [sys.executable, "-m", "pip", "install", "google-genai"],
                        capture_output=True, text=True,
                    )
                if proc.returncode == 0:
                    print_success("SDK installed successfully! It will be used on the next discovery.")
                else:
                    print_error(f"Installation failed:\n{proc.stderr.strip()}")
            else:
                print_info("Continuing with REST API — all features work fine without the SDK.")
            print()
        elif result.sdk_status == GEMINI_OLD_SDK_OK:
            print()
            print_info("Using deprecated google-generativeai SDK (still works).")
            print_info("  To upgrade to the new SDK:")
            print_info(f"    {C.BOLD}pip install google-genai{C.RESET}")
            print()
        elif result.sdk_status == GEMINI_SDK_ERROR:
            detail = result.sdk_detail or "unknown error"
            print()
            print_warning(f"Gemini SDK(s) failed ({detail}) — fell back to REST API.")
            print_info("  Consider installing/upgrading: pip install -U google-genai")
            print()
        # GEMINI_NEW_SDK_OK / GEMINI_SDK_OK → no message needed

    models = result.models

    if not models:
        print_warning(f"No models found for {provider_name}.")
        return

    # Step 3 ── Display & select
    print_header(f"Models for {provider_name.capitalize()} ({len(models)} found)")

    if verbose:
        table = format_model_verbose(models)
    else:
        show_ctx = provider_name == "gemini"
        table = format_model_table(
            models, show_tier=True, show_context=show_ctx, show_description=show_ctx,
        )
    print(table)

    # Build option list for prompt_choice
    option_labels = [m.id for m in models]
    sel = prompt_choice(
        "\nSelect a model to use:", option_labels, default=1, allow_back=True
    )
    if sel is GO_BACK:
        return _browse_and_select_model()

    chosen = models[sel]
    print()
    print_info(f"Selected: {C.BOLD}{chosen.id}{C.RESET}")

    # Step 4 ── Persist the choice
    _ENV_MODEL_KEYS = {
        "openai":    "OPENAI_MODEL",
        "anthropic":  "ANTHROPIC_MODEL",
        "gemini":     "GEMINI_MODEL",
        "deepseek":   "DEEPSEEK_MODEL",
        "ollama":     "OLLAMA_MODEL",
        "azure":      "AZURE_OPENAI_DEPLOYMENT",
    }
    env_key = _ENV_MODEL_KEYS.get(provider_name, "")

    # Always set in the running process so this session picks it up.
    if env_key:
        os.environ[env_key] = chosen.id

    # Offer to persist to .env
    persist = prompt_yes_no("Save selection to .env file?", default=True)
    if persist and persist is not GO_BACK:
        _persist_env_value(env_key, chosen.id)

    cfg = reload_config()
    print_success(f"Model set to {C.BOLD}{chosen.id}{C.RESET} for {provider_name}.")


def _persist_env_value(key: str, value: str):
    """Write or update a KEY=VALUE pair in the project .env file."""
    env_path = PROJECT_ROOT / ".env"

    lines: List[str] = []
    found = False
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip().startswith(f"{key}=") or line.strip().startswith(f"{key} ="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line)

    if not found:
        lines.append(f"{key}={value}\n")

    with open(env_path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)

    print_success(f"Saved {key}={value} to {env_path}")


# =============================================================================
# FEATURE: RUN BENCHMARKS
# =============================================================================

def interactive_benchmark():
    """Run provider benchmarks (with go-back)."""
    print_header("Provider Benchmarks")

    providers = _get_available_providers()
    if not providers:
        print_error("No providers configured. Set API keys first.")
        return

    print_info(f"Available providers: {', '.join(providers)}")

    selected = runs = None
    step = 0

    while step <= 2:
        # Step 0 ── Select providers
        if step == 0:
            if len(providers) == 1:
                selected = providers
            else:
                v = prompt_yes_no(f"Benchmark all {len(providers)} providers?", default=True, allow_back=True)
                if v is GO_BACK:
                    return
                if v:
                    selected = providers
                else:
                    selected = []
                    for p in providers:
                        inc = prompt_yes_no(f"  Include {p}?", default=True, allow_back=True)
                        if inc is GO_BACK:
                            selected = None
                            break
                        if inc:
                            selected.append(p)
                    if selected is None:
                        continue  # re-ask from start of step 0
            if not selected:
                print_warning("No providers selected.")
                return
            step += 1
            continue

        # Step 1 ── Runs
        if step == 1:
            v = prompt_int("Number of runs per provider", cfg.benchmarks.default_runs, 1, 50, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            runs = v
            step += 1
            continue

        # Step 2 ── Confirm
        if step == 2:
            print(f"\n  {C.BOLD}Benchmark Plan:{C.RESET}")
            print(f"    Providers: {C.CYAN}{', '.join(selected)}{C.RESET}")
            print(f"    Runs:      {C.CYAN}{runs}{C.RESET}")

            v = prompt_yes_no("\n  Start benchmarking?", default=True, allow_back=True)
            if v is GO_BACK:
                step -= 1
                continue
            if not v:
                return
            break

    _execute_benchmark(selected, runs)


# =============================================================================
# FEATURE: LIST STYLES
# =============================================================================

def show_styles():
    """Display all available playing styles with details."""
    print_header("Available Playing Styles")
    
    try:
        from aesthetic.style_slider import StyleSlider
        slider = StyleSlider()
        
        for style, desc in slider.get_all_styles().items():
            config = slider.get_config(style)
            print(f"  {C.BOLD}{C.CYAN}{config.style_name}{C.RESET} ({style.value})")
            print(f"    {C.DIM}{desc}{C.RESET}")
            print(f"    Depth: {config.stockfish_depth}  |  "
                  f"Blunder Tolerance: {config.blunder_threshold}cp  |  "
                  f"Aggression: {config.aggression}/10  |  "
                  f"Chaos: {config.chaos}/10")
            print()
    except Exception as e:
        print_error(f"Could not load styles: {e}")


# =============================================================================
# FEATURE: SYSTEM INFO
# =============================================================================

def show_info():
    """Display system information and health check."""
    print_header("System Information")
    
    print(f"  {C.BOLD}CAISSA Chess Engine{C.RESET}")
    print("  Version:  0.3.2")
    print(f"  Python:   {sys.version.split()[0]}")
    print(f"  Platform: {sys.platform}")
    print(f"  Root:     {PROJECT_ROOT}")
    print()
    
    # Check components
    print(f"  {C.BOLD}Component Status:{C.RESET}")
    
    # python-chess
    try:
        import chess
        print_success(f"python-chess {chess.__version__}")
    except ImportError:
        print_error("python-chess not installed")
    
    # openai
    try:
        import openai
        print_success(f"openai {openai.__version__}")
    except ImportError:
        print_warning("openai not installed")
    
    # anthropic
    try:
        import anthropic
        print_success(f"anthropic {anthropic.__version__}")
    except ImportError:
        print_warning("anthropic not installed (optional)")
    
    # google-generativeai
    try:
        import importlib.util
        if importlib.util.find_spec("google.generativeai"):
            print_success("google-generativeai installed")
        else:
            raise ImportError()
    except ImportError:
        print_warning("google-generativeai not installed (optional)")
    
    # Stockfish
    sf_path = cfg.stockfish.path
    if sf_path:
        full_path = PROJECT_ROOT / sf_path if not Path(sf_path).is_absolute() else Path(sf_path)
        if full_path.exists():
            print_success(f"Stockfish binary found: {full_path}")
        else:
            print_warning(f"Stockfish binary not found at: {full_path}")
    else:
        print_warning("Stockfish path not configured")
    
    # API Keys
    print()
    print(f"  {C.BOLD}API Key Status:{C.RESET}")
    
    for name, env_var in [
        ("OpenAI", "OPENAI_API_KEY"),
        ("Anthropic", "ANTHROPIC_API_KEY"),
        ("Google/Gemini", "GOOGLE_API_KEY"),
        ("DeepSeek", "DEEPSEEK_API_KEY"),
    ]:
        key = os.getenv(env_var) or getattr(cfg.llm, env_var.lower().replace("google_api_key", "google_api_key"), None)
        if key and not key.startswith(("sk-...", "YOUR_")):
            print_success(f"{name}: configured ({key[:8]}...)")
        else:
            print(f"  {C.DIM}[ -- ]{C.RESET} {name}: not set")
    
    print()
    print(f"  {C.BOLD}Config Files:{C.RESET}")
    for f in ["caissa_config.yaml", "caissa_config.local.yaml", ".env"]:
        p = PROJECT_ROOT / f
        if p.exists():
            print_success(f"{f}")
        else:
            print(f"  {C.DIM}[ -- ]{C.RESET} {f} (not found)")


# =============================================================================
# EXECUTION HELPERS
# =============================================================================

def _get_available_providers() -> List[str]:
    """Return list of configured provider names."""
    available = []
    
    # Check env vars and config for API keys
    if os.getenv("OPENAI_API_KEY") or cfg.llm.openai_api_key:
        key = os.getenv("OPENAI_API_KEY") or cfg.llm.openai_api_key
        if key and not key.startswith(("sk-...", "YOUR_")):
            available.append("openai")
    
    if os.getenv("ANTHROPIC_API_KEY") or cfg.llm.anthropic_api_key:
        key = os.getenv("ANTHROPIC_API_KEY") or cfg.llm.anthropic_api_key
        if key and not key.startswith(("sk-ant-...", "YOUR_")):
            available.append("anthropic")
    
    if os.getenv("GOOGLE_API_KEY") or cfg.llm.google_api_key:
        key = os.getenv("GOOGLE_API_KEY") or cfg.llm.google_api_key
        if key and not key.startswith("YOUR_"):
            available.append("gemini")
    
    if os.getenv("DEEPSEEK_API_KEY") or cfg.llm.deepseek_api_key:
        key = os.getenv("DEEPSEEK_API_KEY") or cfg.llm.deepseek_api_key
        if key:
            available.append("deepseek")
    
    # Ollama is always available (local)
    available.append("ollama")
    
    return available


def _provider_display(name: str) -> str:
    """Human-readable provider name with model info."""
    models = {
        "openai": cfg.llm.openai_model,
        "anthropic": cfg.llm.anthropic_model,
        "gemini": cfg.llm.gemini_model,
        "deepseek": cfg.llm.deepseek_model,
        "ollama": cfg.llm.ollama_model,
    }
    model = models.get(name, "unknown")
    return f"{name.capitalize()} ({model})"


def _create_provider(provider_name: str):
    """Create an LLM provider instance from config."""
    from core.provider_factory import create_provider
    return create_provider(provider_name, cfg=cfg)


def _resolve_stockfish_path() -> Optional[str]:
    """Resolve stockfish path from config."""
    if not cfg.stockfish.enabled:
        return None
    
    sf_path = cfg.stockfish.path
    if not sf_path:
        return None
    
    p = Path(sf_path)
    if not p.is_absolute():
        p = PROJECT_ROOT / sf_path
    
    return str(p) if p.exists() else None


def _execute_generation(
    style: str,
    era: str,
    theme: Optional[str],
    aggression: int,
    chaos: int,
    depth: int,
    white: str,
    black: str,
    provider_name: str,
    output_format: str,
    output_path: str,
    pretty: bool,
):
    """Execute single game generation."""
    from core.generator import CaissaGenerator
    from core.prompt_manager import GameContext, GameEra, GameTheme, PromptBias
    
    print()
    print_header("Generating Game")
    run_id = _new_run_id("single")
    cli_logger.info("run_id=%s mode=single stage=start", run_id)
    _announce_validation_policy("single")
    
    # Map enums
    era_map = {
        "romantic": GameEra.ROMANTIC, "classical": GameEra.CLASSICAL,
        "hypermodern": GameEra.HYPERMODERN, "soviet": GameEra.SOVIET,
        "computer": GameEra.COMPUTER, "neural": GameEra.NEURAL,
    }
    game_era = era_map.get(era, GameEra.ROMANTIC)
    
    game_theme = None
    if theme:
        try:
            game_theme = GameTheme[theme]
        except KeyError:
            print_warning(f"Unknown theme '{theme}', proceeding without theme.")
    
    # Resolve bias from config
    bias_map = {
        "white": PromptBias.WHITE,
        "black": PromptBias.BLACK,
        "draw": PromptBias.DRAW,
        "random": PromptBias.RANDOM,
        "neutral": PromptBias.NEUTRAL,
    }
    game_bias = bias_map.get(cfg.generation.bias.lower(), PromptBias.NEUTRAL)

    # Build context
    context = GameContext(
        era=game_era,
        theme=game_theme,
        white_player=white,
        black_player=black,
        aggression_score=aggression,
        chaos_score=chaos,
        depth=depth,
        bias=game_bias,
    )
    
    # Create provider
    try:
        provider = _create_provider(provider_name)
        print_success(f"Provider initialized: {type(provider).__name__}")
    except Exception as e:
        print_error(f"Failed to create provider: {e}")
        return
    
    # Create generator
    stockfish_path = _resolve_stockfish_path()
    
    print_info("Starting generation...")
    print()
    cli_logger.info("run_id=%s mode=single stage=prompt_configured provider=%s format=%s", run_id, provider_name, output_format)
    
    start_time = time.time()
    
    try:
        with CaissaGenerator(provider=provider, stockfish_path=stockfish_path) as generator:
            with Spinner("Generating game via LLM"):
                cli_logger.info("run_id=%s mode=single stage=llm_generation_started", run_id)
                success, pgn_string, moves = generator.generate_game(context)
        
        elapsed = time.time() - start_time
        
        if success:
            # ─── NEW UNIFIED EXPORT PIPELINE ───────────────────────────
            # Parse the LLM's raw PGN to extract annotations, comments,
            # NAGs, evaluations, and opening info — previously all lost.
            from export.annotation_parser import parse_pgn
            from export.game_exporter import GameExporter
            
            parsed_game = parse_pgn(pgn_string)
            
            # Enrich with context info that the LLM may not have included
            if not parsed_game.headers.get("White") or parsed_game.headers.get("White") == "?":
                parsed_game.headers["White"] = white
            if not parsed_game.headers.get("Black") or parsed_game.headers.get("Black") == "?":
                parsed_game.headers["Black"] = black
            if not parsed_game.headers.get("Round") or parsed_game.headers.get("Round") == "?":
                parsed_game.headers["Round"] = "1"
            
            exporter = GameExporter(
                game=parsed_game,
                style_name=style,
            )
            
            # Export in the requested format
            out_path = Path(output_path)
            
            try:
                cli_logger.info(
                    "Single game export: format=%s path=%s moves=%d annotations=%d",
                    output_format,
                    str(out_path),
                    parsed_game.move_count,
                    sum(1 for m in parsed_game.moves if m.comment or m.nags),
                )
                if output_format == "all":
                    all_content = exporter.export_all()
                    export_targets = {
                        "pgn": out_path.with_suffix(".pgn"),
                        "markdown": out_path.with_suffix(".md"),
                        "html": out_path.with_suffix(".html"),
                        "json": out_path.with_suffix(".json"),
                    }
                    for fmt_name, file_path in export_targets.items():
                        payload = all_content.get(fmt_name)
                        if payload is None:
                            continue
                        file_path.write_text(payload, encoding="utf-8")
                    content = all_content.get("pgn", pgn_string)
                else:
                    content = exporter.export(output_format)
                    out_path.write_text(content, encoding="utf-8")
            except Exception as export_err:
                # Fallback to raw PGN
                out_path.write_text(pgn_string, encoding="utf-8")
                print_warning(f"Export as {output_format} failed ({export_err}), saved raw PGN.")
            
            # Summary info
            cli_logger.info("run_id=%s mode=single stage=export_completed success=true", run_id)
            ann_count = sum(1 for m in parsed_game.moves if m.comment or m.nags)
            opening_info = ""
            if parsed_game.eco:
                opening_info = f"    Opening:     {C.CYAN}{parsed_game.eco}: {parsed_game.opening_name}{C.RESET}\n"
            
            print()
            print(f"  {C.GREEN}{C.BOLD}Game generated successfully!{C.RESET}")
            if output_format == "all":
                print(f"    Saved to:    {C.CYAN}{out_path.parent.absolute()}{C.RESET}")
                print(f"    Format:      {C.CYAN}ALL (PGN/MD/HTML/JSON){C.RESET}")
                _warn_export_guardrail(
                    [
                        out_path.with_suffix(".pgn"),
                        out_path.with_suffix(".md"),
                        out_path.with_suffix(".html"),
                        out_path.with_suffix(".json"),
                    ],
                    mode="single",
                    run_id=run_id,
                )
            else:
                print(f"    Saved to:    {C.CYAN}{out_path.absolute()}{C.RESET}")
                print(f"    Format:      {C.CYAN}{output_format.upper()}{C.RESET}")
                _warn_export_guardrail([out_path], mode="single", run_id=run_id)
            print(f"    Moves:       {C.CYAN}{parsed_game.move_count}{C.RESET}")
            print(f"    Annotations: {C.CYAN}{ann_count}{C.RESET}")
            if opening_info:
                print(opening_info, end="")
            print(f"    Result:      {C.CYAN}{parsed_game.result}{C.RESET}")
            print(f"    Time:        {C.CYAN}{elapsed:.1f}s{C.RESET}")
            print()
            
            # Preview
            if prompt_yes_no("Show preview?", default=True):
                # Always show PGN preview regardless of output format
                preview = exporter.export_pgn() if output_format != "pgn" else content
                print(f"\n{C.DIM}{'─' * 60}{C.RESET}")
                lines = preview.split('\n')
                for line in lines[:35]:
                    print(f"  {line}")
                if len(lines) > 35:
                    print(f"  {C.DIM}... ({len(lines) - 35} more lines){C.RESET}")
                print(f"{C.DIM}{'─' * 60}{C.RESET}")
        else:
            cli_logger.warning("run_id=%s mode=single stage=generation_failed reason=%s", run_id, pgn_string)
            print_error(f"Generation failed after {elapsed:.1f}s")
            print_info(f"Reason: {pgn_string}")
    
    except Exception as e:
        print_error(f"Error during generation: {e}")
        import traceback
        traceback.print_exc()


def _execute_batch(
    count: int,
    styles: list,
    style_variation: str,
    eras: list,
    themes: list,
    depth: int,
    min_quality: str,
    quality_retries: int,
    mode: str,
    workers: int,
    output_dir: str,
    filename_pattern: str,
    export_formats: list,
    pretty: bool,
    resume: bool,
    generate_summary: bool,
    provider_name: str,
):
    """Execute batch game generation using the BatchEngine."""
    from core.batch_engine import (
        BatchConfig, BatchEngine, BatchMode, BatchJobStatus, StyleVariation,
    )

    cli_logger.info(
        "Batch generation started: count=%d, styles=%s, variation=%s, mode=%s, "
        "provider=%s, quality_gate=%s, output=%s",
        count, styles, style_variation, mode, provider_name, min_quality, output_dir,
    )
    run_id = _new_run_id("batch")
    cli_logger.info("run_id=%s mode=batch stage=start", run_id)
    _announce_validation_policy("batch")
    print()
    print_header("Batch Generation in Progress")

    # ── Create provider ──────────────────────────────────────────────────────
    try:
        provider = _create_provider(provider_name)
        print_success(f"Provider: {type(provider).__name__}")
    except Exception as e:
        print_error(f"Failed to create provider: {e}")
        return

    stockfish_path = _resolve_stockfish_path()

    # ── Build BatchConfig ────────────────────────────────────────────────────
    cli_logger.info("run_id=%s mode=batch stage=configuring", run_id)
    mode_enum = BatchMode.PARALLEL if mode == "parallel" else BatchMode.SEQUENTIAL
    variation_map = {
        "fixed": StyleVariation.FIXED,
        "round_robin": StyleVariation.ROUND_ROBIN,
        "random": StyleVariation.RANDOM,
    }
    style_var_enum = variation_map.get(style_variation, StyleVariation.FIXED)

    batch_cfg = BatchConfig(
        count=count,
        mode=mode_enum,
        workers=workers,
        styles=styles,
        style_variation=style_var_enum,
        themes=themes,
        eras=eras,
        min_quality=min_quality,
        quality_retries=quality_retries,
        depth=depth,
        output_dir=output_dir,
        filename_pattern=filename_pattern,
        export_formats=export_formats,
        pretty_pgn=pretty,
        resume=resume,
        generate_summary=generate_summary,
        summary_format="markdown",
        bias=cfg.generation.bias,
    )

    # ── Build engine ─────────────────────────────────────────────────────────
    engine = BatchEngine(config=batch_cfg, provider=provider, stockfish_path=stockfish_path)

    # ── Animated batch spinner ───────────────────────────────────────────────
    batch_spinner = BatchSpinner(total=count)
    batch_spinner.start()

    # ── Run ──────────────────────────────────────────────────────────────────
    try:
        cli_logger.info("run_id=%s mode=batch stage=llm_generation_started", run_id)
        summary = engine.run(on_progress=batch_spinner.update)
    except Exception as e:
        batch_spinner.stop()
        print_error(f"Batch engine error: {e}")
        import traceback
        traceback.print_exc()
        return
    finally:
        batch_spinner.stop()

    # ── Display results ──────────────────────────────────────────────────────
    cli_logger.info("run_id=%s mode=batch stage=generation_completed success=%d failed=%d", run_id, summary.successful, summary.failed)
    print()
    print(f"  {C.BOLD}{'═' * 50}{C.RESET}")
    print(f"  {C.BOLD}Batch Complete{C.RESET}")
    print(f"  {C.BOLD}{'═' * 50}{C.RESET}")
    print(f"    Total:      {summary.total}")
    print(f"    Successful: {C.GREEN}{summary.successful}{C.RESET}")
    if summary.failed > 0:
        print(f"    Failed:     {C.RED}{summary.failed}{C.RESET}")
    if summary.skipped > 0:
        print(f"    Skipped:    {C.DIM}{summary.skipped}{C.RESET} (resume)")
    print(f"    Time:       {C.CYAN}{summary.total_time:.1f}s{C.RESET}")
    if summary.avg_time_per_game > 0:
        print(f"    Avg/game:   {C.CYAN}{summary.avg_time_per_game:.1f}s{C.RESET}")
    if summary.avg_moves > 0:
        print(f"    Avg moves:  {C.CYAN}{summary.avg_moves:.0f}{C.RESET}")
    if summary.avg_beauty > 0:
        print(f"    Avg beauty: {C.CYAN}{summary.avg_beauty:.1f}{C.RESET}")
    print(f"    Output:     {C.CYAN}{Path(output_dir).absolute()}{C.RESET}")

    # Quality distribution
    if summary.quality_distribution:
        print(f"\n  {C.BOLD}Quality Distribution:{C.RESET}")
        for quality, cnt in sorted(summary.quality_distribution.items()):
            bar = "█" * cnt
            print(f"    {quality:<12s} {bar} {cnt}")

    # Style distribution
    if summary.style_distribution and len(summary.style_distribution) > 1:
        print(f"\n  {C.BOLD}Style Distribution:{C.RESET}")
        for style, cnt in sorted(summary.style_distribution.items()):
            bar = "█" * cnt
            print(f"    {style:<14s} {bar} {cnt}")

    # Best/worst
    if summary.best_game_index is not None:
        print(f"\n  {C.GREEN}★ Best game:{C.RESET}  #{summary.best_game_index}")
    if summary.worst_game_index is not None and summary.successful > 1:
        print(f"  {C.DIM}▼ Weakest:    #{summary.worst_game_index}{C.RESET}")

    # Formats exported
    fmt_str = ", ".join(f.upper() for f in export_formats)
    print(f"\n  Exported formats: {C.CYAN}{fmt_str}{C.RESET}")
    if generate_summary:
        print(f"  Summary report:   {C.CYAN}batch_summary.md{C.RESET}")
    _warn_export_guardrail(
        [
            Path(output_dir) / "batch_summary.json",
            Path(output_dir) / "batch_summary.md",
        ],
        mode="batch",
        run_id=run_id,
    )
    print()


def _execute_matchup(white_name: str, black_name: str, output: str, provider_name: str):
    """Execute historical matchup generation."""
    from core.generator import CaissaGenerator
    from core.prompt_manager import GameContext, GameEra
    from aesthetic.style_slider import StyleSlider, StylePreset
    
    print()
    print_header(f"{white_name} vs {black_name}")
    
    # Map player names to styles
    player_style_map = {
        "mikhail tal": "tal", "jose raul capablanca": "capablanca",
        "paul morphy": "morphy", "bobby fischer": "morphy",
        "garry kasparov": "tal", "anatoly karpov": "karpov",
        "magnus carlsen": "neural", "alexander alekhine": "morphy",
        "tigran petrosian": "karpov", "boris spassky": "morphy",
        "emanuel lasker": "capablanca", "wilhelm steinitz": "capablanca",
    }
    
    white_style = player_style_map.get(white_name.lower(), "morphy")
    
    try:
        provider = _create_provider(provider_name)
    except Exception as e:
        print_error(f"Failed to create provider: {e}")
        return
    
    slider = StyleSlider()
    
    try:
        w_config = slider.get_config(StylePreset(white_style))
    except ValueError:
        w_config = slider.get_config(StylePreset.MORPHY)
    
    context = GameContext(
        era=GameEra.SOVIET,
        white_player=white_name,
        black_player=black_name,
        aggression_score=w_config.aggression,
        chaos_score=w_config.chaos,
        depth=w_config.stockfish_depth,
    )
    
    stockfish_path = _resolve_stockfish_path()
    start_time = time.time()
    
    try:
        with CaissaGenerator(provider=provider, stockfish_path=stockfish_path) as generator:
            with Spinner(f"Generating {white_name} vs {black_name}"):
                success, pgn_string, moves = generator.generate_game(context)
        
        elapsed = time.time() - start_time
        
        if success:
            Path(output).write_text(pgn_string, encoding="utf-8")
            print_success(f"Matchup generated in {elapsed:.1f}s")
            print_info(f"Saved to: {Path(output).absolute()}")
            print_info(f"Moves: {len(moves)}")
        else:
            print_error("Generation failed.")
    except Exception as e:
        print_error(f"Error: {e}")


def _execute_analysis(filepath: str, depth: int, beauty: bool):
    """Execute PGN analysis."""
    print()
    print_header(f"Analyzing: {filepath}")
    
    try:
        import chess.pgn
        
        with open(filepath, encoding="utf-8") as f:
            game = chess.pgn.read_game(f)
        
        if game is None:
            print_error("Could not parse PGN file.")
            return
        
        print(f"  {C.BOLD}Game Information:{C.RESET}")
        print(f"    Event:  {game.headers.get('Event', 'Unknown')}")
        print(f"    White:  {game.headers.get('White', 'Unknown')}")
        print(f"    Black:  {game.headers.get('Black', 'Unknown')}")
        print(f"    Result: {game.headers.get('Result', '*')}")
        print()
        
        board = game.board()
        move_count = 0
        moves = []
        for move in game.mainline_moves():
            board.push(move)
            moves.append(move)
            move_count += 1
        
        print(f"    Total half-moves: {move_count}")
        print(f"    Full moves:       {(move_count + 1) // 2}")
        
        # Legality check
        print()
        print(f"  {C.BOLD}Validation:{C.RESET}")
        print_success("All moves are legal (parsed by python-chess)")
        
        # Beauty analysis
        if beauty:
            print()
            print(f"  {C.BOLD}Beauty Analysis:{C.RESET}")
            try:
                from aesthetic.beauty_eval import BeautyEvaluator
                evaluator = BeautyEvaluator()
                
                board2 = chess.Board()
                total_score = 0
                for m in moves:
                    score, beauty_type = evaluator.evaluate_move(
                        board2, m, eval_before=0, eval_after=0
                    )
                    total_score += score
                    board2.push(m)
                
                print(f"    Cumulative beauty score: {C.CYAN}{total_score:.1f}{C.RESET}")
                print_info("(Note: full beauty analysis requires Stockfish evaluations)")
            except Exception as e:
                print_warning(f"Beauty analysis error: {e}")
        
    except Exception as e:
        print_error(f"Analysis error: {e}")


def _execute_benchmark(providers: List[str], runs: int):
    """Execute provider benchmarks."""
    print()
    print_header("Running Benchmarks")
    
    try:
        from benchmarks.provider_benchmark import BenchmarkEngine
        
        engine = BenchmarkEngine()
        
        for provider_name in providers:
            print(f"\n  Benchmarking {C.CYAN}{provider_name}{C.RESET} ({runs} runs)...")
            
            try:
                result = engine.run_provider_benchmark(provider_name, runs=runs)
                
                success_rate = result.successful_runs / result.runs if result.runs > 0 else 0
                print(f"    Avg latency: {C.CYAN}{result.latency.mean_ms:.0f}ms{C.RESET}")
                print(f"    Success:     {C.GREEN}{success_rate*100:.1f}%{C.RESET}")
            except Exception as e:
                print_error(f"  Benchmark failed for {provider_name}: {e}")
        
        print_success("Benchmarks complete.")
    except ImportError:
        print_warning("Benchmark module not available. Running basic latency test...")
        
        for provider_name in providers:
            print(f"\n  Testing {C.CYAN}{provider_name}{C.RESET}...", end=" ")
            try:
                provider = _create_provider(provider_name)
                start = time.time()
                provider.generate(
                    system_prompt="You are a chess assistant.",
                    user_prompt="What is 1.e4?",
                    temperature=0.1,
                )
                elapsed = (time.time() - start) * 1000
                print(f"{C.GREEN}OK{C.RESET} ({elapsed:.0f}ms)")
            except Exception as e:
                print(f"{C.RED}FAILED: {e}{C.RESET}")


def _display_full_config():
    """Display the entire configuration."""
    data = config_to_dict(cfg)
    
    # Pretty print with colors
    for section, values in data.items():
        if section in ("project_root", "data_dir", "engines_dir", "export_dir"):
            continue
        
        print(f"  {C.BOLD}{C.CYAN}[{section}]{C.RESET}")
        
        if isinstance(values, dict):
            for key, val in values.items():
                if isinstance(val, dict):
                    print(f"    {key}:")
                    for k2, v2 in val.items():
                        _print_config_value(k2, v2, indent=6)
                else:
                    _print_config_value(key, val)
        else:
            print(f"    {values}")
        print()


def _display_config_section(section: str):
    """Display a single configuration section."""
    data = config_to_dict(cfg)
    section_data = data.get(section, {})
    
    print(f"  {C.BOLD}{C.CYAN}[{section}]{C.RESET}")
    
    if isinstance(section_data, dict):
        for key, val in section_data.items():
            if isinstance(val, dict):
                print(f"    {key}:")
                for k2, v2 in val.items():
                    _print_config_value(k2, v2, indent=6)
            else:
                _print_config_value(key, val)
    print()


def _print_config_value(key: str, val: Any, indent: int = 4):
    """Pretty print a single config value."""
    spaces = " " * indent
    if val is None:
        print(f"{spaces}{key}: {C.DIM}null{C.RESET}")
    elif isinstance(val, bool):
        color = C.GREEN if val else C.RED
        print(f"{spaces}{key}: {color}{val}{C.RESET}")
    elif isinstance(val, (int, float)):
        print(f"{spaces}{key}: {C.YELLOW}{val}{C.RESET}")
    elif isinstance(val, str):
        # Mask API keys
        if "api_key" in key and val and len(val) > 8:
            display = val[:8] + "..." + val[-4:]
            print(f"{spaces}{key}: {C.GREEN}{display}{C.RESET}")
        else:
            print(f"{spaces}{key}: {C.WHITE}{val}{C.RESET}")
    else:
        print(f"{spaces}{key}: {val}")


# =============================================================================
# MAIN MENU
# =============================================================================

def main_menu():
    """Main interactive menu loop."""
    
    while True:
        print()
        print(f"  {C.BOLD}What would you like to do?{C.RESET}")
        print()
        
        menu_items = [
            f"{C.GREEN}Generate a Game{C.RESET}         - Create a single chess masterpiece",
            f"{C.GREEN}Batch Generate{C.RESET}          - Generate multiple games at once",
            f"{C.GREEN}Historical Matchup{C.RESET}      - Pit legendary players against each other",
            f"{C.GREEN}Analyze PGN{C.RESET}             - Analyze an existing chess game",
            f"{C.GREEN}Run Benchmarks{C.RESET}          - Test and compare LLM providers",
            f"{C.MAGENTA}LLM vs LLM Match{C.RESET}        - Single game between two LLMs",
            f"{C.MAGENTA}LLM Tournament{C.RESET}          - Run a full tournament",
            f"{C.MAGENTA}ELO Ratings{C.RESET}             - View LLM chess ratings",
            f"{C.MAGENTA}Prompt Studio{C.RESET}           - View and customize prompts safely",
            f"{C.CYAN}View Styles{C.RESET}            - Browse all available playing styles",
            f"{C.CYAN}Configuration{C.RESET}          - View and manage settings",
            f"{C.CYAN}System Info{C.RESET}            - Check system status and components",
            f"{C.RED}Exit{C.RESET}                   - Quit CAISSA",
        ]
        
        for i, item in enumerate(menu_items, 1):
            print(f"    {C.BOLD}{i}.{C.RESET} {item}")
        
        print()
        raw = input(f"  {C.YELLOW}>{C.RESET} Enter choice [1-{len(menu_items)}] (or q to exit): ").strip()
        
        try:
            choice = int(raw)
            if choice == 0:
                choice = len(menu_items)
        except ValueError:
            # Handle text commands
            cmd = raw.lower()
            if cmd in ("q", "quit", "exit"):
                choice = len(menu_items)
            elif cmd in ("generate", "gen", "g"):
                choice = 1
            elif cmd in ("batch", "b"):
                choice = 2
            elif cmd in ("matchup", "m"):
                choice = 3
            elif cmd in ("analyze", "a"):
                choice = 4
            elif cmd in ("benchmark", "bench"):
                choice = 5
            elif cmd in ("match", "llm"):
                choice = 6
            elif cmd in ("tournament", "tourney", "t"):
                choice = 7
            elif cmd in ("elo", "ratings", "r"):
                choice = 8
            elif cmd in ("prompts", "prompt", "studio", "p"):
                choice = 9
            elif cmd in ("styles", "s"):
                choice = 10
            elif cmd in ("config", "cfg", "c"):
                choice = 11
            elif cmd in ("info", "i"):
                choice = 12
            else:
                print(f"  {C.RED}Unknown command. Enter 1-{len(menu_items)} or a keyword.{C.RESET}")
                continue
        
        if choice == 1:
            interactive_generate()
        elif choice == 2:
            interactive_batch()
        elif choice == 3:
            interactive_matchup()
        elif choice == 4:
            interactive_analyze()
        elif choice == 5:
            interactive_benchmark()
        elif choice == 6:
            interactive_match()
        elif choice == 7:
            interactive_tournament()
        elif choice == 8:
            show_elo_ratings()
        elif choice == 9:
            interactive_prompt_studio()
        elif choice == 10:
            show_styles()
        elif choice == 11:
            interactive_config()
        elif choice == 12:
            show_info()
        elif choice == len(menu_items):
            print(f"\n  {C.DIM}Goodbye! May your games be beautiful.{C.RESET}\n")
            break
        else:
            print(f"  {C.RED}Invalid choice.{C.RESET}")


# =============================================================================
# LLM vs LLM TOURNAMENT SYSTEM (v0.5.0)
# =============================================================================

def interactive_match():
    """
    Interactive LLM vs LLM single match setup with improved UX.
    
    Features:
    - Smart navigation (go back at any step)
    - Optimized step ordering
    - Analysis configuration
    - Better defaults
    """
    from core.tournament_cli_improved import ImprovedMatchBuilder
    
    print()
    print_header("LLM vs LLM Match")
    
    # Get available providers
    providers = _get_available_providers()
    if len(providers) < 1:
        print_error("No LLM providers available. Configure API keys first.")
        return
    
    # Use improved builder
    builder = ImprovedMatchBuilder(providers)
    config = builder.build()
    
    if not config:
        print_info("Match cancelled.")
        return
    
    # Execute match with new config
    _execute_llm_match_v2(config)


def _execute_llm_match(
    white_provider_name: str, 
    black_provider_name: str, 
    time_control: str,
    export_format: str = "pgn",
):
    """
    Execute a single LLM vs LLM match.
    
    Uses the unified GameExporter system for consistent output across the system.
    
    Supports formats:
    - pgn: Standard PGN with annotations
    - markdown: Rich markdown with game summary
    - html: Interactive HTML with dark mode
    - json: Structured data with match metadata
    """
    import asyncio
    from core.tournament_player import TournamentPlayer, TimeControl
    from core.match_engine import MatchEngine
    
    print()
    print_header(f"{white_provider_name} vs {black_provider_name}")
    
    # Create providers
    try:
        white_provider = _create_provider(white_provider_name)
        black_provider = _create_provider(black_provider_name)
        print_success(f"White: {white_provider_name}")
        print_success(f"Black: {black_provider_name}")
    except Exception as e:
        print_error(f"Failed to create providers: {e}")
        return
    
    # Create players
    white_player = TournamentPlayer(
        name=white_provider_name,
        provider=white_provider,
        provider_name=white_provider_name,
    )
    black_player = TournamentPlayer(
        name=black_provider_name,
        provider=black_provider,
        provider_name=black_provider_name,
    )
    
    # Map time control
    tc_map = {
        "bullet": TimeControl.BULLET,
        "blitz": TimeControl.BLITZ,
        "rapid": TimeControl.RAPID,
        "classical": TimeControl.CLASSICAL,
        "unlimited": TimeControl.UNLIMITED,
    }
    tc = tc_map.get(time_control, TimeControl.RAPID)
    
    print_info(f"Time control: {time_control}")
    print()
    
    # Create and run match
    engine = MatchEngine(white_player, black_player, time_control=tc)
    
    start_time = time.time()
    
    try:
        with Spinner("Playing match"):
            result = asyncio.run(engine.play_match())
        
        elapsed = time.time() - start_time
        
        # CRITICAL FIX: Check if match has moves before displaying/exporting
        if not result.moves or len(result.moves) == 0:
            print()
            print(f"  {C.BOLD}{'═' * 60}{C.RESET}")
            print(f"  {C.BOLD}⚠️  Match Did Not Complete{C.RESET}")
            print(f"  {C.BOLD}{'═' * 60}{C.RESET}")
            
            print(f"    Result: {result.result.value}")
            print(f"    Termination: {result.termination.value}")
            print(f"    Moves: 0")
            print(f"    Duration: {elapsed:.1f}s")
            
            if result.elo_change:
                print(f"    ELO change: {result.elo_change.summary}")
            
            print()
            print(f"  {C.YELLOW}ℹ️  No game file exported (match has no moves){C.RESET}")
            return
        
        # Display results
        print()
        print(f"  {C.BOLD}{'═' * 50}{C.RESET}")
        print(f"  {C.BOLD}Match Result{C.RESET}")
        print(f"  {C.BOLD}{'═' * 50}{C.RESET}")
        
        if result.result.value == "1-0":
            print(f"    Winner: {C.GREEN}{white_player.name} (White){C.RESET}")
        elif result.result.value == "0-1":
            print(f"    Winner: {C.GREEN}{black_player.name} (Black){C.RESET}")
        else:
            print(f"    Result: {C.YELLOW}Draw{C.RESET}")
        
        print(f"    Result: {result.result.value}")
        print(f"    Termination: {result.termination.value}")
        print(f"    Moves: {result.total_moves}")
        print(f"    Duration: {elapsed:.1f}s")
        
        if result.elo_change:
            print(f"    ELO change: {result.elo_change.summary}")
        
        # Export game using the unified exporter system
        output_dir = Path("games") / "matches"
        
        # Use the proper tournament exporter for consistent output
        from export.tournament_exporter import export_match
        
        # CRITICAL FIX: export_match now validates and handles empty matches
        exported = export_match(
            match_result=result,
            output_dir=str(output_dir),
            formats=[export_format],
            include_elo=True,
        )
        
        # Check if export succeeded (empty dict means validation failed)
        if exported:
            print()
            for fmt, path in exported.items():
                print_success(f"Game saved ({fmt}): {path}")
        else:
            print()
            print_error("Export failed: Match has no moves")
        
    except Exception as e:
        print_error(f"Match error: {e}")
        import traceback
        traceback.print_exc()


def _execute_llm_match_v2(config):
    """
    Execute LLM match with improved config object (from ImprovedMatchBuilder).
    
    Supports post-match analysis and threading preparation.
    """
    import asyncio
    import hashlib
    from core.tournament_player import TournamentPlayer, TimeControl
    from core.match_engine import MatchEngine
    from core.prompt_manager import PromptManager, GameContext, GameEra, PromptBias
    from pathlib import Path
    
    print()
    print_header(f"{config.white_provider} (W) vs {config.black_provider} (B)")
    run_id = _new_run_id("match")
    cli_logger.info("run_id=%s mode=match stage=start", run_id)
    _announce_validation_policy("match")
    
    # Create providers
    try:
        white_prov = _create_provider(config.white_provider)
        black_prov = _create_provider(config.black_provider)
    except Exception as e:
        print_error(f"Failed to create provider: {e}")
        return
    
    # Create players
    white_player = TournamentPlayer(
        name=config.white_provider,
        provider=white_prov,
        provider_name=config.white_provider,
    )
    
    black_player = TournamentPlayer(
        name=config.black_provider,
        provider=black_prov,
        provider_name=config.black_provider,
    )
    
    # Map time control
    tc_map = {
        "bullet": TimeControl.BULLET,
        "blitz": TimeControl.BLITZ,
        "rapid": TimeControl.RAPID,
        "classical": TimeControl.CLASSICAL,
        "unlimited": TimeControl.UNLIMITED,
    }
    tc = tc_map.get(config.time_control, TimeControl.RAPID)
    
    print_info(f"Time control: {config.time_control}")
    if config.enable_analysis:
        analysis_status = "Full Analysis + Commentary" if config.enable_commentary else "Analysis Only"
        print_info(f"Analysis: {analysis_status}")
    print()

    prompt_state = PromptManager.get_prompt_context_state()
    active_catalog = PromptManager.get_prompt_catalog()
    template_checksum = hashlib.sha256(
        active_catalog.get("system_template", "").encode("utf-8")
    ).hexdigest()[:16]
    lint_report = PromptManager.lint_template_with_mode(
        active_catalog.get("system_template", ""),
        "match",
    )
    prompt_trace_base = {
        "mode": "match",
        "context_state": prompt_state,
        "template_checksum": template_checksum,
        "lint_risk_score": lint_report.get("risk_score", 0),
        "lint_risk_level": lint_report.get("risk_level", "low"),
        "commentary_profile": prompt_state.get("commentary_profile", "off"),
        "commentary_intensity": prompt_state.get("commentary_intensity", "5"),
    }

    variant_b_suffix = (
        "\n\n### VARIANT B INSTRUCTION\n"
        "- Prioritize move safety and legal-move robustness over speculative complexity.\n"
        "- If multiple moves are close, choose the cleaner continuation."
    )
    prompt_context = GameContext(
        era=GameEra.ROMANTIC,
        theme=None,
        white_player=white_player.name,
        black_player=black_player.name,
        aggression_score=7,
        chaos_score=5,
        depth=40,
        bias=PromptBias.NEUTRAL,
    )
    system_prompt_a = PromptManager().build_system_prompt(prompt_context)
    system_prompt_b = system_prompt_a + variant_b_suffix

    def _run_prompt_variant(variant: str, system_prompt: str):
        local_engine = MatchEngine(
            white_player,
            black_player,
            time_control=tc,
            prompt_variant=variant,
            prompt_trace={**prompt_trace_base, "variant": variant},
            system_prompt_override=system_prompt,
        )
        with Spinner(f"Playing match (Variant {variant})"):
            local_result = asyncio.run(local_engine.play_match())
        local_result.prompt_trace["white_provider"] = config.white_provider
        local_result.prompt_trace["black_provider"] = config.black_provider
        local_result.prompt_trace["ab_enabled"] = bool(getattr(config, "ab_test_enabled", False))
        local_result.prompt_trace["variant_b_template_checksum"] = hashlib.sha256(
            system_prompt_b.encode("utf-8")
        ).hexdigest()[:16]
        return local_result
    
    start_time = time.time()
    
    try:
        cli_logger.info("run_id=%s mode=match stage=llm_generation_started", run_id)
        result = _run_prompt_variant("A", system_prompt_a)
        ab_results = [result]
        if getattr(config, "ab_test_enabled", False):
            ab_results.append(_run_prompt_variant("B", system_prompt_b))
            print_info(
                f"Prompt A/B completed: A={ab_results[0].result.value}, "
                f"B={ab_results[1].result.value}"
            )
        
        match_time = time.time() - start_time
        
        # CRITICAL FIX: Check if match is exportable (has moves)
        if not result.moves or len(result.moves) == 0:
            print()
            print(f"  {C.BOLD}{'═' * 60}{C.RESET}")
            print(f"  {C.BOLD}⚠️  Match Did Not Complete{C.RESET}")
            print(f"  {C.BOLD}{'═' * 60}{C.RESET}")
            
            termination = result.termination.value if hasattr(result.termination, 'value') else str(result.termination)
            
            print(f"    {C.YELLOW}Result:{C.RESET} {result.result.value}")
            print(f"    {C.YELLOW}Reason:{C.RESET} {termination}")
            print(f"    {C.YELLOW}Moves played:{C.RESET} 0")
            
            # Show which player had issues
            if result.termination.value == "forfeit":
                # Check which player forfeited
                if result.result.value == "0-1":
                    forfeiter = white_player.name
                    cause = getattr(result, "forfeit_cause", None)
                    if cause == "timeout":
                        print(f"    {C.RED}⚠️  {forfeiter} (White) forfeited after repeated move timeouts{C.RESET}")
                    elif cause == "api_error":
                        print(f"    {C.RED}⚠️  {forfeiter} (White) forfeited due to LLM API errors (e.g., quota/rate-limit){C.RESET}")
                    else:
                        print(f"    {C.RED}⚠️  {forfeiter} (White) forfeited due to repeated invalid move attempts{C.RESET}")
                elif result.result.value == "1-0":
                    forfeiter = black_player.name
                    cause = getattr(result, "forfeit_cause", None)
                    if cause == "timeout":
                        print(f"    {C.RED}⚠️  {forfeiter} (Black) forfeited after repeated move timeouts{C.RESET}")
                    elif cause == "api_error":
                        print(f"    {C.RED}⚠️  {forfeiter} (Black) forfeited due to LLM API errors (e.g., quota/rate-limit){C.RESET}")
                    else:
                        print(f"    {C.RED}⚠️  {forfeiter} (Black) forfeited due to repeated invalid move attempts{C.RESET}")
            elif result.termination.value == "timeout":
                print(f"    {C.RED}⚠️  Match timed out before any moves were played{C.RESET}")
            
            print()
            print(f"  {C.YELLOW}ℹ️  No game file exported (match has no moves){C.RESET}")
            print(f"  {C.YELLOW}💡 Tip: Check your LLM configuration and prompts{C.RESET}")
            
            if result.elo_change:
                print()
                print(f"  {C.BOLD}ELO Changes:{C.RESET}")
                print(f"    {result.elo_change.summary}")
            
            return
        
        # Post-match analysis (if enabled)
        analysis = None
        ab_analyses = []
        if config.enable_analysis:
            for idx, match_result in enumerate(ab_results):
                try:
                    from core.match_analyzer import MatchAnalyzer
                    stockfish_path = getattr(cfg.stockfish, 'path', None)
                    if stockfish_path and Path(stockfish_path).exists():
                        with Spinner(f"Analyzing match (Variant {match_result.prompt_variant})"):
                            with MatchAnalyzer(
                                stockfish_path=stockfish_path,
                                commentary_provider=white_prov if config.enable_commentary else None,
                                enable_commentary=config.enable_commentary,
                            ) as analyzer:
                                current_analysis = asyncio.run(analyzer.analyze_match(match_result))
                                ab_analyses.append(current_analysis)
                                if idx == 0:
                                    analysis = current_analysis
                        print_success(
                            f"Analysis complete (Variant {match_result.prompt_variant}, "
                            f"beauty={current_analysis.beauty_score:.1f})"
                        )
                    else:
                        print_info("Stockfish not configured - skipping analysis")
                        break
                except Exception as e:
                    print_error(f"Analysis failed: {e}")
                    break
        
        elapsed = time.time() - start_time
        
        # Display results
        print()
        print(f"  {C.BOLD}{'═' * 50}{C.RESET}")
        print(f"  {C.BOLD}Match Result{C.RESET}")
        print(f"  {C.BOLD}{'═' * 50}{C.RESET}")
        
        if result.result.value == "1-0":
            print(f"    Winner: {C.GREEN}{white_player.name} (White){C.RESET}")
        elif result.result.value == "0-1":
            print(f"    Winner: {C.GREEN}{black_player.name} (Black){C.RESET}")
        else:
            print(f"    Result: {C.YELLOW}Draw{C.RESET}")
        
        print(f"    Result: {result.result.value}")
        print(f"    Termination: {result.termination.value}")
        if result.termination.value == "forfeit" and getattr(result, "forfeit_cause", None) == "timeout":
            print(f"    {C.YELLOW}Note:{C.RESET} Forfeit caused by repeated move timeouts.")
        print(f"    Moves: {result.total_moves}")
        print(f"    Match time: {match_time:.1f}s")
        
        if analysis:
            print(f"    Beauty score: {analysis.beauty_score:.1f}/100")
            print(f"    Critical moments: {len(analysis.critical_moments)}")
        
        if result.elo_change:
            print(f"    ELO change: {result.elo_change.summary}")
        
        print(f"    Total time: {elapsed:.1f}s")
        cli_logger.info("run_id=%s mode=match stage=match_completed result=%s termination=%s moves=%d", run_id, result.result.value, result.termination.value, result.total_moves)
        
        # Export game using the unified exporter system
        output_dir = Path(config.output_dir)
        
        # Use the proper tournament exporter with analysis
        from export.tournament_exporter import MatchExporter
        
        # Determine formats
        if config.export_format == "all":
            formats_to_export = ["html", "pgn", "json", "markdown"]
        else:
            formats_to_export = [config.export_format]
        
        # Export
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print()
        for idx, match_result in enumerate(ab_results):
            current_analysis = ab_analyses[idx] if idx < len(ab_analyses) else None
            try:
                exporter = MatchExporter(
                    match_result=match_result,
                    match_analysis=current_analysis,
                    include_elo=True,
                )
            except ValueError as e:
                print_error(f"Cannot export match Variant {match_result.prompt_variant}: {e}")
                continue

            filename_base = (
                f"{match_result.match_id[:8]}_{config.white_provider}_vs_"
                f"{config.black_provider}_variant_{match_result.prompt_variant.lower()}"
            )
            cli_logger.info(
                "LLM match export planned: formats=%s output_dir=%s match_id=%s variant=%s",
                formats_to_export,
                str(output_dir),
                match_result.match_id,
                match_result.prompt_variant,
            )
            for fmt in formats_to_export:
                try:
                    if fmt == "html":
                        content = exporter.export_html()
                        ext = "html"
                    elif fmt == "pgn":
                        content = exporter.export_pgn()
                        ext = "pgn"
                    elif fmt == "json":
                        content = exporter.export_json()
                        ext = "json"
                    elif fmt == "markdown":
                        content = exporter.export_markdown()
                        ext = "md"
                    else:
                        continue

                    filepath = output_dir / f"{filename_base}.{ext}"
                    cli_logger.info(
                        "LLM match export: format=%s path=%s moves=%d termination=%s variant=%s",
                        fmt,
                        str(filepath),
                        match_result.total_moves,
                        match_result.termination.value,
                        match_result.prompt_variant,
                    )
                    filepath.write_text(content, encoding="utf-8")
                    print_success(f"Game saved ({fmt}, Variant {match_result.prompt_variant}): {filepath}")
                    _warn_export_guardrail([filepath], mode="match", run_id=run_id)
                except Exception as e:
                    print_error(f"Export failed ({fmt}, Variant {match_result.prompt_variant}): {e}")

        if getattr(config, "ab_test_enabled", False) and len(ab_results) >= 2:
            summary_path = output_dir / (
                f"{ab_results[0].match_id[:8]}_{config.white_provider}_vs_{config.black_provider}_ab_summary.json"
            )
            ab_summary = {
                "mode": "match_ab",
                "white_provider": config.white_provider,
                "black_provider": config.black_provider,
                "time_control": config.time_control,
                "variants": [
                    {
                        "variant": r.prompt_variant,
                        "match_id": r.match_id,
                        "result": r.result.value,
                        "termination": r.termination.value,
                        "moves": r.total_moves,
                        "duration_seconds": r.duration,
                        "prompt_trace": r.prompt_trace,
                        "beauty_score": (
                            ab_analyses[i].beauty_score
                            if i < len(ab_analyses) and ab_analyses[i] is not None
                            else None
                        ),
                    }
                    for i, r in enumerate(ab_results)
                ],
            }
            summary_path.write_text(json.dumps(ab_summary, indent=2, ensure_ascii=False), encoding="utf-8")
            print_success(f"A/B summary saved: {summary_path}")
        
    except Exception as e:
        print_error(f"Match error: {e}")
        import traceback
        traceback.print_exc()


def interactive_tournament():
    """
    Interactive tournament setup with improved UX.
    
    Features:
    - Smart bulk player input (gemini x 100, ranges, etc.)
    - Go back navigation
    - Parallel execution support
    - Better step ordering
    """
    from core.tournament_cli_improved import ImprovedTournamentBuilder
    
    print()
    print_header("LLM vs LLM Tournament")
    
    # Get available providers
    providers = _get_available_providers()
    if len(providers) < 2:
        print_error("Need at least 2 providers for a tournament.")
        return
    
    # Use improved builder
    builder = ImprovedTournamentBuilder(providers)
    config = builder.build()
    
    if not config:
        print_info("Tournament cancelled.")
        return
    
    # Execute tournament with new config
    _execute_tournament_v2(config)


def _execute_tournament_v2(config):
    """
    Execute tournament with improved config object (from ImprovedTournamentBuilder).
    
    Supports parallel execution using threading for faster tournaments.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from core.tournament_player import TournamentPlayer, TimeControl
    from core.tournament import Tournament, TournamentConfig, TournamentFormat
    from export.tournament_exporter import export_tournament
    
    print()
    print_header(f"Tournament: {config.name}")
    run_id = _new_run_id("tournament")
    cli_logger.info("run_id=%s mode=tournament stage=start", run_id)
    _announce_validation_policy("tournament")
    
    # Create players for each provider in the list
    players = []
    provider_instances = {}  # Cache provider instances
    
    for pname in config.providers:
        try:
            # Reuse provider instance if same provider
            if pname not in provider_instances:
                provider_instances[pname] = _create_provider(pname)
            
            provider = provider_instances[pname]
            
            # Create unique player ID
            player_id = f"{pname}_{len([p for p in players if p.provider_name == pname]) + 1}"
            
            player = TournamentPlayer(
                name=player_id,
                provider=provider,
                provider_name=pname,
            )
            players.append(player)
        except Exception as e:
            print_error(f"Failed to create player for {pname}: {e}")
    
    if len(players) < 2:
        print_error("Not enough players for tournament.")
        return
    
    print_info(f"Registered {len(players)} players")
    
    # Map format
    format_map = {
        "round_robin": TournamentFormat.ROUND_ROBIN,
        "double_round_robin": TournamentFormat.DOUBLE_ROUND_ROBIN,
        "swiss": TournamentFormat.SWISS,
        "knockout": TournamentFormat.KNOCKOUT,
    }
    tournament_format = format_map.get(config.format, TournamentFormat.ROUND_ROBIN)
    
    # Map time control
    tc_map = {
        "bullet": TimeControl.BULLET,
        "blitz": TimeControl.BLITZ,
        "rapid": TimeControl.RAPID,
        "classical": TimeControl.CLASSICAL,
        "unlimited": TimeControl.UNLIMITED,
    }
    tc = tc_map.get(config.time_control, TimeControl.RAPID)
    
    # Create tournament config
    tournament_config = TournamentConfig(
        name=config.name,
        format=tournament_format,
        players=players,
        time_control=tc,
    )
    
    tournament = Tournament(tournament_config)
    
    print()
    print_info(f"Format: {tournament_format.value}")
    print_info(f"Time control: {config.time_control}")
    print_info(f"Parallel: {config.enable_parallel} ({config.max_workers} workers)")
    print()
    
    start_time = time.time()
    
    try:
        # Note: Full parallel tournament execution would require modifying Tournament class
        # For now, we run the tournament normally and add parallel support in future
        with Spinner(f"Running {config.format} tournament"):
            cli_logger.info("run_id=%s mode=tournament stage=llm_generation_started format=%s", run_id, config.format)
            result = asyncio.run(tournament.run())
        
        elapsed = time.time() - start_time
        
        # Display results
        print()
        print(f"  {C.BOLD}{'═' * 55}{C.RESET}")
        print(f"  {C.BOLD}Tournament Complete{C.RESET}")
        print(f"  {C.BOLD}{'═' * 55}{C.RESET}")
        
        if result.winner:
            print(f"    🏆 Winner: {C.GREEN}{result.winner.name}{C.RESET}")
        
        print(f"    Total games: {result.total_games}")
        print(f"    Decisive: {result.decisive_games}")
        print(f"    Draws: {result.draws}")
        print(f"    Duration: {elapsed:.1f}s")
        cli_logger.info("run_id=%s mode=tournament stage=tournament_completed total_games=%d decisive=%d draws=%d", run_id, result.total_games, result.decisive_games, result.draws)
        
        # Standings
        print()
        print(f"  {C.BOLD}Final Standings:{C.RESET}")
        print(f"    {'#':<3} {'Player':<20} {'Pts':<6} {'W':<3} {'D':<3} {'L':<3}")
        print(f"    {'-'*40}")
        
        for standing in result.standings:
            rank_str = f"{standing.rank}."
            print(f"    {rank_str:<3} {standing.player.name:<20} {standing.points:<6.1f} "
                  f"{standing.wins:<3} {standing.draws:<3} {standing.losses:<3}")
        
        # Export
        output_dir = Path(config.output_dir) / config.name.replace(" ", "_").lower()
        
        # Determine formats and PGN mode
        pretty_pgn = False
        per_game_pgn = False
        if config.export_format == "all":
            format_list = ["html", "markdown", "json", "pgn"]
            pretty_pgn = getattr(config, "pgn_pretty", True)
            per_game_pgn = True
        else:
            if config.export_format == "pgn_pretty":
                format_list = ["pgn", "json"]
                pretty_pgn = True
            elif config.export_format == "pgn_per_game":
                format_list = ["pgn", "json"]
                per_game_pgn = True
            else:
                format_list = [config.export_format]
                # Always include json for ELO tracking
                if "json" not in format_list:
                    format_list.append("json")
        
        exported = export_tournament(
            result,
            str(output_dir),
            formats=format_list,
            pretty_pgn=pretty_pgn,
            per_game_pgn=per_game_pgn,
        )
        cli_logger.info(
            "Tournament export complete: name=%s formats=%s pretty_pgn=%s per_game_pgn=%s output=%s files=%d",
            config.name,
            format_list,
            pretty_pgn,
            per_game_pgn,
            str(output_dir),
            len(exported),
        )
        
        print()
        print_success(f"Results exported to: {output_dir}")
        for fmt, path in exported.items():
            print_info(f"  {fmt}: {Path(path).name}")
        _warn_export_guardrail(
            [Path(p) for p in exported.values()],
            mode="tournament",
            run_id=run_id,
        )
        
    except Exception as e:
        print_error(f"Tournament error: {e}")
        import traceback
        traceback.print_exc()


def interactive_tournament_old():
    """
    OLD Interactive tournament setup (DEPRECATED - kept for reference).
    
    Use interactive_tournament() for the new improved version.
    """
    print()
    print_header("LLM vs LLM Tournament")
    
    # Step 1: Select format
    print(f"  {C.BOLD}Tournament formats:{C.RESET}")
    formats = [
        ("round_robin", "Round Robin - Everyone plays everyone once"),
        ("double_round_robin", "Double Round Robin - Everyone plays everyone twice"),
        ("swiss", "Swiss - Pair by score each round"),
        ("knockout", "Knockout - Single elimination bracket"),
    ]
    for i, (_, desc) in enumerate(formats, 1):
        print(f"    {i}. {desc}")
    
    # prompt_int(prompt, default, min_val, max_val)
    fmt_idx = prompt_int("Select format", 1, 1, len(formats))
    format_name = formats[fmt_idx - 1][0]
    
    # Step 2: Select players
    providers = _get_available_providers()
    if len(providers) < 2:
        print_error("Need at least 2 providers for a tournament.")
        return
    
    print()
    print(f"  {C.BOLD}Available providers:{C.RESET}")
    for i, p in enumerate(providers, 1):
        print(f"    {i}. {p}")
    
    print()
    print_info("Enter player numbers separated by commas (e.g., 1,2,3)")
    selection = input(f"  {C.YELLOW}>{C.RESET} Players: ").strip()
    
    try:
        indices = [int(x.strip()) for x in selection.split(",")]
        selected_providers = [providers[i-1] for i in indices if 1 <= i <= len(providers)]
    except (ValueError, IndexError):
        print_error("Invalid selection. Using first 2 providers.")
        selected_providers = providers[:2]
    
    if len(selected_providers) < 2:
        print_error("Need at least 2 players.")
        return
    
    # Step 3: Tournament name
    default_name = f"CAISSA Tournament {datetime.datetime.now().strftime('%Y-%m-%d')}"
    name = input(f"  Tournament name [{default_name}]: ").strip() or default_name
    
    # Step 4: Export format
    print()
    print(f"  {C.BOLD}Export formats:{C.RESET}")
    export_formats = [
        ("markdown", "Markdown (default)"),
        ("html", "HTML"),
        ("json", "JSON"),
        ("pgn", "PGN (all games)"),
    ]
    for i, (_, desc) in enumerate(export_formats, 1):
        print(f"    {i}. {desc}")
    
    export_idx = prompt_int("Select export format", 1, 1, len(export_formats))
    export_format = export_formats[export_idx - 1][0]
    
    # Step 5: Confirm
    print()
    print(f"  {C.BOLD}Tournament Configuration:{C.RESET}")
    print(f"    Name: {name}")
    print(f"    Format: {format_name}")
    print(f"    Players: {', '.join(selected_providers)}")
    print(f"    Export: {export_format}")
    print()
    
    confirm = prompt_yes_no("Start tournament?", default=True)
    if not confirm:
        print_info("Tournament cancelled.")
        return
    
    _execute_tournament(name, format_name, selected_providers, export_format)


def _execute_tournament(name: str, format_name: str, provider_names: List[str], export_format: str = "markdown"):
    """
    Execute a full tournament.
    
    Supports multiple export formats:
    - markdown: Rich markdown report
    - html: Interactive HTML report
    - json: Structured data format
    - pgn: All games in PGN format
    """
    import asyncio
    from core.tournament_player import TournamentPlayer, TimeControl
    from core.tournament import Tournament, TournamentConfig, TournamentFormat
    from export.tournament_exporter import export_tournament
    
    print()
    print_header(f"Tournament: {name}")
    
    # Create players
    players = []
    for pname in provider_names:
        try:
            provider = _create_provider(pname)
            player = TournamentPlayer(
                name=pname,
                provider=provider,
                provider_name=pname,
            )
            players.append(player)
            print_success(f"Player registered: {pname}")
        except Exception as e:
            print_error(f"Failed to create {pname}: {e}")
    
    if len(players) < 2:
        print_error("Not enough players for tournament.")
        return
    
    # Map format
    format_map = {
        "round_robin": TournamentFormat.ROUND_ROBIN,
        "double_round_robin": TournamentFormat.DOUBLE_ROUND_ROBIN,
        "swiss": TournamentFormat.SWISS,
        "knockout": TournamentFormat.KNOCKOUT,
    }
    tournament_format = format_map.get(format_name, TournamentFormat.ROUND_ROBIN)
    
    # Create config
    config = TournamentConfig(
        name=name,
        format=tournament_format,
        players=players,
        time_control=TimeControl.RAPID,
    )
    
    tournament = Tournament(config)
    
    print()
    print_info(f"Format: {tournament_format.value}")
    print_info(f"Rounds: {config.rounds}")
    print_info(f"Players: {len(players)}")
    print()
    
    start_time = time.time()
    
    try:
        with Spinner("Running tournament"):
            result = asyncio.run(tournament.run())
        
        elapsed = time.time() - start_time
        
        # Display results
        print()
        print(f"  {C.BOLD}{'═' * 55}{C.RESET}")
        print(f"  {C.BOLD}Tournament Complete{C.RESET}")
        print(f"  {C.BOLD}{'═' * 55}{C.RESET}")
        
        if result.winner:
            print(f"    🏆 Winner: {C.GREEN}{result.winner.name}{C.RESET}")
        
        print(f"    Total games: {result.total_games}")
        print(f"    Decisive: {result.decisive_games}")
        print(f"    Draws: {result.draws}")
        print(f"    Duration: {elapsed:.1f}s")
        
        # Standings
        print()
        print(f"  {C.BOLD}Final Standings:{C.RESET}")
        print(f"    {'#':<3} {'Player':<20} {'Pts':<6} {'W':<3} {'D':<3} {'L':<3}")
        print(f"    {'-'*40}")
        
        for standing in result.standings:
            rank_str = f"{standing.rank}."
            print(f"    {rank_str:<3} {standing.player.name:<20} {standing.points:<6.1f} "
                  f"{standing.wins:<3} {standing.draws:<3} {standing.losses:<3}")
        
        # Export - use selected format
        output_dir = Path("tournaments") / name.replace(" ", "_").lower()
        
        # Map user selection to export formats
        format_list = [export_format]
        # Always include json for ELO tracking
        if "json" not in format_list:
            format_list.append("json")
        
        exported = export_tournament(result, str(output_dir), formats=format_list)
        
        print()
        print_success(f"Results exported to: {output_dir}")
        for fmt, path in exported.items():
            print_info(f"  {fmt}: {Path(path).name}")
        
    except Exception as e:
        print_error(f"Tournament error: {e}")
        import traceback
        traceback.print_exc()


def show_elo_ratings():
    """Display ELO ratings from tournament history."""
    print()
    print_header("ELO Ratings")
    
    # Check for tournament history
    tournaments_dir = Path("tournaments")
    if not tournaments_dir.exists():
        print_info("No tournament history found.")
        print_info("Run a tournament first to generate ELO ratings.")
        return
    
    # Collect ratings from tournament results
    import json
    ratings = {}
    
    for tournament_dir in tournaments_dir.iterdir():
        if tournament_dir.is_dir():
            json_file = tournament_dir / "tournament.json"
            if json_file.exists():
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))
                    for standing in data.get("standings", []):
                        player_name = standing.get("player_name", "Unknown")
                        rating = standing.get("player", {}).get("elo_rating", 1500)
                        if player_name not in ratings:
                            ratings[player_name] = {"rating": rating, "games": 0}
                        ratings[player_name]["rating"] = rating
                        ratings[player_name]["games"] += standing.get("games_played", 0)
                except Exception:
                    continue
    
    if not ratings:
        print_info("No ELO data available yet.")
        return
    
    # Sort by rating
    sorted_ratings = sorted(ratings.items(), key=lambda x: -x[1]["rating"])
    
    print(f"    {'#':<3} {'Player':<25} {'Rating':<8} {'Games':<6}")
    print(f"    {'-'*45}")
    
    for i, (name, data) in enumerate(sorted_ratings, 1):
        print(f"    {i:<3} {name:<25} {data['rating']:<8} {data['games']:<6}")
    
    print()
    input(f"  {C.YELLOW}>{C.RESET} Press Enter to continue...")


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    """Main entry point."""
    # Support quick command-line shortcuts: python main.py generate, etc.
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        
        if cmd in ("--help", "-h"):
            print(f"""
{C.BOLD}CAISSA Chess Engine - Interactive CLI{C.RESET}

Usage:
  python main.py                  Launch interactive menu
  python main.py generate         Jump to game generation
  python main.py batch            Jump to batch generation
  python main.py matchup          Jump to historical matchup
  python main.py analyze          Jump to PGN analysis
              python main.py benchmark        Jump to benchmarks
  python main.py prompts          Open Prompt Studio
              python main.py styles           List available styles
  python main.py config           View configuration
  python main.py info             Show system info

LLM vs LLM Tournament (v0.5.0):
  python main.py match            Single LLM vs LLM match
  python main.py tournament       Full tournament mode
  python main.py elo              View ELO ratings

Configuration:
  Edit caissa_config.yaml for all settings.
  Create caissa_config.local.yaml for personal overrides.
  Set API keys in .env file.
""")
            return 0
        
        clear_screen()
        print_banner()
        
        shortcuts = {
            "generate": interactive_generate,
            "gen": interactive_generate,
            "batch": interactive_batch,
            "matchup": interactive_matchup,
            "analyze": interactive_analyze,
            "benchmark": interactive_benchmark,
            "bench": interactive_benchmark,
            "prompts": interactive_prompt_studio,
            "prompt": interactive_prompt_studio,
            "studio": interactive_prompt_studio,
            "styles": show_styles,
            "config": interactive_config,
            "cfg": interactive_config,
            "info": show_info,
            # v0.5.0 Tournament commands
            "match": interactive_match,
            "tournament": interactive_tournament,
            "tourney": interactive_tournament,
            "elo": show_elo_ratings,
            "ratings": show_elo_ratings,
        }
        
        handler = shortcuts.get(cmd)
        if handler:
            handler()
            return 0
        else:
            print_error(f"Unknown command: {cmd}")
            print_info("Run 'python main.py --help' for usage.")
            return 1
    
    # Interactive mode
    clear_screen()
    print_banner()
    
    # Quick status line
    providers = _get_available_providers()
    active_providers = [p for p in providers if p != "ollama"]
    if active_providers:
        print(f"  {C.DIM}Active providers: {', '.join(active_providers)} (+ ollama){C.RESET}")
    else:
        print(f"  {C.YELLOW}No cloud providers configured. Set API keys in .env or caissa_config.yaml{C.RESET}")
    
    sf_path = _resolve_stockfish_path()
    sf_status = f"{C.GREEN}active{C.RESET}" if sf_path else f"{C.YELLOW}not found{C.RESET}"
    print(f"  {C.DIM}Stockfish: {sf_status}{C.RESET}")
    print(f"  {C.DIM}Config: caissa_config.yaml{C.RESET}")
    
    main_menu()
    return 0


if __name__ == "__main__":
    sys.exit(main())
