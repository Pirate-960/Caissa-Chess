"""
Comprehensive tests for configuration.py (legacy bridge)

Covers:
- Config class singleton
- All ~28 @property methods delegating to config_manager.cfg
"""

from pathlib import Path

from configuration import Config, config


# =============================================================================
# SINGLETON & CLASS
# =============================================================================

class TestConfigClass:
    def test_config_singleton_exists(self):
        assert config is not None
        assert isinstance(config, Config)

    def test_instantiable(self):
        c = Config()
        assert isinstance(c, Config)


# =============================================================================
# LLM PROPERTIES
# =============================================================================

class TestLLMProperties:
    def test_llm_provider(self):
        c = Config()
        assert isinstance(c.LLM_PROVIDER, str)
        assert len(c.LLM_PROVIDER) > 0

    def test_openai_api_key(self):
        c = Config()
        # Could be None or string
        assert c.OPENAI_API_KEY is None or isinstance(c.OPENAI_API_KEY, str)

    def test_anthropic_api_key(self):
        c = Config()
        assert c.ANTHROPIC_API_KEY is None or isinstance(c.ANTHROPIC_API_KEY, str)

    def test_google_api_key(self):
        c = Config()
        assert c.GOOGLE_API_KEY is None or isinstance(c.GOOGLE_API_KEY, str)

    def test_deepseek_api_key(self):
        c = Config()
        assert c.DEEPSEEK_API_KEY is None or isinstance(c.DEEPSEEK_API_KEY, str)

    def test_gemini_model(self):
        c = Config()
        assert isinstance(c.GEMINI_MODEL, str)

    def test_openai_model(self):
        c = Config()
        assert isinstance(c.OPENAI_MODEL, str)

    def test_anthropic_model(self):
        c = Config()
        assert isinstance(c.ANTHROPIC_MODEL, str)


# =============================================================================
# STOCKFISH PROPERTIES
# =============================================================================

class TestStockfishProperties:
    def test_stockfish_path(self):
        c = Config()
        assert isinstance(c.STOCKFISH_PATH, str)

    def test_stockfish_depth(self):
        c = Config()
        assert isinstance(c.STOCKFISH_DEPTH, int)
        assert c.STOCKFISH_DEPTH > 0

    def test_stockfish_threads(self):
        c = Config()
        assert isinstance(c.STOCKFISH_THREADS, int)
        assert c.STOCKFISH_THREADS >= 1

    def test_stockfish_hash_mb(self):
        c = Config()
        assert isinstance(c.STOCKFISH_HASH_MB, int)
        assert c.STOCKFISH_HASH_MB > 0


# =============================================================================
# GENERATION PROPERTIES
# =============================================================================

class TestGenerationProperties:
    def test_default_style(self):
        c = Config()
        assert isinstance(c.DEFAULT_STYLE, str)

    def test_default_theme(self):
        c = Config()
        assert c.DEFAULT_THEME is None or isinstance(c.DEFAULT_THEME, str)

    def test_default_aggression(self):
        c = Config()
        val = c.DEFAULT_AGGRESSION
        assert isinstance(val, int)
        assert 1 <= val <= 10

    def test_default_chaos(self):
        c = Config()
        val = c.DEFAULT_CHAOS
        assert isinstance(val, int)
        assert 1 <= val <= 10

    def test_default_game_length(self):
        c = Config()
        val = c.DEFAULT_GAME_LENGTH
        assert isinstance(val, int)
        assert val > 0

    def test_default_era(self):
        c = Config()
        assert isinstance(c.DEFAULT_ERA, str)

    def test_default_white(self):
        c = Config()
        assert isinstance(c.DEFAULT_WHITE, str)

    def test_default_black(self):
        c = Config()
        assert isinstance(c.DEFAULT_BLACK, str)


# =============================================================================
# EXPORT PROPERTIES
# =============================================================================

class TestExportProperties:
    def test_export_format(self):
        c = Config()
        assert isinstance(c.EXPORT_FORMAT, str)

    def test_enable_visualization(self):
        c = Config()
        assert isinstance(c.ENABLE_VISUALIZATION, bool)

    def test_output_path(self):
        c = Config()
        assert isinstance(c.OUTPUT_PATH, str)


# =============================================================================
# LOGGING PROPERTIES
# =============================================================================

class TestLoggingProperties:
    def test_log_level(self):
        c = Config()
        assert c.LOG_LEVEL in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

    def test_log_file(self):
        c = Config()
        assert c.LOG_FILE is None or isinstance(c.LOG_FILE, str)


# =============================================================================
# PATH PROPERTIES
# =============================================================================

class TestPathProperties:
    def test_project_root(self):
        c = Config()
        val = c.PROJECT_ROOT
        assert isinstance(val, (str, Path))

    def test_data_dir(self):
        c = Config()
        val = c.DATA_DIR
        assert isinstance(val, (str, Path))

    def test_engines_dir(self):
        c = Config()
        val = c.ENGINES_DIR
        assert isinstance(val, (str, Path))

    def test_export_dir(self):
        c = Config()
        val = c.EXPORT_DIR
        assert isinstance(val, (str, Path))
