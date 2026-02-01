# ♟️ Contributing to CAISSA

Welcome! Thank you for your interest in building the most aesthetic chess engine in history. This guide will help you contribute effectively.

**Vision**: *We don't generate chess games. We generate immortality.*

Table of Contents:
1. [Getting Started](#-getting-started)
2. [Development Setup](#-development-setup)
3. [Branching Strategy](#-branching-strategy)
4. [Commit Conventions](#-commit-conventions)
5. [Code Style Guide](#-code-style-guide)
6. [Testing Requirements](#-testing-requirements)
7. [Pull Request Process](#-pull-request-process)
8. [Architecture Overview](#-architecture-overview)
9. [Common Tasks](#-common-tasks)
10. [Getting Help](#-getting-help)

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11 or 3.12
- Poetry 1.7.0+
- Git 2.0+
- (Optional) Stockfish 16+ for local testing

### First-Time Setup

```bash
# 1. Fork the repository on GitHub
# 2. Clone your fork
git clone https://github.com/Pirate-960/Caissa-Chess.git
cd Caissa-Chess

# 3. Add upstream remote
git remote add upstream https://github.com/Pirate-960/Caissa-Chess.git

# 4. Create virtual environment and install dependencies
poetry install

# 5. Verify installation
poetry run pytest tests/ -v
poetry run python caissa.py --help
```

---

## 🛠️ Development Setup

### IDE Configuration

**Visual Studio Code**
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
  "python.linting.enabled": true,
  "python.linting.pylintArgs": ["--load-plugins=pylint_django"],
  "python.formatting.provider": "black"
}
```

**PyCharm/IntelliJ**
- Settings → Editor → Code Style → Python
- Enable Black formatter
- Configure isort for import sorting

### Essential Tools

```bash
# Install pre-commit hooks (optional but recommended)
pip install pre-commit
pre-commit install

# Format code before committing
poetry run black caissa core engine aesthetic
poetry run isort caissa core engine aesthetic

# Lint code
poetry run pylint caissa core engine aesthetic

# Type checking
poetry run mypy caissa core engine aesthetic --ignore-missing-imports

# Run all checks
poetry run pytest tests/ --cov --cov-report=term-missing
```

---

## 🌿 Branching Strategy

We use **GitFlow** for branch management:

### Main Branches

**`main`** - Production branch
- Only stable, tested code
- Merges only from `release/*` branches
- Tagged with version numbers (v0.1.0, v0.2.0, etc.)
- Protected: requires PR review + CI pass

**`develop`** - Integration/development branch
- Active development happens here
- Merges from `feature/*` and `fix/*` branches
- Should always have passing tests
- This is your base branch for PRs

### Feature Branches

Create these from `develop`:

```bash
# New features
git checkout -b feature/llm-integration
git checkout -b feature/kasparov-style

# Bug fixes
git checkout -b fix/castling-validation
git checkout -b fix/beauty-scorer-edge-case

# Documentation
git checkout -b docs/api-reference

# Tests
git checkout -b test/legality-coverage

# Refactoring
git checkout -b refactor/generator-structure

# Performance
git checkout -b perf/move-validation-optimization
```

### Branch Naming Convention

```
<type>/<short-description>
      ↓
feature/llm-integration
fix/castling-bug
docs/setup-guide
test/beauty-eval-edge-cases
refactor/clean-prompt-builder
perf/cache-move-validation
```

---

## 💬 Commit Conventions

We follow **Conventional Commits** for clear, semantic commit history.

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

| Type | Purpose | Example |
|------|---------|---------|
| `feat` | New feature | `feat(generator): add retry logic for LLM calls` |
| `fix` | Bug fix | `fix(legality): resolve castling rights detection` |
| `docs` | Documentation | `docs(readme): add installation instructions` |
| `style` | Code style (no logic change) | `style: format with black` |
| `refactor` | Code restructuring | `refactor(beauty): simplify scoring algorithm` |
| `perf` | Performance improvement | `perf(validator): optimize move parsing by 40%` |
| `test` | Test additions/fixes | `test(legality): add en passant edge cases` |
| `ci` | CI/CD changes | `ci: add Python 3.12 to test matrix` |
| `chore` | Maintenance tasks | `chore: update dependencies` |

### Scope

Specify the affected component (optional but recommended):
- `generator` - Game generation pipeline
- `legality` - Move validation
- `beauty` - Beauty evaluation
- `prompt` - LLM prompting
- `cli` - Command-line interface
- `stockfish` - Stockfish integration
- `config` - Configuration management
- `deps` - Dependencies

### Subject Line

- Use imperative mood: "add feature" not "added feature"
- Don't capitalize first letter
- No period at end
- Maximum 50 characters
- Clear and descriptive

### Body (Optional)

Explain what and why, not how:

```
feat(generator): implement exponential backoff retry logic

When the LLM API is temporarily unavailable, the generator
currently fails immediately. This implements exponential
backoff (1s, 2s, 4s, 8s) with maximum 3 retries to improve
reliability during transient failures.

The retry policy is configurable via GameGenerator parameters.
```

### Footer (Optional)

Reference related issues:

```
feat(validator): add algebraic notation validation

Implement proper SAN (Standard Algebraic Notation) validation
for all generated moves.

Closes #123
Related to #456
Breaking: BREAKING CHANGE: Changed validator API signature
```

### Examples

✅ **Good**:
```
feat(generator): add OpenAI GPT-4 integration
fix(legality): resolve en passant validation bug
docs(api): document LLMClient interface and usage
refactor(beauty): consolidate scoring metrics
test: increase coverage to 95%
```

❌ **Bad**:
```
fixed stuff
WIP: trying new thing
updates
changes to files
update dependencies
```

---

## 🎨 Code Style Guide

### Python Code Style

We use **Black** for formatting (non-negotiable):

```bash
poetry run black caissa core engine aesthetic
```

### Imports

Organize imports with **isort** (3 groups):

```python
# 1. Standard library
import os
import sys
from datetime import datetime
from typing import Optional, List

# 2. Third-party
import chess
import numpy as np
from pydantic import BaseModel

# 3. Local
from core.generator import GameGenerator
from engine.legality import GameLegalityValidator
```

Run: `poetry run isort caissa core engine aesthetic`

### Type Hints

All public functions must have type hints:

```python
# ✅ Good
def validate_move(move: str, board: chess.Board) -> bool:
    """Validate if move is legal on the board."""
    return move in board.legal_moves

# ❌ Bad
def validate_move(move, board):
    """Validate if move is legal on the board."""
    return move in board.legal_moves
```

### Docstrings

Use Google-style docstrings:

```python
def calculate_beauty_score(moves: List[str], style: str) -> float:
    """Calculate aesthetic beauty score for chess moves.
    
    Evaluates moves based on style-specific metrics like sacrifice
    patterns, tempo advantages, and positional brilliance.
    
    Args:
        moves: List of moves in algebraic notation
        style: Chess style (e.g., 'kasparov', 'tal', 'fischer')
    
    Returns:
        Beauty score between 0.0 and 1.0, where 1.0 is most beautiful
    
    Raises:
        ValueError: If style is not recognized
        IllegalMoveError: If any move is invalid
    
    Examples:
        >>> score = calculate_beauty_score(['e4', 'e5'], 'kasparov')
        >>> score > 0.5
        True
    """
    ...
```

### Constants

Use UPPER_CASE for module-level constants:

```python
# In aesthetic/beauty_eval.py
DEFAULT_BEAUTY_THRESHOLD = 0.75
STYLE_WEIGHTS = {
    'kasparov': 0.85,
    'tal': 0.90,
    'fischer': 0.80,
}
MAX_RETRIES = 3
BASE_RETRY_DELAY_SECONDS = 1.0
```

### Error Handling

```python
# ✅ Good: Specific exceptions
if not is_valid_notation(move):
    raise ValueError(f"Invalid move notation: {move}")

try:
    result = api_call()
except ConnectionError as e:
    logger.error(f"API connection failed: {e}")
    raise
except TimeoutError as e:
    logger.warning(f"API timeout, retrying: {e}")
    # Handle retry

# ❌ Bad: Generic exceptions
try:
    result = api_call()
except:
    pass  # Silent failure is dangerous
```

---

## 🧪 Testing Requirements

### Testing Philosophy

**Correctness First**: We prioritize move legality and validation
**Beauty Second**: Style and aesthetic quality are secondary
**Coverage Target**: 90%+

### Writing Tests

Use **pytest** with descriptive names:

```python
# tests/test_legality.py
import pytest
from engine.legality import GameLegalityValidator, IllegalMoveError

class TestGameLegalityValidator:
    """Test suite for move and game legality validation."""
    
    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return GameLegalityValidator()
    
    def test_valid_game_accepts_legal_moves(self, validator):
        """Verify valid games with legal moves are accepted."""
        pgn = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6"
        assert validator.validate_game_pgn(pgn) is True
    
    def test_invalid_game_rejects_illegal_moves(self, validator):
        """Verify games with illegal moves are rejected."""
        pgn = "1. e4 e5 2. Ke2"  # King can't move to e2 in opening
        with pytest.raises(IllegalMoveError):
            validator.validate_game_pgn(pgn)
    
    @pytest.mark.parametrize("moves,expected", [
        (["e4", "e5"], True),
        (["e4", "e5", "Nf3"], True),
        (["e5"], False),  # e5 illegal as first move
        (["Ke2"], False),  # King can't move to e2 from starting position
    ])
    def test_move_legality_validation(self, validator, moves, expected):
        """Test legality validation for various move sequences."""
        result = validator.validate_moves(moves)
        assert result == expected
```

### Running Tests

```bash
# Run all tests
poetry run pytest tests/ -v

# Run specific test file
poetry run pytest tests/test_legality.py -v

# Run specific test
poetry run pytest tests/test_legality.py::TestGameLegalityValidator::test_valid_game_accepts_legal_moves -v

# Run with coverage
poetry run pytest tests/ --cov=caissa --cov=core --cov=engine --cov=aesthetic --cov-report=term-missing

# Run with markers
poetry run pytest -m "not slow" -v  # Skip slow tests
```

### Test Coverage Requirements

- **Overall**: Minimum 90%
- **Core modules**: Minimum 95% (legality, generator)
- **New features**: Must include tests
- **Bug fixes**: Must include regression test

---

## 📄 Pull Request Process

### Before Creating a PR

1. **Update from upstream**:
   ```bash
   git fetch upstream
   git rebase upstream/develop
   ```

2. **Run full test suite**:
   ```bash
   poetry run pytest tests/ --cov
   ```

3. **Format and lint**:
   ```bash
   poetry run black caissa core engine aesthetic
   poetry run isort caissa core engine aesthetic
   poetry run pylint caissa core engine aesthetic
   ```

4. **Commit with conventional format**:
   ```bash
   git commit -m "feat(module): clear description"
   ```

### Creating a PR

1. **Push to your fork**:
   ```bash
   git push origin feature/my-feature
   ```

2. **Create PR on GitHub**:
   - Title: Use conventional commit format
   - Description: Use the provided PR template
   - Link related issues
   - Describe testing approach

3. **Review checklist**:
   - [ ] Code follows style guidelines
   - [ ] Tests added and passing
   - [ ] Documentation updated
   - [ ] Commit messages clear
   - [ ] No breaking changes (without discussion)

### PR Review Process

Expect:
- **Response time**: 2-3 days
- **Review depth**: Line-by-line code review
- **Feedback**: Constructive suggestions for improvement
- **Revision rounds**: May be asked to make changes
- **Approval**: Requires at least 1 approval before merge
- **CI**: Must pass all checks

### After PR Approval

```bash
# PR gets merged on GitHub

# Locally, update and clean up
git checkout develop
git pull upstream develop
git branch -d feature/my-feature
```

---

## 🏗️ Architecture Overview

### Project Structure

```
Caissa-Chess/
├── caissa/                 # Main package
│   ├── __init__.py
│   └── caissa.py          # CLI entry point
├── core/                   # Core generation pipeline
│   ├── prompt_manager.py  # LLM prompt construction
│   ├── generator.py       # Game generation orchestrator
│   └── config.py          # Configuration management
├── engine/                 # Chess logic
│   ├── legality.py        # Move validation ("The Enforcer")
│   ├── stockfish_client.py # Stockfish evaluation
│   └── position_analyzer.py
├── aesthetic/             # Beauty evaluation
│   ├── beauty_eval.py     # Beauty scoring ("The Poet")
│   ├── style_presets.py   # Chess style definitions
│   └── metrics.py         # Beauty metrics
├── tests/                 # Test suite
│   ├── test_legality.py
│   ├── test_generator.py
│   ├── test_beauty_eval.py
│   └── ...
├── .github/               # GitHub configuration
│   ├── workflows/
│   ├── ISSUE_TEMPLATE/
│   └── pull_request_template.md
├── pyproject.toml         # Poetry configuration
├── poetry.lock            # Dependency lock file
└── README.md              # Project documentation
```

### Module Responsibilities

**`engine/legality.py`** (The Enforcer)
- Validates move legality (chess rules)
- Parses PGN format
- Detects illegal moves

**`core/generator.py`** (The Orchestrator)
- Coordinates game generation
- Handles LLM integration
- Manages validation and evaluation

**`aesthetic/beauty_eval.py`** (The Poet)
- Scores move aesthetics
- Evaluates style adherence
- Rates game beauty

---

## 📝 Common Tasks

### Add a New Chess Style

```python
# 1. Define in aesthetic/style_presets.py
STYLE_DEFINITIONS = {
    'your_style': {
        'aggression': 0.85,
        'sacrifice_weight': 0.90,
        'tempo_weight': 0.75,
        'description': 'Your style description',
    }
}

# 2. Add tests in tests/test_beauty_eval.py
def test_your_style_generates_aggressive_moves():
    evaluator = BeautyEvaluator()
    score = evaluator.evaluate_move(move, 'your_style')
    assert score > 0.70

# 3. Update CLI in caissa.py if needed
```

### Add a New Validation Rule

```python
# 1. Implement in engine/legality.py
class GameLegalityValidator:
    def validate_your_rule(self, move: chess.Move, board: chess.Board) -> bool:
        """Check your custom rule."""
        # Your validation logic
        return is_valid

# 2. Add tests in tests/test_legality.py
def test_your_rule_validation():
    validator = GameLegalityValidator()
    # Your test logic

# 3. Integrate into validate_game_pgn() if needed
```

### Fix a Bug

1. Create a test that reproduces the bug
2. Verify the test fails
3. Implement the fix
4. Verify the test passes
5. Run full test suite
6. Commit with `fix:` type

---

## 🆘 Getting Help

### Documentation
- [README.md](../README.md) - Project overview
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System design
- [DEVELOPMENT_ROADMAP.md](../DEVELOPMENT_ROADMAP.md) - Project roadmap
- [GIT_WORKFLOW_CHEATSHEET.md](../GIT_WORKFLOW_CHEATSHEET.md) - Git commands

### Issues & Discussions
- Check [open issues](https://github.com/Pirate-960/Caissa-Chess/issues) first
- [Discussions](https://github.com/Pirate-960/Caissa-Chess/discussions) for ideas
- Create a new issue if yours isn't listed

### Code Questions
- Ask in issue comments
- Reference relevant code sections
- Provide minimal examples

---

## 🎓 Learning Resources

### Chess Programming
- [Chess Programming Wiki](https://www.chessprogramming.org/)
- [python-chess Documentation](https://python-chess.readthedocs.io/)
- [Stockfish Documentation](https://github.com/official-stockfish/Stockfish)

### Python Best Practices
- [PEP 8 Style Guide](https://pep8.org/)
- [Type Hints PEP 484](https://www.python.org/dev/peps/pep-0484/)
- [Conventional Commits](https://www.conventionalcommits.org/)

### Git & GitHub
- [GitHub Flow Guide](https://guides.github.com/introduction/flow/)
- [Git Documentation](https://git-scm.com/doc)
- [GitFlow Model](https://nvie.com/posts/a-successful-git-branching-model/)

---

**Happy contributing! Together, we're generating immortality. ♟️✨**
