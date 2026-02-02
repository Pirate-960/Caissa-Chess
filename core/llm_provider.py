"""
core/llm_provider.py

Abstract provider interface for LLM integration.
Supports OpenAI, Anthropic, Azure OpenAI, Google Gemini, local models (Ollama), and mock providers.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional

from openai import OpenAI, AzureOpenAI, RateLimitError, APIConnectionError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type,
)

# Configure logging
logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    Defines the interface that all concrete providers must implement.
    This allows swapping between OpenAI, Anthropic, local models, etc.
    """

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


class OpenAIProvider(LLMProvider):
    """
    OpenAI API provider with automatic retry logic.
    
    Features:
    - Exponential backoff for rate limits
    - Automatic retry on network errors
    - Configurable model selection
    """

    def __init__(
        self, 
        api_key: Optional[str] = None,
        model: str = "gpt-4-turbo",
        max_tokens: int = 4096
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
            model: Model to use (default: gpt-4-turbo)
            max_tokens: Maximum tokens to generate
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
