"""
tests/test_live_providers.py

Live integration tests for all LLM providers.
These tests make actual API calls and are skipped in CI environments.

PHASE 3.2: Quality & Testing
- Live API testing for all providers
- Response quality validation
- Error handling verification

To run these tests locally:
    pytest tests/test_live_providers.py -v --run-live

Environment variables required:
    - OPENAI_API_KEY: For OpenAI tests
    - ANTHROPIC_API_KEY: For Anthropic tests
    - AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT: For Azure tests
    - GOOGLE_API_KEY: For Gemini tests
    - OLLAMA_HOST: For Ollama tests (default: http://localhost:11434)
"""

import os
import time
import unittest
import pytest
from typing import Optional, Tuple
from dataclasses import dataclass

# Skip all tests if --run-live flag is not provided.
# The ``--run-live`` flag is registered in the root conftest.py. Here we use
# the ``live`` marker which conftest.pytest_collection_modifyitems will skip
# automatically when the flag is absent.
pytestmark = pytest.mark.live


@dataclass
class ProviderTestResult:
    """Result of a provider test."""
    provider_name: str
    success: bool
    response_length: int = 0
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    
    def __str__(self) -> str:
        if self.success:
            return f"{self.provider_name}: ✓ ({self.response_length} chars, {self.latency_ms:.0f}ms)"
        return f"{self.provider_name}: ✗ ({self.error_message})"


def check_provider_available(provider_name: str) -> Tuple[bool, str]:
    """Check if a provider has required credentials configured."""
    if provider_name == "openai":
        key = os.getenv("OPENAI_API_KEY")
        return bool(key), "OPENAI_API_KEY not set"
    
    elif provider_name == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY")
        return bool(key), "ANTHROPIC_API_KEY not set"
    
    elif provider_name == "azure":
        key = os.getenv("AZURE_OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if not key:
            return False, "AZURE_OPENAI_API_KEY not set"
        if not endpoint:
            return False, "AZURE_OPENAI_ENDPOINT not set"
        return True, ""
    
    elif provider_name == "gemini":
        key = os.getenv("GOOGLE_API_KEY")
        return bool(key), "GOOGLE_API_KEY not set"
    
    elif provider_name == "ollama":
        # Check if Ollama is running
        try:
            import requests
            host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            response = requests.get(f"{host}/api/tags", timeout=2)
            return response.status_code == 200, "Ollama not running"
        except Exception as e:
            return False, f"Ollama connection failed: {e}"
    
    return False, f"Unknown provider: {provider_name}"


# Simple chess prompt for testing
CHESS_SYSTEM_PROMPT = """You are a chess game generator. Generate a short chess game in PGN format.
The game should be 5-10 moves with proper chess notation."""

CHESS_USER_PROMPT = """Generate a brief chess game between White and Black.
Start with 1. e4 e5 and continue for 5 more moves.
Return only the moves in PGN format, nothing else."""


class TestOpenAILive(unittest.TestCase):
    """Live tests for OpenAI provider."""
    
    @classmethod
    def setUpClass(cls):
        available, reason = check_provider_available("openai")
        if not available:
            raise unittest.SkipTest(reason)
    
    def setUp(self):
        from core.llm_provider import OpenAIProvider
        self.provider = OpenAIProvider(model="gpt-4o-mini")
    
    def test_basic_generation(self):
        """Test basic response generation."""
        start = time.time()
        response = self.provider.generate(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say 'Hello, World!' and nothing else.",
            temperature=0.1
        )
        latency = (time.time() - start) * 1000
        
        self.assertIsNotNone(response)
        self.assertIn("Hello", response)
        self.assertLess(latency, 30000)  # Should respond within 30s
        print(f"\nOpenAI basic: {len(response)} chars, {latency:.0f}ms")
    
    def test_chess_generation(self):
        """Test chess game generation."""
        start = time.time()
        response = self.provider.generate(
            system_prompt=CHESS_SYSTEM_PROMPT,
            user_prompt=CHESS_USER_PROMPT,
            temperature=0.7
        )
        latency = (time.time() - start) * 1000
        
        self.assertIsNotNone(response)
        self.assertIn("e4", response)  # Should contain chess notation
        print(f"\nOpenAI chess: {len(response)} chars, {latency:.0f}ms")
        print(f"Response preview: {response[:200]}...")
    
    def test_temperature_variation(self):
        """Test different temperature settings."""
        # Low temperature (deterministic)
        response_low = self.provider.generate(
            system_prompt="You are a chess expert.",
            user_prompt="What is the best first move in chess?",
            temperature=0.1
        )
        
        # High temperature (creative)
        response_high = self.provider.generate(
            system_prompt="You are a chess expert.",
            user_prompt="What is the best first move in chess?",
            temperature=0.9
        )
        
        self.assertIsNotNone(response_low)
        self.assertIsNotNone(response_high)
        print(f"\nLow temp: {response_low[:100]}...")
        print(f"High temp: {response_high[:100]}...")


class TestAnthropicLive(unittest.TestCase):
    """Live tests for Anthropic Claude provider."""
    
    @classmethod
    def setUpClass(cls):
        available, reason = check_provider_available("anthropic")
        if not available:
            raise unittest.SkipTest(reason)
    
    def setUp(self):
        from core.llm_provider import AnthropicProvider
        self.provider = AnthropicProvider(model="claude-3-haiku-20240307")
    
    def test_basic_generation(self):
        """Test basic response generation."""
        start = time.time()
        response = self.provider.generate(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say 'Hello, World!' and nothing else.",
            temperature=0.1
        )
        latency = (time.time() - start) * 1000
        
        self.assertIsNotNone(response)
        self.assertIn("Hello", response)
        print(f"\nAnthropic basic: {len(response)} chars, {latency:.0f}ms")
    
    def test_chess_generation(self):
        """Test chess game generation."""
        start = time.time()
        response = self.provider.generate(
            system_prompt=CHESS_SYSTEM_PROMPT,
            user_prompt=CHESS_USER_PROMPT,
            temperature=0.7
        )
        latency = (time.time() - start) * 1000
        
        self.assertIsNotNone(response)
        self.assertIn("e4", response)
        print(f"\nAnthropic chess: {len(response)} chars, {latency:.0f}ms")
        print(f"Response preview: {response[:200]}...")
    
    def test_long_context(self):
        """Test handling of longer context."""
        long_prompt = "Generate a 20-move chess game with annotations. " * 10
        response = self.provider.generate(
            system_prompt=CHESS_SYSTEM_PROMPT,
            user_prompt=long_prompt,
            temperature=0.7
        )
        
        self.assertIsNotNone(response)
        self.assertGreater(len(response), 50)


class TestAzureOpenAILive(unittest.TestCase):
    """Live tests for Azure OpenAI provider."""
    
    @classmethod
    def setUpClass(cls):
        available, reason = check_provider_available("azure")
        if not available:
            raise unittest.SkipTest(reason)
    
    def setUp(self):
        from core.llm_provider import AzureOpenAIProvider
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
        self.provider = AzureOpenAIProvider(deployment_name=deployment)
    
    def test_basic_generation(self):
        """Test basic response generation."""
        start = time.time()
        response = self.provider.generate(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say 'Hello, World!' and nothing else.",
            temperature=0.1
        )
        latency = (time.time() - start) * 1000
        
        self.assertIsNotNone(response)
        self.assertIn("Hello", response)
        print(f"\nAzure OpenAI basic: {len(response)} chars, {latency:.0f}ms")
    
    def test_chess_generation(self):
        """Test chess game generation."""
        start = time.time()
        response = self.provider.generate(
            system_prompt=CHESS_SYSTEM_PROMPT,
            user_prompt=CHESS_USER_PROMPT,
            temperature=0.7
        )
        latency = (time.time() - start) * 1000
        
        self.assertIsNotNone(response)
        self.assertIn("e4", response)
        print(f"\nAzure OpenAI chess: {len(response)} chars, {latency:.0f}ms")


class TestGeminiLive(unittest.TestCase):
    """Live tests for Google Gemini provider."""
    
    @classmethod
    def setUpClass(cls):
        available, reason = check_provider_available("gemini")
        if not available:
            raise unittest.SkipTest(reason)
    
    def setUp(self):
        from core.llm_provider import GoogleGeminiProvider
        self.provider = GoogleGeminiProvider(model="gemini-pro")
    
    def test_basic_generation(self):
        """Test basic response generation."""
        start = time.time()
        response = self.provider.generate(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say 'Hello, World!' and nothing else.",
            temperature=0.1
        )
        latency = (time.time() - start) * 1000
        
        self.assertIsNotNone(response)
        self.assertIn("Hello", response)
        print(f"\nGemini basic: {len(response)} chars, {latency:.0f}ms")
    
    def test_chess_generation(self):
        """Test chess game generation."""
        start = time.time()
        response = self.provider.generate(
            system_prompt=CHESS_SYSTEM_PROMPT,
            user_prompt=CHESS_USER_PROMPT,
            temperature=0.7
        )
        latency = (time.time() - start) * 1000
        
        self.assertIsNotNone(response)
        self.assertIn("e4", response)
        print(f"\nGemini chess: {len(response)} chars, {latency:.0f}ms")


class TestOllamaLive(unittest.TestCase):
    """Live tests for Ollama local provider."""
    
    @classmethod
    def setUpClass(cls):
        available, reason = check_provider_available("ollama")
        if not available:
            raise unittest.SkipTest(reason)
    
    def setUp(self):
        from core.llm_provider import OllamaProvider
        model = os.getenv("OLLAMA_MODEL", "llama2")
        self.provider = OllamaProvider(model=model)
    
    def test_basic_generation(self):
        """Test basic response generation."""
        start = time.time()
        response = self.provider.generate(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say 'Hello, World!' and nothing else.",
            temperature=0.1
        )
        latency = (time.time() - start) * 1000
        
        self.assertIsNotNone(response)
        print(f"\nOllama basic: {len(response)} chars, {latency:.0f}ms")
    
    def test_chess_generation(self):
        """Test chess game generation (may be slow for local models)."""
        start = time.time()
        response = self.provider.generate(
            system_prompt=CHESS_SYSTEM_PROMPT,
            user_prompt=CHESS_USER_PROMPT,
            temperature=0.7
        )
        latency = (time.time() - start) * 1000
        
        self.assertIsNotNone(response)
        print(f"\nOllama chess: {len(response)} chars, {latency:.0f}ms")


class TestProviderComparison(unittest.TestCase):
    """Compare all available providers."""
    
    def test_compare_all_providers(self):
        """Run same prompt through all available providers."""
        results: list[ProviderTestResult] = []
        
        # Test each provider
        providers_to_test = [
            ("openai", "OpenAI"),
            ("anthropic", "Anthropic"),
            ("azure", "Azure OpenAI"),
            ("gemini", "Gemini"),
            ("ollama", "Ollama"),
        ]
        
        for provider_id, provider_name in providers_to_test:
            available, reason = check_provider_available(provider_id)
            
            if not available:
                results.append(ProviderTestResult(
                    provider_name=provider_name,
                    success=False,
                    error_message=reason
                ))
                continue
            
            try:
                # Create provider
                if provider_id == "openai":
                    from core.llm_provider import OpenAIProvider
                    provider = OpenAIProvider(model="gpt-4o-mini")
                elif provider_id == "anthropic":
                    from core.llm_provider import AnthropicProvider
                    provider = AnthropicProvider(model="claude-3-haiku-20240307")
                elif provider_id == "azure":
                    from core.llm_provider import AzureOpenAIProvider
                    provider = AzureOpenAIProvider()
                elif provider_id == "gemini":
                    from core.llm_provider import GoogleGeminiProvider
                    provider = GoogleGeminiProvider()
                elif provider_id == "ollama":
                    from core.llm_provider import OllamaProvider
                    provider = OllamaProvider()
                
                # Test generation
                start = time.time()
                response = provider.generate(
                    system_prompt="You are a chess expert.",
                    user_prompt="What is the Italian Game opening? Answer in 2 sentences.",
                    temperature=0.5
                )
                latency = (time.time() - start) * 1000
                
                results.append(ProviderTestResult(
                    provider_name=provider_name,
                    success=True,
                    response_length=len(response),
                    latency_ms=latency
                ))
                
            except Exception as e:
                results.append(ProviderTestResult(
                    provider_name=provider_name,
                    success=False,
                    error_message=str(e)[:100]
                ))
        
        # Print summary
        print("\n" + "=" * 60)
        print("Provider Comparison Results")
        print("=" * 60)
        for result in results:
            print(result)
        print("=" * 60)
        
        # At least one provider should work
        successful = sum(1 for r in results if r.success)
        self.assertGreater(successful, 0, "At least one provider should be available")


# NOTE: pytest_addoption and pytest_configure are now defined in the
# root conftest.py.  They are no longer needed in this test file.


if __name__ == "__main__":
    # When run directly, always run live tests
    import sys
    sys.argv.append("--run-live")
    unittest.main(verbosity=2)
