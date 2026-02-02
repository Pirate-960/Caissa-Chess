# Multi-Provider Support

CAISSA now supports **6 different LLM providers**, giving you flexibility to choose based on cost, performance, privacy, and availability:

## Supported Providers

| Provider | Models | Cost | Best For |
|----------|--------|------|----------|
| **OpenAI** | GPT-4, GPT-3.5-turbo | $$$ | Highest quality, most reliable |
| **Anthropic** | Claude 3.5 Sonnet, Opus | $$$ | Long context, safety-focused |
| **Azure OpenAI** | GPT-4, GPT-3.5 | $$$ | Enterprise, compliance |
| **Google Gemini** | Gemini Pro | $$ | Multimodal, fast |
| **Ollama** | Llama2, Mistral, Mixtral, etc. | **FREE** | Local, private, no API costs |
| **Mock** | N/A | FREE | Testing, development |

---

## Quick Start

### 1. OpenAI (GPT-4)

**Setup:**
```bash
export OPENAI_API_KEY='sk-...'
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

---

### 2. Anthropic (Claude)

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
```

**Advantages:**
- Longer context windows (200K tokens)
- Strong safety guardrails
- Excellent instruction following

---

### 3. Azure OpenAI

**Setup:**
```bash
export AZURE_OPENAI_API_KEY='...'
export AZURE_OPENAI_ENDPOINT='https://your-resource.openai.azure.com/'
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

**Advantages:**
- Enterprise security and compliance
- Private network deployment
- SLA guarantees
- Regional data residency

---

### 4. Google Gemini

**Setup:**
```bash
export GOOGLE_API_KEY='...'
pip install google-generativeai
```

**Usage:**
```python
from core.llm_provider import GoogleGeminiProvider

provider = GoogleGeminiProvider(
    model="gemini-pro",  # or "gemini-pro-vision" for multimodal
    max_tokens=4096
)

# Use with GameGenerator as above
```

**Advantages:**
- Fast generation
- Multimodal capabilities (vision models)
- Competitive pricing

---

### 5. Ollama (Local Models) 🌟 **FREE & PRIVATE**

**Setup:**
```bash
# 1. Install Ollama
# macOS/Linux:
curl -fsSL https://ollama.ai/install.sh | sh

# Windows: Download from https://ollama.ai/

# 2. Start Ollama server
ollama serve

# 3. Pull a model
ollama pull llama2        # 7B model (~4GB)
ollama pull mistral       # 7B model (~4GB)
ollama pull mixtral       # 8x7B MoE (~26GB)
ollama pull codellama     # Code-specialized
```

**Usage:**
```python
from core.llm_provider import OllamaProvider

provider = OllamaProvider(
    model="llama2",  # or "mistral", "mixtral", "codellama"
    base_url="http://localhost:11434",
    max_tokens=4096
)

# Use with GameGenerator as above
```

**Advantages:**
- ✅ **100% FREE** - No API costs
- ✅ **100% PRIVATE** - All processing local
- ✅ **OFFLINE** - Works without internet
- ✅ **NO LIMITS** - Unlimited generations
- ✅ **CUSTOMIZABLE** - Fine-tune your own models

**Recommended Models:**
- `llama2` - Good general purpose (7B)
- `mistral` - Better quality (7B)
- `mixtral` - Highest quality (8x7B)
- `codellama` - Code/logic tasks (7B)

---

## Installation

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

**For Ollama:**
```bash
pip install requests  # Usually already installed
```

**All at once:**
```bash
pip install openai anthropic google-generativeai tenacity python-chess requests
```

---

## Configuration

### Environment Variables

Create a `.env` file in your project root:

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Azure OpenAI
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# Google Gemini
GOOGLE_API_KEY=...
```

Load with:
```python
from dotenv import load_dotenv
load_dotenv()
```

---

## Advanced Usage

### Provider Comparison Script

Run the demo to test all providers:

```bash
python script_multi_provider_demo.py
```

This will:
1. Check which API keys are configured
2. Test each available provider
3. Generate a game with each
4. Display results and configuration help

### Custom Configuration

All providers support custom configuration:

```python
# OpenAI with custom settings
provider = OpenAIProvider(
    api_key="sk-...",
    model="gpt-4-turbo-preview",
    max_tokens=8192,
    base_url="https://custom-proxy.com/v1"  # Optional proxy
)

# Anthropic with custom model
provider = AnthropicProvider(
    api_key="sk-ant-...",
    model="claude-3-opus-20240229",  # Highest quality
    max_tokens=8192
)

# Ollama with remote server
provider = OllamaProvider(
    model="mixtral",
    base_url="http://192.168.1.100:11434",  # Remote Ollama server
    max_tokens=8192
)
```

### Switching Providers at Runtime

```python
from core.llm_provider import OpenAIProvider, OllamaProvider
from core.generator import GameGenerator
from core.prompt_manager import PromptManager

prompt_manager = PromptManager()

# Start with OpenAI
provider = OpenAIProvider(model="gpt-4")
generator = GameGenerator(provider, prompt_manager)
game1 = generator.generate_game("Romantic chess", 15)

# Switch to local Ollama (no API costs!)
provider = OllamaProvider(model="mixtral")
generator = GameGenerator(provider, prompt_manager)
game2 = generator.generate_game("Positional chess", 15)
```

---

## Testing

Run tests for all providers:

```bash
# Test all providers
pytest tests/test_multi_providers.py -v

# Test specific provider
pytest tests/test_multi_providers.py::TestAnthropicProvider -v
pytest tests/test_multi_providers.py::TestOllamaProvider -v
```

---

## Cost Comparison

| Provider | Model | Cost per 1M input tokens | Cost per 1M output tokens |
|----------|-------|--------------------------|---------------------------|
| OpenAI | GPT-4 | $10.00 | $30.00 |
| OpenAI | GPT-3.5-turbo | $0.50 | $1.50 |
| Anthropic | Claude 3.5 Sonnet | $3.00 | $15.00 |
| Anthropic | Claude 3 Opus | $15.00 | $75.00 |
| Google | Gemini Pro | $0.50 | $1.50 |
| Azure | GPT-4 | $10.00 | $30.00 |
| **Ollama** | **Any model** | **$0.00** | **$0.00** ✨ |

**Estimate for generating one chess game:**
- Input: ~500 tokens (prompt + retries)
- Output: ~300 tokens (PGN + headers)

**Cost per game:**
- GPT-4: ~$0.014
- Claude Sonnet: ~$0.006
- GPT-3.5/Gemini: ~$0.0007
- **Ollama: $0.00** 🎉

---

## Performance Comparison

Based on informal testing with aesthetic chess generation:

| Provider | Model | Quality | Speed | Context | Best Use Case |
|----------|-------|---------|-------|---------|---------------|
| OpenAI | GPT-4 | ⭐⭐⭐⭐⭐ | 🐢 Medium | 8K-128K | Highest quality games |
| Anthropic | Claude Sonnet | ⭐⭐⭐⭐⭐ | 🐇 Fast | 200K | Long analysis, safety |
| Azure | GPT-4 | ⭐⭐⭐⭐⭐ | 🐢 Medium | 8K-128K | Enterprise deployments |
| Google | Gemini Pro | ⭐⭐⭐⭐ | 🐇 Fast | 32K | Quick generations |
| Ollama | Mixtral | ⭐⭐⭐⭐ | 🐌 Slow* | 32K | Private/free |
| Ollama | Llama2 | ⭐⭐⭐ | 🐌 Slow* | 4K | Private/free |

*Local speed depends on your hardware (GPU recommended)

---

## Recommendations

### For Production
✅ **OpenAI GPT-4** - Most reliable and highest quality
✅ **Azure OpenAI** - If you need enterprise features

### For Development
✅ **Ollama (Mixtral)** - Free, private, unlimited testing
✅ **OpenAI GPT-3.5-turbo** - Fast and cheap API testing

### For Privacy-Sensitive Projects
✅ **Ollama** - 100% local, no data sent externally
✅ **Azure OpenAI** - Private deployment with compliance

### For Cost Optimization
1. **Development**: Ollama (free)
2. **Testing**: GPT-3.5-turbo or Gemini Pro ($0.0007/game)
3. **Production**: Claude Sonnet ($0.006/game) or GPT-4 ($0.014/game)

---

## Troubleshooting

### "Provider package not installed"

```bash
# Install missing provider
pip install anthropic              # For Anthropic
pip install google-generativeai    # For Google Gemini
pip install requests               # For Ollama (usually already installed)
```

### "API key not found"

```bash
# Check your environment variables
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY

# Set temporarily
export OPENAI_API_KEY='sk-...'

# Or use .env file
echo "OPENAI_API_KEY=sk-..." >> .env
```

### Ollama: "Connection refused"

```bash
# Make sure Ollama is running
ollama serve

# In another terminal, verify it's working
ollama list

# Pull a model if needed
ollama pull llama2
```

### Ollama: Slow generation

- **Use GPU**: Ollama automatically uses GPU if available
- **Check GPU usage**: `nvidia-smi` (NVIDIA) or `amdgpu-top` (AMD)
- **Try smaller model**: `llama2` (7B) is faster than `mixtral` (47B)
- **Increase resources**: Give Docker more RAM/CPU if using containers

---

## Future Providers

We're considering adding support for:
- **LM Studio** - Another local model option
- **Cohere** - Command-R models
- **Together AI** - Open source model hosting
- **OpenRouter** - Multi-provider aggregator

Want to add a provider? See [CONTRIBUTING.md](CONTRIBUTING.md)

---

## API Reference

### Base Provider Interface

```python
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

All providers implement this interface, ensuring drop-in compatibility.

---

## See Also

- [Architecture Documentation](ARCHITECTURE.md)
- [Development Roadmap](DEVELOPMENT_ROADMAP.md)
- [Contributing Guide](CONTRIBUTING.md)
- [Ollama Documentation](https://ollama.ai/)
