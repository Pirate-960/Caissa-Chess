# API Configuration Guide

## ✅ Yes, All API Configs Go in `.env`

All API keys and sensitive configurations should be stored in a `.env` file (or passed as environment variables).

## Current Provider Environment Variables

Each provider looks for specific environment variables:

### **OpenAI**
```bash
OPENAI_API_KEY=sk-...
```
- Required for `OpenAIProvider`
- Falls back to env var if not passed to constructor

### **Anthropic (Claude)**
```bash
ANTHROPIC_API_KEY=sk-ant-...
```
- Required for `AnthropicProvider`
- Falls back to env var if not passed to constructor

### **Azure OpenAI**
```bash
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
```
- Both required for `AzureOpenAIProvider`
- Falls back to env vars if not passed to constructor

### **Google Gemini**
```bash
GOOGLE_API_KEY=...
```
- Required for `GoogleGeminiProvider`
- Falls back to env var if not passed to constructor

### **Ollama (Local)**
```bash
OLLAMA_BASE_URL=http://localhost:11434
```
- Optional - defaults to `http://localhost:11434`
- No API key needed (runs locally)

## Example `.env` File

```bash
# OpenAI
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxx

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx

# Azure OpenAI
AZURE_OPENAI_API_KEY=xxxxxxxxxxxxxxxx
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# Google Gemini
GOOGLE_API_KEY=AIzaxxxxxxxxxxxx

# Ollama (optional, defaults to localhost:11434)
OLLAMA_BASE_URL=http://localhost:11434
```

## How to Use

### **Option 1: Environment Variables (Recommended)**
```bash
# Load from .env file (python-dotenv will auto-load)
from core.llm_provider import OpenAIProvider

# Reads OPENAI_API_KEY from .env
provider = OpenAIProvider()
```

### **Option 2: Constructor Arguments**
```python
from core.llm_provider import OpenAIProvider

# Pass directly (useful for deployment/CI-CD)
provider = OpenAIProvider(api_key="sk-proj-xxxx")
```

### **Option 3: Mixed**
```python
from core.llm_provider import AzureOpenAIProvider

# Uses env vars for defaults, but allows override
provider = AzureOpenAIProvider(
    api_key="override-key-if-needed",
    azure_endpoint="https://custom.openai.azure.com/"
)
```

## Setup Instructions

1. **Create `.env` file** in project root:
   ```bash
   touch .env
   ```

2. **Add your API keys**:
   ```
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   GOOGLE_API_KEY=...
   AZURE_OPENAI_API_KEY=...
   AZURE_OPENAI_ENDPOINT=...
   ```

3. **Add `.env` to `.gitignore`** (if not already):
   ```bash
   echo ".env" >> .gitignore
   ```

4. **Load in code** (auto-loaded by `python-dotenv`):
   ```python
   from dotenv import load_dotenv
   import os
   
   load_dotenv()  # Loads .env file
   
   # Now use environment variables
   from core.llm_provider import OpenAIProvider
   provider = OpenAIProvider()  # Reads from env
   ```

## Security Notes

🔒 **Important:**
- ✅ Never commit `.env` to git
- ✅ Add `.env` to `.gitignore`
- ✅ Never hardcode API keys in code
- ✅ Use environment variables for all deployments
- ✅ Rotate keys regularly
- ✅ Use service accounts with minimal permissions

## Example Usage

```python
# Load environment
from dotenv import load_dotenv
load_dotenv()

# Use any provider - all read from environment
from core.llm_provider import (
    OpenAIProvider,
    AnthropicProvider,
    AzureOpenAIProvider,
    GoogleGeminiProvider,
    OllamaProvider
)

# All automatically use .env variables
openai = OpenAIProvider()
claude = AnthropicProvider()
azure = AzureOpenAIProvider()
gemini = GoogleGeminiProvider()
ollama = OllamaProvider()  # No API key needed

# Or override for specific use case
provider = OpenAIProvider(api_key="custom-key-for-testing")
```

## Verification

To verify your `.env` is being loaded:

```python
import os
from dotenv import load_dotenv

load_dotenv()

print(os.getenv("OPENAI_API_KEY"))  # Should print your key (or None if not set)
print(os.getenv("ANTHROPIC_API_KEY"))  # etc.
```

---

**Summary:** All API keys go in `.env`, and the providers automatically read from environment variables if not passed to the constructor.
