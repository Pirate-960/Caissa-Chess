#!/usr/bin/env bash

# CAISSA Quick Start Script
# Run this to get started with the project

set -e

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                                                                              ║"
echo "║     ♟️  CAISSA: The Aesthetic Chess Engine - Quick Start Script  ♟️         ║"
echo "║                                                                              ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11+ first."
    exit 1
fi

echo "✅ Python found: $(python3 --version)"
echo ""

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "⚠️  Poetry is not installed. Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "✅ Poetry found: $(poetry --version)"
echo ""

# Install dependencies
echo "📦 Installing dependencies with Poetry..."
poetry install --no-root

echo ""
echo "✅ Installation complete!"
echo ""

# Run tests
echo "🧪 Running tests..."
poetry run pytest tests/test_legality.py -v

echo ""
echo "✅ Tests passed!"
echo ""

# Run demos
echo "📚 Running demo modules..."
echo ""
echo "--- Prompt Manager Demo ---"
poetry run python -m core.prompt_manager | head -20
echo ""

echo "--- Legality Validator Demo ---"
poetry run python -m engine.legality | head -15
echo ""

echo "--- Style Slider Demo ---"
poetry run python -m aesthetic.style_slider | head -20
echo ""

# Show help
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                         NEXT STEPS                                           ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "1. Read the documentation:"
echo "   cat QUICKSTART.md          # 10-minute setup guide"
echo "   cat README.md              # Project overview"
echo "   cat ARCHITECTURE.md        # System design"
echo ""
echo "2. Show available styles:"
echo "   poetry run python caissa.py list-styles"
echo ""
echo "3. Show project info:"
echo "   poetry run python caissa.py info"
echo ""
echo "4. To generate a game (requires LLM API key):"
echo "   export OPENAI_API_KEY=sk-your-api-key"
echo "   poetry run python caissa.py generate --style romantic --output game.pgn"
echo ""
echo "Happy generating! 🚀"
echo ""
