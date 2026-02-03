# ♟️ CAISSA: The Aesthetic Chess Engine

> **"We don't generate chess games. We generate immortality."**

## 📜 Executive Summary

CAISSA is a Generative Adversarial-Cooperative Pipeline (GACP) that combines Large Language Model narrative creativity with Stockfish tactical verification to generate "Perfect" chess games—sound enough to be real, dramatic enough to be masterpieces.

Unlike traditional engines that optimize for a single metric (strength), CAISSA optimizes for **Beauty**: the intersection of tactical soundness, strategic coherence, and aesthetic brilliance.

## 📚 Documentation

### 🚀 Quick References (Root)
| File | Purpose |
|------|---------|
| [QUICKSTART.md](QUICKSTART.md) | Get running in 10 minutes |
| [PROVIDER_QUICK_REFERENCE.md](PROVIDER_QUICK_REFERENCE.md) | One-liner examples for all 6 providers |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System overview |
| [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) | Current status & what's next |

### 📚 Comprehensive Guides (docs/)
| File | Purpose |
|------|---------|
| [docs/SETUP.md](docs/SETUP.md) | Complete installation & configuration |
| [docs/PROVIDERS.md](docs/PROVIDERS.md) | Full provider guide with troubleshooting |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Deep technical design |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Contributing & code standards |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Full project vision & timeline |

## 🏗️ Architecture Overview

```mermaid
flowchart LR
    A["The Dreamer<br/>(LLM)"]
    B["The Architect<br/>(python-chess)"]
    C["The Critic<br/>(Stockfish)"]
    D["The Curator<br/>(Scorer)"]

    A --> B --> C --> D
```

## 📁 Directory Structure

```
Caissa-Chess/
├── core/                    # Main generation pipeline
│   ├── generator.py         # Primary orchestrator
│   ├── board_state.py       # Chess board wrapper
│   ├── llm_provider.py      # Multi-provider LLM abstraction + metrics
│   └── prompt_manager.py    # Dynamic prompt assembly
│
├── engine/                  # Validation & analysis
│   ├── stockfish_client.py  # UCI protocol wrapper
│   ├── legality.py          # Move validation
│   └── tac_search.py        # Tactical pattern detection
│
├── aesthetic/               # Beauty evaluation
│   ├── beauty_eval.py       # Brilliance scoring algorithm
│   ├── style_slider.py      # Style presets (Tal, Capablanca, etc)
│   └── sacrifice_detector.py
│
├── benchmarks/              # Performance & quality analysis
│   ├── provider_benchmark.py    # Multi-provider benchmarking
│   ├── rich_console.py          # Color output & charts
│   ├── quality_analyzer.py      # Game quality scoring
│   ├── benchmark_history.py     # Trend analysis & persistence
│   └── report_generator.py      # HTML/Markdown reports
│
├── export/                  # Output formatting
│   ├── pgn_builder.py       # PGN formatting
│   ├── gif_generator.py     # Board visualization
│   └── markdown_report.py   # Game narrative
│
├── data/                    # Reference data
│   ├── openings.json        # ECO codes
│   └── master_styles/       # Few-shot examples
│
├── tests/                   # Test suite (264 tests)
└── README.md
```

## ✨ Features

- **🌐 Multi-Provider Support**: Use OpenAI, Anthropic (Claude), Azure OpenAI, Google Gemini, or run 100% FREE & PRIVATE with local models via Ollama
- **🎨 LLM-Powered Generation**: Uses advanced AI to propose creative, high-entropy moves
- **✅ Legality Enforcement**: Every move validated through `python-chess`
- **🔄 Self-Correction Loop**: Automatically detects and fixes illegal moves with retry logic
- **💎 Beauty Metrics**: Mathematical scoring of aesthetic qualities
- **🎭 Style Injection**: Generate games in historical styles (Romantic, Hypermodern, Neural)
- **📝 GM Commentary**: Auto-annotation explaining brilliant and curious moves
- **📦 PGN Export**: Professional publication-ready format

## 🚀 Quick Start

```bash
# Install dependencies
poetry install

# Set up your preferred provider (choose one):
export OPENAI_API_KEY='sk-...'              # For OpenAI (GPT-4)
export ANTHROPIC_API_KEY='sk-ant-...'      # For Anthropic (Claude)
# OR use Ollama for FREE local models (see MULTI_PROVIDER_GUIDE.md)

# Run the demo script
python script_multi_provider_demo.py

# Or generate programmatically:
from core.llm_provider import OpenAIProvider  # or AnthropicProvider, OllamaProvider
from core.generator import GameGenerator
from core.prompt_manager import PromptManager

provider = OpenAIProvider(model="gpt-4")
prompt_manager = PromptManager()
generator = GameGenerator(provider, prompt_manager)

game = generator.generate_game(
    aesthetic_goal="Romantic attacking chess with sacrifices",
    move_limit=15
)

print(game.pgn_str)
```

**💡 See [PROVIDERS.md](docs/PROVIDERS.md) for detailed setup of all 6 LLM providers!**

## 💎 The Beauty Score Formula

$$\text{Beauty} = (\text{Sacrifices} \times 3) + (\text{Tension} \times 2) + (\text{Quiet Moves} \times 4) - (\text{Draws} \times 5)$$

See `docs/beauty_metric.md` for the full mathematical framework.

## 🎛️ Style Presets

| Style | Depth | Blunder Tolerance | Best For |
|-------|-------|-------------------|----------|
| **Tal** | 10 | High (-2.0) | Intuitive attacks, complications |
| **Capablanca** | 20 | Zero | Positional perfection |
| **Coffee House** | Very Low | Very High | Gambits and tricks |
| **Neural** | Max | Zero | AlphaZero-style sacrifices |

### 🎭 Historical Player Personalities (Phase 3.1)

Generate games in the style of legendary chess masters:

| Player | Era | Style | Aggression |
|--------|-----|-------|------------|
| **Morphy** | Romantic | Classical development, rapid attacks | 7/10 |
| **Tal** | Soviet | Wild sacrifices, magical combinations | 9/10 |
| **Capablanca** | Classical | Crystal-clear logic, endgame perfection | 4/10 |
| **Fischer** | Computer | Perfect calculation, crushing technique | 7/10 |
| **Kasparov** | Computer | Relentless attacking power | 8/10 |
| **Carlsen** | Neural | Universal style, grinding technique | 5/10 |
| **AlphaZero** | Neural | Alien logic, long-term sacrifices | 6/10 |

## 🚀 Phase 3.1 Features

### Batch Generation
```python
from core.generator import CaissaGenerator, RetryConfig, RetryStrategy

generator = CaissaGenerator(provider)
generator.set_retry_config(RetryConfig(
    strategy=RetryStrategy.EXPONENTIAL,
    max_retries=5,
))

# Generate multiple games
batch_result = generator.generate_batch(contexts)
print(f"Success rate: {batch_result.success_rate:.1%}")
```

### Multi-Format Export
```python
from export.pgn_builder import PGNBuilder, ExportFormat, NAG

builder = PGNBuilder(white="Tal", black="Petrosian")
builder.add_move_advanced("e4", nags=[NAG.GOOD_MOVE], comment="The king's pawn")
builder.add_move_advanced("c5")  # Sicilian!

# Export in multiple formats
print(builder.export(ExportFormat.PGN))
print(builder.export(ExportFormat.MARKDOWN))
print(builder.export(ExportFormat.HTML))
print(builder.export(ExportFormat.JSON))
```

### Narrative Arcs
Generate games with story structure:
- **Blitzkrieg** - Fast, overwhelming attack
- **The Comeback** - Near-loss turned into victory
- **The Slow Squeeze** - Gradual positional domination
- **The Brilliancy** - Single stunning move turns game

## 📊 Phase 3.2+ Benchmarking Features

### Provider Benchmarking
```bash
# Rich console output with colors and charts
python -m benchmarks.provider_benchmark --all --rich

# Generate HTML report
python -m benchmarks.provider_benchmark --all --report benchmark.html

# Save to history database for trend analysis
python -m benchmarks.provider_benchmark --all --save-history
```

### Quality Analysis
```python
from benchmarks.quality_analyzer import QualityAnalyzer

analyzer = QualityAnalyzer()
report = analyzer.analyze(pgn_string)

print(f"Grade: {report.grade}")  # A+, A, B+, etc.
print(f"Score: {report.overall_score}/100")
print(f"Opening: {report.detected_opening}")
```

### Benchmark History & Trends
```bash
# Analyze performance trends over time
python -m benchmarks.benchmark_history --provider openai --trends

# Detect performance regressions
python -m benchmarks.benchmark_history --regressions
```

## 📋 Development Roadmap

See [ROADMAP.md](docs/ROADMAP.md) for complete project timeline and vision.

**Current Status**: 
- ✅ **v0.1**: Core generation pipeline (legality validation)
- ✅ **v0.2**: Multi-provider LLM support (6 providers, 49 tests passing)
- ✅ **v0.3**: Stockfish integration complete + Phase 3.1 enhancements
  - 🎯 Batch generation with progress tracking
  - 🎭 15 historical player personalities
  - 📝 NAG annotations & multi-format export (PGN/HTML/MD/JSON)
  - 🔄 Advanced retry strategies with exponential backoff
  - 📊 Generation statistics and caching
- ✅ **v0.3.1**: Quality & Testing (Phase 3.2)
  - 📊 Provider metrics tracking (tokens, cost, latency)
  - 🧪 Live API testing for all providers
  - 🔬 End-to-end generation tests
- ✅ **v0.3.2**: Enhanced Benchmarking (Phase 3.2+)
  - 🎨 Rich console output with colors and charts
  - 📈 Benchmark history and trend analysis
  - 📋 HTML/Markdown report generation
  - 🔍 Quality analysis for generated games
  - ⚠️ Regression detection and alerts
- 🎯 **v1.0**: Production-ready web interface

## 🔬 Research Applications

CAISSA is positioned as "Alignment Research in Game Aesthetics"—exploring how to generate strategic content that entertains *and* instructs humans, not just maximizes ELO.

Key metrics:
- **Memorability**: Can humans recall the key position?
- **Instructional Value**: Does the game teach a clear thematic concept?
- **Human-Likeness**: Turing test against GM game databases

## 📜 License

MIT

---

**Status**: `✅ Stable Release`  
**Version**: v0.3.2 (Phase 3.2+ Enhanced Benchmarking Complete)  
**Last Updated**: February 2026  
**Tests**: 264 passing ✅
