"""
Comprehensive tests for core/provider_factory.py

Covers:
- get_supported_providers
- create_provider: unknown provider, missing API keys, each provider branch
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from core.provider_factory import create_provider, get_supported_providers


# =============================================================================
# get_supported_providers
# =============================================================================

class TestGetSupportedProviders:
    def test_returns_list(self):
        result = get_supported_providers()
        assert isinstance(result, list)

    def test_correct_providers(self):
        result = get_supported_providers()
        assert set(result) == {"openai", "anthropic", "gemini", "deepseek", "ollama", "azure"}

    def test_count(self):
        assert len(get_supported_providers()) == 6


# =============================================================================
# create_provider – unknown provider
# =============================================================================

class TestCreateProviderUnknown:
    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            create_provider("nonexistent_provider")

    def test_unknown_provider_message(self):
        with pytest.raises(ValueError) as exc_info:
            create_provider("bad_name")
        assert "Supported:" in str(exc_info.value)


# =============================================================================
# create_provider – missing API keys
# =============================================================================

class TestCreateProviderMissingKeys:
    def test_openai_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove any env var, and pass cfg without a real key
            mock_cfg = MagicMock()
            mock_cfg.llm.openai_api_key = None
            mock_cfg.llm.openai_model = "gpt-4o"
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                create_provider("openai", cfg=mock_cfg)

    def test_openai_placeholder_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-..."}, clear=True):
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                create_provider("openai", cfg=None)

    def test_anthropic_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            mock_cfg = MagicMock()
            mock_cfg.llm.anthropic_api_key = None
            mock_cfg.llm.anthropic_model = "claude-3-5-sonnet-20241022"
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                create_provider("anthropic", cfg=mock_cfg)

    def test_gemini_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            mock_cfg = MagicMock()
            mock_cfg.llm.google_api_key = None
            mock_cfg.llm.gemini_model = "gemini-2.5-pro"
            with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
                create_provider("gemini", cfg=mock_cfg)

    def test_gemini_placeholder_key(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "YOUR_GEMINI_API_KEY_HERE"}, clear=True):
            with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
                create_provider("gemini", cfg=None)

    def test_deepseek_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            mock_cfg = MagicMock()
            mock_cfg.llm.deepseek_api_key = None
            mock_cfg.llm.deepseek_model = "deepseek-chat"
            with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
                create_provider("deepseek", cfg=mock_cfg)


# =============================================================================
# create_provider – successful creation with mocked providers
# =============================================================================

class TestCreateProviderSuccess:
    @patch("core.llm_provider.OpenAIProvider")
    def test_openai_creation(self, mock_cls):
        mock_cls.return_value = MagicMock()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-real-key"}, clear=True):
            create_provider("openai", cfg=None)
            mock_cls.assert_called_once_with(api_key="sk-real-key", model="gpt-4o")

    @patch("core.llm_provider.AnthropicProvider")
    def test_anthropic_creation(self, mock_cls):
        mock_cls.return_value = MagicMock()
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "real-key"}, clear=True):
            create_provider("anthropic", cfg=None)
            mock_cls.assert_called_once()

    @patch("core.llm_provider.GoogleGeminiProvider")
    def test_gemini_creation(self, mock_cls):
        mock_cls.return_value = MagicMock()
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "real-gemini-key"}, clear=True):
            create_provider("gemini", cfg=None)
            mock_cls.assert_called_once()

    @patch("core.llm_provider.OpenAIProvider")
    def test_deepseek_uses_openai_provider(self, mock_cls):
        mock_cls.return_value = MagicMock()
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "ds-key"}, clear=True):
            create_provider("deepseek", cfg=None)
            mock_cls.assert_called_once_with(
                api_key="ds-key",
                model="deepseek-chat",
                base_url="https://api.deepseek.com",
            )

    @patch("core.llm_provider.OllamaProvider")
    def test_ollama_creation_no_key_needed(self, mock_cls):
        mock_cls.return_value = MagicMock()
        with patch.dict(os.environ, {}, clear=True):
            mock_cfg = MagicMock()
            mock_cfg.llm.ollama_model = "llama2"
            mock_cfg.llm.ollama_base_url = "http://localhost:11434"
            create_provider("ollama", cfg=mock_cfg)
            mock_cls.assert_called_once()

    @patch("core.llm_provider.AzureOpenAIProvider")
    def test_azure_creation(self, mock_cls):
        mock_cls.return_value = MagicMock()
        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "az-key",
            "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
        }, clear=True):
            create_provider("azure", cfg=None)
            mock_cls.assert_called_once()


# =============================================================================
# create_provider – name normalization
# =============================================================================

class TestProviderNameNormalization:
    @patch("core.llm_provider.OllamaProvider")
    def test_uppercase_name(self, mock_cls):
        mock_cls.return_value = MagicMock()
        with patch.dict(os.environ, {}, clear=True):
            create_provider("OLLAMA", cfg=MagicMock())
            mock_cls.assert_called_once()

    @patch("core.llm_provider.OllamaProvider")
    def test_whitespace_stripped(self, mock_cls):
        mock_cls.return_value = MagicMock()
        with patch.dict(os.environ, {}, clear=True):
            create_provider("  ollama  ", cfg=MagicMock())
            mock_cls.assert_called_once()


# =============================================================================
# create_provider – config resolution
# =============================================================================

class TestConfigResolution:
    @patch("core.llm_provider.GoogleGeminiProvider")
    def test_env_takes_precedence_over_config(self, mock_cls):
        mock_cls.return_value = MagicMock()
        mock_cfg = MagicMock()
        mock_cfg.llm.google_api_key = "config-key"
        mock_cfg.llm.gemini_model = "gemini-pro"

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "env-key"}, clear=True):
            create_provider("gemini", cfg=mock_cfg)
            # env key should take precedence
            call_args = mock_cls.call_args
            assert call_args[1]["api_key"] == "env-key" or call_args[0][0] == "env-key"

    @patch("core.llm_provider.GoogleGeminiProvider")
    def test_config_fallback(self, mock_cls):
        mock_cls.return_value = MagicMock()
        mock_cfg = MagicMock()
        mock_cfg.llm.google_api_key = "config-value"
        mock_cfg.llm.gemini_model = "gemini-2.5-pro"

        with patch.dict(os.environ, {}, clear=True):
            create_provider("gemini", cfg=mock_cfg)
            mock_cls.assert_called_once()
