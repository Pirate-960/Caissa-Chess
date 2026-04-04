"""
core/provider_factory.py

Unified LLM provider factory.
Single source of truth for creating provider instances from config.

Usage:
    from core.provider_factory import create_provider
    provider = create_provider("openai")          # uses config defaults
    provider = create_provider("openai", cfg=cfg) # explicit config
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def create_provider(provider_name: str, cfg=None):
    """
    Create an LLM provider instance.
    
    Resolves API keys from:
      1. Environment variables (highest priority)
      2. Config object (caissa_config.yaml)
      3. Provider defaults
    
    Args:
        provider_name: One of 'openai', 'anthropic', 'gemini', 'deepseek', 'ollama', 'azure'
        cfg: Optional CaissaConfig instance. If None, loads from config_manager.
        
    Returns:
        An LLMProvider instance
        
    Raises:
        ValueError: If provider is unknown or API key is missing
    """
    from core.llm_provider import (
        OpenAIProvider,
        AnthropicProvider,
        GoogleGeminiProvider,
        OllamaProvider,
        AzureOpenAIProvider,
    )
    
    if cfg is None:
        try:
            from config_manager import load_config
            cfg = load_config()
        except Exception:
            cfg = None
    
    provider_name = provider_name.lower().strip()
    logger.info("Creating provider: %s", provider_name)
    
    if provider_name == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL", "gpt-4o")
        if cfg:
            api_key = api_key or cfg.llm.openai_api_key
            model = cfg.llm.openai_model or model
        if not api_key or api_key.startswith("sk-..."):
            raise ValueError(
                "OPENAI_API_KEY not configured. "
                "Set it in .env or caissa_config.yaml"
            )
        return OpenAIProvider(api_key=api_key, model=model)
    
    elif provider_name == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        if cfg:
            api_key = api_key or cfg.llm.anthropic_api_key
            model = cfg.llm.anthropic_model or model
        if not api_key or api_key.startswith("sk-ant-..."):
            raise ValueError(
                "ANTHROPIC_API_KEY not configured. "
                "Set it in .env or caissa_config.yaml"
            )
        return AnthropicProvider(api_key=api_key, model=model)
    
    elif provider_name == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY")
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        if cfg:
            api_key = api_key or cfg.llm.google_api_key
            model = cfg.llm.gemini_model or model
        if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
            raise ValueError(
                "GOOGLE_API_KEY not configured. "
                "Set it in .env or caissa_config.yaml"
            )
        return GoogleGeminiProvider(api_key=api_key, model=model)
    
    elif provider_name == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        if cfg:
            api_key = api_key or cfg.llm.deepseek_api_key
            model = cfg.llm.deepseek_model or model
        if not api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY not configured. "
                "Set it in .env or caissa_config.yaml"
            )
        return OpenAIProvider(
            api_key=api_key,
            model=model,
            base_url="https://api.deepseek.com",
        )
    
    elif provider_name == "ollama":
        model = os.getenv("OLLAMA_MODEL", "llama2")
        base_url = "http://localhost:11434"
        if cfg:
            model = cfg.llm.ollama_model or model
            base_url = cfg.llm.ollama_base_url or base_url
        return OllamaProvider(model=model, base_url=base_url)
    
    elif provider_name == "azure":
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
        api_version = "2024-02-15-preview"
        if cfg:
            api_key = api_key or getattr(cfg.llm, 'openai_api_key', None)
            endpoint = endpoint or getattr(cfg.llm, 'azure_endpoint', None)
            deployment = getattr(cfg.llm, 'azure_deployment', None) or deployment
            api_version = getattr(cfg.llm, 'azure_api_version', None) or api_version
        return AzureOpenAIProvider(
            api_key=api_key,
            azure_endpoint=endpoint,
            deployment_name=deployment,
            api_version=api_version,
        )
    
    else:
        supported = "openai, anthropic, gemini, deepseek, ollama, azure"
        raise ValueError(
            f"Unknown provider: '{provider_name}'. Supported: {supported}"
        )


def get_supported_providers():
    """Return list of supported provider names."""
    return ["openai", "anthropic", "gemini", "deepseek", "ollama", "azure"]
