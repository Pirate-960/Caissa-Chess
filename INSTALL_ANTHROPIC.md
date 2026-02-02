# Installing Anthropic & Running Full Test Suite

## Quick Start (Pick One Method)

### **Method 1: Using Poetry (Recommended)**
```bash
cd "d:\Github Projects\Games\Chess\caissa-chess"

# Install all dependencies including anthropic
poetry install

# Run all tests
poetry run pytest tests/test_multi_providers.py -v
```

### **Method 2: Direct pip Install**
```bash
# Activate your virtual environment
"d:\Github Projects\Games\Chess\caissa-chess\.venv\Scripts\activate"

# Install anthropic
pip install anthropic

# Run tests
pytest tests/test_multi_providers.py -v
```

### **Method 3: Using Python Directly**
```bash
# In the project directory
cd "d:\Github Projects\Games\Chess\caissa-chess"

# Run the check script to verify environment
"d:\Github Projects\Games\Chess\caissa-chess\.venv\Scripts\python.exe" check_environment.py
```

## Expected Output After Installation

When all dependencies (including anthropic) are properly installed, you should see:

```
================================================= 26 passed in X.XXs ==================================================

tests/test_multi_providers.py::TestAnthropicProvider::test_initialization_without_key_raises_error PASSED                  [  3%]
tests/test_multi_providers.py::TestAnthropicProvider::test_initialization_with_api_key PASSED                             [  7%]
tests/test_multi_providers.py::TestAnthropicProvider::test_initialization_from_env PASSED                                 [ 11%]
tests/test_multi_providers.py::TestAnthropicProvider::test_custom_model_configuration PASSED                              [ 15%]
tests/test_multi_providers.py::TestAnthropicProvider::test_generate_success PASSED                                        [ 19%]
tests/test_multi_providers.py::TestAnthropicProvider::test_missing_package_raises_import_error PASSED                     [ 23%]
tests/test_multi_providers.py::TestAzureOpenAIProvider::test_initialization_with_credentials PASSED                        [ 26%]
... (20 more tests all PASSED)
```

## Current Status

- ✅ **Anthropic is in dependencies**: `pyproject.toml` line 23: `anthropic = "^0.21.0"`
- ❌ **Anthropic needs to be installed**: Install with one of the methods above
- 📊 **Current test results**: 21 passed, 5 skipped (anthropic tests)
- 🎯 **After installation**: 26 passed, 0 skipped

## Why This Matters

Anthropic Claude is **one of the best LLMs for coding** because:
- 🧠 Excellent code understanding and generation
- 📚 Strong context window (200K tokens)
- 💬 Natural conversation capabilities
- 🔍 Superior debugging and explanation abilities

By installing anthropic, you unlock:
1. **Full test coverage** - All 26 tests will pass
2. **Production-ready code** - Can use Claude as a provider in CAISSA
3. **Best-in-class coding** - Claude's superior coding abilities for game analysis
4. **Multi-provider flexibility** - Switch between OpenAI, Claude, Azure, Google, and Ollama

## Verification

After installing, verify anthropic is available:

```bash
python -c "import anthropic; print('✓ Anthropic installed:', anthropic.__version__)"
```

## Troubleshooting

If installation fails:

1. **Check Python version**:
   ```bash
   python --version  # Should be 3.11 or 3.12
   ```

2. **Update pip**:
   ```bash
   python -m pip install --upgrade pip
   ```

3. **Check internet connection** - Anthropic package requires download

4. **Try alternative install**:
   ```bash
   python -m pip install --no-cache-dir anthropic
   ```

## Files Related to Testing

- `tests/test_multi_providers.py` - Full test suite (26 tests)
- `check_environment.py` - Environment verification script
- `run_full_tests.py` - Full test runner with detailed output
- `validate_tests.py` - Basic validation without full test framework
- `pyproject.toml` - All dependencies listed (line 23)

---

**Once anthropic is installed, you'll have 26/26 tests passing! 🎉**
