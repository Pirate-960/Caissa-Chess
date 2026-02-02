# CAISSA Setup & Configuration Guide

Complete guide for installing CAISSA and configuring all 6 LLM providers.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Project Structure](#project-structure)
4. [Initial Testing](#initial-testing)
5. [LLM Provider Setup](#llm-provider-setup)
6. [API Configuration](#api-configuration)
7. [Verification](#verification)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- **Python 3.11 or 3.12**
- **Poetry 1.7.0+** - Dependency manager
  ```bash
  # Install Poetry (if you don't have it)
  curl -sSL https://install.python-poetry.org | python3 -
  ```
- **Git 2.0+** - Version control
- **(Optional) Stockfish 16+** - For local engine testing

---

## Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/Pirate-960/Caissa-Chess.git
cd Caissa-Chess
```

### Step 2: Create Virtual Environment & Install Dependencies

```bash
# Install all dependencies using Poetry
poetry install

# This installs:
# - python-chess (chess logic)
# - openai, anthropic, google-generativeai, azure-openai (LLM APIs)
# - requests, tenacity (HTTP and retry logic)
# - pydantic (configuration & validation)
# - pytest (testing framework)
# - black, flake8, mypy (code quality)
# - And other dependencies specified in pyproject.toml
```

### Step 3: Verify Installation

```bash
# Test that Poetry environment is set up correctly
poetry run python --version

# Run basic tests (no API keys needed)
poetry run pytest tests/test_multi_providers.py -v

# Should show: 26 passed, 2 warnings
```

---

## Project Structure

```
Caissa-Chess/
├── core/                          # Main generation pipeline
│   ├── generator.py               # Game orchestrator
│   ├── board_state.py             # Chess board state
│   ├── prompt_manager.py          # LLM prompt assembly
│   └── llm_provider.py            # Multi-provider LLM interface
│
├── engine/                        # Validation & analysis
│   ├── legality.py                # Move validation
│   └── __init__.py
│
├── aesthetic/                     # Beauty evaluation
│   ├── beauty_eval.py             # Brilliance scoring
│   └── style_slider.py            # Style presets
│
├── export/                        # Output formatting
│   └── pgn_builder.py             # PGN generation
│
├── tests/                         # Test suite
│   ├── test_legality.py
│   └── test_multi_providers.py    # Provider tests (26 tests)
│
├── data/                          # Reference data
│   └── openings.json              # ECO codes
│
├── docs/                          # Documentation
│   ├── SETUP.md                   # This file
│   ├── PROVIDERS.md               # LLM provider guide
│   ├── ARCHITECTURE.md            # System design
│   ├── DEVELOPMENT.md             # Contributing guide
│   └── ROADMAP.md                 # Project roadmap
│
└── caissa.py                      # CLI entry point
```

---

## Initial Testing

Test core components without needing an LLM API key:

```bash
# Run all tests
poetry run pytest tests/ -v

# Run only provider tests
poetry run pytest tests/test_multi_providers.py -v

# Run with coverage
poetry run pytest tests/ --cov --cov-report=term-missing

# Run legality validator tests
poetry run pytest tests/test_legality.py -v

# Expected output: 26 passed, 2 warnings in ~28 seconds
```

---

## LLM Provider Setup

CAISSA supports **6 different LLM providers**. Choose one or multiple based on your needs.

### Quick Summary

| Provider | API Key | Cost | Best For |
|----------|---------|------|----------|
| **OpenAI** | OPENAI_API_KEY | $$$ | Highest quality |
| **Anthropic (Claude)** | ANTHROPIC_API_KEY | $$$ | Long context, safety |
| **Azure OpenAI** | AZURE_OPENAI_* | $$$ | Enterprise, compliance |
| **Google Gemini** | GOOGLE_API_KEY | $$ | Fast, multimodal |
| **Ollama** | OLLAMA_BASE_URL | **FREE** | Local, private |
| **Mock** | N/A | **FREE** | Testing |

### Creating .env File

Create a `.env` file in the project root:

```bash
# Using any text editor or command line:
cat > .env << 'EOF'
# OpenAI
OPENAI_API_KEY=sk-proj-your-key-here

# Anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Azure OpenAI
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# Google Gemini
GOOGLE_API_KEY=AIza-your-key-here

# Ollama (optional, defaults to localhost:11434)
OLLAMA_BASE_URL=http://localhost:11434
EOF
```

**IMPORTANT**: Add `.env` to `.gitignore`:
```bash
echo ".env" >> .gitignore
```

---

## API Configuration

### OpenAI (GPT-4)

1. **Get API Key**
   - Go to https://platform.openai.com/api-keys
   - Create a new API key
   - Copy it

2. **Add to .env**
   ```
   OPENAI_API_KEY=sk-proj-xxxxxxxxxxxx
   ```

3. **Verify**
   ```bash
   poetry run python -c "from core.llm_provider import OpenAIProvider; print('✓ OpenAI configured')"
   ```

### Anthropic (Claude 3.5 Sonnet)

1. **Get API Key**
   - Go to https://console.anthropic.com/
   - Create API key
   - Copy it

2. **Add to .env**
   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
   ```

3. **Install Package** (if not installed)
   ```bash
   poetry add anthropic
   ```

4. **Verify**
   ```bash
   poetry run python -c "from core.llm_provider import AnthropicProvider; print('✓ Anthropic configured')"
   ```

5. **Run Tests**
   ```bash
   poetry run pytest tests/test_multi_providers.py::TestAnthropicProvider -v
   ```

### Azure OpenAI

1. **Get Credentials**
   - Log in to Azure portal
   - Create OpenAI resource
   - Get deployment name, API key, and endpoint

2. **Add to .env**
   ```
   AZURE_OPENAI_API_KEY=your-key
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   ```

3. **Verify**
   ```bash
   poetry run python -c "from core.llm_provider import AzureOpenAIProvider; print('✓ Azure configured')"
   ```

### Google Gemini

1. **Get API Key**
   - Go to https://makersuite.google.com/app/apikey
   - Create API key
   - Copy it

2. **Add to .env**
   ```
   GOOGLE_API_KEY=AIza-xxxxxxxxxxxx
   ```

3. **Verify**
   ```bash
   poetry run python -c "from core.llm_provider import GoogleGeminiProvider; print('✓ Google configured')"
   ```

### Ollama (Local - FREE!)

1. **Download & Install**
   - Go to https://ollama.ai
   - Download for your OS
   - Run the installer

2. **Start Ollama Server**
   ```bash
   ollama serve
   ```
   - Runs on http://localhost:11434 (default)

3. **Pull a Model** (in another terminal)
   ```bash
   # Try these free models:
   ollama pull mistral      # Fast, good quality
   ollama pull llama2       # Reliable
   ollama pull neural-chat  # Good for chat
   ```

4. **Add to .env** (optional)
   ```
   OLLAMA_BASE_URL=http://localhost:11434
   ```

5. **Verify**
   ```bash
   poetry run python -c "from core.llm_provider import OllamaProvider; print('✓ Ollama configured')"
   ```

### Mock Provider (Testing)

No setup needed! Used for testing without API calls.

```bash
poetry run pytest tests/test_multi_providers.py -v
```

---

## Verification

### Check Environment

```bash
# View all installed packages
poetry show

# View specific package versions
poetry show openai anthropic google-generativeai

# Show environment info
poetry env info
```

### Test Each Provider

```bash
# Create a test script
cat > test_providers.py << 'EOF'
#!/usr/bin/env python3
import os
from dotenv import load_dotenv

load_dotenv()

print("Testing provider imports...")

try:
    from core.llm_provider import OpenAIProvider
    print("✓ OpenAI")
except Exception as e:
    print(f"✗ OpenAI: {e}")

try:
    from core.llm_provider import AnthropicProvider
    print("✓ Anthropic")
except Exception as e:
    print(f"✗ Anthropic: {e}")

try:
    from core.llm_provider import AzureOpenAIProvider
    print("✓ Azure")
except Exception as e:
    print(f"✗ Azure: {e}")

try:
    from core.llm_provider import GoogleGeminiProvider
    print("✓ Google")
except Exception as e:
    print(f"✗ Google: {e}")

try:
    from core.llm_provider import OllamaProvider
    print("✓ Ollama")
except Exception as e:
    print(f"✗ Ollama: {e}")

print("\nAll providers loaded successfully!")
EOF

poetry run python test_providers.py
```

### Run Full Test Suite

```bash
poetry run pytest tests/ -v

# Expected: 26 passed, 2 warnings in ~28s
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'openai'"

**Solution:**
```bash
poetry install
poetry run pytest tests/test_multi_providers.py -v
```

### "OPENAI_API_KEY not found in environment"

**Solution:**
1. Create `.env` file in project root (see above)
2. Add your API key: `OPENAI_API_KEY=sk-proj-xxx`
3. Restart terminal/Python session
4. Verify: `poetry run python -c "import os; print(os.getenv('OPENAI_API_KEY'))"`

### "Connection refused" with Ollama

**Solution:**
```bash
# Make sure Ollama is running
ollama serve

# In another terminal, verify
curl http://localhost:11434/api/tags
```

### Tests Failing with "anthropic package not installed"

**Solution:**
```bash
poetry add anthropic
poetry install
poetry run pytest tests/test_multi_providers.py::TestAnthropicProvider -v
```

### "AZURE_OPENAI_ENDPOINT not provided"

**Solution:**
1. Check your `.env` file has both:
   - `AZURE_OPENAI_API_KEY=...`
   - `AZURE_OPENAI_ENDPOINT=https://...`
2. Endpoint should be like: `https://your-resource-name.openai.azure.com/`

### Python Version Mismatch

**Solution:**
```bash
# Check Python version
python --version

# If wrong version, use Poetry's environment
poetry env use python3.12

# Reinstall
poetry install
```

### Virtual Environment Issues

**Solution:**
```bash
# Remove existing venv
poetry env remove $(poetry env list | head -1)

# Create fresh environment
poetry install

# Verify
poetry run python --version
```

---

## Security Best Practices

🔒 **Important:**

1. **Never commit `.env` to git**
   ```bash
   echo ".env" >> .gitignore
   ```

2. **Never hardcode API keys in code**
   ```python
   # ❌ BAD
   provider = OpenAIProvider(api_key="sk-proj-xxx")
   
   # ✅ GOOD
   provider = OpenAIProvider()  # Reads from .env
   ```

3. **Rotate keys regularly**
   - Regenerate API keys monthly
   - Revoke old keys

4. **Use service accounts with minimal permissions**
   - Create separate keys for different environments
   - Limit API permissions to only needed scopes

5. **Never share API keys**
   - Don't post in GitHub issues
   - Don't send via email
   - Don't log them

---

## Next Steps

1. ✅ Choose your LLM provider (see [PROVIDERS.md](PROVIDERS.md))
2. ✅ Configure API keys in `.env`
3. ✅ Run tests to verify setup
4. ✅ Read [DEVELOPMENT.md](DEVELOPMENT.md) to contribute
5. ✅ Check [ROADMAP.md](ROADMAP.md) for upcoming features

For detailed provider usage, see [PROVIDERS.md](PROVIDERS.md).
For architectural details, see [ARCHITECTURE.md](ARCHITECTURE.md).
