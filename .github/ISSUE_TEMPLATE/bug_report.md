---
name: 🐛 Bug Report
about: Create a report to help us improve CAISSA
title: 'fix: [brief bug description]'
labels: bug
assignees: ''
---

## 🐛 Describe the Bug

A clear and concise description of what the bug is. Include:
- What you were trying to do
- What went wrong
- How the behavior differs from what you expected

**Example:**
> When I tried to generate a game with `--style tal`, the generator crashed instead of producing aggressive moves.

---

## 🔁 Reproduction Steps

Provide exact steps to reproduce the issue:

1. **Setup**: 
   ```bash
   # Commands to prepare the environment
   poetry install
   # etc
   ```

2. **Execute**:
   ```bash
   poetry run python caissa.py generate --style tal --output game.pgn
   ```

3. **Observe**:
   - Application crashes/freezes/produces incorrect output
   - Specific error message appears

**Expected Success Scenario:**
- Should generate a valid PGN file
- Should contain 20+ moves in Tal's aggressive style
- Beauty score should be > 0.75

---

## 📉 Expected Behavior

Describe in detail what should happen:

- **Correct Behavior**: [What should happen]
- **Actual Behavior**: [What actually happens]
- **Deviation**: [Why this is wrong]

**Example:**
> **Correct**: The `validate_game_pgn()` function should detect illegal moves and raise `IllegalMoveError`.
> **Actual**: It silently accepts invalid moves and continues.
> **Deviation**: This breaks the core validation guarantee of the Enforcer module.

---

## 📜 Full Error Output

### Stack Trace
```
Paste the complete error trace here, including:
- Exception type
- Error message
- Full stack trace
- Line numbers where error occurred
```

### Minimal Code to Reproduce
```python
# Provide a minimal Python script that demonstrates the bug
from core.prompt_manager import PromptManager

pm = PromptManager(theme="romantic")
# This causes the error:
result = pm.build_system_prompt()  # Error happens here
```

### Debug Information

If applicable, include:
```bash
# Python version and packages
python --version
poetry show

# Specific dependency versions
poetry show python-chess
```

---

## 🌍 Environment Details

Provide complete system information:

- **Operating System**: Windows 11 / macOS 14.2 / Ubuntu 22.04
- **Python Version**: 3.11.6 / 3.12.1
- **Poetry Version**: 1.7.0
- **Project Version**: v0.1.0 (from `pyproject.toml`)

### Python Environment
```bash
# Run these commands to gather info:
python --version
poetry --version
poetry env info
poetry show
```

---

## 📋 Affected Components

Select all that apply:
- [ ] `engine/legality.py` - Move validation
- [ ] `engine/stockfish_client.py` - Stockfish integration
- [ ] `core/prompt_manager.py` - LLM prompting
- [ ] `core/generator.py` - Game generation
- [ ] `aesthetic/beauty_eval.py` - Beauty scoring
- [ ] `cli.py` - Command-line interface
- [ ] Other: _____________________

---

## 🔍 Additional Context

Add any other context about the problem here:

### Frequency
- [ ] Always reproduces
- [ ] Intermittent (happens ~___% of time)
- [ ] Only on specific inputs/conditions

### Related Issues
- References: #123, #456
- Similar to: (link to issues)

### Workarounds
Have you found a workaround? Describe it:
```python
# Temporary fix or workaround code
```

### Screenshots/Visuals
If applicable, add screenshots or terminal output.

---

## 🧪 Testing

Have you verified this?
- [ ] Bug reproduces with latest `develop` branch
- [ ] Bug does NOT occur on `main` branch (regression)
- [ ] Bug occurs on clean environment (fresh `poetry install`)
- [ ] Bug persists after clearing cache (`rm -rf .venv __pycache__`)

---

## 📝 Notes for Maintainers

Add any notes that might help us investigate:
- Priority assessment (Critical/High/Medium/Low)
- Suspected root cause (if you have one)
- Suggested fix approach (if you have one)

**Thank you for helping CAISSA become more beautiful! ♟️**
