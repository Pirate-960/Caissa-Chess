"""
tests/test_log_manager.py

Tests for the centralized logging infrastructure (log_manager.py).

Covers:
- SESSION_ID format and uniqueness
- setup_logging() directory creation and handler wiring
- get_logger() category routing
- is_llm_logging_enabled() flag
- get_log_dir() path
- Verbosity levels
- LOG_CATEGORIES completeness
- Legacy module mapping
"""

import re
import shutil
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import log_manager
from log_manager import (
    SESSION_ID,
    LOG_CATEGORIES,
    _LEGACY_MODULE_MAP,
    _VERBOSITY_LEVELS,
    _CONSOLE_FMT,
    _MASTER_FMT,
    setup_logging,
    get_logger,
    get_session_id,
    is_llm_logging_enabled,
    get_log_dir,
    get_console_handler,
)


def _reset_log_manager():
    """Reset log_manager module state so setup_logging() can be called again."""
    log_manager._setup_done = False
    log_manager._log_dir = None
    log_manager._llm_prompts_enabled = True
    log_manager._console_handler = None

    # Clear all handlers from caissa.* loggers + root to avoid cross-test leaks
    root = logging.getLogger()
    root.handlers.clear()

    for cat in LOG_CATEGORIES:
        lg = logging.getLogger(f"caissa.{cat}")
        lg.handlers.clear()
        lg.propagate = True

    for mod in _LEGACY_MODULE_MAP:
        lg = logging.getLogger(mod)
        lg.handlers.clear()


class TestSessionID(unittest.TestCase):
    """Tests for the process-wide SESSION_ID."""

    def test_session_id_is_hex_string(self):
        """SESSION_ID should be 8 hex characters."""
        self.assertIsInstance(SESSION_ID, str)
        self.assertEqual(len(SESSION_ID), 8)
        self.assertTrue(
            re.fullmatch(r"[0-9a-f]{8}", SESSION_ID),
            f"SESSION_ID '{SESSION_ID}' is not 8 hex chars",
        )

    def test_get_session_id_matches(self):
        """get_session_id() should return the same value."""
        self.assertEqual(get_session_id(), SESSION_ID)


class TestLogCategories(unittest.TestCase):
    """Tests for LOG_CATEGORIES dictionary."""

    EXPECTED_CATEGORIES = [
        "cli", "config", "generation", "llm.calls", "llm.errors",
        "prompts", "validation", "engine", "export", "aesthetic", "benchmark",
    ]

    def test_all_expected_categories_present(self):
        """All 11 expected categories should be defined."""
        for cat in self.EXPECTED_CATEGORIES:
            self.assertIn(cat, LOG_CATEGORIES, f"Missing category: {cat}")

    def test_category_structure(self):
        """Each category should have 'dir' and 'file' keys."""
        for cat, info in LOG_CATEGORIES.items():
            self.assertIn("dir", info, f"Category '{cat}' missing 'dir'")
            self.assertIn("file", info, f"Category '{cat}' missing 'file'")
            self.assertTrue(info["file"].endswith(".log"), f"{cat} file should end in .log")

    def test_category_count(self):
        """Should have exactly 11 categories."""
        self.assertEqual(len(LOG_CATEGORIES), 11)


class TestVerbosityLevels(unittest.TestCase):
    """Tests for _VERBOSITY_LEVELS mapping."""

    def test_quiet_is_critical(self):
        """'quiet' should map to CRITICAL (effectively silent)."""
        self.assertEqual(_VERBOSITY_LEVELS["quiet"], logging.CRITICAL)

    def test_normal_is_info(self):
        """'normal' should map to INFO."""
        self.assertEqual(_VERBOSITY_LEVELS["normal"], logging.INFO)

    def test_verbose_is_debug(self):
        """'verbose' should map to DEBUG."""
        self.assertEqual(_VERBOSITY_LEVELS["verbose"], logging.DEBUG)

    def test_debug_is_debug(self):
        """'debug' should map to DEBUG."""
        self.assertEqual(_VERBOSITY_LEVELS["debug"], logging.DEBUG)

    def test_all_four_levels_defined(self):
        """Should have exactly 4 verbosity levels."""
        self.assertEqual(len(_VERBOSITY_LEVELS), 4)


class TestLegacyModuleMap(unittest.TestCase):
    """Tests for _LEGACY_MODULE_MAP."""

    EXPECTED_MODULES = [
        "core.generator",
        "core.llm_provider",
        "core.prompt_manager",
        "engine.legality",
        "engine.stockfish_client",
        "export.pgn_builder",
        "config_manager",
        "benchmarks.provider_benchmark",
    ]

    def test_expected_modules_present(self):
        """Key module loggers should be mapped."""
        for mod in self.EXPECTED_MODULES:
            self.assertIn(mod, _LEGACY_MODULE_MAP, f"Missing mapping for {mod}")

    def test_all_targets_are_valid_categories(self):
        """Every mapped target should be a valid LOG_CATEGORIES key."""
        for mod, cat in _LEGACY_MODULE_MAP.items():
            self.assertIn(
                cat, LOG_CATEGORIES,
                f"Module '{mod}' maps to unknown category '{cat}'",
            )


class TestFormatStrings(unittest.TestCase):
    """Tests for format string constants."""

    def test_master_fmt_has_time_and_name(self):
        """Master format should include asctime, name, and levelname."""
        self.assertIn("%(asctime)s", _MASTER_FMT)
        self.assertIn("%(name)", _MASTER_FMT)
        self.assertIn("%(levelname)", _MASTER_FMT)

    def test_console_fmt_compact(self):
        """Console format should be compact (no timestamp)."""
        self.assertNotIn("%(asctime)s", _CONSOLE_FMT)
        self.assertIn("%(levelname)", _CONSOLE_FMT)
        self.assertIn("%(message)s", _CONSOLE_FMT)


class TestSetupLogging(unittest.TestCase):
    """Tests for setup_logging() function."""

    def setUp(self):
        """Create a temporary directory for logs."""
        self.temp_dir = tempfile.mkdtemp(prefix="caissa_test_logs_")
        _reset_log_manager()

    def tearDown(self):
        """Clean up temp dir and reset state."""
        _reset_log_manager()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_creates_directory_tree(self):
        """setup_logging() should create all subdirectories."""
        setup_logging(log_dir=self.temp_dir, verbosity="quiet")

        # NOTE: setup_logging resolves relative to project root, but we pass
        # an absolute temp dir.  The function uses Path(__file__).parent / log_dir
        # so we need to check the actual created path.
        actual_dir = get_log_dir()
        self.assertIsNotNone(actual_dir)

        # Check subdirectories exist
        expected_dirs = {info["dir"] for info in LOG_CATEGORIES.values()}
        for d in expected_dirs:
            self.assertTrue(
                (actual_dir / d).is_dir(),
                f"Expected subdirectory '{d}' not created",
            )

    def test_creates_master_log(self):
        """setup_logging() should create master.log."""
        setup_logging(log_dir=self.temp_dir, verbosity="quiet")
        actual_dir = get_log_dir()
        self.assertTrue((actual_dir / "master.log").exists())

    def test_idempotent(self):
        """Calling setup_logging() twice should be a no-op."""
        setup_logging(log_dir=self.temp_dir, verbosity="quiet")
        first_dir = get_log_dir()

        # Second call with different params should be ignored
        setup_logging(log_dir="different_dir", verbosity="quiet")
        second_dir = get_log_dir()

        self.assertEqual(first_dir, second_dir)

    def test_root_logger_has_handlers(self):
        """Root logger should have at least the master RotatingFileHandler."""
        setup_logging(log_dir=self.temp_dir, verbosity="quiet")
        root = logging.getLogger()
        self.assertGreater(len(root.handlers), 0)

    def test_console_handler_added_for_normal(self):
        """Non-quiet verbosity should add a StreamHandler to root."""
        setup_logging(log_dir=self.temp_dir, verbosity="normal")
        root = logging.getLogger()
        stream_handlers = [
            h for h in root.handlers if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        self.assertGreater(len(stream_handlers), 0, "Expected a console StreamHandler")

    def test_no_console_handler_for_quiet(self):
        """'quiet' verbosity should not add a StreamHandler."""
        setup_logging(log_dir=self.temp_dir, verbosity="quiet")
        root = logging.getLogger()
        stream_handlers = [
            h for h in root.handlers if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        self.assertEqual(len(stream_handlers), 0, "Quiet mode should have no console handler")
        self.assertIsNone(get_console_handler())

    def test_get_console_handler_for_normal(self):
        """Normal verbosity should expose the managed console StreamHandler."""
        setup_logging(log_dir=self.temp_dir, verbosity="normal")
        console = get_console_handler()
        self.assertIsNotNone(console)
        self.assertIsInstance(console, logging.StreamHandler)
        self.assertNotIsInstance(console, logging.FileHandler)

    def test_llm_loggers_no_propagate(self):
        """LLM call/error loggers should have propagate=False."""
        setup_logging(log_dir=self.temp_dir, verbosity="quiet")
        calls_logger = logging.getLogger("caissa.llm.calls")
        errors_logger = logging.getLogger("caissa.llm.errors")
        self.assertFalse(calls_logger.propagate)
        self.assertFalse(errors_logger.propagate)

    def test_llm_prompts_disabled(self):
        """When log_llm_prompts=False, is_llm_logging_enabled() returns False."""
        setup_logging(log_dir=self.temp_dir, log_llm_prompts=False, verbosity="quiet")
        self.assertFalse(is_llm_logging_enabled())

    def test_llm_prompts_enabled_default(self):
        """By default, LLM prompt logging should be enabled."""
        setup_logging(log_dir=self.temp_dir, verbosity="quiet")
        self.assertTrue(is_llm_logging_enabled())


class TestGetLogger(unittest.TestCase):
    """Tests for get_logger() function."""

    def setUp(self):
        """Create temp log dir."""
        self.temp_dir = tempfile.mkdtemp(prefix="caissa_test_logs_")
        _reset_log_manager()
        setup_logging(log_dir=self.temp_dir, verbosity="quiet")

    def tearDown(self):
        _reset_log_manager()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_returns_logger_instance(self):
        """get_logger() should return a logging.Logger."""
        logger = get_logger("generation")
        self.assertIsInstance(logger, logging.Logger)

    def test_logger_name_prefix(self):
        """Logger name should be 'caissa.<category>'."""
        logger = get_logger("validation")
        self.assertEqual(logger.name, "caissa.validation")

    def test_known_category_has_handlers(self):
        """Known categories should have at least one handler."""
        get_logger("cli")
        cat_logger = logging.getLogger("caissa.cli")
        self.assertGreater(len(cat_logger.handlers), 0)

    def test_custom_category_works(self):
        """Unknown category should still return a logger (via hierarchy)."""
        logger = get_logger("my_custom_category")
        self.assertEqual(logger.name, "caissa.my_custom_category")

    def test_auto_setup_triggers(self):
        """get_logger() should trigger auto-setup if not yet done."""
        _reset_log_manager()
        # Don't call setup_logging — let get_logger trigger it
        # Reset the flag so auto-setup runs
        log_manager._setup_done = False
        # auto_setup calls setup_logging, but we mock it to prevent side effects
        with patch("log_manager._auto_setup") as mock_auto:
            mock_auto.side_effect = lambda: setattr(log_manager, "_setup_done", True)
            get_logger("test")
            mock_auto.assert_called_once()


class TestGetLogDir(unittest.TestCase):
    """Tests for get_log_dir()."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="caissa_test_logs_")
        _reset_log_manager()

    def tearDown(self):
        _reset_log_manager()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_none_before_setup(self):
        """get_log_dir() should return None before setup_logging()."""
        self.assertIsNone(get_log_dir())

    def test_returns_path_after_setup(self):
        """get_log_dir() should return a Path after setup."""
        setup_logging(log_dir=self.temp_dir, verbosity="quiet")
        result = get_log_dir()
        self.assertIsInstance(result, Path)


class TestLoggingIntegration(unittest.TestCase):
    """Integration tests: write a log message and verify it appears in files."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="caissa_test_logs_")
        _reset_log_manager()
        setup_logging(log_dir=self.temp_dir, level="DEBUG", verbosity="quiet")

    def tearDown(self):
        _reset_log_manager()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_message_appears_in_category_file(self):
        """A message to caissa.cli should appear in cli/activity.log."""
        logger = get_logger("cli")
        logger.info("test_message_12345")

        # Flush handlers
        for h in logger.handlers:
            h.flush()
        for h in logging.getLogger().handlers:
            h.flush()

        actual_dir = get_log_dir()
        log_file = actual_dir / "cli" / "activity.log"
        self.assertTrue(log_file.exists(), f"{log_file} should exist")

        content = log_file.read_text(encoding="utf-8")
        self.assertIn("test_message_12345", content)

    def test_message_appears_in_master_log(self):
        """A normal category message should also appear in master.log (via propagation)."""
        logger = get_logger("generation")
        logger.info("master_test_67890")

        for h in logging.getLogger().handlers:
            h.flush()

        actual_dir = get_log_dir()
        master = actual_dir / "master.log"
        self.assertTrue(master.exists())

        content = master.read_text(encoding="utf-8")
        self.assertIn("master_test_67890", content)

    def test_llm_calls_not_in_master(self):
        """LLM call messages should NOT appear in master.log (propagate=False)."""
        llm_logger = logging.getLogger("caissa.llm.calls")
        llm_logger.info("secret_llm_call")

        for h in logging.getLogger().handlers:
            h.flush()

        actual_dir = get_log_dir()
        master = actual_dir / "master.log"
        content = master.read_text(encoding="utf-8")
        self.assertNotIn("secret_llm_call", content)

    def test_legacy_module_logger_routes_correctly(self):
        """A message from 'core.generator' should land in generation/generation.log."""
        gen_logger = logging.getLogger("core.generator")
        gen_logger.info("legacy_routing_test_99999")

        for h in gen_logger.handlers:
            h.flush()

        actual_dir = get_log_dir()
        gen_log = actual_dir / "generation" / "generation.log"
        self.assertTrue(gen_log.exists(), f"{gen_log} should exist")

        content = gen_log.read_text(encoding="utf-8")
        self.assertIn("legacy_routing_test_99999", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
