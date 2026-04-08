"""Tests for all LLM providers in CAISSA - 26 test methods."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from core.llm_provider import (
    AnthropicProvider,
    AzureOpenAIProvider,
    GoogleGeminiProvider,
    LLMProvider,
    LLMResponse,
    MockProvider,
    OllamaProvider,
    OpenAIProvider,
)


# ---------------------------------------------------------------------------
# OpenAI Provider Tests (4 tests)
# ---------------------------------------------------------------------------
class TestOpenAIProvider(unittest.TestCase):

    def test_openai_init_no_key(self) -> None:
        """Provider should initialise without raising even without an API key."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENAI_API_KEY", None)
            provider = OpenAIProvider(api_key="")
        self.assertIsInstance(provider, LLMProvider)
        self.assertIsNone(provider._client)

    def test_openai_recommended_models(self) -> None:
        """get_recommended_models returns expected model names."""
        provider = OpenAIProvider(api_key="")
        models = provider.get_recommended_models()
        self.assertIsInstance(models, list)
        self.assertIn("gpt-4o", models)
        self.assertIn("gpt-4o-mini", models)
        self.assertIn("o1-preview", models)

    def test_openai_list_models(self) -> None:
        """list_models returns a dict with descriptions."""
        models = OpenAIProvider.list_models()
        self.assertIsInstance(models, dict)
        self.assertIn("gpt-4o", models)
        self.assertIn("gpt-4-turbo", models)
        self.assertTrue(all(isinstance(v, str) for v in models.values()))

    def test_openai_generate_raises_without_key(self) -> None:
        """generate() should raise RuntimeError when no client is initialised."""
        provider = OpenAIProvider(api_key="")
        with self.assertRaises(RuntimeError):
            provider.generate("e4")


# ---------------------------------------------------------------------------
# Anthropic Provider Tests (4 tests)
# ---------------------------------------------------------------------------
class TestAnthropicProvider(unittest.TestCase):

    def test_anthropic_init_no_key(self) -> None:
        """Provider should initialise without raising even without an API key."""
        provider = AnthropicProvider(api_key="")
        self.assertIsInstance(provider, LLMProvider)
        self.assertIsNone(provider._client)

    def test_anthropic_recommended_models(self) -> None:
        """get_recommended_models returns Claude model names."""
        provider = AnthropicProvider(api_key="")
        models = provider.get_recommended_models()
        self.assertIsInstance(models, list)
        self.assertIn("claude-3-5-sonnet-20241022", models)
        self.assertIn("claude-3-opus-20240229", models)

    def test_anthropic_list_models(self) -> None:
        """list_models returns a dict with model descriptions."""
        models = AnthropicProvider.list_models()
        self.assertIsInstance(models, dict)
        self.assertIn("claude-3-haiku-20240307", models)
        self.assertTrue(len(models) >= 3)

    def test_anthropic_generate_raises_without_key(self) -> None:
        """generate() should raise RuntimeError when no client is initialised."""
        provider = AnthropicProvider(api_key="")
        with self.assertRaises(RuntimeError):
            provider.generate("e4")


# ---------------------------------------------------------------------------
# Azure OpenAI Provider Tests (4 tests)
# ---------------------------------------------------------------------------
class TestAzureOpenAIProvider(unittest.TestCase):

    def test_azure_init_no_credentials(self) -> None:
        """Provider should initialise gracefully without credentials."""
        provider = AzureOpenAIProvider(api_key="", endpoint="")
        self.assertIsInstance(provider, LLMProvider)
        self.assertIsNone(provider._client)

    def test_azure_recommended_models(self) -> None:
        """get_recommended_models returns Azure model names."""
        provider = AzureOpenAIProvider(api_key="", endpoint="")
        models = provider.get_recommended_models()
        self.assertIsInstance(models, list)
        self.assertIn("gpt-4o", models)

    def test_azure_list_models(self) -> None:
        """list_models returns a dict with Azure model descriptions."""
        models = AzureOpenAIProvider.list_models()
        self.assertIsInstance(models, dict)
        self.assertIn("gpt-4o", models)
        self.assertTrue(len(models) >= 2)

    def test_azure_generate_raises_without_credentials(self) -> None:
        """generate() should raise RuntimeError when no client is initialised."""
        provider = AzureOpenAIProvider(api_key="", endpoint="")
        with self.assertRaises(RuntimeError):
            provider.generate("Nf3")


# ---------------------------------------------------------------------------
# Google Gemini Provider Tests (4 tests)
# ---------------------------------------------------------------------------
class TestGoogleGeminiProvider(unittest.TestCase):

    def test_gemini_init_no_key(self) -> None:
        """Provider should initialise without raising even without an API key."""
        provider = GoogleGeminiProvider(api_key="")
        self.assertIsInstance(provider, LLMProvider)
        self.assertIsNone(provider._client)

    def test_gemini_recommended_models(self) -> None:
        """get_recommended_models includes Gemini 1.5 and 2.0 models."""
        provider = GoogleGeminiProvider(api_key="")
        models = provider.get_recommended_models()
        self.assertIsInstance(models, list)
        self.assertIn("gemini-1.5-pro", models)
        self.assertIn("gemini-1.5-flash", models)
        self.assertIn("gemini-2.0-flash", models)
        self.assertIn("gemini-2.0-flash-exp", models)

    def test_gemini_list_models(self) -> None:
        """list_models returns a dict with Gemini model descriptions."""
        models = GoogleGeminiProvider.list_models()
        self.assertIsInstance(models, dict)
        self.assertIn("gemini-1.5-pro", models)
        self.assertIn("gemini-2.0-flash", models)
        self.assertTrue(len(models) >= 4)

    def test_gemini_generate_raises_without_key(self) -> None:
        """generate() should raise RuntimeError when no client is initialised."""
        provider = GoogleGeminiProvider(api_key="")
        with self.assertRaises(RuntimeError):
            provider.generate("d4")


# ---------------------------------------------------------------------------
# Ollama Provider Tests (3 tests)
# ---------------------------------------------------------------------------
class TestOllamaProvider(unittest.TestCase):

    def test_ollama_init(self) -> None:
        """OllamaProvider should initialise with default base_url."""
        provider = OllamaProvider()
        self.assertIsInstance(provider, LLMProvider)
        self.assertEqual(provider._base_url, "http://localhost:11434")

    def test_ollama_recommended_models(self) -> None:
        """get_recommended_models returns known open-source models."""
        provider = OllamaProvider()
        models = provider.get_recommended_models()
        self.assertIsInstance(models, list)
        self.assertIn("llama3.2", models)
        self.assertIn("mistral", models)

    def test_ollama_list_models(self) -> None:
        """list_models returns a dict of available Ollama models."""
        models = OllamaProvider.list_models()
        self.assertIsInstance(models, dict)
        self.assertTrue(len(models) >= 5)
        self.assertIn("llama3.2", models)


# ---------------------------------------------------------------------------
# Mock Provider Tests (4 tests)
# ---------------------------------------------------------------------------
class TestMockProvider(unittest.TestCase):

    def test_mock_generate(self) -> None:
        """MockProvider should return an LLMResponse without any API call."""
        provider = MockProvider()
        response = provider.generate("What is the best move?")
        self.assertIsInstance(response, LLMResponse)
        self.assertEqual(response.provider, "mock")
        self.assertIsInstance(response.content, str)
        self.assertGreater(len(response.content), 0)

    def test_mock_recommended_models(self) -> None:
        """get_recommended_models returns mock model names."""
        provider = MockProvider()
        models = provider.get_recommended_models()
        self.assertIsInstance(models, list)
        self.assertIn("mock-chess", models)

    def test_mock_list_models(self) -> None:
        """list_models returns mock model descriptions."""
        models = MockProvider.list_models()
        self.assertIsInstance(models, dict)
        self.assertIn("mock-chess", models)
        self.assertIn("mock-deterministic", models)

    def test_mock_reset(self) -> None:
        """reset() should reset the call counter."""
        provider = MockProvider(responses=["e4", "d4"])
        r1 = provider.generate("prompt")
        self.assertEqual(r1.content, "e4")
        r2 = provider.generate("prompt")
        self.assertEqual(r2.content, "d4")
        provider.reset()
        r3 = provider.generate("prompt")
        self.assertEqual(r3.content, "e4")


# ---------------------------------------------------------------------------
# Integration Tests (3 tests)
# ---------------------------------------------------------------------------
class TestIntegration(unittest.TestCase):

    def test_all_providers_have_list_models(self) -> None:
        """All provider classes should implement list_models()."""
        provider_classes = [
            OpenAIProvider,
            AnthropicProvider,
            AzureOpenAIProvider,
            GoogleGeminiProvider,
            OllamaProvider,
            MockProvider,
        ]
        for cls in provider_classes:
            with self.subTest(cls=cls.__name__):
                models = cls.list_models()
                self.assertIsInstance(models, dict)
                self.assertGreater(len(models), 0)

    def test_all_providers_have_recommended_models(self) -> None:
        """All provider instances should implement get_recommended_models()."""
        providers: list[LLMProvider] = [
            OpenAIProvider(api_key=""),
            AnthropicProvider(api_key=""),
            AzureOpenAIProvider(api_key="", endpoint=""),
            GoogleGeminiProvider(api_key=""),
            OllamaProvider(),
            MockProvider(),
        ]
        for provider in providers:
            with self.subTest(provider=provider.provider_name):
                models = provider.get_recommended_models()
                self.assertIsInstance(models, list)
                self.assertGreater(len(models), 0)

    def test_mock_match_engine(self) -> None:
        """MatchEngine should run a short match with MockProviders."""
        from match_engine import MatchEngine, PlayerProfile, TimeControl

        engine = MatchEngine(time_control=TimeControl.BLITZ, max_moves=6)
        white = PlayerProfile(
            name="MockWhite",
            provider=MockProvider(responses=["e4", "Nf3", "Bc4", "O-O", "d3", "Nc3"]),
            elo=1500,
        )
        black = PlayerProfile(
            name="MockBlack",
            provider=MockProvider(responses=["e5", "Nc6", "Nf6", "Be7", "d6", "O-O"]),
            elo=1500,
        )
        result = engine.play_match(white, black)
        from match_engine import MatchResult
        self.assertIsInstance(result, MatchResult)
        self.assertEqual(result.white_player, "MockWhite")
        self.assertEqual(result.black_player, "MockBlack")


if __name__ == "__main__":
    unittest.main()
