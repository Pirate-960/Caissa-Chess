"""
core/llm_provider.py

Abstract provider interface for LLM integration.
Supports OpenAI, Anthropic, Azure OpenAI, Google Gemini, local models (Ollama), and mock providers.

PHASE 3.2 ENHANCEMENTS:
- ProviderMetrics for tracking latency, tokens, costs
- GenerationMetrics returned with each response
- Cost estimation per provider/model
- Token usage tracking
- Performance analytics

Original functionality 100% preserved.
"""

import os
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

from openai import OpenAI, AzureOpenAI, RateLimitError, APIConnectionError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
)

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# PHASE 3.2: METRICS AND TRACKING
# =============================================================================

class CostTier(str, Enum):
    """Cost tiers for different models."""
    FREE = "free"           # Local models (Ollama)
    BUDGET = "budget"       # GPT-3.5, Claude Haiku
    STANDARD = "standard"   # GPT-4o-mini, Claude Sonnet
    PREMIUM = "premium"     # GPT-4, Claude Opus


@dataclass
class TokenUsage:
    """Token usage for a single generation."""
    input_tokens: int = 0
    output_tokens: int = 0
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
    
    def to_dict(self) -> Dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class CostEstimate:
    """Cost estimate for a generation."""
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    
    @property
    def total_cost_usd(self) -> float:
        return self.input_cost_usd + self.output_cost_usd
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "input_cost_usd": self.input_cost_usd,
            "output_cost_usd": self.output_cost_usd,
            "total_cost_usd": self.total_cost_usd,
        }


@dataclass
class GenerationMetrics:
    """Metrics for a single generation call."""
    latency_ms: float = 0.0
    tokens: TokenUsage = field(default_factory=TokenUsage)
    cost: CostEstimate = field(default_factory=CostEstimate)
    model: str = ""
    provider: str = ""
    success: bool = True
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "latency_ms": self.latency_ms,
            "tokens": self.tokens.to_dict(),
            "cost": self.cost.to_dict(),
            "model": self.model,
            "provider": self.provider,
            "success": self.success,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
        }


@dataclass
class ProviderMetrics:
    """Aggregate metrics for a provider."""
    provider_name: str
    model: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    
    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls
    
    @property
    def avg_latency_ms(self) -> float:
        if self.successful_calls == 0:
            return 0.0
        return self.total_latency_ms / self.successful_calls
    
    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens
    
    def record_call(self, metrics: GenerationMetrics) -> None:
        """Record a generation call."""
        self.total_calls += 1
        
        if metrics.success:
            self.successful_calls += 1
            self.total_input_tokens += metrics.tokens.input_tokens
            self.total_output_tokens += metrics.tokens.output_tokens
            self.total_cost_usd += metrics.cost.total_cost_usd
            self.total_latency_ms += metrics.latency_ms
            self.min_latency_ms = min(self.min_latency_ms, metrics.latency_ms)
            self.max_latency_ms = max(self.max_latency_ms, metrics.latency_ms)
        else:
            self.failed_calls += 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "model": self.model,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": self.success_rate,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "avg_latency_ms": self.avg_latency_ms,
            "min_latency_ms": self.min_latency_ms if self.min_latency_ms != float('inf') else 0.0,
            "max_latency_ms": self.max_latency_ms,
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.total_latency_ms = 0.0
        self.min_latency_ms = float('inf')
        self.max_latency_ms = 0.0


# Model pricing (per 1M tokens: input, output)
MODEL_PRICING: Dict[str, Tuple[float, float]] = {
    # OpenAI
    "gpt-4-turbo": (10.0, 30.0),
    "gpt-4o": (5.0, 15.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4": (30.0, 60.0),
    "gpt-3.5-turbo": (0.50, 1.50),
    # Anthropic
    "claude-3-opus": (15.0, 75.0),
    "claude-3-sonnet": (3.0, 15.0),
    "claude-3-haiku": (0.25, 1.25),
    "claude-3-5-sonnet": (3.0, 15.0),
    # Google
    "gemini-pro": (0.50, 1.50),
    "gemini-1.5-pro": (3.50, 10.50),
    "gemini-1.5-flash": (0.075, 0.30),
    # Local
    "ollama": (0.0, 0.0),
    "llama2": (0.0, 0.0),
    "mistral": (0.0, 0.0),
    "codellama": (0.0, 0.0),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> CostEstimate:
    """Estimate cost for given model and token counts."""
    # Find matching pricing
    input_price, output_price = 0.15, 0.60  # Default to GPT-4o-mini
    model_lower = model.lower()
    
    # First try exact match
    if model_lower in MODEL_PRICING:
        input_price, output_price = MODEL_PRICING[model_lower]
    else:
        # Then try substring match, preferring longer keys first
        sorted_keys = sorted(MODEL_PRICING.keys(), key=len, reverse=True)
        for model_key in sorted_keys:
            if model_key.lower() in model_lower:
                input_price, output_price = MODEL_PRICING[model_key]
                break
    
    return CostEstimate(
        input_cost_usd=(input_tokens / 1_000_000) * input_price,
        output_cost_usd=(output_tokens / 1_000_000) * output_price,
    )


def estimate_tokens(text: str) -> int:
    """Rough token estimate (average ~4 chars per token)."""
    return len(text) // 4


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    Defines the interface that all concrete providers must implement.
    This allows swapping between OpenAI, Anthropic, local models, etc.
    
    PHASE 3.2: Added metrics tracking and generate_with_metrics method.
    """
    
    # Provider metrics (class-level, shared across instances)
    _metrics: Optional[ProviderMetrics] = None

    @abstractmethod
    def generate(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float = 0.8
    ) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            system_prompt: The system/instruction prompt
            user_prompt: The user's actual request/query
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
        
        Returns:
            The LLM's text response
        
        Raises:
            Exception: If the LLM call fails after retries
        """
        pass
    
    def generate_with_metrics(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8
    ) -> Tuple[str, GenerationMetrics]:
        """
        Generate a response and return metrics.
        
        PHASE 3.2: New method for tracked generation.
        
        Args:
            system_prompt: The system/instruction prompt
            user_prompt: The user's actual request/query
            temperature: Sampling temperature
        
        Returns:
            Tuple of (response text, generation metrics)
        """
        provider_name = self.__class__.__name__.replace("Provider", "")
        model = getattr(self, "model", getattr(self, "deployment_name", "unknown"))
        
        metrics = GenerationMetrics(
            model=model,
            provider=provider_name,
        )
        
        start_time = time.perf_counter()
        
        try:
            response = self.generate(system_prompt, user_prompt, temperature)
            metrics.latency_ms = (time.perf_counter() - start_time) * 1000
            metrics.success = True
            
            # Estimate tokens
            input_tokens = estimate_tokens(system_prompt + user_prompt)
            output_tokens = estimate_tokens(response)
            metrics.tokens = TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            metrics.cost = estimate_cost(model, input_tokens, output_tokens)
            
            # Record in aggregate metrics
            if self._metrics:
                self._metrics.record_call(metrics)
            
            return response, metrics
            
        except Exception as e:
            metrics.latency_ms = (time.perf_counter() - start_time) * 1000
            metrics.success = False
            metrics.error_message = str(e)
            
            if self._metrics:
                self._metrics.record_call(metrics)
            
            raise
    
    def get_metrics(self) -> Optional[ProviderMetrics]:
        """Get aggregate metrics for this provider."""
        return self._metrics
    
    def reset_metrics(self) -> None:
        """Reset aggregate metrics."""
        if self._metrics:
            self._metrics.reset()
    
    def enable_metrics(self) -> None:
        """Enable metrics tracking for this provider."""
        provider_name = self.__class__.__name__.replace("Provider", "")
        model = getattr(self, "model", getattr(self, "deployment_name", "unknown"))
        self._metrics = ProviderMetrics(provider_name=provider_name, model=model)


class OpenAIProvider(LLMProvider):
    """
    OpenAI API provider with automatic retry logic.
    
    Features:
    - Exponential backoff for rate limits
    - Automatic retry on network errors
    - Configurable model selection
    - PHASE 3.2: Metrics tracking
    """

    def __init__(
        self, 
        api_key: Optional[str] = None,
        model: str = "gpt-4-turbo",
        max_tokens: int = 4096,
        track_metrics: bool = False
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
            model: Model to use (default: gpt-4-turbo)
            max_tokens: Maximum tokens to generate
            track_metrics: Enable metrics tracking (Phase 3.2)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable "
                "or pass api_key to constructor."
            )
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.max_tokens = max_tokens
        
        # PHASE 3.2: Initialize metrics if tracking enabled
        if track_metrics:
            self.enable_metrics()
        
        logger.info(f"Initialized OpenAIProvider with model: {model}")

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        wait=wait_random_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
        reraise=True
    )
    def generate(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float = 0.8
    ) -> str:
        """
        Generate a response using OpenAI's API.
        
        Includes automatic retry logic with exponential backoff for:
        - Rate limit errors (429)
        - API connection errors
        
        Args:
            system_prompt: System instructions for the model
            user_prompt: User's query/request
            temperature: Sampling temperature (0.0-2.0)
        
        Returns:
            Generated text response
        
        Raises:
            RateLimitError: If rate limit persists after retries
            APIConnectionError: If connection fails after retries
            Exception: For other API errors
        """
        logger.debug(f"Generating with temperature={temperature}")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=self.max_tokens
            )
            
            content = response.choices[0].message.content
            logger.debug(f"Generated {len(content)} characters")
            
            return content
        
        except (RateLimitError, APIConnectionError) as e:
            logger.warning(f"Retryable error: {type(e).__name__}: {str(e)}")
            raise  # Will be caught by tenacity retry
        
        except Exception as e:
            logger.error(f"OpenAI API error: {type(e).__name__}: {str(e)}")
            raise


class MockProvider(LLMProvider):
    """
    Mock provider for testing without API calls.
    
    Returns pre-defined responses in sequence, allowing controlled
    testing of the self-correction loop and error handling.
    """

    def __init__(self, responses: list[str]):
        """
        Initialize mock provider.
        
        Args:
            responses: List of responses to return sequentially
        """
        if not responses:
            raise ValueError("MockProvider requires at least one response")
        
        self.responses = responses
        self.call_count = 0
        
        logger.info(f"Initialized MockProvider with {len(responses)} responses")

    def generate(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float = 0.8
    ) -> str:
        """
        Return the next pre-defined response.
        
        Args:
            system_prompt: Ignored (for testing)
            user_prompt: Ignored (for testing)
            temperature: Ignored (for testing)
        
        Returns:
            Next response from the list
        
        Raises:
            IndexError: If all responses have been exhausted
        """
        if self.call_count >= len(self.responses):
            raise IndexError(
                f"MockProvider exhausted: {self.call_count} calls made, "
                f"only {len(self.responses)} responses available"
            )
        
        response = self.responses[self.call_count]
        self.call_count += 1
        
        logger.debug(
            f"MockProvider returning response {self.call_count}/{len(self.responses)}"
        )
        
        return response

    def reset(self) -> None:
        """Reset the call counter."""
        self.call_count = 0
        logger.debug("MockProvider reset")


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude API provider with automatic retry logic.
    
    Features:
    - Exponential backoff for rate limits
    - Automatic retry on network errors
    - Configurable model selection (Claude 3.5 Sonnet, Opus, etc.)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 4096
    ):
        """
        Initialize Anthropic provider.
        
        Args:
            api_key: Anthropic API key (if None, reads from ANTHROPIC_API_KEY env var)
            model: Model to use (default: claude-3-5-sonnet-20241022)
            max_tokens: Maximum tokens to generate
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key not provided. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key to constructor."
            )
        
        try:
            from anthropic import Anthropic, RateLimitError as AnthropicRateLimitError
            self.client = Anthropic(api_key=self.api_key)
            self.rate_limit_error = AnthropicRateLimitError
        except ImportError:
            raise ImportError(
                "anthropic package required. Install with: pip install anthropic"
            )
        
        self.model = model
        self.max_tokens = max_tokens
        
        logger.info(f"Initialized AnthropicProvider with model: {model}")

    @retry(
        retry=retry_if_exception_type(Exception),  # Anthropic errors will be caught
        wait=wait_random_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
        reraise=True
    )
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8
    ) -> str:
        """
        Generate a response using Anthropic's API.
        
        Args:
            system_prompt: System instructions for the model
            user_prompt: User's query/request
            temperature: Sampling temperature (0.0-1.0)
        
        Returns:
            Generated text response
        """
        logger.debug(f"Generating with temperature={temperature}")
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            content = response.content[0].text
            logger.debug(f"Generated {len(content)} characters")
            
            return content
        
        except Exception as e:
            logger.error(f"Anthropic API error: {type(e).__name__}: {str(e)}")
            raise


class AzureOpenAIProvider(LLMProvider):
    """
    Azure OpenAI API provider with automatic retry logic.
    
    Features:
    - Exponential backoff for rate limits
    - Automatic retry on network errors
    - Configurable deployment and endpoint
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        azure_endpoint: Optional[str] = None,
        deployment_name: str = "gpt-4",
        api_version: str = "2024-02-15-preview",
        max_tokens: int = 4096
    ):
        """
        Initialize Azure OpenAI provider.
        
        Args:
            api_key: Azure OpenAI API key (if None, reads from AZURE_OPENAI_API_KEY)
            azure_endpoint: Azure endpoint URL (if None, reads from AZURE_OPENAI_ENDPOINT)
            deployment_name: Deployment name in Azure
            api_version: API version to use
            max_tokens: Maximum tokens to generate
        """
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.azure_endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        
        if not self.api_key:
            raise ValueError(
                "Azure OpenAI API key not provided. Set AZURE_OPENAI_API_KEY environment variable "
                "or pass api_key to constructor."
            )
        
        if not self.azure_endpoint:
            raise ValueError(
                "Azure endpoint not provided. Set AZURE_OPENAI_ENDPOINT environment variable "
                "or pass azure_endpoint to constructor."
            )
        
        self.client = AzureOpenAI(
            api_key=self.api_key,
            api_version=api_version,
            azure_endpoint=self.azure_endpoint
        )
        self.deployment_name = deployment_name
        self.max_tokens = max_tokens
        
        logger.info(f"Initialized AzureOpenAIProvider with deployment: {deployment_name}")

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        wait=wait_random_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
        reraise=True
    )
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8
    ) -> str:
        """
        Generate a response using Azure OpenAI's API.
        
        Args:
            system_prompt: System instructions for the model
            user_prompt: User's query/request
            temperature: Sampling temperature (0.0-2.0)
        
        Returns:
            Generated text response
        """
        logger.debug(f"Generating with temperature={temperature}")
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=self.max_tokens
            )
            
            content = response.choices[0].message.content
            logger.debug(f"Generated {len(content)} characters")
            
            return content
        
        except (RateLimitError, APIConnectionError) as e:
            logger.warning(f"Retryable error: {type(e).__name__}: {str(e)}")
            raise
        
        except Exception as e:
            logger.error(f"Azure OpenAI API error: {type(e).__name__}: {str(e)}")
            raise


class GoogleGeminiProvider(LLMProvider):
    """
    Google Gemini API provider with automatic retry logic.
    
    Features:
    - Exponential backoff for rate limits
    - Automatic retry on network errors
    - Configurable model selection (Gemini Pro, etc.)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-pro",
        max_tokens: int = 4096
    ):
        """
        Initialize Google Gemini provider.
        
        Args:
            api_key: Google API key (if None, reads from GOOGLE_API_KEY)
            model: Model to use (default: gemini-pro)
            max_tokens: Maximum tokens to generate
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Google API key not provided. Set GOOGLE_API_KEY environment variable "
                "or pass api_key to constructor."
            )
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.client = genai.GenerativeModel(model)
        except ImportError:
            raise ImportError(
                "google-generativeai package required. Install with: pip install google-generativeai"
            )
        
        self.model = model
        self.max_tokens = max_tokens
        
        logger.info(f"Initialized GoogleGeminiProvider with model: {model}")

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_random_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
        reraise=True
    )
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8
    ) -> str:
        """
        Generate a response using Google Gemini API.
        
        Args:
            system_prompt: System instructions for the model
            user_prompt: User's query/request
            temperature: Sampling temperature (0.0-2.0)
        
        Returns:
            Generated text response
        """
        logger.debug(f"Generating with temperature={temperature}")
        
        try:
            # Gemini combines system and user prompts
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            
            response = self.client.generate_content(
                full_prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": self.max_tokens
                }
            )
            
            content = response.text
            logger.debug(f"Generated {len(content)} characters")
            
            return content
        
        except Exception as e:
            logger.error(f"Google Gemini API error: {type(e).__name__}: {str(e)}")
            raise


class OllamaProvider(LLMProvider):
    """
    Ollama provider for local LLM models.
    
    Features:
    - Run models locally without API costs
    - Supports any model available in Ollama
    - Configurable base URL for remote Ollama servers
    """

    def __init__(
        self,
        model: str = "llama2",
        base_url: str = "http://localhost:11434",
        max_tokens: int = 4096
    ):
        """
        Initialize Ollama provider.
        
        Args:
            model: Model name (e.g., "llama2", "mistral", "codellama")
            base_url: Ollama server URL (default: http://localhost:11434)
            max_tokens: Maximum tokens to generate
        """
        try:
            import requests
            self.requests = requests
        except ImportError:
            raise ImportError(
                "requests package required. Install with: pip install requests"
            )
        
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.max_tokens = max_tokens
        
        # Test connection
        try:
            response = self.requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            logger.info(f"Initialized OllamaProvider with model: {model}")
        except Exception as e:
            logger.warning(f"Could not connect to Ollama at {base_url}: {e}")
            logger.warning("Make sure Ollama is running: ollama serve")

    @retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_random_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
        reraise=True
    )
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8
    ) -> str:
        """
        Generate a response using Ollama.
        
        Args:
            system_prompt: System instructions for the model
            user_prompt: User's query/request
            temperature: Sampling temperature (0.0-2.0)
        
        Returns:
            Generated text response
        """
        logger.debug(f"Generating with temperature={temperature}")
        
        try:
            response = self.requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": f"{system_prompt}\n\n{user_prompt}",
                    "temperature": temperature,
                    "stream": False,
                    "options": {
                        "num_predict": self.max_tokens
                    }
                },
                timeout=300  # 5 minutes for local generation
            )
            
            response.raise_for_status()
            result = response.json()
            content = result.get("response", "")
            
            logger.debug(f"Generated {len(content)} characters")
            
            return content
        
        except Exception as e:
            logger.error(f"Ollama API error: {type(e).__name__}: {str(e)}")
            raise


class MockProvider(LLMProvider):
    """
    Mock provider for testing without API calls.
    
    Returns pre-defined responses in sequence, allowing controlled
    testing of the self-correction loop and error handling.
    """

    def __init__(self, responses: list[str]):
        """
        Initialize mock provider.
        
        Args:
            responses: List of responses to return sequentially
        """
        if not responses:
            raise ValueError("MockProvider requires at least one response")
        
        self.responses = responses
        self.call_count = 0
        
        logger.info(f"Initialized MockProvider with {len(responses)} responses")

    def generate(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float = 0.8
    ) -> str:
        """
        Return the next pre-defined response.
        
        Args:
            system_prompt: Ignored (for testing)
            user_prompt: Ignored (for testing)
            temperature: Ignored (for testing)
        
        Returns:
            Next response from the list
        
        Raises:
            IndexError: If all responses have been exhausted
        """
        if self.call_count >= len(self.responses):
            raise IndexError(
                f"MockProvider exhausted: {self.call_count} calls made, "
                f"only {len(self.responses)} responses available"
            )
        
        response = self.responses[self.call_count]
        self.call_count += 1
        
        logger.debug(
            f"MockProvider returning response {self.call_count}/{len(self.responses)}"
        )
        
        return response

    def reset(self) -> None:
        """Reset the call counter."""
        self.call_count = 0
        logger.debug("MockProvider reset")
