"""LLM Provider abstractions for CAISSA."""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Structured response from an LLM provider."""

    content: str
    model: str
    provider: str
    tokens_used: int = 0
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self, model: str, temperature: float = 0.7, max_tokens: int = 512) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client: Any = None

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        """Generate a response from the LLM."""
        ...

    @abstractmethod
    def get_recommended_models(self) -> list[str]:
        """Return a list of recommended model names for this provider."""
        ...

    @classmethod
    @abstractmethod
    def list_models(cls) -> dict[str, str]:
        """Return a dict of model_name -> description for available models."""
        ...

    @property
    def provider_name(self) -> str:
        return self.__class__.__name__

    def __repr__(self) -> str:
        return f"{self.provider_name}(model={self.model!r})"


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""

    MODELS: dict[str, str] = {
        "gpt-4o": "GPT-4o - Most capable multimodal model",
        "gpt-4o-mini": "GPT-4o mini - Affordable and intelligent small model",
        "gpt-4-turbo": "GPT-4 Turbo - High intelligence with a 128k context window",
        "o1-preview": "o1-preview - Reasoning model for complex tasks",
        "o1-mini": "o1-mini - Faster, cheaper reasoning model",
        "gpt-3.5-turbo": "GPT-3.5 Turbo - Fast and cost-effective",
    }

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: int = 512,
        api_key: str | None = None,
    ) -> None:
        super().__init__(model, temperature, max_tokens)
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._client = None
        if self._api_key:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self._api_key)
            except ImportError:
                logger.warning("openai package not installed")
            except Exception as exc:
                logger.warning("OpenAI client init failed: %s", exc)

    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        if not self._client:
            raise RuntimeError("OpenAI client not initialised (missing API key or package)")
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        t0 = time.monotonic()
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        latency = (time.monotonic() - t0) * 1000
        content = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        return LLMResponse(
            content=content,
            model=self.model,
            provider="openai",
            tokens_used=tokens,
            latency_ms=latency,
        )

    def get_recommended_models(self) -> list[str]:
        return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1-preview", "o1-mini"]

    @classmethod
    def list_models(cls) -> dict[str, str]:
        return dict(cls.MODELS)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    MODELS: dict[str, str] = {
        "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet - Most intelligent Claude model",
        "claude-3-opus-20240229": "Claude 3 Opus - Powerful model for complex tasks",
        "claude-3-haiku-20240307": "Claude 3 Haiku - Fast and compact",
        "claude-3-sonnet-20240229": "Claude 3 Sonnet - Balance of speed and intelligence",
    }

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.7,
        max_tokens: int = 512,
        api_key: str | None = None,
    ) -> None:
        super().__init__(model, temperature, max_tokens)
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = None
        if self._api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError:
                logger.warning("anthropic package not installed")
            except Exception as exc:
                logger.warning("Anthropic client init failed: %s", exc)

    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        if not self._client:
            raise RuntimeError("Anthropic client not initialised (missing API key or package)")
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        t0 = time.monotonic()
        response = self._client.messages.create(**kwargs)
        latency = (time.monotonic() - t0) * 1000
        content = response.content[0].text if response.content else ""
        tokens = (response.usage.input_tokens + response.usage.output_tokens) if response.usage else 0
        return LLMResponse(
            content=content,
            model=self.model,
            provider="anthropic",
            tokens_used=tokens,
            latency_ms=latency,
        )

    def get_recommended_models(self) -> list[str]:
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-haiku-20240307",
        ]

    @classmethod
    def list_models(cls) -> dict[str, str]:
        return dict(cls.MODELS)


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI provider."""

    MODELS: dict[str, str] = {
        "gpt-4o": "GPT-4o on Azure",
        "gpt-4-turbo": "GPT-4 Turbo on Azure",
        "gpt-35-turbo": "GPT-3.5 Turbo on Azure",
    }

    def __init__(
        self,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 512,
        api_key: str | None = None,
        endpoint: str | None = None,
        api_version: str = "2024-02-01",
        deployment_name: str | None = None,
    ) -> None:
        super().__init__(model, temperature, max_tokens)
        self._api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY", "")
        self._endpoint = endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        self._api_version = api_version
        self._deployment_name = deployment_name or model
        self._client = None
        if self._api_key and self._endpoint:
            try:
                import openai
                self._client = openai.AzureOpenAI(
                    api_key=self._api_key,
                    azure_endpoint=self._endpoint,
                    api_version=self._api_version,
                )
            except ImportError:
                logger.warning("openai package not installed")
            except Exception as exc:
                logger.warning("Azure OpenAI client init failed: %s", exc)

    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        if not self._client:
            raise RuntimeError("Azure OpenAI client not initialised (missing credentials or package)")
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        t0 = time.monotonic()
        response = self._client.chat.completions.create(
            model=self._deployment_name,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        latency = (time.monotonic() - t0) * 1000
        content = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        return LLMResponse(
            content=content,
            model=self.model,
            provider="azure_openai",
            tokens_used=tokens,
            latency_ms=latency,
        )

    def get_recommended_models(self) -> list[str]:
        return ["gpt-4o", "gpt-4-turbo", "gpt-35-turbo"]

    @classmethod
    def list_models(cls) -> dict[str, str]:
        return dict(cls.MODELS)


class GoogleGeminiProvider(LLMProvider):
    """Google Gemini provider."""

    MODELS: dict[str, str] = {
        "gemini-1.5-pro": "Gemini 1.5 Pro - Most capable Gemini model with long context",
        "gemini-1.5-flash": "Gemini 1.5 Flash - Fast and versatile multimodal model",
        "gemini-2.0-flash": "Gemini 2.0 Flash - Next generation fast model",
        "gemini-2.0-flash-exp": "Gemini 2.0 Flash Experimental - Experimental features",
        "gemini-pro": "Gemini Pro - Legacy model",
    }

    def __init__(
        self,
        model: str = "gemini-1.5-flash",
        temperature: float = 0.7,
        max_tokens: int = 512,
        api_key: str | None = None,
    ) -> None:
        super().__init__(model, temperature, max_tokens)
        self._api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self._client = None
        if self._api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self._api_key)
                self._client = genai.GenerativeModel(model)
            except ImportError:
                logger.warning("google-generativeai package not installed")
            except Exception as exc:
                logger.warning("Google Gemini client init failed: %s", exc)

    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        if not self._client:
            raise RuntimeError("Google Gemini client not initialised (missing API key or package)")
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        t0 = time.monotonic()
        response = self._client.generate_content(
            full_prompt,
            generation_config={"temperature": self.temperature, "max_output_tokens": self.max_tokens},
        )
        latency = (time.monotonic() - t0) * 1000
        content = response.text if hasattr(response, "text") else ""
        return LLMResponse(
            content=content,
            model=self.model,
            provider="google_gemini",
            tokens_used=0,
            latency_ms=latency,
        )

    def get_recommended_models(self) -> list[str]:
        return [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-2.0-flash",
            "gemini-2.0-flash-exp",
        ]

    @classmethod
    def list_models(cls) -> dict[str, str]:
        return dict(cls.MODELS)


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""

    MODELS: dict[str, str] = {
        "llama3.2": "Llama 3.2 - Meta's latest open model",
        "llama3.1": "Llama 3.1 - Meta's open model",
        "mistral": "Mistral 7B - High quality compact model",
        "mixtral": "Mixtral 8x7B - Mixture of experts model",
        "codellama": "Code Llama - Specialised code model",
        "phi3": "Phi-3 - Microsoft's small language model",
        "gemma2": "Gemma 2 - Google's open model",
        "qwen2.5": "Qwen 2.5 - Alibaba's multilingual model",
    }

    def __init__(
        self,
        model: str = "llama3.2",
        temperature: float = 0.7,
        max_tokens: int = 512,
        base_url: str = "http://localhost:11434",
    ) -> None:
        super().__init__(model, temperature, max_tokens)
        self._base_url = base_url.rstrip("/")

    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        import requests

        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
        }
        if system_prompt:
            payload["system"] = system_prompt
        t0 = time.monotonic()
        resp = requests.post(f"{self._base_url}/api/generate", json=payload, timeout=120)
        resp.raise_for_status()
        latency = (time.monotonic() - t0) * 1000
        data = resp.json()
        content = data.get("response", "")
        return LLMResponse(
            content=content,
            model=self.model,
            provider="ollama",
            tokens_used=data.get("eval_count", 0),
            latency_ms=latency,
        )

    def get_recommended_models(self) -> list[str]:
        return ["llama3.2", "mistral", "mixtral", "phi3", "gemma2"]

    @classmethod
    def list_models(cls) -> dict[str, str]:
        return dict(cls.MODELS)


class MockProvider(LLMProvider):
    """Mock LLM provider for testing without API keys."""

    MODELS: dict[str, str] = {
        "mock-chess": "Mock Chess Model - always returns valid moves",
        "mock-random": "Mock Random Model - returns random legal moves",
        "mock-deterministic": "Mock Deterministic Model - always returns e4",
    }

    def __init__(
        self,
        model: str = "mock-chess",
        temperature: float = 0.7,
        max_tokens: int = 512,
        responses: list[str] | None = None,
    ) -> None:
        super().__init__(model, temperature, max_tokens)
        self._responses = responses or ["e4", "e5", "Nf3", "Nc6", "Bc4"]
        self._call_count = 0

    def generate(self, prompt: str, system_prompt: str | None = None) -> LLMResponse:
        response = self._responses[self._call_count % len(self._responses)]
        self._call_count += 1
        return LLMResponse(
            content=response,
            model=self.model,
            provider="mock",
            tokens_used=len(prompt.split()),
            latency_ms=1.0,
        )

    def get_recommended_models(self) -> list[str]:
        return ["mock-chess", "mock-random", "mock-deterministic"]

    @classmethod
    def list_models(cls) -> dict[str, str]:
        return dict(cls.MODELS)

    def reset(self) -> None:
        self._call_count = 0
