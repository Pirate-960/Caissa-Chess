#!/usr/bin/env python3
"""
tests/test_multi_providers.py

Comprehensive tests for all LLM providers.
Tests initialization, configuration, and basic functionality for:
- AnthropicProvider
- AzureOpenAIProvider
- GoogleGeminiProvider
- OllamaProvider
"""

import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from core.llm_provider import (
    AnthropicProvider,
    AzureOpenAIProvider,
    GoogleGeminiProvider,
    OllamaProvider,
)


# ============================================================================
# Anthropic Provider Tests
# ============================================================================

class TestAnthropicProvider:
    """Test suite for Anthropic Claude provider."""
    
    def test_initialization_without_key_raises_error(self):
        """Should raise ValueError if no API key provided."""
        with patch('os.getenv', return_value=None):
            with pytest.raises(ValueError, match="Anthropic API key not provided"):
                AnthropicProvider()
    
    def test_initialization_with_api_key(self):
        """Should initialize with provided API key."""
        with patch('anthropic.Anthropic'):
            provider = AnthropicProvider(api_key="sk-ant-test-key")
            assert provider.model == "claude-3-5-sonnet-20241022"
            assert provider.max_tokens == 4096
    
    def test_initialization_from_env(self):
        """Should read API key from environment variable."""
        with patch('os.getenv', return_value="sk-ant-env-key"):
            with patch('anthropic.Anthropic'):
                provider = AnthropicProvider()
                assert provider.api_key == "sk-ant-env-key"
    
    def test_custom_model_configuration(self):
        """Should support custom model selection."""
        with patch('anthropic.Anthropic'):
            provider = AnthropicProvider(
                api_key="sk-ant-test",
                model="claude-3-opus-20240229",
                max_tokens=8192
            )
            assert provider.model == "claude-3-opus-20240229"
            assert provider.max_tokens == 8192
    
    def test_generate_success(self):
        """Should generate response successfully."""
        mock_response = Mock()
        mock_response.content = [Mock(text="1. e4 e5 2. Nf3 Nc6")]
        
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        
        with patch('anthropic.Anthropic', return_value=mock_client):
            provider = AnthropicProvider(api_key="sk-ant-test")
            
            result = provider.generate(
                system_prompt="You are a chess expert",
                user_prompt="Generate a game",
                temperature=0.8
            )
            
            assert result == "1. e4 e5 2. Nf3 Nc6"
            mock_client.messages.create.assert_called_once()
    
    def test_missing_package_raises_import_error(self):
        """Should raise ImportError if anthropic package not installed."""
        # When anthropic is installed, this test verifies graceful error handling
        with patch('anthropic.Anthropic', side_effect=ImportError("No module named 'anthropic'")):
            with pytest.raises(ImportError):
                AnthropicProvider(api_key="sk-ant-test")


# ============================================================================
# Azure OpenAI Provider Tests
# ============================================================================

class TestAzureOpenAIProvider:
    """Test suite for Azure OpenAI provider."""
    
    def test_initialization_with_credentials(self):
        """Should initialize with provided credentials."""
        provider = AzureOpenAIProvider(
            api_key="test-key",
            azure_endpoint="https://test.openai.azure.com",
            deployment_name="gpt-4-test"
        )
        assert provider.deployment_name == "gpt-4-test"
        assert provider.max_tokens == 4096
    
    def test_initialization_from_env(self):
        """Should read credentials from environment variables."""
        with patch('core.llm_provider.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda x: {
                "AZURE_OPENAI_API_KEY": "env-key",
                "AZURE_OPENAI_ENDPOINT": "https://env.openai.azure.com"
            }.get(x)
            
            provider = AzureOpenAIProvider()
            assert provider.api_key == "env-key"
            assert provider.azure_endpoint == "https://env.openai.azure.com"
    
    def test_initialization_without_key_raises_error(self):
        """Should raise ValueError if no API key provided."""
        with patch('core.llm_provider.os.getenv', return_value=None):
            with pytest.raises(ValueError, match="Azure OpenAI API key not provided"):
                AzureOpenAIProvider(azure_endpoint="https://test.com")
    
    def test_initialization_without_endpoint_raises_error(self):
        """Should raise ValueError if no endpoint provided."""
        with patch('core.llm_provider.os.getenv', return_value=None):
            with pytest.raises(ValueError, match="Azure endpoint not provided"):
                AzureOpenAIProvider(api_key="test-key")
    
    def test_custom_configuration(self):
        """Should support custom deployment and API version."""
        provider = AzureOpenAIProvider(
            api_key="test-key",
            azure_endpoint="https://test.com",
            deployment_name="gpt-35-turbo",
            api_version="2023-05-15",
            max_tokens=2048
        )
        assert provider.deployment_name == "gpt-35-turbo"
        assert provider.max_tokens == 2048
    
    def test_generate_success(self):
        """Should generate response successfully."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="1. e4 e5 1-0"))]
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        
        with patch('core.llm_provider.AzureOpenAI', return_value=mock_client):
            provider = AzureOpenAIProvider(
                api_key="test-key",
                azure_endpoint="https://test.com"
            )
            
            result = provider.generate(
                system_prompt="You are a chess expert",
                user_prompt="Generate a game",
                temperature=0.7
            )
            
            assert result == "1. e4 e5 1-0"
            mock_client.chat.completions.create.assert_called_once()


# ============================================================================
# Google Gemini Provider Tests
# ============================================================================

class TestGoogleGeminiProvider:
    """Test suite for Google Gemini provider."""
    
    def test_initialization_with_api_key(self):
        """Should initialize with provided API key."""
        with patch('google.generativeai.configure'):
            with patch('google.generativeai.GenerativeModel'):
                provider = GoogleGeminiProvider(api_key="test-key")
                assert provider.model == "gemini-pro"
                assert provider.max_tokens == 4096
    
    def test_initialization_from_env(self):
        """Should read API key from environment variable."""
        with patch('os.getenv', return_value="env-key"):
            with patch('google.generativeai.configure'):
                with patch('google.generativeai.GenerativeModel'):
                    provider = GoogleGeminiProvider()
                    assert provider.api_key == "env-key"
    
    def test_initialization_without_key_raises_error(self):
        """Should raise ValueError if no API key provided."""
        with patch('os.getenv', return_value=None):
            with pytest.raises(ValueError, match="Google API key not provided"):
                GoogleGeminiProvider()
    
    def test_custom_model_configuration(self):
        """Should support custom model selection."""
        with patch('google.generativeai.configure'):
            with patch('google.generativeai.GenerativeModel'):
                provider = GoogleGeminiProvider(
                    api_key="test-key",
                    model="gemini-pro-vision",
                    max_tokens=8192
                )
                assert provider.model == "gemini-pro-vision"
                assert provider.max_tokens == 8192
    
    def test_generate_success(self):
        """Should generate response successfully."""
        mock_response = Mock()
        mock_response.text = "1. e4 e5 2. Nf3 1-0"
        
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        
        with patch('google.generativeai.configure'):
            with patch('google.generativeai.GenerativeModel', return_value=mock_model):
                provider = GoogleGeminiProvider(api_key="test-key")
                
                result = provider.generate(
                    system_prompt="You are a chess expert",
                    user_prompt="Generate a game",
                    temperature=0.9
                )
                
                assert result == "1. e4 e5 2. Nf3 1-0"
                mock_model.generate_content.assert_called_once()
    
    def test_missing_package_raises_import_error(self):
        """Should raise ImportError if google-generativeai not installed."""
        with patch('builtins.__import__', side_effect=ImportError("No module named 'google'")):
            with pytest.raises(ImportError, match="google-generativeai package required"):
                GoogleGeminiProvider(api_key="test-key")


# ============================================================================
# Ollama Provider Tests
# ============================================================================

class TestOllamaProvider:
    """Test suite for Ollama local model provider."""
    
    def test_initialization_default_config(self):
        """Should initialize with default configuration."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            provider = OllamaProvider()
            assert provider.model == "llama2"
            assert provider.base_url == "http://localhost:11434"
            assert provider.max_tokens == 4096
    
    def test_initialization_custom_config(self):
        """Should support custom model and URL."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            provider = OllamaProvider(
                model="mistral",
                base_url="http://192.168.1.100:11434",
                max_tokens=2048
            )
            assert provider.model == "mistral"
            assert provider.base_url == "http://192.168.1.100:11434"
            assert provider.max_tokens == 2048
    
    def test_connection_test_on_init(self):
        """Should test connection to Ollama server on initialization."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            OllamaProvider()
            mock_get.assert_called_once_with(
                "http://localhost:11434/api/tags",
                timeout=5
            )
    
    def test_initialization_warns_on_connection_failure(self):
        """Should warn if cannot connect to Ollama server."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            
            # Should still initialize but log warning
            with patch('core.llm_provider.logger.warning') as mock_warning:
                provider = OllamaProvider()
                assert provider.model == "llama2"
                assert mock_warning.call_count == 2
    
    def test_generate_success(self):
        """Should generate response successfully."""
        with patch('requests.get') as mock_get:
            with patch('requests.post') as mock_post:
                # Mock connection test
                mock_test_response = Mock()
                mock_test_response.raise_for_status = Mock()
                
                # Mock generation
                mock_gen_response = Mock()
                mock_gen_response.raise_for_status = Mock()
                mock_gen_response.json.return_value = {
                    "response": "1. e4 e5 2. Nf3 Nc6 1-0"
                }
                
                mock_get.return_value = mock_test_response
                mock_post.return_value = mock_gen_response
                
                provider = OllamaProvider()
                
                result = provider.generate(
                    system_prompt="You are a chess expert",
                    user_prompt="Generate a game",
                    temperature=0.8
                )
                
                assert result == "1. e4 e5 2. Nf3 Nc6 1-0"
                mock_post.assert_called_once()
                
                # Check request payload
                call_args = mock_post.call_args
                assert call_args[1]["json"]["model"] == "llama2"
                assert call_args[1]["json"]["temperature"] == 0.8
    
    def test_missing_package_raises_import_error(self):
        """Should raise ImportError if requests package not installed."""
        with patch('builtins.__import__', side_effect=ImportError("No module named 'requests'")):
            with pytest.raises(ImportError, match="requests package required"):
                OllamaProvider()


# ============================================================================
# Integration Tests
# ============================================================================

class TestProviderIntegration:
    """Integration tests for provider compatibility."""
    
    def test_all_providers_implement_interface(self):
        """Should verify all providers implement LLMProvider interface."""
        from core.llm_provider import LLMProvider
        
        providers = [
            AnthropicProvider,
            AzureOpenAIProvider,
            GoogleGeminiProvider,
            OllamaProvider,
        ]
        
        for provider_class in providers:
            assert issubclass(provider_class, LLMProvider)
            
            # Check required methods exist
            assert hasattr(provider_class, 'generate')
            assert callable(getattr(provider_class, 'generate'))
    
    def test_all_providers_support_temperature(self):
        """Should verify all providers accept temperature parameter."""
        # This is implicitly tested in each provider's test_generate_success
        # but we verify the signature here
        from inspect import signature
        
        providers = [
            AnthropicProvider,
            AzureOpenAIProvider,
            GoogleGeminiProvider,
            OllamaProvider,
        ]
        
        for provider_class in providers:
            sig = signature(provider_class.generate)
            assert 'temperature' in sig.parameters
