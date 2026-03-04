"""
Comprehensive tests for config_manager.py

Covers:
- ConfigValidationError
- Validation helpers (_check_range, _check_positive, _check_non_negative, _check_choice)
- validate_config (valid + invalid combos)
- 8 SUPPORTED_* constants
- All dataclasses: LLMConfig, StockfishConfig, GenerationConfig, AestheticsConfig,
  PromptsConfig, ExportConfig, BenchmarkQualityWeights, BenchmarksConfig,
  LoggingConfig, RetryConfig, ParallelConfig, AdvancedConfig, CaissaConfig
- _deep_merge, _apply_env_overrides, load_config, config_to_dict, reload_config
"""

import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from config_manager import (
    ConfigValidationError,
    _check_range,
    _check_positive,
    _check_non_negative,
    _check_choice,
    validate_config,
    _deep_merge,
    load_config,
    config_to_dict,
    reload_config,
    SUPPORTED_PROVIDERS,
    SUPPORTED_EXPORT_FORMATS,
    SUPPORTED_LOG_LEVELS,
    SUPPORTED_EVAL_MODES,
    SUPPORTED_RETRY_STRATEGIES,
    SUPPORTED_COMMENTARY_STYLES,
    SUPPORTED_DIFFICULTIES,
    SUPPORTED_BIASES,
    LLMConfig,
    StockfishConfig,
    GenerationConfig,
    AestheticsConfig,
    PromptsConfig,
    ExportConfig,
    BenchmarkQualityWeights,
    BenchmarksConfig,
    LoggingConfig,
    RetryConfig,
    ParallelConfig,
    AdvancedConfig,
    CaissaConfig,
)


# =============================================================================
# SUPPORTED CONSTANTS
# =============================================================================

class TestSupportedConstants:
    def test_providers(self):
        assert "openai" in SUPPORTED_PROVIDERS
        assert "anthropic" in SUPPORTED_PROVIDERS
        assert "gemini" in SUPPORTED_PROVIDERS
        assert "deepseek" in SUPPORTED_PROVIDERS
        assert "ollama" in SUPPORTED_PROVIDERS
        assert "azure" in SUPPORTED_PROVIDERS
        assert "mock" in SUPPORTED_PROVIDERS

    def test_export_formats(self):
        assert "pgn" in SUPPORTED_EXPORT_FORMATS
        assert "json" in SUPPORTED_EXPORT_FORMATS
        assert "html" in SUPPORTED_EXPORT_FORMATS
        assert "markdown" in SUPPORTED_EXPORT_FORMATS
        assert "export_all" in SUPPORTED_EXPORT_FORMATS

    def test_log_levels(self):
        for lvl in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            assert lvl in SUPPORTED_LOG_LEVELS

    def test_eval_modes(self):
        assert "hybrid" in SUPPORTED_EVAL_MODES
        assert "stockfish" in SUPPORTED_EVAL_MODES
        assert "aesthetic" in SUPPORTED_EVAL_MODES

    def test_retry_strategies(self):
        assert "exponential" in SUPPORTED_RETRY_STRATEGIES
        assert "linear" in SUPPORTED_RETRY_STRATEGIES
        assert "none" in SUPPORTED_RETRY_STRATEGIES

    def test_commentary_styles(self):
        assert "analytical" in SUPPORTED_COMMENTARY_STYLES
        assert "poetic" in SUPPORTED_COMMENTARY_STYLES

    def test_difficulties(self):
        assert "beginner" in SUPPORTED_DIFFICULTIES
        assert "grandmaster" in SUPPORTED_DIFFICULTIES

    def test_biases(self):
        assert SUPPORTED_BIASES == {"white", "black", "draw", "random", "neutral"}


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

class TestCheckRange:
    def test_in_range(self):
        errors = []
        _check_range(errors, "sec", "f", 5, 1, 10)
        assert len(errors) == 0

    def test_at_boundary(self):
        errors = []
        _check_range(errors, "sec", "f", 1, 1, 10)
        assert len(errors) == 0
        _check_range(errors, "sec", "f", 10, 1, 10)
        assert len(errors) == 0

    def test_out_of_range_low(self):
        errors = []
        _check_range(errors, "sec", "f", 0, 1, 10)
        assert len(errors) == 1
        assert "sec.f" in errors[0]

    def test_out_of_range_high(self):
        errors = []
        _check_range(errors, "sec", "f", 11, 1, 10)
        assert len(errors) == 1


class TestCheckPositive:
    def test_positive(self):
        errors = []
        _check_positive(errors, "s", "f", 1)
        assert len(errors) == 0

    def test_zero_fails(self):
        errors = []
        _check_positive(errors, "s", "f", 0)
        assert len(errors) == 1

    def test_negative_fails(self):
        errors = []
        _check_positive(errors, "s", "f", -5)
        assert len(errors) == 1


class TestCheckNonNegative:
    def test_positive(self):
        errors = []
        _check_non_negative(errors, "s", "f", 1)
        assert len(errors) == 0

    def test_zero_passes(self):
        errors = []
        _check_non_negative(errors, "s", "f", 0)
        assert len(errors) == 0

    def test_negative_fails(self):
        errors = []
        _check_non_negative(errors, "s", "f", -1)
        assert len(errors) == 1


class TestCheckChoice:
    def test_valid(self):
        errors = []
        _check_choice(errors, "s", "f", "a", {"a", "b", "c"})
        assert len(errors) == 0

    def test_invalid(self):
        errors = []
        _check_choice(errors, "s", "f", "z", {"a", "b"})
        assert len(errors) == 1
        assert "must be one of" in errors[0]


# =============================================================================
# CONFIG VALIDATION ERROR
# =============================================================================

class TestConfigValidationError:
    def test_stores_errors(self):
        err = ConfigValidationError(["err1", "err2"])
        assert err.errors == ["err1", "err2"]
        assert "err1" in str(err)
        assert "err2" in str(err)

    def test_inherits_exception(self):
        assert issubclass(ConfigValidationError, Exception)


# =============================================================================
# DATACLASS DEFAULTS
# =============================================================================

class TestLLMConfig:
    def test_defaults(self):
        cfg = LLMConfig()
        assert cfg.provider == "gemini"
        assert cfg.temperature == 0.8
        assert cfg.max_tokens == 4096
        assert cfg.top_p == 1.0
        assert cfg.openai_model == "gpt-4o"
        assert cfg.anthropic_model == "claude-3-5-sonnet-20241022"
        assert cfg.gemini_model == "gemini-2.5-pro"
        assert cfg.deepseek_model == "deepseek-chat"

    def test_custom(self):
        cfg = LLMConfig(provider="openai", temperature=0.5, max_tokens=512)
        assert cfg.provider == "openai"
        assert cfg.temperature == 0.5


class TestStockfishConfig:
    def test_defaults(self):
        cfg = StockfishConfig()
        assert cfg.depth == 15
        assert cfg.threads == 1
        assert cfg.hash_mb == 64
        assert cfg.time_limit == 0.1
        assert cfg.blunder_threshold == 300
        assert cfg.sacrifice_margin == 100
        assert cfg.enabled is True


class TestGenerationConfig:
    def test_defaults(self):
        cfg = GenerationConfig()
        assert cfg.style == "tal"
        assert cfg.era == "romantic"
        assert cfg.aggression == 7
        assert cfg.chaos == 5
        assert cfg.depth == 40
        assert cfg.bias == "neutral"
        assert cfg.difficulty == "intermediate"
        assert cfg.target_beauty_score == 70.0
        assert cfg.include_annotations is True


class TestAestheticsConfig:
    def test_defaults(self):
        cfg = AestheticsConfig()
        assert cfg.sacrifice_bonus == 15.0
        assert cfg.quiet_killer_bonus == 20.0
        assert cfg.evaluation_mode == "hybrid"
        assert cfg.enable_style_blending is False
        assert cfg.blend_styles == {}


class TestPromptsConfig:
    def test_defaults(self):
        cfg = PromptsConfig()
        assert cfg.enable_personalities is True
        assert cfg.commentary_style == "analytical"
        assert cfg.opening_book_depth == 6
        assert cfg.custom_constraints == []


class TestExportConfig:
    def test_defaults(self):
        cfg = ExportConfig()
        assert cfg.format == "pgn"
        assert cfg.output_path == "game.pgn"
        assert cfg.pretty_pgn is True
        assert cfg.max_line_width == 80
        assert cfg.enable_visualization is True


class TestBenchmarkQualityWeights:
    def test_defaults_sum_to_one(self):
        w = BenchmarkQualityWeights()
        total = w.legality + w.tactical + w.aesthetic + w.structural
        assert abs(total - 1.0) < 1e-9

    def test_individual_defaults(self):
        w = BenchmarkQualityWeights()
        assert w.legality == 0.30
        assert w.tactical == 0.25
        assert w.aesthetic == 0.25
        assert w.structural == 0.20


class TestBenchmarksConfig:
    def test_defaults(self):
        cfg = BenchmarksConfig()
        assert cfg.default_runs == 5
        assert cfg.save_history is True
        assert cfg.regression_threshold == 0.15
        assert isinstance(cfg.quality_weights, BenchmarkQualityWeights)


class TestLoggingConfig:
    def test_defaults(self):
        cfg = LoggingConfig()
        assert cfg.level == "INFO"
        assert cfg.max_bytes == 10_485_760
        assert cfg.backup_count == 3
        assert cfg.verbosity == "normal"


class TestRetryConfig:
    def test_defaults(self):
        cfg = RetryConfig()
        assert cfg.strategy == "exponential"
        assert cfg.max_retries == 3
        assert cfg.base_delay == 1.0
        assert cfg.max_delay == 30.0
        assert cfg.jitter == 0.1


class TestParallelConfig:
    def test_defaults(self):
        cfg = ParallelConfig()
        assert cfg.enabled is False
        assert cfg.max_workers == 4
        assert cfg.fail_fast is False


class TestAdvancedConfig:
    def test_defaults(self):
        cfg = AdvancedConfig()
        assert isinstance(cfg.retry, RetryConfig)
        assert isinstance(cfg.parallel, ParallelConfig)
        assert cfg.enable_move_cache is True
        assert cfg.track_stats is True
        assert cfg.stats_file == ".caissa_stats.json"


class TestCaissaConfig:
    def test_defaults(self):
        cfg = CaissaConfig()
        assert isinstance(cfg.llm, LLMConfig)
        assert isinstance(cfg.stockfish, StockfishConfig)
        assert isinstance(cfg.generation, GenerationConfig)
        assert isinstance(cfg.aesthetics, AestheticsConfig)
        assert isinstance(cfg.prompts, PromptsConfig)
        assert isinstance(cfg.export, ExportConfig)
        assert isinstance(cfg.benchmarks, BenchmarksConfig)
        assert isinstance(cfg.logging, LoggingConfig)
        assert isinstance(cfg.advanced, AdvancedConfig)
        assert isinstance(cfg.project_root, Path)
        assert isinstance(cfg.data_dir, Path)

    def test_nine_subsections(self):
        """Ensure all 9 config subsections are present."""
        cfg = CaissaConfig()
        sections = ["llm", "stockfish", "generation", "aesthetics",
                     "prompts", "export", "benchmarks", "logging", "advanced"]
        for section in sections:
            assert hasattr(cfg, section)


# =============================================================================
# VALIDATE_CONFIG
# =============================================================================

class TestValidateConfig:
    def test_valid_defaults(self):
        cfg = CaissaConfig()
        # Should not raise
        validate_config(cfg)

    def test_invalid_provider(self):
        cfg = CaissaConfig()
        cfg.llm = LLMConfig(provider="invalid_xyz")
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(cfg)
        assert any("provider" in e for e in exc_info.value.errors)

    def test_temperature_out_of_range(self):
        cfg = CaissaConfig()
        cfg.llm = LLMConfig(temperature=3.0)
        with pytest.raises(ConfigValidationError):
            validate_config(cfg)

    def test_negative_max_tokens(self):
        cfg = CaissaConfig()
        cfg.llm = LLMConfig(max_tokens=-1)
        with pytest.raises(ConfigValidationError):
            validate_config(cfg)

    def test_stockfish_depth_out_of_range(self):
        cfg = CaissaConfig()
        cfg.stockfish = StockfishConfig(depth=100)
        with pytest.raises(ConfigValidationError):
            validate_config(cfg)

    def test_generation_aggression_out_of_range(self):
        cfg = CaissaConfig()
        cfg.generation = GenerationConfig(aggression=0)
        with pytest.raises(ConfigValidationError):
            validate_config(cfg)

    def test_generation_depth_out_of_range(self):
        cfg = CaissaConfig()
        cfg.generation = GenerationConfig(depth=5)  # min is 10
        with pytest.raises(ConfigValidationError):
            validate_config(cfg)

    def test_invalid_bias(self):
        cfg = CaissaConfig()
        cfg.generation = GenerationConfig(bias="blue")
        with pytest.raises(ConfigValidationError):
            validate_config(cfg)

    def test_negative_aesthetic_bonus(self):
        cfg = CaissaConfig()
        cfg.aesthetics = AestheticsConfig(sacrifice_bonus=-5.0)
        with pytest.raises(ConfigValidationError):
            validate_config(cfg)

    def test_invalid_eval_mode(self):
        cfg = CaissaConfig()
        cfg.aesthetics = AestheticsConfig(evaluation_mode="random")
        with pytest.raises(ConfigValidationError):
            validate_config(cfg)

    def test_invalid_export_format(self):
        cfg = CaissaConfig()
        cfg.export = ExportConfig(format="pdf")
        with pytest.raises(ConfigValidationError):
            validate_config(cfg)

    def test_zero_max_line_width(self):
        cfg = CaissaConfig()
        cfg.export = ExportConfig(max_line_width=0)
        with pytest.raises(ConfigValidationError):
            validate_config(cfg)

    def test_invalid_commentary_style(self):
        cfg = CaissaConfig()
        cfg.prompts = PromptsConfig(commentary_style="silly")
        with pytest.raises(ConfigValidationError):
            validate_config(cfg)

    def test_quality_weights_sum(self):
        cfg = CaissaConfig()
        cfg.benchmarks = BenchmarksConfig(
            quality_weights=BenchmarkQualityWeights(
                legality=0.5, tactical=0.5, aesthetic=0.5, structural=0.5
            )
        )
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(cfg)
        assert any("quality_weights" in e for e in exc_info.value.errors)

    def test_invalid_retry_strategy(self):
        cfg = CaissaConfig()
        cfg.advanced = AdvancedConfig(retry=RetryConfig(strategy="random"))
        with pytest.raises(ConfigValidationError):
            validate_config(cfg)

    def test_retry_max_retries_out_of_range(self):
        cfg = CaissaConfig()
        cfg.advanced = AdvancedConfig(retry=RetryConfig(max_retries=50))
        with pytest.raises(ConfigValidationError):
            validate_config(cfg)

    def test_parallel_max_workers_out_of_range(self):
        cfg = CaissaConfig()
        cfg.advanced = AdvancedConfig(parallel=ParallelConfig(max_workers=100))
        with pytest.raises(ConfigValidationError):
            validate_config(cfg)

    def test_invalid_log_level(self):
        cfg = CaissaConfig()
        cfg.logging = LoggingConfig(level="TRACE")
        with pytest.raises(ConfigValidationError):
            validate_config(cfg)

    def test_multiple_errors_collected(self):
        cfg = CaissaConfig()
        cfg.llm = LLMConfig(provider="bad", temperature=99.0, max_tokens=-1)
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_config(cfg)
        assert len(exc_info.value.errors) >= 3


# =============================================================================
# DEEP MERGE
# =============================================================================

class TestDeepMerge:
    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"llm": {"provider": "gemini", "temp": 0.8}}
        override = {"llm": {"provider": "openai"}}
        result = _deep_merge(base, override)
        assert result["llm"]["provider"] == "openai"
        assert result["llm"]["temp"] == 0.8

    def test_empty_override(self):
        base = {"a": 1}
        result = _deep_merge(base, {})
        assert result == {"a": 1}

    def test_empty_base(self):
        result = _deep_merge({}, {"a": 1})
        assert result == {"a": 1}

    def test_base_not_mutated(self):
        base = {"a": {"b": 1}}
        _deep_merge(base, {"a": {"b": 2}})
        assert base["a"]["b"] == 1


# =============================================================================
# CONFIG_TO_DICT
# =============================================================================

class TestConfigToDict:
    def test_returns_dict(self):
        cfg = CaissaConfig()
        d = config_to_dict(cfg)
        assert isinstance(d, dict)

    def test_has_all_sections(self):
        cfg = CaissaConfig()
        d = config_to_dict(cfg)
        for section in ("llm", "stockfish", "generation", "aesthetics",
                        "prompts", "export", "benchmarks", "logging", "advanced"):
            assert section in d

    def test_path_converted_to_string(self):
        cfg = CaissaConfig()
        d = config_to_dict(cfg)
        assert isinstance(d["project_root"], str)
        assert isinstance(d["data_dir"], str)

    def test_nested_dataclass_converted(self):
        cfg = CaissaConfig()
        d = config_to_dict(cfg)
        assert isinstance(d["advanced"]["retry"], dict)
        assert d["advanced"]["retry"]["strategy"] == "exponential"

    def test_roundtrip_values(self):
        cfg = CaissaConfig()
        d = config_to_dict(cfg)
        assert d["llm"]["provider"] == "gemini"
        assert d["stockfish"]["depth"] == 15
        assert d["generation"]["aggression"] == 7


# =============================================================================
# LOAD_CONFIG (integration — using nonexistent files returns defaults)
# =============================================================================

class TestLoadConfig:
    def test_loads_default_when_no_file(self, tmp_path):
        """Loading from a nonexistent file should fall back to defaults."""
        fake_config = str(tmp_path / "nonexistent.yaml")
        fake_local = str(tmp_path / "nonexistent.local.yaml")
        cfg = load_config(config_path=fake_config, local_path=fake_local)
        assert isinstance(cfg, CaissaConfig)
        assert cfg.llm.provider == "gemini"

    def test_loads_from_json(self, tmp_path):
        """Loading from a JSON file should work."""
        config_data = {
            "llm": {"provider": "openai", "temperature": 0.5},
            "generation": {"style": "morphy"},
        }
        json_file = tmp_path / "test_config.json"
        json_file.write_text(json.dumps(config_data), encoding="utf-8")
        # Clear all env vars so nothing overrides JSON values
        with patch.dict(os.environ, {}, clear=True):
            cfg = load_config(
                config_path=str(json_file),
                local_path=str(tmp_path / "nonexistent.local.json"),
            )
        assert cfg.llm.provider == "openai"
        assert cfg.llm.temperature == 0.5
        assert cfg.generation.style == "morphy"

    def test_cli_overrides(self, tmp_path):
        fake = str(tmp_path / "empty.json")
        Path(fake).write_text("{}", encoding="utf-8")
        cfg = load_config(
            config_path=fake,
            local_path=str(tmp_path / "nope.json"),
            cli_overrides={"llm": {"provider": "anthropic"}},
        )
        assert cfg.llm.provider == "anthropic"

    def test_env_override(self, tmp_path):
        fake = str(tmp_path / "e.json")
        Path(fake).write_text("{}", encoding="utf-8")
        with patch.dict(os.environ, {"LLM_PROVIDER": "deepseek"}):
            cfg = load_config(
                config_path=fake,
                local_path=str(tmp_path / "x.json"),
            )
            assert cfg.llm.provider == "deepseek"


# =============================================================================
# RELOAD_CONFIG
# =============================================================================

class TestReloadConfig:
    def test_reload_returns_config(self, tmp_path):
        fake = str(tmp_path / "r.json")
        Path(fake).write_text("{}", encoding="utf-8")
        cfg = reload_config(
            config_path=fake,
            local_path=str(tmp_path / "nope.json"),
        )
        assert isinstance(cfg, CaissaConfig)
