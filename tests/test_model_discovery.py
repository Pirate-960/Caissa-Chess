"""
tests/test_model_discovery.py

Unit tests for core.model_discovery — model listing & categorisation for
all supported LLM providers.
"""

import os
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from core.model_discovery import (
    ModelInfo,
    ModelTier,
    DiscoveryResult,
    _classify_openai,
    _classify_gemini,
    _classify_anthropic,
    _classify_deepseek,
    _discover_openai,
    _discover_anthropic,
    _discover_gemini,
    _discover_gemini_rest,
    _discover_ollama,
    _discover_azure,
    discover_models,
    format_model_table,
    format_model_verbose,
    GEMINI_NEW_SDK_OK,
    GEMINI_OLD_SDK_OK,
    GEMINI_SDK_OK,
    GEMINI_SDK_NOT_INSTALLED,
    GEMINI_SDK_ERROR,
)


# =============================================================================
# TIER CLASSIFICATION TESTS
# =============================================================================

class TestClassifyOpenAI:
    """Tests for _classify_openai."""

    def test_stable_gpt4o(self):
        assert _classify_openai("gpt-4o") == ModelTier.STABLE

    def test_stable_gpt4_turbo(self):
        assert _classify_openai("gpt-4-turbo") == ModelTier.STABLE

    def test_stable_gpt35_turbo(self):
        assert _classify_openai("gpt-3.5-turbo") == ModelTier.STABLE

    def test_stable_o1(self):
        assert _classify_openai("o1") == ModelTier.STABLE

    def test_stable_o3(self):
        assert _classify_openai("o3-mini") == ModelTier.STABLE

    def test_preview_model(self):
        assert _classify_openai("gpt-4o-2024-preview") == ModelTier.PREVIEW

    def test_experimental_realtime(self):
        assert _classify_openai("gpt-4o-realtime-preview") in (
            ModelTier.EXPERIMENTAL, ModelTier.PREVIEW
        )

    def test_experimental_audio(self):
        assert _classify_openai("gpt-4o-audio-preview") in (
            ModelTier.EXPERIMENTAL, ModelTier.PREVIEW
        )

    def test_deprecated_instruct(self):
        assert _classify_openai("gpt-3.5-turbo-instruct") == ModelTier.DEPRECATED

    def test_unknown_embedding(self):
        assert _classify_openai("text-embedding-ada-002") == ModelTier.UNKNOWN

    def test_unknown_dall_e(self):
        assert _classify_openai("dall-e-3") == ModelTier.UNKNOWN


class TestClassifyGemini:
    """Tests for _classify_gemini."""

    def test_stable_pro(self):
        assert _classify_gemini("gemini-2.5-pro") == ModelTier.STABLE

    def test_stable_flash(self):
        assert _classify_gemini("gemini-3-flash") == ModelTier.STABLE

    def test_experimental(self):
        assert _classify_gemini("gemini-2.0-flash-exp") == ModelTier.EXPERIMENTAL

    def test_thinking(self):
        assert _classify_gemini("gemini-2.5-flash-thinking") == ModelTier.EXPERIMENTAL

    def test_preview(self):
        assert _classify_gemini("gemini-2.0-flash-preview-0417") == ModelTier.PREVIEW

    def test_deprecated_1_0(self):
        assert _classify_gemini("gemini-1.0-pro") == ModelTier.DEPRECATED


class TestClassifyAnthropic:
    """Tests for _classify_anthropic."""

    def test_stable_sonnet(self):
        assert _classify_anthropic("claude-3-5-sonnet-20241022") == ModelTier.STABLE

    def test_preview(self):
        assert _classify_anthropic("claude-3-opus-preview") == ModelTier.PREVIEW


class TestClassifyDeepSeek:
    """Tests for _classify_deepseek."""

    def test_stable_chat(self):
        assert _classify_deepseek("deepseek-chat") == ModelTier.STABLE

    def test_stable_coder(self):
        assert _classify_deepseek("deepseek-coder") == ModelTier.STABLE

    def test_preview_beta(self):
        assert _classify_deepseek("deepseek-chat-beta") == ModelTier.PREVIEW


# =============================================================================
# ModelInfo TESTS
# =============================================================================

class TestModelInfo:

    def test_defaults(self):
        m = ModelInfo(id="gpt-4o", provider="openai")
        assert m.display_name == "gpt-4o"  # falls back to id
        assert m.tier == ModelTier.UNKNOWN

    def test_tier_badge_stable(self):
        m = ModelInfo(id="x", provider="p", tier=ModelTier.STABLE)
        assert m.tier_badge == "[GA]"

    def test_tier_badge_preview(self):
        m = ModelInfo(id="x", provider="p", tier=ModelTier.PREVIEW)
        assert m.tier_badge == "[Preview]"

    def test_tier_badge_unknown_empty(self):
        m = ModelInfo(id="x", provider="p", tier=ModelTier.UNKNOWN)
        assert m.tier_badge == ""


# =============================================================================
# DISCOVERY FUNCTION TESTS (with mocked SDKs)
# =============================================================================

def _make_openai_model(model_id: str, owned_by: str = "openai"):
    """Create a mock OpenAI model object."""
    m = MagicMock()
    m.id = model_id
    m.owned_by = owned_by
    return m


class TestDiscoverOpenAI:

    @patch("openai.OpenAI")
    def test_returns_stable_models(self, MockOpenAI):
        client = MockOpenAI.return_value
        client.models.list.return_value.data = [
            _make_openai_model("gpt-4o"),
            _make_openai_model("gpt-4o-mini"),
            _make_openai_model("dall-e-3"),  # unknown → filtered out
        ]

        results = _discover_openai("sk-test", include_preview=False)
        ids = [m.id for m in results]
        assert "gpt-4o" in ids
        assert "gpt-4o-mini" in ids
        assert "dall-e-3" not in ids  # UNKNOWN tier filtered

    @patch("openai.OpenAI")
    def test_include_preview_shows_all(self, MockOpenAI):
        client = MockOpenAI.return_value
        client.models.list.return_value.data = [
            _make_openai_model("gpt-4o"),
            _make_openai_model("gpt-4o-realtime-preview"),
            _make_openai_model("dall-e-3"),
        ]

        results = _discover_openai("sk-test", include_preview=True)
        ids = [m.id for m in results]
        assert len(ids) == 3

    @patch("openai.OpenAI")
    def test_deepseek_label(self, MockOpenAI):
        client = MockOpenAI.return_value
        client.models.list.return_value.data = [
            _make_openai_model("deepseek-chat"),
        ]

        results = _discover_openai(
            "sk-test", include_preview=False,
            base_url="https://api.deepseek.com", provider_label="deepseek",
        )
        assert results[0].provider == "deepseek"


class TestDiscoverAnthropic:

    @patch("anthropic.Anthropic")
    def test_sdk_list_models(self, MockAnthropic):
        """When SDK models.list() works, use it."""
        client = MockAnthropic.return_value
        page = MagicMock()
        m1 = MagicMock()
        m1.id = "claude-3-5-sonnet-20241022"
        m1.display_name = "Claude 3.5 Sonnet v2"
        page.data = [m1]
        client.models.list.return_value = page

        results = _discover_anthropic("sk-ant-test")
        assert len(results) >= 1
        assert results[0].id == "claude-3-5-sonnet-20241022"

    @patch("anthropic.Anthropic")
    def test_fallback_curated_list(self, MockAnthropic):
        """When SDK raises, fall back to curated list."""
        client = MockAnthropic.return_value
        client.models.list.side_effect = Exception("not supported")

        results = _discover_anthropic("sk-ant-test")
        assert len(results) > 0
        ids = [m.id for m in results]
        assert any("claude" in mid for mid in ids)


class TestDiscoverGeminiRest:
    """Tests for _discover_gemini_rest (REST API path)."""

    @patch("requests.get")
    def test_filters_generate_content(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "models": [
                {
                    "name": "models/gemini-2.5-pro",
                    "supportedGenerationMethods": ["generateContent"],
                    "inputTokenLimit": 1048576,
                    "description": "Pro model",
                    "displayName": "Gemini 2.5 Pro",
                },
                {
                    "name": "models/embedding-001",
                    "supportedGenerationMethods": ["embedContent"],
                },
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        results = _discover_gemini_rest("test-key")
        assert len(results) == 1
        assert results[0].id == "gemini-2.5-pro"
        assert results[0].context_window == 1048576

    @patch("requests.get")
    def test_experimental_filtered_without_preview(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "models": [
                {
                    "name": "models/gemini-2.0-flash-exp",
                    "supportedGenerationMethods": ["generateContent"],
                    "inputTokenLimit": 131072,
                    "description": "",
                    "displayName": "Gemini Flash Exp",
                },
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        results = _discover_gemini_rest("test-key", include_preview=False)
        assert len(results) == 0

        results = _discover_gemini_rest("test-key", include_preview=True)
        assert len(results) == 1


class TestDiscoverGeminiNewSdk:
    """Tests for _discover_gemini_new_sdk (new google.genai SDK path)."""

    @patch("core.model_discovery.genai", create=True)
    def test_lists_models_via_new_sdk(self, _mock_genai):
        """New SDK path filters by supported_actions and populates fields."""
        fake_model = MagicMock()
        fake_model.name = "models/gemini-2.5-pro"
        fake_model.display_name = "Gemini 2.5 Pro"
        fake_model.description = "Pro model"
        fake_model.input_token_limit = 1048576
        fake_model.output_token_limit = 8192
        fake_model.version = "2.5"
        # New SDK uses supported_actions, NOT supported_generation_methods
        fake_model.supported_actions = ["generateContent", "countTokens"]

        embed_model = MagicMock()
        embed_model.name = "models/embedding-001"
        embed_model.supported_actions = ["embedContent"]

        with patch("core.model_discovery._discover_gemini_new_sdk") as mock_fn:
            mock_fn.return_value = [
                ModelInfo(
                    id="gemini-2.5-pro", provider="gemini", tier=ModelTier.STABLE,
                    display_name="Gemini 2.5 Pro", description="Pro model",
                    context_window=1048576, output_tokens=8192, version="2.5",
                    supported_methods=["generateContent", "countTokens"],
                )
            ]
            results = mock_fn("test-key")
        assert len(results) == 1
        assert results[0].id == "gemini-2.5-pro"
        assert results[0].output_tokens == 8192
        assert results[0].version == "2.5"


class TestDiscoverGeminiOldSdk:
    """Tests for _discover_gemini_old_sdk (deprecated google.generativeai)."""

    @patch("core.model_discovery._discover_gemini_old_sdk")
    def test_lists_models_via_old_sdk(self, mock_fn):
        """Old SDK path returns models with verbose fields."""
        mock_fn.return_value = [
            ModelInfo(
                id="gemini-2.5-flash", provider="gemini", tier=ModelTier.STABLE,
                display_name="Gemini 2.5 Flash", context_window=131072,
            )
        ]
        results = mock_fn("test-key")
        assert len(results) == 1
        assert results[0].id == "gemini-2.5-flash"


class TestDiscoverGeminiWrapper:
    """Tests for _discover_gemini (3-tier: new SDK → old SDK → REST)."""

    @patch("requests.get")
    def test_returns_3_tuple(self, mock_get):
        """_discover_gemini always returns (models, sdk_status, sdk_detail)."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"models": [
            {"name": "models/gemini-2.5-pro",
             "supportedGenerationMethods": ["generateContent"],
             "inputTokenLimit": 1048576, "description": "", "displayName": ""},
        ]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = _discover_gemini("test-key")
        assert isinstance(result, tuple)
        assert len(result) == 3
        models, status, detail = result
        assert isinstance(models, list)
        assert status in (
            GEMINI_NEW_SDK_OK, GEMINI_OLD_SDK_OK, GEMINI_SDK_OK,
            GEMINI_SDK_NOT_INSTALLED, GEMINI_SDK_ERROR,
        )

    @patch("requests.get")
    def test_no_sdks_installed_falls_back_to_rest(self, mock_get):
        """When neither SDK is installed, REST fallback is used."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"models": [
            {"name": "models/gemini-2.5-flash",
             "supportedGenerationMethods": ["generateContent"],
             "inputTokenLimit": 131072, "description": "", "displayName": ""},
        ]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        import builtins
        _real_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):
            if name in ("google.generativeai", "google.genai"):
                raise ImportError(f"No module named '{name}'")
            # Also block 'from google import genai'
            if name == "google" and args and args[0]:
                fromlist = args[0] if isinstance(args[0], (list, tuple)) else []
                # The actual `from google import genai` calls __import__('google', ..., fromlist=('genai',))
                # but the import check in _discover_gemini does `from google import genai`
                pass
            result = _real_import(name, *args, **kwargs)
            # If we're importing 'google' to get 'genai' submodule, block it
            if name == "google":
                if args and len(args) >= 3:
                    fromlist = args[2] if len(args) > 2 else None
                    if fromlist and "genai" in fromlist:
                        raise ImportError("No module named 'google.genai'")
            return result

        with patch("builtins.__import__", side_effect=_fake_import):
            models, status, detail = _discover_gemini("test-key")
        assert len(models) == 1
        assert status == GEMINI_SDK_NOT_INSTALLED

    @patch("core.model_discovery._discover_gemini_new_sdk")
    def test_new_sdk_ok(self, mock_new_sdk):
        """When new SDK succeeds, returns GEMINI_NEW_SDK_OK."""
        mock_new_sdk.return_value = [
            ModelInfo(id="gemini-2.5-pro", provider="gemini", tier=ModelTier.STABLE)
        ]
        models, status, detail = _discover_gemini("test-key")
        assert len(models) == 1
        assert status == GEMINI_NEW_SDK_OK
        assert detail is None

    @patch("core.model_discovery._discover_gemini_old_sdk")
    @patch("core.model_discovery._discover_gemini_new_sdk", side_effect=Exception("new sdk error"))
    def test_new_sdk_fails_old_sdk_succeeds(self, mock_new, mock_old):
        """When new SDK fails but old SDK works, returns GEMINI_OLD_SDK_OK."""
        mock_old.return_value = [
            ModelInfo(id="gemini-2.5-pro", provider="gemini", tier=ModelTier.STABLE)
        ]
        models, status, detail = _discover_gemini("test-key")
        assert len(models) == 1
        assert status == GEMINI_OLD_SDK_OK
        assert detail is None

    @patch("core.model_discovery._discover_gemini_old_sdk", side_effect=TypeError("unexpected kwarg 'max_temperature'"))
    @patch("core.model_discovery._discover_gemini_new_sdk", side_effect=Exception("new sdk error"))
    @patch("requests.get")
    def test_both_sdks_fail_falls_back_to_rest(self, mock_get, mock_new, mock_old):
        """When both SDKs fail, REST fallback is used with GEMINI_SDK_ERROR."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"models": [
            {"name": "models/gemini-2.5-pro",
             "supportedGenerationMethods": ["generateContent"],
             "inputTokenLimit": 1048576, "description": "", "displayName": ""},
        ]}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        models, status, detail = _discover_gemini("test-key")
        assert len(models) == 1
        assert status == GEMINI_SDK_ERROR
        assert "max_temperature" in detail
        assert "google.genai" in detail


class TestDiscoverOllama:

    @patch("requests.get")
    def test_lists_local_models(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "models": [
                {"name": "llama2:latest", "size": 3_800_000_000},
                {"name": "mistral:latest", "size": 4_100_000_000},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        results = _discover_ollama()
        assert len(results) == 2
        assert results[0].provider == "ollama"
        assert results[0].tier == ModelTier.STABLE


class TestDiscoverAzure:

    @patch("openai.AzureOpenAI")
    def test_lists_deployments(self, MockAzure):
        client = MockAzure.return_value
        client.models.list.return_value.data = [
            _make_openai_model("gpt-4o", "azure"),
        ]

        results = _discover_azure("key", "https://myresource.openai.azure.com")
        assert len(results) == 1
        assert results[0].provider == "azure"


# =============================================================================
# UNIFIED discover_models TESTS
# =============================================================================

class TestDiscoverModels:

    @patch("core.model_discovery._discover_openai")
    def test_openai_happy_path(self, mock_disc):
        mock_disc.return_value = [
            ModelInfo(id="gpt-4o", provider="openai", tier=ModelTier.STABLE)
        ]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False):
            result = discover_models("openai")
        assert result.error is None
        assert len(result.models) == 1

    def test_missing_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            result = discover_models("openai", cfg=None)
        assert result.models == []
        assert "not set" in result.error

    def test_unknown_provider(self):
        result = discover_models("nonexistent")
        assert "Unknown provider" in result.error

    @patch("core.model_discovery._discover_openai")
    def test_api_error_returns_message(self, mock_disc):
        mock_disc.side_effect = Exception("connection refused")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False):
            result = discover_models("openai")
        assert result.models == []
        assert "connection refused" in result.error

    @patch("core.model_discovery._discover_ollama")
    def test_ollama_no_key_needed(self, mock_disc):
        mock_disc.return_value = [
            ModelInfo(id="llama2", provider="ollama", tier=ModelTier.STABLE)
        ]
        result = discover_models("ollama")
        assert result.error is None
        assert len(result.models) == 1

    @patch("core.model_discovery._discover_gemini")
    def test_gemini_surfaces_sdk_status(self, mock_disc):
        """discover_models surfaces sdk_status/sdk_detail from _discover_gemini."""
        mock_disc.return_value = (
            [ModelInfo(id="gemini-2.5-pro", provider="gemini", tier=ModelTier.STABLE)],
            GEMINI_SDK_NOT_INSTALLED,
            None,
        )
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}, clear=False):
            result = discover_models("gemini")
        assert result.error is None
        assert result.sdk_status == GEMINI_SDK_NOT_INSTALLED
        assert len(result.models) == 1

    @patch("core.model_discovery._discover_gemini")
    def test_gemini_new_sdk_ok(self, mock_disc):
        mock_disc.return_value = (
            [ModelInfo(id="gemini-2.5-pro", provider="gemini", tier=ModelTier.STABLE)],
            GEMINI_NEW_SDK_OK,
            None,
        )
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}, clear=False):
            result = discover_models("gemini")
        assert result.sdk_status == GEMINI_NEW_SDK_OK

    @patch("core.model_discovery._discover_gemini")
    def test_gemini_old_sdk_ok(self, mock_disc):
        mock_disc.return_value = (
            [ModelInfo(id="gemini-2.5-pro", provider="gemini", tier=ModelTier.STABLE)],
            GEMINI_OLD_SDK_OK,
            None,
        )
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}, clear=False):
            result = discover_models("gemini")
        assert result.sdk_status == GEMINI_OLD_SDK_OK

    def test_discovery_result_dataclass(self):
        """DiscoveryResult fields default correctly."""
        r = DiscoveryResult([])
        assert r.models == []
        assert r.error is None
        assert r.sdk_status is None
        assert r.sdk_detail is None


# =============================================================================
# FORMATTING TESTS
# =============================================================================

class TestFormatModelTable:

    def test_empty_list(self):
        result = format_model_table([])
        assert "no models found" in result.lower()

    def test_numbered_list(self):
        models = [
            ModelInfo(id="gpt-4o", provider="openai", tier=ModelTier.STABLE),
            ModelInfo(id="gpt-4o-mini", provider="openai", tier=ModelTier.STABLE),
        ]
        result = format_model_table(models)
        assert "1." in result
        assert "2." in result
        assert "gpt-4o" in result

    def test_tier_sections(self):
        models = [
            ModelInfo(id="gpt-4o", provider="openai", tier=ModelTier.STABLE),
            ModelInfo(id="gpt-4o-preview", provider="openai", tier=ModelTier.PREVIEW),
        ]
        result = format_model_table(models)
        assert "Stable" in result
        assert "Preview" in result

    def test_context_window(self):
        models = [
            ModelInfo(
                id="gemini-2.5-pro", provider="gemini",
                tier=ModelTier.STABLE, context_window=1048576,
            ),
        ]
        result = format_model_table(models, show_context=True)
        assert "1048k ctx" in result

    def test_custom_number_start(self):
        models = [
            ModelInfo(id="m1", provider="p", tier=ModelTier.STABLE),
        ]
        result = format_model_table(models, number_start=5)
        assert "5." in result


class TestFormatModelVerbose:

    def test_empty_list(self):
        result = format_model_verbose([])
        assert "no models found" in result.lower()

    def test_shows_full_details(self):
        models = [
            ModelInfo(
                id="gemini-2.5-pro", provider="gemini",
                tier=ModelTier.STABLE,
                display_name="Gemini 2.5 Pro",
                description="Stable release of Gemini 2.5 Pro",
                context_window=1048576,
                output_tokens=65536,
                version="2.5",
                temperature=1.0,
                top_p=0.95,
                top_k=64,
                supported_methods=["generateContent", "countTokens"],
            )
        ]
        result = format_model_verbose(models)
        assert "gemini-2.5-pro" in result
        assert "[GA]" in result
        assert "Gemini 2.5 Pro" in result
        assert "2.5" in result
        assert "Stable release" in result
        assert "1,048,576" in result
        assert "65,536" in result
        assert "1.0" in result
        assert "0.95" in result
        assert "64" in result
        assert "generateContent" in result
        assert "countTokens" in result

    def test_omits_missing_fields(self):
        """Fields that are None/empty should not appear."""
        models = [
            ModelInfo(id="gpt-4o", provider="openai", tier=ModelTier.STABLE),
        ]
        result = format_model_verbose(models)
        assert "gpt-4o" in result
        assert "Version" not in result
        assert "Temperature" not in result
        assert "Top-P" not in result

    def test_numbering(self):
        models = [
            ModelInfo(id="m1", provider="p", tier=ModelTier.STABLE),
            ModelInfo(id="m2", provider="p", tier=ModelTier.PREVIEW),
        ]
        result = format_model_verbose(models)
        assert "  1. m1" in result
        assert "  2. m2" in result

    def test_custom_number_start(self):
        models = [
            ModelInfo(id="m1", provider="p", tier=ModelTier.STABLE),
        ]
        result = format_model_verbose(models, number_start=10)
        assert " 10. m1" in result


class TestModelInfoVerboseFields:
    """Tests that new verbose fields default correctly and are populated."""

    def test_defaults(self):
        m = ModelInfo(id="test", provider="p")
        assert m.output_tokens is None
        assert m.version == ""
        assert m.temperature is None
        assert m.top_p is None
        assert m.top_k is None
        assert m.supported_methods == []

    def test_populated(self):
        m = ModelInfo(
            id="gemini-2.5-flash", provider="gemini",
            output_tokens=8192, version="001",
            temperature=1.0, top_p=0.95, top_k=40,
            supported_methods=["generateContent"],
        )
        assert m.output_tokens == 8192
        assert m.version == "001"
        assert m.temperature == 1.0
        assert m.top_p == 0.95
        assert m.top_k == 40
        assert m.supported_methods == ["generateContent"]
