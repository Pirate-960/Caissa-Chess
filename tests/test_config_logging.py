"""
tests/test_config_logging.py

Tests for the LoggingConfig dataclass and its validation
within the configuration system (config_manager.py).

Covers:
- Default field values
- All 7 fields present
- Validation of the logging.level choice
- Integration with CaissaConfig
"""

import unittest
from config_manager import LoggingConfig, CaissaConfig, validate_config, ConfigValidationError


class TestLoggingConfigDefaults(unittest.TestCase):
    """Tests for LoggingConfig default values."""

    def setUp(self):
        self.cfg = LoggingConfig()

    def test_level_default(self):
        """Default log level should be INFO."""
        self.assertEqual(self.cfg.level, "INFO")

    def test_log_dir_default(self):
        """Default log directory should be 'logs'."""
        self.assertEqual(self.cfg.log_dir, "logs")

    def test_format_default(self):
        """Default format string should contain asctime and levelname."""
        self.assertIn("%(asctime)s", self.cfg.format)
        self.assertIn("%(levelname)", self.cfg.format)

    def test_log_llm_prompts_default(self):
        """LLM prompt logging should be enabled by default."""
        self.assertTrue(self.cfg.log_llm_prompts)

    def test_max_bytes_default(self):
        """Default max_bytes should be 10 MB."""
        self.assertEqual(self.cfg.max_bytes, 10_485_760)

    def test_backup_count_default(self):
        """Default backup count should be 3."""
        self.assertEqual(self.cfg.backup_count, 3)

    def test_verbosity_default(self):
        """Default verbosity should be 'normal'."""
        self.assertEqual(self.cfg.verbosity, "normal")


class TestLoggingConfigFieldCount(unittest.TestCase):
    """Ensure no fields are accidentally removed."""

    EXPECTED_FIELDS = {
        "level", "log_dir", "format", "log_llm_prompts",
        "max_bytes", "backup_count", "console_logs", "verbosity",
    }

    def test_all_fields_present(self):
        """LoggingConfig should have exactly 8 fields."""
        actual = {f.name for f in LoggingConfig.__dataclass_fields__.values()}
        self.assertEqual(actual, self.EXPECTED_FIELDS)

    def test_field_count(self):
        self.assertEqual(len(LoggingConfig.__dataclass_fields__), 8)


class TestLoggingConfigCustomValues(unittest.TestCase):
    """Tests for custom value construction."""

    def test_override_all(self):
        """All fields should accept custom values."""
        cfg = LoggingConfig(
            level="DEBUG",
            log_dir="custom_logs",
            format="%(message)s",
            log_llm_prompts=False,
            max_bytes=5_000_000,
            backup_count=5,
            verbosity="verbose",
        )
        self.assertEqual(cfg.level, "DEBUG")
        self.assertEqual(cfg.log_dir, "custom_logs")
        self.assertFalse(cfg.log_llm_prompts)
        self.assertEqual(cfg.max_bytes, 5_000_000)
        self.assertEqual(cfg.backup_count, 5)
        self.assertEqual(cfg.verbosity, "verbose")


class TestLoggingConfigValidation(unittest.TestCase):
    """Tests that validate_config catches invalid logging values."""

    def test_valid_config_passes(self):
        """Default CaissaConfig should pass validation."""
        config = CaissaConfig()
        # Should not raise
        validate_config(config)

    def test_invalid_log_level_fails(self):
        """An invalid log level should raise ConfigValidationError."""
        config = CaissaConfig()
        config.logging.level = "INVALID"
        with self.assertRaises(ConfigValidationError) as ctx:
            validate_config(config)
        self.assertTrue(any("logging.level" in e for e in ctx.exception.errors))


class TestLoggingConfigInCaissaConfig(unittest.TestCase):
    """Tests for LoggingConfig as part of the top-level CaissaConfig."""

    def test_logging_section_exists(self):
        """CaissaConfig should have a 'logging' attribute of type LoggingConfig."""
        config = CaissaConfig()
        self.assertIsInstance(config.logging, LoggingConfig)

    def test_logging_section_is_default(self):
        """A fresh CaissaConfig should have default logging values."""
        config = CaissaConfig()
        defaults = LoggingConfig()
        self.assertEqual(config.logging.level, defaults.level)
        self.assertEqual(config.logging.verbosity, defaults.verbosity)
        self.assertEqual(config.logging.max_bytes, defaults.max_bytes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
