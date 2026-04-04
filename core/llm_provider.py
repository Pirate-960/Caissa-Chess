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
import threading
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from log_manager import (
    get_logger as _get_caissa_logger,
    is_llm_logging_enabled,
    SESSION_ID as _session_id,
)

from openai import OpenAI, AzureOpenAI, RateLimitError, APIConnectionError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
)

# Configure logging — handlers are wired by log_manager.setup_logging()
logger = logging.getLogger(__name__)


# =============================================================================
# LLM CALL LOGGING — routes through log_manager
# =============================================================================

# Thread-safe call counter so every API call in a session gets a unique ID.
_call_counter = 0
_call_lock = threading.Lock()


def _next_call_id() -> str:
    """Return a session-unique call identifier, e.g. ``a1b2c3d4-0001``."""
    global _call_counter
    with _call_lock:
        _call_counter += 1
        return f"{_session_id}-{_call_counter:04d}"


# ── Public helpers used by every provider ────────────────────────────────────

def _log_llm_call(
    *,
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    response: str,
    temperature: float,
    max_tokens: int,
    elapsed_ms: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
    call_id: str = "",
) -> None:
    """Log a **successful** LLM call with full metadata."""
    if not is_llm_logging_enabled():
        return

    lg = _get_caissa_logger("llm.calls")

    msg = (
        f"{'=' * 70}\n"
        f"  Call ID:       {call_id}\n"
        f"  Provider:      {provider}\n"
        f"  Model:         {model}\n"
        f"  Temperature:   {temperature}\n"
        f"  Max Tokens:    {max_tokens}\n"
        f"  Elapsed:       {elapsed_ms:,.0f} ms\n"
        f"  Tokens (est):  {input_tokens} in / {output_tokens} out"
        f" / {input_tokens + output_tokens} total\n"
        f"{'-' * 70}\n"
        f"  SYSTEM PROMPT\n"
        f"{'-' * 70}\n"
        f"{system_prompt}\n"
        f"{'-' * 70}\n"
        f"  USER PROMPT\n"
        f"{'-' * 70}\n"
        f"{user_prompt}\n"
        f"{'-' * 70}\n"
        f"  RESPONSE\n"
        f"{'-' * 70}\n"
        f"{response}\n"
        f"{'=' * 70}"
    )
    lg.info(msg)

    # Summary line to module logger → master.log + generation.log
    logger.info(
        "LLM call [%s] %s/%s — %.0f ms, ~%d tokens",
        call_id, provider, model, elapsed_ms, input_tokens + output_tokens,
    )


def _log_llm_error(
    *,
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    error: Exception,
    temperature: float,
    max_tokens: int,
    elapsed_ms: float,
    call_id: str = "",
    is_retry: bool = False,
) -> None:
    """Log a **failed** LLM call (retryable or fatal)."""
    lg = _get_caissa_logger("llm.errors")

    label = "RETRYABLE ERROR" if is_retry else "FATAL ERROR"
    msg = (
        f"{'!' * 70}\n"
        f"  {label}\n"
        f"  Call ID:       {call_id}\n"
        f"  Provider:      {provider}\n"
        f"  Model:         {model}\n"
        f"  Temperature:   {temperature}\n"
        f"  Max Tokens:    {max_tokens}\n"
        f"  Elapsed:       {elapsed_ms:,.0f} ms\n"
        f"  Error Type:    {type(error).__name__}\n"
        f"  Error Message: {error}\n"
        f"{'!' * 70}"
    )
    lg.warning(msg)

    # Summary line to module logger → master.log + generation.log
    logger.warning(
        "LLM error [%s] %s/%s — %s: %s",
        call_id, provider, model, type(error).__name__, error,
    )


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
    # ===== Google Gemini 3.0 (Latest Flagship - Nov/Dec 2025) =====
    "gemini-3-pro": (2.00, 12.00),              # $2 (≤200k) / $4 (>200k) input, $12/$18 output
    "gemini-3-pro-200k": (4.00, 18.00),         # Pricing for >200k context
    "gemini-3-flash": (0.50, 3.00),             # Fast & capable flagship
    "gemini-3-deep-think": (2.00, 12.00),       # Deep reasoning (Pro tier pricing)
    "nano-banana-pro": (2.00, 120.00),          # Image-focused Gemini 3 variant
    # ===== Google Gemini 2.5 (Production Standard - June/July 2025) =====
    "gemini-2.5-pro": (1.25, 10.00),            # $1.25 (≤200k) / $2.50 (>200k) input
    "gemini-2.5-pro-200k": (2.50, 15.00),       # Pricing for >200k context
    "gemini-2.5-flash": (0.30, 2.50),           # Native audio/video output
    "gemini-2.5-flash-lite": (0.10, 0.40),      # Best price-to-performance
    "nano-banana": (0.30, 30.00),               # Gemini 2.5 image variant
    # ===== Google Gemini 2.0 (Legacy Support - Dec 2024/Feb 2025) =====
    "gemini-2.0-pro": (1.25, 10.00),            # Legacy production
    "gemini-2.0-flash": (0.15, 0.60),           # Standard default (legacy)
    "gemini-2.0-flash-lite": (0.075, 0.30),     # High-volume automation
    # ===== Google Gemini 1.5 (Context Revolution - Feb/May 2024) =====
    "gemini-1.5-pro": (1.25, 5.00),             # Deprecated, limited access
    "gemini-1.5-pro-latest": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),          # Replaced by 2.x/3.x Flash
    "gemini-1.5-flash-latest": (0.075, 0.30),
    "gemini-1.5-flash-8b": (0.0375, 0.15),      # Smallest API model
    # ===== Google Gemini 1.0 (Discontinued - Dec 2023) =====
    "gemini-pro": (0.50, 1.50),                 # Discontinued
    "gemini-1.0-pro": (0.50, 1.50),             # Discontinued
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
        track_metrics: bool = False,
        base_url: Optional[str] = None
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
            model: Model to use (default: gpt-4-turbo)
            max_tokens: Maximum tokens to generate
            track_metrics: Enable metrics tracking (Phase 3.2)
            base_url: Optional custom API base URL (e.g. for DeepSeek)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable "
                "or pass api_key to constructor."
            )
        
        client_kwargs = {"api_key": self.api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = OpenAI(**client_kwargs)
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
        call_id = _next_call_id()
        start = time.perf_counter()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            content = response.choices[0].message.content
            elapsed_ms = (time.perf_counter() - start) * 1000
            in_tok = estimate_tokens(system_prompt + user_prompt)
            out_tok = estimate_tokens(content)
            logger.debug(f"Generated {len(content)} characters in {elapsed_ms:.0f}ms")

            _log_llm_call(
                provider=self.__class__.__name__,
                model=self.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response=content,
                temperature=temperature,
                max_tokens=self.max_tokens,
                elapsed_ms=elapsed_ms,
                input_tokens=in_tok,
                output_tokens=out_tok,
                call_id=call_id,
            )

            return content

        except (RateLimitError, APIConnectionError) as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.warning(f"Retryable error: {type(e).__name__}: {str(e)}")
            _log_llm_error(
                provider=self.__class__.__name__,
                model=self.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                error=e,
                temperature=temperature,
                max_tokens=self.max_tokens,
                elapsed_ms=elapsed_ms,
                call_id=call_id,
                is_retry=True,
            )
            raise  # Will be caught by tenacity retry

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(f"OpenAI API error: {type(e).__name__}: {str(e)}")
            _log_llm_error(
                provider=self.__class__.__name__,
                model=self.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                error=e,
                temperature=temperature,
                max_tokens=self.max_tokens,
                elapsed_ms=elapsed_ms,
                call_id=call_id,
            )
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
        call_id = _next_call_id()
        start = time.perf_counter()

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
            elapsed_ms = (time.perf_counter() - start) * 1000
            in_tok = estimate_tokens(system_prompt + user_prompt)
            out_tok = estimate_tokens(content)
            logger.debug(f"Generated {len(content)} characters in {elapsed_ms:.0f}ms")

            _log_llm_call(
                provider=self.__class__.__name__,
                model=self.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response=content,
                temperature=temperature,
                max_tokens=self.max_tokens,
                elapsed_ms=elapsed_ms,
                input_tokens=in_tok,
                output_tokens=out_tok,
                call_id=call_id,
            )

            return content

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(f"Anthropic API error: {type(e).__name__}: {str(e)}")
            _log_llm_error(
                provider=self.__class__.__name__,
                model=self.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                error=e,
                temperature=temperature,
                max_tokens=self.max_tokens,
                elapsed_ms=elapsed_ms,
                call_id=call_id,
                is_retry=True,
            )
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
        call_id = _next_call_id()
        start = time.perf_counter()

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
            elapsed_ms = (time.perf_counter() - start) * 1000
            in_tok = estimate_tokens(system_prompt + user_prompt)
            out_tok = estimate_tokens(content)
            logger.debug(f"Generated {len(content)} characters in {elapsed_ms:.0f}ms")

            _log_llm_call(
                provider=self.__class__.__name__,
                model=self.deployment_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response=content,
                temperature=temperature,
                max_tokens=self.max_tokens,
                elapsed_ms=elapsed_ms,
                input_tokens=in_tok,
                output_tokens=out_tok,
                call_id=call_id,
            )

            return content

        except (RateLimitError, APIConnectionError) as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.warning(f"Retryable error: {type(e).__name__}: {str(e)}")
            _log_llm_error(
                provider=self.__class__.__name__,
                model=self.deployment_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                error=e,
                temperature=temperature,
                max_tokens=self.max_tokens,
                elapsed_ms=elapsed_ms,
                call_id=call_id,
                is_retry=True,
            )
            raise

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(f"Azure OpenAI API error: {type(e).__name__}: {str(e)}")
            _log_llm_error(
                provider=self.__class__.__name__,
                model=self.deployment_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                error=e,
                temperature=temperature,
                max_tokens=self.max_tokens,
                elapsed_ms=elapsed_ms,
                call_id=call_id,
            )
            raise


class GoogleGeminiProvider(LLMProvider):
    """
    Google Gemini API provider with automatic retry logic.
    
    Features:
    - Exponential backoff for rate limits
    - Automatic retry on network errors
    - Configurable model selection
    - Support for Gemini 3.0, 2.5, 2.0, 1.5, and 1.0 series
    
    Supported Models (Feb 2026):
    
    GEMINI 3.0 (Flagship - Nov/Dec 2025):
    - gemini-3-flash (RECOMMENDED) - Best value, 1M context
    - gemini-3-pro - Premium quality, 1-2M context
    - gemini-3-deep-think - Advanced reasoning capabilities
    - nano-banana-pro - Image-focused variant (64k context)
    
    GEMINI 2.5 (Production Standard - June/July 2025):
    - gemini-2.5-flash - Native audio/video output
    - gemini-2.5-flash-lite - Cheapest price-to-perf ratio
    - gemini-2.5-pro - High multimodal reasoning
    - nano-banana - Gemini 2.5 image variant
    
    GEMINI 2.0 (Legacy - Dec 2024/Feb 2025):
    - gemini-2.0-flash - First speed breakthrough
    - gemini-2.0-flash-lite - High-volume automation
    - gemini-2.0-pro - Legacy production
    
    GEMINI 1.5/1.0 (Deprecated):
    - gemini-1.5-pro/flash - Limited access
    - gemini-1.0-pro - Discontinued
    """
    
    SUPPORTED_MODELS = [
        # Gemini 3.0 (Latest Flagship)
        "gemini-3-flash",
        "gemini-3-pro",
        "gemini-3-pro-200k",
        "gemini-3-deep-think",
        "nano-banana-pro",
        # Gemini 2.5 (Production Standard)
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-pro",
        "gemini-2.5-pro-200k",
        "nano-banana",
        # Gemini 2.0 (Legacy Support)
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.0-pro",
        # Gemini 1.5 (Deprecated)
        "gemini-1.5-pro",
        "gemini-1.5-pro-latest",
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash-8b",
        # Gemini 1.0 (Discontinued)
        "gemini-pro",
        "gemini-1.0-pro",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-3-flash",
        max_tokens: int = 8192
    ):
        """
        Initialize Google Gemini provider.
        
        Args:
            api_key: Google API key (if None, reads from GOOGLE_API_KEY)
            model: Model to use (default: gemini-3-flash)
            max_tokens: Maximum tokens to generate (default: 8192)
        
        Recommended models by use case:
            - gemini-3-flash: Best value, fast & capable (RECOMMENDED)
            - gemini-3-pro: Premium quality, complex reasoning
            - gemini-3-deep-think: Advanced reasoning tasks
            - gemini-2.5-flash-lite: Budget-friendly, high volume
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Google API key not provided. Set GOOGLE_API_KEY environment variable "
                "or pass api_key to constructor."
            )

        self._use_new_sdk = False
        self._use_old_sdk = False
        self._use_rest = False
        self._genai_client = None
        self.client = None  # old SDK GenerativeModel

        # ── Tier 1: Try the new google-genai SDK ────────────────
        try:
            from google import genai  # noqa: F401
            self._genai_client = genai.Client(api_key=self.api_key)
            self._use_new_sdk = True
            logger.info("Gemini tier-1: using google-genai (new SDK)")
        except ImportError:
            logger.info(
                "google-genai SDK not installed. "
                "Install with: pip install google-genai   "
                "Falling back to google-generativeai..."
            )

        # ── Tier 2: Fall back to deprecated google-generativeai ─
        if not self._use_new_sdk:
            try:
                import google.generativeai as genai_old
                genai_old.configure(api_key=self.api_key)
                self.client = genai_old.GenerativeModel(model)
                self._use_old_sdk = True
                logger.info("Gemini tier-2: using google-generativeai (deprecated SDK)")
            except ImportError:
                logger.info(
                    "google-generativeai SDK not installed either. "
                    "Install with: pip install google-generativeai   "
                    "Falling back to REST API..."
                )

        # ── Tier 3: REST API fallback (no SDK required) ─────────
        if not self._use_new_sdk and not self._use_old_sdk:
            try:
                import requests as _req  # noqa: F401
                self._use_rest = True
                self._rest_base = (
                    "https://generativelanguage.googleapis.com/v1beta/models"
                )
                logger.info(
                    "Gemini tier-3: using REST API (no SDK). "
                    "For a richer experience install: pip install google-genai"
                )
            except ImportError:
                raise ImportError(
                    "No Gemini SDK and no 'requests' library installed. "
                    "Install at least one:\n"
                    "  pip install google-genai          (recommended)\n"
                    "  pip install google-generativeai   (deprecated)\n"
                    "  pip install requests              (REST fallback)"
                )

        self.model = model
        self.max_tokens = max_tokens
        
        tier_label = (
            "new SDK (google.genai)" if self._use_new_sdk
            else "deprecated SDK (google.generativeai)" if self._use_old_sdk
            else "REST API"
        )
        logger.info(
            f"Initialized GoogleGeminiProvider with model: {model} "
            f"[backend: {tier_label}]"
        )

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
        call_id = _next_call_id()
        start = time.perf_counter()

        try:
            if self._use_new_sdk:
                # ── Tier 1: New google-genai SDK ─────────────────
                from google.genai import types as genai_types

                response = self._genai_client.models.generate_content(
                    model=self.model,
                    contents=user_prompt,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                        max_output_tokens=self.max_tokens,
                    ),
                )
                content = response.text

            elif self._use_old_sdk:
                # ── Tier 2: Deprecated google-generativeai SDK ───
                full_prompt = f"{system_prompt}\n\n{user_prompt}"

                response = self.client.generate_content(
                    full_prompt,
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": self.max_tokens
                    }
                )
                content = response.text

            else:
                # ── Tier 3: REST API fallback ────────────────────
                import requests as _req
                import json as _json

                url = f"{self._rest_base}/{self.model}:generateContent"
                payload = {
                    "contents": [
                        {"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}
                    ],
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": self.max_tokens,
                    },
                }
                resp = _req.post(
                    url,
                    params={"key": self.api_key},
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()

                # Extract text from REST response
                candidates = data.get("candidates", [])
                if not candidates:
                    raise RuntimeError(
                        f"Gemini REST API returned no candidates: {_json.dumps(data)[:300]}"
                    )
                parts = candidates[0].get("content", {}).get("parts", [])
                content = "".join(p.get("text", "") for p in parts)
                if not content:
                    raise RuntimeError(
                        f"Gemini REST API returned empty content: {_json.dumps(data)[:300]}"
                    )
            elapsed_ms = (time.perf_counter() - start) * 1000
            in_tok = estimate_tokens(system_prompt) + estimate_tokens(user_prompt)
            out_tok = estimate_tokens(content)
            logger.debug(f"Generated {len(content)} characters in {elapsed_ms:.0f}ms")

            _log_llm_call(
                provider=self.__class__.__name__,
                model=self.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response=content,
                temperature=temperature,
                max_tokens=self.max_tokens,
                elapsed_ms=elapsed_ms,
                input_tokens=in_tok,
                output_tokens=out_tok,
                call_id=call_id,
            )

            return content

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(f"Google Gemini API error: {type(e).__name__}: {str(e)}")
            _log_llm_error(
                provider=self.__class__.__name__,
                model=self.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                error=e,
                temperature=temperature,
                max_tokens=self.max_tokens,
                elapsed_ms=elapsed_ms,
                call_id=call_id,
                is_retry=True,
            )
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
        call_id = _next_call_id()
        start = time.perf_counter()

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

            elapsed_ms = (time.perf_counter() - start) * 1000
            in_tok = estimate_tokens(system_prompt + user_prompt)
            out_tok = estimate_tokens(content)
            logger.debug(f"Generated {len(content)} characters in {elapsed_ms:.0f}ms")

            _log_llm_call(
                provider=self.__class__.__name__,
                model=self.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response=content,
                temperature=temperature,
                max_tokens=self.max_tokens,
                elapsed_ms=elapsed_ms,
                input_tokens=in_tok,
                output_tokens=out_tok,
                call_id=call_id,
            )

            return content

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(f"Ollama API error: {type(e).__name__}: {str(e)}")
            _log_llm_error(
                provider=self.__class__.__name__,
                model=self.model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                error=e,
                temperature=temperature,
                max_tokens=self.max_tokens,
                elapsed_ms=elapsed_ms,
                call_id=call_id,
                is_retry=True,
            )
            raise
