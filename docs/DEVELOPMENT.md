# Development Guide

## Getting Started with CAISSA Development

Welcome! This guide will help you contribute to CAISSA effectively.

**Vision**: *We don't generate chess games. We generate immortality.*

---

## Prerequisites

- Python 3.11 or 3.12
- Poetry 1.7.0+ (dependency management)
- Git 2.0+ (version control)
- (Optional) Stockfish 16+ for chess engine evaluation
- (Optional) For LLM testing: API keys (OpenAI, Anthropic, Google, etc.)

---

## Initial Setup

### 1. Fork and Clone

```bash
# Fork repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/caissa-chess.git
cd caissa-chess

# Add upstream remote for syncing
git remote add upstream https://github.com/Pirate-960/caissa-chess.git
git fetch upstream
```

### 2. Set Up Development Environment

```bash
# Create and activate virtual environment
poetry install
poetry shell

# Or run commands with poetry run
poetry run pytest tests/ -v
poetry run python caissa.py --help
```

### 3. Configure IDE

**VS Code (Recommended)**:
```json
{
  "[python]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "ms-python.python",
    "editor.codeActionsOnSave": {
      "source.organizeImports": "explicit"
    }
  },
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black"
}
```

**PyCharm/IntelliJ**:
- Settings → Editor → Code Style → Python
- Enable Black formatter
- Configure isort for import sorting

### 4. Install Pre-Commit Hooks (Optional)

```bash
pip install pre-commit
pre-commit install

# This will auto-format code before commits
```

---

## Git Workflow

### Branching Strategy (GitFlow)

We use GitFlow for organized development:

**Main Branches**:
- **`main`** - Production-ready code only
  - Only merged from `release/*` branches
  - Protected: requires PR review + CI pass
  - Tagged with versions (v0.1.0, v0.2.0, etc.)

- **`develop`** - Integration branch for new features
  - Base branch for all PRs
  - Should always have passing tests
  - Merged from feature/fix/docs branches

**Feature Branches** (create from `develop`):
```bash
git checkout -b feature/new-feature-name
git checkout -b fix/bug-description
git checkout -b docs/document-name
git checkout -b test/test-feature
git checkout -b refactor/component-name
git checkout -b perf/optimization-description
```

### Branch Naming Convention

```
<type>/<short-kebab-case-description>

Examples:
feature/multi-provider-support        # New feature
fix/castling-validation-bug           # Bug fix
docs/api-reference                    # Documentation
test/beauty-evaluator-coverage        # Tests
refactor/generator-architecture       # Refactoring
perf/move-validation-optimization     # Performance
```

### Commit Conventions

Use **conventional commits** for clear history:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `style` - Code style (formatting, semicolons, etc.)
- `refactor` - Code refactoring without feature change
- `perf` - Performance improvement
- `test` - Adding/updating tests
- `chore` - Build, dependencies, tooling

**Examples**:
```bash
# Good commit messages
git commit -m "feat(providers): Add Anthropic Claude support"
git commit -m "fix(legality): Handle castling in check correctly"
git commit -m "docs(setup): Add Ollama installation instructions"
git commit -m "test(beauty): Add sacrifice detection test cases"
git commit -m "refactor(generator): Simplify error handling flow"
```

---

## Code Style Guide

### Python Standards

We follow **PEP 8** with some additions:

**Line Length**: 100 characters (Black default)

**Type Hints**: Required for all functions
```python
# ✅ Good
def generate(
    self,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.8
) -> str:
    """Generate response from LLM."""
    pass

# ❌ Bad
def generate(self, system_prompt, user_prompt, temperature=0.8):
    """Generate response from LLM."""
    pass
```

**Docstrings**: Google-style with examples
```python
def validate_move(self, san: str) -> LegalityReport:
    """Validate a move in standard algebraic notation.
    
    Args:
        san: Move in SAN format (e.g., "e4", "Nf3", "O-O").
        
    Returns:
        LegalityReport with legality status and details.
        
    Raises:
        ValueError: If SAN notation is invalid.
        
    Examples:
        >>> validator = LegalityValidator()
        >>> report = validator.validate_move("e4")
        >>> report.is_legal
        True
    """
    pass
```

**Classes**: Uppercase with descriptive names
```python
class LLMProvider(ABC):          # ✅ Good
class BeautyEvaluator:           # ✅ Good
class llm_provider:              # ❌ Bad
class LLMProviderInterface:       # ❌ Redundant
```

**Constants**: UPPERCASE_WITH_UNDERSCORES
```python
DEFAULT_TEMPERATURE = 0.8
MAX_RETRIES = 3
SUPPORTED_ERAS = ["ROMANTIC", "CLASSICAL", ...]
```

### Formatting Tools

```bash
# Auto-format code with Black
poetry run black caissa core engine aesthetic export tests

# Sort imports with isort
poetry run isort caissa core engine aesthetic export tests

# Lint with pylint
poetry run pylint caissa core engine aesthetic

# Type checking with mypy
poetry run mypy . --ignore-missing-imports

# Run all at once
poetry run black . && poetry run isort . && poetry run pylint . && poetry run mypy .
```

### Code Organization

**Imports**: Group and sort
```python
# 1. Standard library
import json
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

# 2. Third-party
import chess
from tenacity import retry, wait_exponential

# 3. Local imports
from core.board_state import BoardState
from engine.legality import LegalityValidator
```

**Classes**: Order methods logically
```python
class MyClass:
    # 1. __init__ and class methods
    def __init__(self): pass
    
    @classmethod
    def from_file(cls): pass
    
    # 2. Public methods (alphabetically)
    def get_value(self): pass
    def process(self): pass
    def validate(self): pass
    
    # 3. Private methods (alphabetically)
    def _internal_helper(self): pass
    
    # 4. Properties
    @property
    def computed_value(self): pass
    
    # 5. Magic methods
    def __str__(self): pass
    def __repr__(self): pass
```

---

## Testing Requirements

### Test Structure

All tests must have:
- ✅ Clear, descriptive names
- ✅ Single responsibility (test one thing)
- ✅ Proper setup and teardown
- ✅ Mock external dependencies
- ✅ Clear assertions with messages

### Running Tests

```bash
# Run all tests
poetry run pytest tests/ -v

# Run specific test file
poetry run pytest tests/test_legality.py -v

# Run specific test
poetry run pytest tests/test_legality.py::test_parse_san_notation -v

# Run with coverage
poetry run pytest tests/ --cov=core --cov=engine --cov=aesthetic --cov-report=term-missing

# Run specific provider tests
poetry run pytest tests/test_multi_providers.py::TestOllamaProvider -v
```

### Writing Tests

**Good Test Structure**:
```python
import pytest
from unittest.mock import Mock, patch
from engine.legality import LegalityValidator

class TestLegalityValidator:
    """Test suite for LegalityValidator."""
    
    def setup_method(self):
        """Run before each test."""
        self.validator = LegalityValidator()
    
    def test_valid_pawn_move(self):
        """Test that e4 is recognized as legal."""
        report = self.validator.parse_and_validate_move("e4")
        assert report.is_legal, "e4 should be legal opening move"
        assert report.move_object is not None
        assert str(report.move_object) == "e2e4"
    
    def test_illegal_move(self):
        """Test that invalid move is rejected."""
        report = self.validator.parse_and_validate_move("Nf9")
        assert not report.is_legal
        assert "invalid" in report.error_message.lower()
```

**Mocking LLM Calls**:
```python
from unittest.mock import MagicMock, patch
from core.llm_provider import OpenAIProvider

@patch('openai.ChatCompletion.create')
def test_openai_generation(mock_create):
    """Test OpenAI generation without real API call."""
    # Mock the API response
    mock_create.return_value = {
        'choices': [{'message': {'content': 'Generated PGN...'}}]
    }
    
    provider = OpenAIProvider()
    response = provider.generate("system", "user", 0.8)
    
    assert "Generated PGN" in response
    mock_create.assert_called_once()
```

### Test Coverage Goals

- **Minimum**: 80% code coverage
- **Target**: 90%+ code coverage
- All public functions/classes must have tests
- Edge cases and error conditions must be tested

---

## Adding New Features

### Step 1: Plan Your Feature

1. Check existing issues/PRs to avoid duplication
2. Open an issue with your proposal (for major features)
3. Wait for feedback before coding
4. Create a branch: `git checkout -b feature/your-feature`

### Step 2: Implement with Tests

1. Write tests first (TDD approach recommended)
2. Implement feature to pass tests
3. Maintain >80% code coverage
4. Add docstrings and comments
5. Run linters and formatters

```bash
# Format your code
poetry run black . && poetry run isort .

# Run tests
poetry run pytest tests/ -v --cov

# Check type hints
poetry run mypy . --ignore-missing-imports
```

### Step 3: Adding a New LLM Provider

This is a common contribution type. Here's the process:

1. **Create provider class** in `core/llm_provider.py`:
```python
class NewProvider(LLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "default-model",
        max_tokens: int = 4096
    ):
        self.api_key = api_key or os.getenv("NEW_PROVIDER_API_KEY")
        self.model = model
        self.max_tokens = max_tokens
    
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8
    ) -> str:
        """Implementation using NewProvider API."""
        # Call API
        # Handle errors
        # Return response
        pass
```

2. **Add tests** in `tests/test_multi_providers.py`:
```python
class TestNewProvider:
    def test_init_with_api_key(self):
        provider = NewProvider(api_key="key-123")
        assert provider.api_key == "key-123"
    
    def test_generate(self):
        with patch('new_provider_module.api_call') as mock:
            mock.return_value = "Generated PGN"
            provider = NewProvider(api_key="test")
            response = provider.generate("sys", "user")
            assert response == "Generated PGN"
```

3. **Update documentation** in [PROVIDERS.md](../docs/PROVIDERS.md):
- Add to provider table
- Add quick start example
- Add setup instructions
- Add cost/performance info

4. **Update dependencies** in `pyproject.toml`:
```toml
new-provider = "^1.0.0"
```

---

## Documentation

### Types of Documentation

1. **Docstrings**: In code, for functions/classes
2. **Inline Comments**: For complex logic
3. **README.md**: Project overview
4. **docs/SETUP.md**: Installation guide
5. **docs/PROVIDERS.md**: LLM provider guide
6. **docs/ARCHITECTURE.md**: System design
7. **docs/DEVELOPMENT.md**: This file
8. **docs/ROADMAP.md**: Project roadmap

### Writing Good Documentation

- Write from user perspective
- Include examples and code snippets
- Link to related sections
- Keep it up-to-date with code changes
- Use clear headings and formatting

---

## Pull Request Process

### Before Submitting

1. **Sync with upstream**:
```bash
git fetch upstream
git rebase upstream/develop
```

2. **Run full test suite**:
```bash
poetry run pytest tests/ -v --cov
```

3. **Format and lint**:
```bash
poetry run black . && poetry run isort . && poetry run pylint .
```

4. **Check type hints**:
```bash
poetry run mypy . --ignore-missing-imports
```

5. **Update docs** if needed

### Submitting PR

1. **Push your branch**:
```bash
git push origin feature/your-feature
```

2. **Create PR** on GitHub
   - **Title**: Follow conventional commits
   - **Description**: Use template (provided automatically)
   - **Base branch**: `develop`
   - **Link issue**: "Closes #123" if applicable

3. **PR Description Template**:
```markdown
## Description
Brief explanation of what this PR does.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Refactoring

## Testing
Describe how you tested your changes.

## Checklist
- [ ] Tests pass (`pytest tests/ -v`)
- [ ] Code is formatted (`black .`)
- [ ] Imports are sorted (`isort .`)
- [ ] Type hints added (type-safe)
- [ ] Docstrings updated
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

### PR Review Process

- **Automated checks**: Must pass before manual review
  - Linting
  - Type checking
  - Test coverage
- **Manual review**: Team will review code quality
- **Feedback**: Implement requested changes
- **Approval**: Merge once approved

---

## Common Development Tasks

### Adding a New Module

```bash
# Create module in appropriate package
touch core/new_module.py

# Add to __init__.py
echo "from .new_module import MyClass" >> core/__init__.py

# Create test file
touch tests/test_new_module.py

# Add tests following the template above
```

### Running Specific Tests

```bash
# Test single provider
poetry run pytest tests/test_multi_providers.py::TestAnthropicProvider -v

# Test with detailed output
poetry run pytest tests/ -vv

# Test with print statements
poetry run pytest tests/ -v -s

# Test in parallel (faster)
poetry run pytest tests/ -n auto
```

### Debugging

```bash
# Run test with debugger
poetry run pytest tests/test_file.py::test_name -vv --pdb

# Or use print debugging
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug("Value: %s", value)
```

### Checking Test Coverage

```bash
# Generate coverage report
poetry run pytest tests/ --cov=core --cov=engine --cov=aesthetic --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
start htmlcov/index.html # Windows
xdg-open htmlcov/index.html # Linux
```

---

## Performance Optimization

### Profiling

```bash
# Profile with cProfile
poetry run python -m cProfile -s cumtime caissa.py generate

# Profile memory usage
poetry run python -m memory_profiler script.py
```

### Common Optimizations

1. **Move Validation**: Cache legal moves
2. **Beauty Evaluation**: Pre-compute sacrifice masks
3. **LLM Calls**: Implement batching for multiple games
4. **Board State**: Use bitboards instead of squares

---

## Troubleshooting

### Common Issues

**Issue**: Tests fail with "ModuleNotFoundError"
```bash
# Solution: Ensure poetry environment is active
poetry install
poetry shell
pytest tests/ -v
```

**Issue**: API key not found
```bash
# Solution: Set environment variable
export OPENAI_API_KEY="sk-..."
# Or create .env file
echo "OPENAI_API_KEY=sk-..." > .env
```

**Issue**: Import errors in IDE
```bash
# Solution: Set Python interpreter to poetry venv
poetry run which python  # Get path
# Configure IDE to use this path
```

**Issue**: Tests pass locally but fail in CI
```bash
# Solution: Run with CI environment variables
python -c "import sys; print(sys.version)"
poetry show  # Check dependency versions
```

---

## Getting Help

- **Questions**: Open GitHub Discussions
- **Bugs**: Open GitHub Issues with reproduction steps
- **Chat**: Join project Discord/Slack (if applicable)
- **Code Review**: Ask in PR comments
- **Architecture**: Check [ARCHITECTURE.md](ARCHITECTURE.md)

---

## Code of Conduct

- **Be Respectful**: Treat all contributors with respect
- **Be Helpful**: Help others learn and grow
- **Be Honest**: Provide honest feedback
- **Be Inclusive**: Welcome all skill levels and backgrounds

---

## Useful Links

- [Python-Chess Documentation](https://python-chess.readthedocs.io/)
- [OpenAI API Docs](https://platform.openai.com/docs/)
- [Anthropic Claude Docs](https://docs.anthropic.com/)
- [PEP 8 Style Guide](https://www.python.org/dev/peps/pep-0008/)
- [Git Conventions](https://conventionalcommits.org/)
- [Pytest Documentation](https://docs.pytest.org/)

---

## Thank You!

Thank you for contributing to CAISSA. Your work helps create the most beautiful chess games imaginable.

**Remember**: We don't just generate chess games. We generate immortality. 🌟
