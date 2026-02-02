# CAISSA Provider Quick Reference

## 🚀 One-Liners for Each Provider

### OpenAI (GPT-4)
```python
from core.llm_provider import OpenAIProvider
provider = OpenAIProvider(model="gpt-4")  # Needs: OPENAI_API_KEY
```

### Anthropic (Claude)
```python
from core.llm_provider import AnthropicProvider
provider = AnthropicProvider(model="claude-3-5-sonnet-20241022")  # Needs: ANTHROPIC_API_KEY
```

### Azure OpenAI
```python
from core.llm_provider import AzureOpenAIProvider
provider = AzureOpenAIProvider(deployment_name="gpt-4")  # Needs: AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT
```

### Google Gemini
```python
from core.llm_provider import GoogleGeminiProvider
provider = GoogleGeminiProvider(model="gemini-pro")  # Needs: GOOGLE_API_KEY
```

### Ollama (FREE ⭐)
```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Pull a model
ollama pull mixtral
```
```python
from core.llm_provider import OllamaProvider
provider = OllamaProvider(model="mixtral")  # No API key needed!
```

### Mock (Testing)
```python
from core.llm_provider import MockProvider
provider = MockProvider(responses=["1. e4 e5 1-0", "1. d4 d5 1/2-1/2"])
```

---

## 📦 Installation Quick Start

```bash
# Core (required)
pip install openai tenacity python-chess

# Optional providers
pip install anthropic google-generativeai

# For Ollama
# Install from https://ollama.ai/ then:
ollama serve
ollama pull mixtral  # or llama2, mistral, codellama
```

---

## 🎯 Use Case Decision Tree

```
Need to generate chess games?
│
├─ Development/Testing?
│  └─ Use: Ollama (FREE) or MockProvider
│
├─ Privacy-sensitive?
│  └─ Use: Ollama (100% local) or Azure OpenAI (private)
│
├─ Best quality?
│  └─ Use: GPT-4 or Claude Opus
│
├─ Cheapest API?
│  └─ Use: Gemini Pro or GPT-3.5-turbo
│
└─ Enterprise compliance?
   └─ Use: Azure OpenAI
```

---

## 💰 Cost Comparison (per game)

| Provider | Model | Cost/Game | Notes |
|----------|-------|-----------|-------|
| Ollama | Any | **$0.00** | FREE, local, private ⭐ |
| Google | Gemini Pro | $0.0007 | Cheapest API |
| OpenAI | GPT-3.5-turbo | $0.0007 | Fast & cheap |
| Anthropic | Claude Sonnet | $0.006 | Good balance |
| OpenAI | GPT-4 | $0.014 | Highest quality |
| Anthropic | Claude Opus | $0.028 | Premium quality |

---

## ⚡ Performance Quick Facts

| Provider | Speed | Quality | Context | Privacy |
|----------|-------|---------|---------|---------|
| GPT-4 | 🐢 | ⭐⭐⭐⭐⭐ | 128K | ☁️ Cloud |
| Claude Sonnet | 🐇 | ⭐⭐⭐⭐⭐ | 200K | ☁️ Cloud |
| Gemini Pro | 🐇 | ⭐⭐⭐⭐ | 32K | ☁️ Cloud |
| Ollama (Mixtral) | 🐌* | ⭐⭐⭐⭐ | 32K | 🔒 Local |
| Ollama (Llama2) | 🐌* | ⭐⭐⭐ | 4K | 🔒 Local |

*Speed depends on your hardware (GPU recommended)

---

## 🔧 Troubleshooting One-Liners

```bash
# Check if API key is set
echo $OPENAI_API_KEY

# Set API key (temporary)
export OPENAI_API_KEY='sk-...'

# Install missing provider package
pip install anthropic  # or google-generativeai

# Test Ollama connection
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve

# Check GPU usage (NVIDIA)
nvidia-smi

# Pull Ollama model
ollama pull mixtral
```

---

## 📚 Complete Example

```python
#!/usr/bin/env python3
from core.llm_provider import OllamaProvider  # FREE!
from core.generator import GameGenerator
from core.prompt_manager import PromptManager

# Initialize provider (no API key needed!)
provider = OllamaProvider(model="mixtral")

# Create generator
prompt_manager = PromptManager()
generator = GameGenerator(provider, prompt_manager)

# Generate aesthetic chess game
game = generator.generate_game(
    aesthetic_goal="Romantic attacking chess with brilliant sacrifices",
    move_limit=20,
    max_retries=3
)

# Output
print(f"Generated {len(game.moves)} moves")
print(f"Opening: {game.metadata.opening}")
print(f"\n{game.pgn_str}")

# Save to file
with open("my_game.pgn", "w") as f:
    f.write(game.pgn_str)

print("\n✅ Saved to my_game.pgn")
```

---

## 🎨 Provider Switching

```python
# Switch providers at runtime
providers = {
    "openai": OpenAIProvider(model="gpt-4"),
    "anthropic": AnthropicProvider(model="claude-3-5-sonnet-20241022"),
    "google": GoogleGeminiProvider(model="gemini-pro"),
    "local": OllamaProvider(model="mixtral"),
}

# Select based on user preference or fallback
selected = "local"  # Use FREE local model!
provider = providers[selected]

generator = GameGenerator(provider, prompt_manager)
game = generator.generate_game("Tactical brilliancy", 15)
```

---

## 📖 More Info

- **Comprehensive Guide**: [MULTI_PROVIDER_GUIDE.md](MULTI_PROVIDER_GUIDE.md)
- **Implementation Details**: [MULTI_PROVIDER_IMPLEMENTATION.md](MULTI_PROVIDER_IMPLEMENTATION.md)
- **Tests**: [tests/test_multi_providers.py](tests/test_multi_providers.py)
- **Demo Script**: [script_multi_provider_demo.py](script_multi_provider_demo.py)

---

## ⭐ Recommended Setup

For the best experience, we recommend using **Ollama** for development:

1. **Install Ollama**: https://ollama.ai/
2. **Start server**: `ollama serve`
3. **Pull best model**: `ollama pull mixtral`
4. **Use in code**: `provider = OllamaProvider(model="mixtral")`

**Benefits:**
- ✅ 100% FREE (no API costs)
- ✅ 100% PRIVATE (no data sent externally)
- ✅ UNLIMITED generations
- ✅ Works OFFLINE
- ✅ Good quality (Mixtral matches GPT-3.5)

Then upgrade to paid APIs (GPT-4, Claude) for production if needed!

---

**Need help?** See the full guide: [MULTI_PROVIDER_GUIDE.md](MULTI_PROVIDER_GUIDE.md)
