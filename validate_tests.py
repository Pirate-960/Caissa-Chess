#!/usr/bin/env python3
"""
Quick validation script to check if tests can be imported and basic functionality works.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all providers can be imported."""
    print("Testing imports...")
    try:
        from core.llm_provider import (
            LLMProvider,
            OpenAIProvider,
            AnthropicProvider,
            AzureOpenAIProvider,
            GoogleGeminiProvider,
            OllamaProvider,
            MockProvider
        )
        print("✓ All provider classes imported successfully")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_mock_provider():
    """Test MockProvider functionality."""
    print("\nTesting MockProvider...")
    try:
        from core.llm_provider import MockProvider
        
        provider = MockProvider(responses=["Test response 1", "Test response 2"])
        result1 = provider.generate("System", "User prompt 1")
        result2 = provider.generate("System", "User prompt 2")
        
        assert result1 == "Test response 1", f"Expected 'Test response 1', got '{result1}'"
        assert result2 == "Test response 2", f"Expected 'Test response 2', got '{result2}'"
        print("✓ MockProvider works correctly")
        return True
    except Exception as e:
        print(f"✗ MockProvider test failed: {e}")
        return False

def test_openai_init():
    """Test OpenAI provider initialization."""
    print("\nTesting OpenAI initialization...")
    try:
        from core.llm_provider import OpenAIProvider
        from unittest.mock import patch
        
        with patch('os.getenv', return_value="test-key"):
            provider = OpenAIProvider()
            assert provider.model == "gpt-4"
            print("✓ OpenAI provider initializes correctly")
            return True
    except Exception as e:
        print(f"✗ OpenAI init test failed: {e}")
        return False

def test_azure_init():
    """Test Azure OpenAI provider initialization."""
    print("\nTesting Azure OpenAI initialization...")
    try:
        from core.llm_provider import AzureOpenAIProvider
        
        provider = AzureOpenAIProvider(
            api_key="test-key",
            azure_endpoint="https://test.openai.azure.com",
            deployment_name="gpt-4-test"
        )
        assert provider.deployment_name == "gpt-4-test"
        print("✓ Azure OpenAI provider initializes correctly")
        return True
    except Exception as e:
        print(f"✗ Azure init test failed: {e}")
        return False

def test_google_init():
    """Test Google Gemini provider initialization."""
    print("\nTesting Google Gemini initialization...")
    try:
        from core.llm_provider import GoogleGeminiProvider
        from unittest.mock import patch, MagicMock
        
        # Mock google.generativeai
        mock_genai = MagicMock()
        with patch.dict('sys.modules', {'google.generativeai': mock_genai}):
            with patch('os.getenv', return_value="test-key"):
                provider = GoogleGeminiProvider()
                assert provider.model == "gemini-1.5-pro"
                print("✓ Google Gemini provider initializes correctly")
                return True
    except Exception as e:
        print(f"✗ Google init test failed: {e}")
        return False

def test_ollama_init():
    """Test Ollama provider initialization."""
    print("\nTesting Ollama initialization...")
    try:
        from core.llm_provider import OllamaProvider
        
        provider = OllamaProvider(base_url="http://localhost:11434")
        assert provider.model == "mistral"
        assert provider.base_url == "http://localhost:11434"
        print("✓ Ollama provider initializes correctly")
        return True
    except Exception as e:
        print(f"✗ Ollama init test failed: {e}")
        return False

def test_anthropic_error():
    """Test Anthropic provider without API key."""
    print("\nTesting Anthropic error handling...")
    try:
        from core.llm_provider import AnthropicProvider
        from unittest.mock import patch
        
        with patch('os.getenv', return_value=None):
            try:
                provider = AnthropicProvider()
                print("✗ Expected ValueError not raised")
                return False
            except ValueError as e:
                if "Anthropic API key not provided" in str(e):
                    print("✓ Anthropic error handling works correctly")
                    return True
                else:
                    print(f"✗ Wrong error message: {e}")
                    return False
    except Exception as e:
        print(f"✗ Anthropic error test failed: {e}")
        return False

def main():
    """Run all validation tests."""
    print("=" * 60)
    print("CAISSA Multi-Provider Validation")
    print("=" * 60)
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("MockProvider", test_mock_provider()))
    results.append(("OpenAI Init", test_openai_init()))
    results.append(("Azure Init", test_azure_init()))
    results.append(("Google Init", test_google_init()))
    results.append(("Ollama Init", test_ollama_init()))
    results.append(("Anthropic Error", test_anthropic_error()))
    
    print("\n" + "=" * 60)
    print("Validation Results Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All validation tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
