#!/usr/bin/env python3
"""
Validation script for multi-provider support.
Tests provider initialization and configuration without making API calls.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.llm_provider import (
    LLMProvider,
    OpenAIProvider,
    AnthropicProvider,
    AzureOpenAIProvider,
    GoogleGeminiProvider,
    OllamaProvider,
    MockProvider,
)


def test_provider_interface():
    """Verify all providers implement LLMProvider interface."""
    print("\n✓ Testing Provider Interface Compliance")
    print("=" * 60)
    
    providers = [
        ("OpenAIProvider", OpenAIProvider),
        ("AnthropicProvider", AnthropicProvider),
        ("AzureOpenAIProvider", AzureOpenAIProvider),
        ("GoogleGeminiProvider", GoogleGeminiProvider),
        ("OllamaProvider", OllamaProvider),
        ("MockProvider", MockProvider),
    ]
    
    for name, provider_class in providers:
        # Check inheritance
        is_subclass = issubclass(provider_class, LLMProvider)
        
        # Check required methods
        has_generate = hasattr(provider_class, 'generate')
        
        status = "✅" if (is_subclass and has_generate) else "❌"
        print(f"{status} {name:25} | Inherits: {is_subclass} | Has generate(): {has_generate}")
    
    print("=" * 60)


def test_mock_provider():
    """Test MockProvider functionality."""
    print("\n✓ Testing MockProvider")
    print("=" * 60)
    
    responses = [
        "1. e4 e5 2. Nf3 Nc6 1-0",
        "1. d4 d5 2. c4 dxc4 1/2-1/2",
    ]
    
    provider = MockProvider(responses=responses)
    print(f"✅ Initialized with {len(responses)} responses")
    
    # Test first response
    r1 = provider.generate("system", "user", 0.8)
    print(f"✅ Response 1: {r1[:30]}...")
    
    # Test second response
    r2 = provider.generate("system", "user", 0.8)
    print(f"✅ Response 2: {r2[:30]}...")
    
    # Test exhaustion
    try:
        provider.generate("system", "user", 0.8)
        print("❌ Should have raised IndexError")
    except IndexError as e:
        print(f"✅ Correctly raises IndexError when exhausted")
    
    # Test reset
    provider.reset()
    r3 = provider.generate("system", "user", 0.8)
    assert r3 == responses[0]
    print(f"✅ Reset works correctly")
    
    print("=" * 60)


def test_ollama_provider_initialization():
    """Test OllamaProvider initialization."""
    print("\n✓ Testing OllamaProvider Initialization")
    print("=" * 60)
    
    try:
        # This will fail if Ollama isn't running, but that's OK for validation
        provider = OllamaProvider(model="llama2")
        print(f"✅ Initialized OllamaProvider with model: llama2")
        print(f"✅ Base URL: {provider.base_url}")
        print(f"✅ Max tokens: {provider.max_tokens}")
    except Exception as e:
        print(f"⚠️  OllamaProvider initialization warning: {str(e)[:50]}...")
        print(f"   (This is OK if Ollama server isn't running)")
    
    print("=" * 60)


def test_api_key_handling():
    """Test API key handling."""
    print("\n✓ Testing API Key Handling")
    print("=" * 60)
    
    # Test missing API key for OpenAI
    try:
        import os
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        
        try:
            OpenAIProvider()
            print("❌ Should have raised ValueError for missing OPENAI_API_KEY")
        except ValueError as e:
            print(f"✅ Correctly raises ValueError for missing OpenAI key")
        finally:
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key
    except Exception as e:
        print(f"⚠️  Test skipped: {e}")
    
    # Test provided API key
    try:
        provider = OpenAIProvider(api_key="sk-test-key")
        print(f"✅ Accepts provided API key without environment variable")
    except Exception as e:
        print(f"❌ Failed: {e}")
    
    print("=" * 60)


def test_provider_configuration():
    """Test provider configuration options."""
    print("\n✓ Testing Provider Configuration")
    print("=" * 60)
    
    # OpenAI with custom model
    try:
        provider = OpenAIProvider(
            api_key="sk-test",
            model="gpt-3.5-turbo",
            max_tokens=2048
        )
        print(f"✅ OpenAI: model={provider.model}, max_tokens={provider.max_tokens}")
    except Exception as e:
        print(f"❌ OpenAI config failed: {e}")
    
    # Ollama with custom base URL
    try:
        provider = OllamaProvider(
            model="mistral",
            base_url="http://192.168.1.100:11434"
        )
        print(f"✅ Ollama: model={provider.model}, base_url={provider.base_url}")
    except Exception as e:
        print(f"⚠️  Ollama config (connection warning OK): {str(e)[:40]}...")
    
    # MockProvider with multiple responses
    try:
        provider = MockProvider(responses=["response1", "response2", "response3"])
        print(f"✅ MockProvider: initialized with 3 responses")
    except Exception as e:
        print(f"❌ MockProvider failed: {e}")
    
    print("=" * 60)


def main():
    """Run all validation tests."""
    print("\n" + "🔍 " * 20)
    print("CAISSA Multi-Provider Validation")
    print("🔍 " * 20)
    
    print("\nThis script validates provider implementations without making API calls.")
    print("Note: Some warnings about connection failures are normal if services aren't running.")
    
    test_provider_interface()
    test_mock_provider()
    test_ollama_provider_initialization()
    test_api_key_handling()
    test_provider_configuration()
    
    print("\n" + "✅ " * 20)
    print("Validation Complete!")
    print("✅ " * 20)
    
    print("\n📚 Next Steps:")
    print("  1. Run full tests: pytest tests/test_multi_providers.py -v")
    print("  2. Try demo script: python script_multi_provider_demo.py")
    print("  3. Read guide: MULTI_PROVIDER_GUIDE.md")
    print()


if __name__ == "__main__":
    main()
