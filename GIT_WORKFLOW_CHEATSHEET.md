# 🛠️ CAISSA Git Workflow Cheatsheet

**Complete Guide**: From git init to production deployment

---

## 📚 Table of Contents
1. [Initial Setup](#-initial-setup-one-time)
2. [Daily Workflow](#-daily-workflow)
3. [Branch Management](#-branch-management)
4. [Commit Guidelines](#-commit-guidelines)
5. [Collaboration](#-collaboration-workflow)
6. [Advanced Operations](#-advanced-operations)
7. [Troubleshooting](#-troubleshooting)
8. [Release Process](#-release-process)

---

## 🚀 Initial Setup (One Time)

### Prerequisites Check
```bash
# Verify Git is installed
git --version

# Configure your identity (if not done)
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Optional: Set default editor
git config --global core.editor "code --wait"  # VS Code
git config --global core.editor "vim"          # Vim
```

### Repository Initialization
```bash
# 1. Initialize Git repository
cd Caissa-Chess
git init
git branch -m main

# 2. Create .gitignore if not exists
cat > .gitignore << EOF
# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
*.egg-info/
.pytest_cache/

# Environment
.env
.env.local

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
EOF

# 3. Add Remote (Create repo on GitHub first!)
git remote add origin https://github.com/Pirate-960/Caissa-Chess.git

# Verify remote
git remote -v

# 4. Initial Commit
git add .
git status  # Review what will be committed
git commit -m "feat: initial commit of CAISSA v0.1.0 core architecture"

# 5. Push to main
git push -u origin main

# 6. Create and push develop branch
git checkout -b develop
git push -u origin develop

# 7. Set develop as default branch (recommended)
# Go to GitHub > Settings > Branches > Default branch > develop
```

---

## ☀️ Daily Workflow

### Starting Your Day
```bash
# 1. Check current status
git status

# 2. Switch to develop and sync
git checkout develop
git pull origin develop

# 3. View recent changes
git log --oneline --graph --decorate --all -10

# 4. Check for any conflicts or issues
git fetch --all
```

### Starting a New Task
```bash
# 1. Create feature branch from develop
git checkout develop
git pull origin develop

# 2. Create and switch to feature branch
# Branch naming conventions:
#   feature/NAME  - New features
#   fix/NAME      - Bug fixes
#   docs/NAME     - Documentation changes
#   test/NAME     - Test additions/fixes
#   refactor/NAME - Code refactoring
#   perf/NAME     - Performance improvements

git checkout -b feature/llm-integration

# 3. Verify you're on the right branch
git branch --show-current
```

### Working on Code
```bash
# Check what's changed
git status

# Review differences
git diff                    # Unstaged changes
git diff --staged          # Staged changes
git diff develop           # Compare with develop branch

# Add files selectively
git add path/to/file.py    # Add specific file
git add core/              # Add entire directory
git add .                  # Add all changes (use carefully!)

# Review what will be committed
git status
git diff --staged
```

---

## 💾 Commit Guidelines

### Conventional Commits Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types and Examples
```bash
# Features (new functionality)
git commit -m "feat(generator): add OpenAI GPT-4 integration"
git commit -m "feat(style): add Kasparov aggressive style preset"

# Bug Fixes
git commit -m "fix(validator): resolve castling rights detection bug"
git commit -m "fix(beauty): correct sacrifice scoring calculation"

# Documentation
git commit -m "docs(readme): add installation instructions for Windows"
git commit -m "docs(api): document LLMClient interface"

# Code Style
git commit -m "style(core): format code with black formatter"
git commit -m "style: add type hints to generator module"

# Refactoring
git commit -m "refactor(beauty): simplify scoring algorithm"
git commit -m "refactor: extract prompt building to separate class"

# Performance
git commit -m "perf(validator): optimize move parsing by 40%"

# Tests
git commit -m "test(legality): add edge cases for en passant"
git commit -m "test: increase coverage to 95%"

# Build/CI
git commit -m "ci: add Python 3.12 to test matrix"
git commit -m "build(deps): upgrade python-chess to 1.11.1"

# Chores
git commit -m "chore: update dependencies"
git commit -m "chore: clean up unused imports"
```

### Detailed Commit Message
```bash
git commit -m "feat(generator): add retry logic for failed LLM calls

- Implement exponential backoff (1s, 2s, 4s, 8s)
- Add max_retries parameter (default: 3)
- Log retry attempts with context
- Raise detailed exception after exhausting retries

Closes #42"
```

### Amending Commits
```bash
# Fix the last commit message
git commit --amend -m "feat(generator): correct typo in commit message"

# Add forgotten files to last commit
git add forgotten_file.py
git commit --amend --no-edit

# ⚠️ Only amend commits that haven't been pushed!
```

---

## 🚢 Collaboration Workflow

### Pushing Your Work
```bash
# Push feature branch (first time)
git push -u origin feature/llm-integration

# Subsequent pushes
git push

# Force push (use with EXTREME caution!)
git push --force-with-lease  # Safer than --force
```

### Creating a Pull Request
```bash
# 1. Push your branch
git push -u origin feature/llm-integration

# 2. Go to GitHub repository
# 3. Click "Compare & pull request" button
# 4. Fill out PR template:
#    - Title: Use conventional commit format
#    - Description: Explain what and why
#    - Link related issues
#    - Check all boxes in checklist

# 5. Request reviewers
# 6. Wait for CI checks to pass
# 7. Address review comments
```

### Keeping Your Branch Updated
```bash
# Method 1: Rebase (cleaner history, recommended)
git checkout feature/llm-integration
git fetch origin
git rebase origin/develop

# If conflicts occur:
# 1. Fix conflicts in files
# 2. Stage resolved files
git add .
# 3. Continue rebase
git rebase --continue

# Method 2: Merge (preserves branch history)
git checkout feature/llm-integration
git merge develop

# Push updated branch
git push --force-with-lease  # Required after rebase
```

### After PR is Merged
```bash
# 1. Switch to develop
git checkout develop

# 2. Pull latest changes
git pull origin develop

# 3. Delete local feature branch
git branch -d feature/llm-integration

# 4. Delete remote branch (if not auto-deleted)
git push origin --delete feature/llm-integration

# 5. Prune stale remote branches
git remote prune origin
```

---

## 🌿 Branch Management

### List Branches
```bash
# Local branches
git branch

# Remote branches
git branch -r

# All branches with last commit
git branch -va

# Merged branches
git branch --merged
git branch --no-merged
```

### Switch Branches
```bash
# Switch to existing branch
git checkout develop
git switch develop  # Newer syntax

# Create and switch
git checkout -b feature/new-feature
git switch -c feature/new-feature  # Newer syntax
```

### Delete Branches
```bash
# Delete local branch (safe)
git branch -d feature/old-feature

# Force delete local branch
git branch -D feature/old-feature

# Delete remote branch
git push origin --delete feature/old-feature

# Prune deleted remote branches
git fetch --prune
git remote prune origin
```

### Rename Branches
```bash
# Rename current branch
git branch -m new-name

# Rename specific branch
git branch -m old-name new-name

# Update remote
git push origin :old-name new-name
git push origin -u new-name
```

---

## 🔧 Advanced Operations

### Stashing Changes
```bash
# Stash current work
git stash
git stash save "WIP: implementing LLM retry logic"

# List stashes
git stash list

# Apply stash
git stash apply          # Keep stash
git stash pop           # Apply and remove stash
git stash apply stash@{2}  # Apply specific stash

# Show stash contents
git stash show -p stash@{0}

# Drop stash
git stash drop stash@{0}

# Clear all stashes
git stash clear
```

### Cherry-Picking Commits
```bash
# Pick a specific commit from another branch
git cherry-pick abc1234

# Pick multiple commits
git cherry-pick abc1234 def5678

# Continue after resolving conflicts
git cherry-pick --continue

# Abort cherry-pick
git cherry-pick --abort
```

### Interactive Rebase
```bash
# Rebase last 3 commits interactively
git rebase -i HEAD~3

# In the editor:
# pick abc1234 First commit
# squash def5678 Second commit (will be merged into first)
# reword ghi9012 Third commit (will allow changing message)

# Reorder commits by changing line order
# Delete commits by removing lines
```

### Resetting Changes
```bash
# Undo unstaged changes
git checkout -- file.py

# Unstage files (keep changes)
git reset HEAD file.py

# Undo last commit (keep changes staged)
git reset --soft HEAD~1

# Undo last commit (keep changes unstaged)
git reset HEAD~1

# Undo last commit (discard changes) ⚠️
git reset --hard HEAD~1

# Reset to specific commit
git reset --hard abc1234
```

### Viewing History
```bash
# Detailed log
git log

# One-line log
git log --oneline

# Graph view
git log --oneline --graph --all

# Changes in files
git log -p file.py

# Commits by author
git log --author="Your Name"

# Commits in date range
git log --since="2 weeks ago"
git log --after="2026-01-01" --before="2026-01-31"

# Find when a line was changed
git blame file.py
```

### Tagging Releases
```bash
# Create annotated tag
git tag -a v0.2.0 -m "Release v0.2.0: LLM Integration"

# List tags
git tag

# Push tag to remote
git push origin v0.2.0

# Push all tags
git push origin --tags

# Delete tag
git tag -d v0.2.0
git push origin :refs/tags/v0.2.0
```

---

## 🆘 Troubleshooting

### Conflicts During Merge/Rebase
```bash
# View conflicted files
git status

# Open conflicted file in editor
# Look for conflict markers:
# <<<<<<< HEAD
# Your changes
# =======
# Their changes
# >>>>>>> branch-name

# After resolving:
git add resolved_file.py

# Continue merge
git commit

# Continue rebase
git rebase --continue

# Abort operation
git merge --abort
git rebase --abort
```

### Accidentally Committed to Wrong Branch
```bash
# Move last commit to new branch
git branch feature/correct-branch
git reset --hard HEAD~1
git checkout feature/correct-branch
```

### Undo Pushed Commits
```bash
# Create revert commit (safe for shared branches)
git revert abc1234

# Revert last 3 commits
git revert HEAD~3..HEAD

# Force push (ONLY for personal branches!)
git reset --hard HEAD~1
git push --force-with-lease
```

### Lost Commits (Reflog)
```bash
# View reflog (history of HEAD)
git reflog

# Recover lost commit
git checkout abc1234
git branch recovery-branch
```

### Sync Forked Repository
```bash
# Add upstream remote (once)
git remote add upstream https://github.com/Pirate-960/Caissa-Chess.git

# Fetch upstream changes
git fetch upstream

# Merge upstream into your develop
git checkout develop
git merge upstream/develop

# Push to your fork
git push origin develop
```

---

## 📦 Release Process

### Preparing a Release
```bash
# 1. Switch to develop and ensure it's up to date
git checkout develop
git pull origin develop

# 2. Run full test suite
poetry run pytest tests/ -v

# 3. Update version in pyproject.toml
# [tool.poetry]
# version = "0.2.0"

# 4. Update DEVELOPMENT_ROADMAP.md with completed features

# 5. Commit version bump
git add pyproject.toml DEVELOPMENT_ROADMAP.md
git commit -m "chore(release): bump version to 0.2.0"
git push origin develop

# 6. Create release branch
git checkout -b release/v0.2.0

# 7. Final testing and bug fixes (if needed)
git commit -m "fix: final tweaks for v0.2.0"

# 8. Merge to main
git checkout main
git merge release/v0.2.0
git tag -a v0.2.0 -m "Release v0.2.0: LLM Integration"
git push origin main --tags

# 9. Merge back to develop
git checkout develop
git merge release/v0.2.0
git push origin develop

# 10. Delete release branch
git branch -d release/v0.2.0
git push origin --delete release/v0.2.0
```

### Hotfix Process
```bash
# 1. Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-bug

# 2. Fix the bug
git commit -m "fix(validator): resolve critical castling bug"

# 3. Merge to main
git checkout main
git merge hotfix/critical-bug
git tag -a v0.2.1 -m "Hotfix v0.2.1"
git push origin main --tags

# 4. Merge to develop
git checkout develop
git merge hotfix/critical-bug
git push origin develop

# 5. Delete hotfix branch
git branch -d hotfix/critical-bug
```

---

## 🎓 Best Practices

### Do's ✅
- Commit frequently with clear messages
- Pull before pushing
- Review changes before committing (`git diff`)
- Use feature branches for all work
- Keep commits atomic (one logical change per commit)
- Write descriptive commit messages
- Test before pushing
- Use `git status` liberally

### Don'ts ❌
- Don't commit secrets (.env files, API keys)
- Don't commit generated files (__pycache__, .pyc)
- Don't force push to shared branches
- Don't commit directly to main
- Don't use `git add .` blindly
- Don't rewrite public history
- Don't commit broken code

---

## 📖 Quick Reference

```bash
# Status & Info
git status                          # Show working tree status
git log --oneline --graph --all     # Visual commit history
git diff                            # Show unstaged changes
git branch -va                      # List all branches

# Basic Workflow
git pull                           # Update current branch
git add <file>                     # Stage changes
git commit -m "message"            # Commit changes
git push                           # Push to remote

# Branch Operations
git checkout -b feature/name       # Create and switch to branch
git checkout develop               # Switch to branch
git branch -d feature/name         # Delete local branch
git push origin --delete name      # Delete remote branch

# Undo Operations
git checkout -- <file>             # Discard unstaged changes
git reset HEAD <file>              # Unstage file
git reset --hard HEAD              # Discard all changes
git revert <commit>                # Create reverting commit

# Emergency
git stash                          # Save work temporarily
git stash pop                      # Restore stashed work
git reflog                         # Show command history
```

---

**Happy Committing! ♟️**
