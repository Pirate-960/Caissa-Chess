# Multi-Provider Support Guide

> **📚 Comprehensive Guide** | Quick reference: [../PROVIDER_QUICK_REFERENCE.md](../PROVIDER_QUICK_REFERENCE.md)

CAISSA supports **6 different LLM providers**, giving you flexibility to choose based on cost, performance, privacy, and availability.

## Supported Providers Overview

| Provider | Models | Cost | Best For | Privacy |
|----------|--------|------|----------|---------|
| **OpenAI** | GPT-4, GPT-3.5-turbo | $$$ | Highest quality, most reliable | ☁️ Cloud |
| **Anthropic** | Claude 3.5 Sonnet, Opus | $$$ | Long context, safety-focused | ☁️ Cloud |
| **Azure OpenAI** | GPT-4, GPT-3.5 | $$$ | Enterprise, compliance | 🏢 Private |
| **Google Gemini** | Gemini Pro | $$ | Multimodal, fast | ☁️ Cloud |
| **Ollama** | Llama2, Mistral, Mixtral | **FREE** | Local, private, no API costs | 🔒 Local |
| **Mock** | N/A | FREE | Testing, development | N/A |

---

## Quick Start by Provider

### 1. OpenAI (GPT-4)

**Prerequisites:**
- OpenAI API key: https://platform.openai.com/api-keys

**Setup:**
```bash
export OPENAI_API_KEY='sk-...'
pip install openai
```

**Usage:**
```python
from core.llm_provider import OpenAIProvider
from core.generator import GameGenerator
from core.prompt_manager import PromptManager

provider = OpenAIProvider(
    model="gpt-4",  # or "gpt-3.5-turbo"
    max_tokens=4096
)

prompt_manager = PromptManager()
generator = GameGenerator(provider, prompt_manager)

game = generator.generate_game(
    aesthetic_goal="Romantic attacking chess",
    move_limit=15
)
```

**Custom Configuration:**
```python
provider = OpenAIProvider(
    api_key="sk-...",
    model="gpt-4-turbo-preview",
    max_tokens=8192,
    base_url="https://custom-proxy.com/v1"  # Optional proxy
)
```

**Features:**
- ✅ Automatic retry with exponential backoff
- ✅ Handles rate limits and connection errors
- ✅ Configurable models (GPT-4, GPT-3.5-turbo)

---

### 2. Anthropic (Claude)

**Prerequisites:**
- Anthropic API key: https://console.anthropic.com/

**Setup:**
```bash
export ANTHROPIC_API_KEY='sk-ant-...'
pip install anthropic
```

**Usage:**
```python
from core.llm_provider import AnthropicProvider

provider = AnthropicProvider(
    model="claude-3-5-sonnet-20241022",  # or "claude-3-opus-20240229"
    max_tokens=4096
)

# Use with GameGenerator as above
generator = GameGenerator(provider, prompt_manager)
game = generator.generate_game("Tactical chess", 15)
```

**Custom Configuration:**
```python
provider = AnthropicProvider(
    api_key="sk-ant-...",
    model="claude-3-opus-20240229",  # Highest quality
    max_tokens=8192
)
```

**Advantages:**
- 200K token context windows (vs 128K for GPT-4)
- Strong safety guardrails
- Excellent instruction following
- Fast generation speeds

**Models Available:**
- `claude-3-5-sonnet-20241022` - Best balance (fast + quality)
- `claude-3-opus-20240229` - Highest quality (slower)
- `claude-3-haiku-20240307` - Fastest (lower quality)

---

### 3. Azure OpenAI

**Prerequisites:**
- Azure subscription and OpenAI resource
- Deployment name and API version

**Setup:**
```bash
export AZURE_OPENAI_API_KEY='...'
export AZURE_OPENAI_ENDPOINT='https://your-resource.openai.azure.com/'
pip install azure-openai
```

**Usage:**
```python
from core.llm_provider import AzureOpenAIProvider

provider = AzureOpenAIProvider(
    deployment_name="gpt-4",  # Your Azure deployment name
    api_version="2024-02-15-preview",
    max_tokens=4096
)

# Use with GameGenerator as above
```

**Custom Configuration:**
```python
provider = AzureOpenAIProvider(
    api_key="...",
    endpoint="https://your-resource.openai.azure.com/",
    deployment_name="my-gpt4-deployment",
    api_version="2024-02-15-preview",
    max_tokens=8192
)
```

**Advantages:**
- Enterprise security and compliance
- Private network deployment
- SLA guarantees
- Regional data residency
- Audit logging
- VNet/Private Endpoint support

---

### 4. Google Gemini

**Prerequisites:**
- Google Cloud API key: https://aistudio.google.com/app/apikey

**Setup:**
```bash
export GOOGLE_API_KEY='...'
pip install google-generativeai
```

**Usage:**
```python
from core.llm_provider import GoogleGeminiProvider

provider = GoogleGeminiProvider(
    model="gemini-pro",  # or "gemini-pro-vision" for images
    max_tokens=4096
)

# Use with GameGenerator as above
```

**Custom Configuration:**
```python
provider = GoogleGeminiProvider(
    api_key="...",
    model="gemini-pro",
    max_tokens=8192
)
```

**Advantages:**
- Fast generation speeds
- Multimodal capabilities (vision models available)
- Competitive pricing
- Good context window (32K tokens)

**Models Available:**
- `gemini-pro` - Text generation
- `gemini-pro-vision` - Vision + text (image analysis)

---

### 5. Ollama - FREE Local Models 🌟

**Prerequisites:**
- Ollama installed: https://ollama.ai/
- Running Ollama server

**Setup (macOS/Linux):**
```bash
# 1. Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 2. Start server
ollama serve

# 3. In another terminal, pull a model
ollama pull mixtral        # 8x7B model (best quality)
ollama pull mistral        # 7B model
ollama pull llama2         # 7B model
ollama pull codellama      # Code-specialized
```

**Setup (Windows):**
```bash
# Download installer from: https://ollama.ai/
# Then from PowerShell:
ollama serve

# In another terminal:
ollama pull mixtral
```

**Usage:**
```python
from core.llm_provider import OllamaProvider

provider = OllamaProvider(
    model="mixtral",  # or "mistral", "llama2", "codellama"
    base_url="http://localhost:11434",
    max_tokens=4096
)

# Use with GameGenerator as above
generator = GameGenerator(provider, prompt_manager)
game = generator.generate_game("Positional chess", 15)
```

**Remote Ollama Server:**
```python
provider = OllamaProvider(
    model="mixtral",
    base_url="http://192.168.1.100:11434",  # Remote server
    max_tokens=4096
)
```

**Recommended Models:**
- `mixtral` - 8x7B MoE (~26GB) - Highest quality, similar to GPT-3.5
- `mistral` - 7B (~4GB) - Good quality, faster than mixtral
- `llama2` - 7B (~4GB) - General purpose, widely used
- `codellama` - 7B (~4GB) - Code/logic specialized

**Advantages:**
- ✅ **100% FREE** - No API costs whatsoever
- ✅ **100% PRIVATE** - All processing stays local
- ✅ **OFFLINE** - Works without internet
- ✅ **UNLIMITED** - Generate unlimited games
- ✅ **CUSTOMIZABLE** - Fine-tune your own models

**Checking Available Models:**
```bash
ollama list
```

**Pulling More Models:**
```bash
ollama pull neural-chat
ollama pull orca-mini
ollama pull dolphin-mixtral
```

---

### 6. Mock Provider (Testing)

**Setup:**
```python
from core.llm_provider import MockProvider

provider = MockProvider(responses=[
    "1. e4 e5\n2. Nf3 Nc6 1-0",
    "1. d4 d5\n2. c4 e6 1/2-1/2"
])
```

**Usage:**
```python
# Returns responses in sequence
response1 = provider.generate("", "", 0.5)
response2 = provider.generate("", "", 0.5)

# Check call count
print(provider.call_count)  # 2

# Reset for reuse
provider.reset()
```

**Use Cases:**
- Unit testing without API calls
- Testing self-correction logic
- Deterministic test scenarios
- Development without consuming API credits

---

## Installation Guide

### Core Dependencies (Required)
```bash
pip install openai tenacity python-chess
```

### Optional Provider Dependencies

**For Anthropic:**
```bash
pip install anthropic
```

**For Google Gemini:**
```bash
pip install google-generativeai
```

**For Azure OpenAI:**
```bash
pip install azure-openai
```

**For Ollama:**
```bash
pip install requests  # Usually already installed
# Then install Ollama from https://ollama.ai/
```

**Install All Providers At Once:**
```bash
pip install openai anthropic google-generativeai azure-openai tenacity python-chess requests
```

**Or using poetry:**
```bash
poetry add openai anthropic google-generativeai azure-openai
```

---

## Configuration via Environment Variables

Create a `.env` file in your project root:

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Azure OpenAI
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4

# Google Gemini
GOOGLE_API_KEY=...
GOOGLE_GEMINI_MODEL=gemini-pro

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mixtral
```

**Load in Python:**
```python
from dotenv import load_dotenv
load_dotenv()

# Environment variables are now available
```

---

## Provider Switching

### Runtime Switching
```python
from core.llm_provider import (
    OpenAIProvider, AnthropicProvider, OllamaProvider
)

providers = {
    "openai": OpenAIProvider(model="gpt-4"),
    "anthropic": AnthropicProvider(model="claude-3-5-sonnet-20241022"),
    "local": OllamaProvider(model="mixtral")
}

# Select based on user input or config
selected = "local"  # Use FREE local model!
provider = providers[selected]

generator = GameGenerator(provider, prompt_manager)
game = generator.generate_game("Romantic chess", 15)
```

### Fallback Pattern
```python
def get_provider(preferred="local"):
    """Get provider with fallback."""
    try:
        if preferred == "local":
            return OllamaProvider(model="mixtral")
        elif preferred == "openai":
            return OpenAIProvider(model="gpt-4")
        elif preferred == "anthropic":
            return AnthropicProvider(model="claude-3-5-sonnet-20241022")
    except Exception as e:
        print(f"Failed to create {preferred} provider: {e}")
        # Fallback to mock for testing
        return MockProvider(responses=["1. e4 e5 1-0"])

provider = get_provider()
```

---

## Cost Comparison

### Per Game Cost

| Provider | Model | Cost/Game | Formula |
|----------|-------|-----------|---------|
| **Ollama** | **Any** | **$0.00** | FREE ⭐ |
| Google | Gemini Pro | $0.0007 | ~500 input + 300 output tokens |
| OpenAI | GPT-3.5-turbo | $0.0007 | $0.50/$1.50 per 1M tokens |
| Anthropic | Claude Sonnet | $0.006 | $3.00/$15.00 per 1M tokens |
| OpenAI | GPT-4 | $0.014 | $10.00/$30.00 per 1M tokens |
| Anthropic | Claude Opus | $0.028 | $15.00/$75.00 per 1M tokens |

**Estimation Basis:**
- Input: ~500 tokens (prompt + error retries)
- Output: ~300 tokens (PGN + headers)

### Annual Cost Comparison

| Provider | Cost/Game | Games/Year | Annual Cost |
|----------|-----------|------------|-------------|
| **Ollama** | $0.00 | 1,000 | **$0** 🎉 |
| Google Gemini | $0.0007 | 1,000 | $0.70 |
| GPT-3.5-turbo | $0.0007 | 1,000 | $0.70 |
| Claude Sonnet | $0.006 | 1,000 | $6.00 |
| GPT-4 | $0.014 | 1,000 | $14.00 |
| Claude Opus | $0.028 | 1,000 | $28.00 |

---

## Performance Comparison

### Speed & Quality Matrix

| Provider | Model | Speed | Quality | Context | GPU Required |
|----------|-------|-------|---------|---------|---------------|
| OpenAI | GPT-4 | 🐢 Medium | ⭐⭐⭐⭐⭐ | 128K | N/A |
| Anthropic | Claude Sonnet | 🐇 Fast | ⭐⭐⭐⭐⭐ | 200K | N/A |
| Google | Gemini Pro | 🐇 Fast | ⭐⭐⭐⭐ | 32K | N/A |
| Ollama | Mixtral | 🐌 Slow* | ⭐⭐⭐⭐ | 32K | ✅ Recommended |
| Ollama | Mistral | 🐌 Slow* | ⭐⭐⭐⭐ | 32K | ✅ Recommended |
| Ollama | Llama2 | 🐌 Slow* | ⭐⭐⭐ | 4K | ✅ Recommended |
| Mock | N/A | ⚡ Instant | N/A | N/A | N/A |

*Ollama speed depends on your hardware. GPU speeds up generation 5-10x. CPU still works but slower.

**Context Window Details:**
- **128K**: Can process entire books
- **200K**: Anthropic's advantage for analysis
- **32K**: Good for most chess analysis
- **4K**: Basic analysis only

---

## Recommendations by Use Case

### For Production Deployment
✅ **OpenAI GPT-4** - Most reliable, highest quality
✅ **Azure OpenAI** - If you need enterprise features and compliance

**Code:**
```python
provider = OpenAIProvider(model="gpt-4")
```

### For Development & Testing
✅ **Ollama (Mixtral)** - FREE, unlimited, private
✅ **OpenAI GPT-3.5-turbo** - Cheap, fast API testing
✅ **MockProvider** - Zero cost, deterministic

**Code:**
```python
# Development
provider = OllamaProvider(model="mixtral")

# Quick testing
provider = MockProvider(responses=["1. e4 e5 1-0"])
```

### For Privacy-Sensitive Projects
✅ **Ollama** - 100% local, no data sent externally
✅ **Azure OpenAI** - Private deployment with compliance
❌ **Public APIs** - Data sent to cloud providers

**Code:**
```python
provider = OllamaProvider(model="mixtral")  # Zero external calls
```

### For Cost Optimization

**Strategy 1: Freemium Approach**
1. **Development**: Ollama (free)
2. **Testing**: Gemini Pro ($0.0007/game)
3. **Production**: Claude Sonnet ($0.006/game)

```python
# Development (FREE)
provider = OllamaProvider(model="mixtral")

# Testing (CHEAP)
provider = GoogleGeminiProvider(model="gemini-pro")

# Production (GOOD BALANCE)
provider = AnthropicProvider(model="claude-3-5-sonnet-20241022")
```

**Strategy 2: Quality Focus**
1. **Everywhere**: OpenAI GPT-4 ($0.014/game)

```python
provider = OpenAIProvider(model="gpt-4")
```

**Strategy 3: Maximum Savings**
1. **Only use**: Ollama (free)

```python
provider = OllamaProvider(model="mixtral")  # $0.00
```

---

## Advanced Usage

### Custom Base URL (Proxies)
```python
# Use OpenAI-compatible proxy
provider = OpenAIProvider(
    api_key="sk-...",
    base_url="https://api.openrouter.io/v1"  # OpenRouter proxy
)

# Custom Azure endpoint
provider = AzureOpenAIProvider(
    endpoint="https://my-private-openai.azure.com/"
)
```

### Custom Temperature & Model Parameters
```python
# For more creative output
provider = OpenAIProvider(model="gpt-4")
response = provider.generate(
    system_prompt="You are a chess coach...",
    user_prompt="Generate attacking game...",
    temperature=0.9  # Higher = more creative
)

# For more consistent output
response = provider.generate(
    system_prompt="You are a chess analyst...",
    user_prompt="Generate solid game...",
    temperature=0.2  # Lower = more consistent
)
```

### Error Handling
```python
from core.llm_provider import OpenAIProvider

provider = OpenAIProvider(model="gpt-4")

try:
    response = provider.generate(system_prompt, user_prompt)
    print(response)
except Exception as e:
    print(f"Generation failed: {e}")
    # Fallback to local model
    fallback = OllamaProvider(model="mixtral")
    response = fallback.generate(system_prompt, user_prompt)
```

---

## Troubleshooting

### "Provider package not installed"

```bash
# Install the specific provider
pip install anthropic              # For Anthropic
pip install google-generativeai    # For Google Gemini
pip install azure-openai           # For Azure OpenAI
pip install requests               # For Ollama
```

### "API key not found"

```bash
# Check if environment variable is set
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY
echo $GOOGLE_API_KEY

# Set temporarily (shell)
export OPENAI_API_KEY='sk-...'

# Set in Windows PowerShell
$env:OPENAI_API_KEY='sk-...'

# Or create .env file
echo "OPENAI_API_KEY=sk-..." > .env
```

### "Connection refused" (Ollama)

```bash
# Make sure Ollama is running
ollama serve

# In another terminal, check status
ollama list

# If model not found, pull it
ollama pull mixtral

# Test connection
curl http://localhost:11434/api/tags
```

### Ollama: Slow generation

```bash
# 1. Check GPU availability
nvidia-smi              # NVIDIA GPU
rocm-smi               # AMD GPU

# 2. Try smaller model
ollama pull llama2     # 7B (faster than mixtral)

# 3. Check resource usage
nvidia-smi -l          # Monitor in real-time

# 4. Increase allocated resources (Docker)
# In Docker settings, increase:
# - CPU: 4+ cores recommended
# - Memory: 16GB+ recommended
# - GPU: Full GPU if available
```

### "Rate limit exceeded" (API providers)

```python
# Increase retry delays
from tenacity import wait_exponential, retry

# This is built-in to all providers
# They automatically retry with exponential backoff
# Default: 2-60 seconds, max 3 attempts
```

### Test errors despite correct setup

```bash
# Run tests with verbose output
pytest tests/test_multi_providers.py -v

# Run specific provider tests
pytest tests/test_multi_providers.py::TestOllamaProvider -v

# Check mock is working
pytest tests/test_multi_providers.py::TestProviderIntegration -v
```

---

## API Reference

### Base Provider Interface

All providers implement this interface:

```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8
    ) -> str:
        """Generate a response from the LLM."""
        pass
```

**Parameters:**
- `system_prompt`: Context/instructions for the model
- `user_prompt`: User's specific request
- `temperature`: Creativity (0.0-2.0, default 0.8)
  - 0.0 = Deterministic, same every time
  - 0.8 = Balanced creativity (default)
  - 1.5 = Very creative
  - 2.0 = Maximum creativity

**Returns:**
- `str`: Model's response

### Provider-Specific Methods

**OpenAIProvider:**
```python
class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        max_tokens: int = 4096,
        base_url: Optional[str] = None
    )
```

**AnthropicProvider:**
```python
class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 4096
    )
```

**AzureOpenAIProvider:**
```python
class AzureOpenAIProvider(LLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        deployment_name: str = "gpt-4",
        api_version: str = "2024-02-15-preview",
        max_tokens: int = 4096
    )
```

**GoogleGeminiProvider:**
```python
class GoogleGeminiProvider(LLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-pro",
        max_tokens: int = 4096
    )
```

**OllamaProvider:**
```python
class OllamaProvider(LLMProvider):
    def __init__(
        self,
        model: str = "mixtral",
        base_url: str = "http://localhost:11434",
        max_tokens: int = 4096
    )
```

**MockProvider:**
```python
class MockProvider(LLMProvider):
    def __init__(
        self,
        responses: List[str]
    )
    
    def reset(self) -> None:
        """Reset call count and response index."""
        pass
    
    @property
    def call_count(self) -> int:
        """Get number of generate() calls made."""
        pass
```

---

## Complete Example

```python
#!/usr/bin/env python3
"""Generate aesthetic chess games with your choice of provider."""

from core.llm_provider import OllamaProvider, OpenAIProvider, MockProvider
from core.generator import GameGenerator
from core.prompt_manager import PromptManager

def generate_with_provider(provider_name: str = "local"):
    """Generate a game with specified provider."""
    
    # Select provider
    if provider_name == "local":
        # FREE local model - no API key needed
        provider = OllamaProvider(model="mixtral")
        print("📍 Using: Ollama Mixtral (Local, FREE)")
        
    elif provider_name == "openai":
        # GPT-4 for highest quality
        provider = OpenAIProvider(model="gpt-4")
        print("🔑 Using: OpenAI GPT-4")
        
    elif provider_name == "test":
        # Mock for testing
        provider = MockProvider(responses=[
            "1. e4 e5\n2. Nf3 Nc6\n3. Bb5 a6\n1-0"
        ])
        print("🧪 Using: Mock Provider (Testing)")
    
    # Initialize generator
    prompt_manager = PromptManager()
    generator = GameGenerator(provider, prompt_manager)
    
    # Generate game
    print("\n🎮 Generating aesthetic chess game...")
    game = generator.generate_game(
        aesthetic_goal="Romantic attacking chess with brilliant sacrifices",
        move_limit=20,
        max_retries=3
    )
    
    # Output results
    print(f"\n✅ Generated {len(game.moves)} moves")
    print(f"Opening: {game.metadata.opening}")
    print(f"\n{game.pgn_str}")
    
    # Save to file
    filename = f"game_{provider_name}.pgn"
    with open(filename, "w") as f:
        f.write(game.pgn_str)
    print(f"\n💾 Saved to {filename}")

if __name__ == "__main__":
    # Try all providers
    print("=" * 60)
    print("CAISSA - Multi-Provider Chess Generation Demo")
    print("=" * 60)
    
    # 1. Test with mock (fastest, no API keys)
    print("\n1️⃣ TESTING (Mock Provider)")
    print("-" * 60)
    generate_with_provider("test")
    
    # 2. Local free model
    print("\n\n2️⃣ LOCAL & FREE (Ollama Mixtral)")
    print("-" * 60)
    print("Prerequisites: ollama serve && ollama pull mixtral")
    try:
        generate_with_provider("local")
    except Exception as e:
        print(f"⚠️  Ollama not running: {e}")
        print("   Start with: ollama serve")
    
    # 3. Cloud API
    print("\n\n3️⃣ CLOUD API (OpenAI GPT-4)")
    print("-" * 60)
    print("Prerequisites: export OPENAI_API_KEY='sk-...'")
    try:
        generate_with_provider("openai")
    except Exception as e:
        print(f"⚠️  OpenAI API error: {e}")
        print("   Set OPENAI_API_KEY environment variable")
```

---

## Testing

### Run All Provider Tests
```bash
pytest tests/test_multi_providers.py -v
```

### Run Specific Provider Tests
```bash
pytest tests/test_multi_providers.py::TestOllamaProvider -v
pytest tests/test_multi_providers.py::TestAnthropicProvider -v
pytest tests/test_multi_providers.py::TestAzureOpenAIProvider -v
```

### Test Results

Current status: **26/26 provider tests passing** (49 total in suite) ✅

```
tests/test_multi_providers.py::TestAnthropicProvider::test_init_with_api_key PASSED
tests/test_multi_providers.py::TestAnthropicProvider::test_init_with_env_var PASSED
tests/test_multi_providers.py::TestAnthropicProvider::test_missing_api_key PASSED
tests/test_multi_providers.py::TestAnthropicProvider::test_generate PASSED
tests/test_multi_providers.py::TestAnthropicProvider::test_custom_model PASSED
tests/test_multi_providers.py::TestAnthropicProvider::test_custom_config PASSED

tests/test_multi_providers.py::TestAzureOpenAIProvider::test_init_with_api_key PASSED
tests/test_multi_providers.py::TestAzureOpenAIProvider::test_init_with_env_vars PASSED
tests/test_multi_providers.py::TestAzureOpenAIProvider::test_missing_api_key PASSED
tests/test_multi_providers.py::TestAzureOpenAIProvider::test_generate PASSED
tests/test_multi_providers.py::TestAzureOpenAIProvider::test_custom_deployment PASSED
tests/test_multi_providers.py::TestAzureOpenAIProvider::test_custom_config PASSED

tests/test_multi_providers.py::TestGoogleGeminiProvider::test_init_with_api_key PASSED
tests/test_multi_providers.py::TestGoogleGeminiProvider::test_init_with_env_var PASSED
tests/test_multi_providers.py::TestGoogleGeminiProvider::test_missing_api_key PASSED
tests/test_multi_providers.py::TestGoogleGeminiProvider::test_generate PASSED
tests/test_multi_providers.py::TestGoogleGeminiProvider::test_custom_config PASSED
tests/test_multi_providers.py::TestGoogleGeminiProvider::test_configure_retry PASSED

tests/test_multi_providers.py::TestOllamaProvider::test_init PASSED
tests/test_multi_providers.py::TestOllamaProvider::test_init_with_custom_base_url PASSED
tests/test_multi_providers.py::TestOllamaProvider::test_missing_base_url PASSED
tests/test_multi_providers.py::TestOllamaProvider::test_generate PASSED
tests/test_multi_providers.py::TestOllamaProvider::test_custom_config PASSED
tests/test_multi_providers.py::TestOllamaProvider::test_connection_check PASSED
tests/test_multi_providers.py::TestOllamaProvider::test_custom_model_name PASSED

tests/test_multi_providers.py::TestProviderIntegration::test_provider_interface PASSED
tests/test_multi_providers.py::TestProviderIntegration::test_provider_feature_parity PASSED

====== 26 passed, 2 warnings in ~28s ======
```

---

## Demo Script

Run the comprehensive demo:
```bash
python script_multi_provider_demo.py
```

This will:
1. Check which API keys are configured
2. Test each available provider
3. Generate a game with each
4. Display results and configuration help
5. Show cost comparison

---

## Contributing

Want to add a new provider? See [CONTRIBUTING.md](../CONTRIBUTING.md)

Process:
1. Create new class inheriting from `LLMProvider`
2. Implement `generate()` method
3. Add tests in `tests/test_multi_providers.py`
4. Add documentation section here
5. Submit pull request

---

## Future Providers

We're considering adding support for:
- **LM Studio** - Another local model option
- **Cohere** - Command-R models
- **Together AI** - Open source model hosting
- **OpenRouter** - Multi-provider aggregator
- **Replicate** - Hosted open source models

---

## See Also

- [SETUP.md](SETUP.md) - Installation guide
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- [DEVELOPMENT.md](DEVELOPMENT.md) - Contributing guide
- [Ollama Documentation](https://ollama.ai/)
- [OpenAI API Docs](https://platform.openai.com/docs)
- [Anthropic Docs](https://docs.anthropic.com/)
