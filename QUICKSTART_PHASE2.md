# Quick Start Commands

## 🏗️ Setup

```bash
# 1. Switch to develop and update
git checkout develop
git pull origin develop

# 2. Create feature branch
git checkout -b feature/llm-integration

# 3. Install dependencies
pip install openai tenacity pytest

# OR using poetry
poetry install
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/test_llm_integration.py -v

# Run specific test class
pytest tests/test_llm_integration.py::TestSelfCorrection -v

# Run with coverage
pytest tests/test_llm_integration.py --cov=core --cov-report=html

# Expected: 15+ tests passing ✅
```

## 🔑 API Setup

```bash
# Windows PowerShell
$env:OPENAI_API_KEY='sk-your-key-here'

# Windows CMD
set OPENAI_API_KEY=sk-your-key-here

# Linux/Mac
export OPENAI_API_KEY='sk-your-key-here'
```

## 🚀 Manual Test

```bash
# Run OpenAI integration test
python script_test_openai.py

# Output: generated_game.pgn
```

## 📦 Git Commit

```bash
# Stage all changes
git add core/llm_provider.py core/generator.py tests/test_llm_integration.py script_test_openai.py pyproject.toml

# Commit
git commit -m "feat: Phase 2 - LLM Integration with self-correction loop

- Add abstract LLMProvider interface
- Implement OpenAIProvider with retry logic
- Implement MockProvider for testing
- Refactor CaissaGenerator with self-correction
- Add comprehensive test suite (15+ tests)
- Add manual test script"

# Push
git push origin feature/llm-integration
```

## 🐍 Quick Python Test

```python
# test_quick.py
from core.llm_provider import MockProvider
from core.generator import CaissaGenerator
from core.prompt_manager import GameContext, GameEra

# Mock test (no API needed)
provider = MockProvider(responses=["1. e4 e5 2. Nf3 Nc6 3. Bc4 1-0"])
generator = CaissaGenerator(provider=provider)
context = GameContext(era=GameEra.ROMANTIC)

success, pgn, moves = generator.generate_game(context)
print(f"Success: {success}")
```

```bash
python test_quick.py
```

## ✅ Verification Checklist

- [ ] Tests pass: `pytest tests/test_llm_integration.py -v`
- [ ] No errors: Check VS Code Problems panel
- [ ] Manual test works: `python script_test_openai.py` (if you have API key)
- [ ] Git branch created: `git branch` shows `feature/llm-integration`
- [ ] Changes staged: `git status` shows files ready to commit

## 📊 Expected Output

### Test Output
```
tests/test_llm_integration.py::TestPerfectGeneration::test_perfect_generation PASSED
tests/test_llm_integration.py::TestSelfCorrection::test_self_correction_one_retry PASSED
tests/test_llm_integration.py::TestMaxRetriesExceeded::test_max_retries_exceeded PASSED
...
==================== 15 passed in 2.34s ====================
```

### Manual Test Output
```
======================================================================
CAISSA Phase 2: OpenAI Integration Test
======================================================================
✓ API Key found: sk-proj-1...A7wQ
✓ Provider initialized
✓ Generator ready

🎨 Generating game... (this may take 30-60 seconds)
----------------------------------------------------------------------
✅ SUCCESS! Game generated successfully!
✓ Game saved to: generated_game.pgn
```
