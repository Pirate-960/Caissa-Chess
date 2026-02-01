# 🏗️ CAISSA Architecture

**Version**: 0.1.0  
**Last Updated**: January 31, 2026

---

## Overview

CAISSA implements a **Generative Adversarial-Cooperative Pipeline (GACP)** that combines:
- **LLM Creativity** (narrative, thematic concepts)
- **Chess Engine Validation** (legality, tactical soundness)
- **Aesthetic Scoring** (beauty, memorability)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CAISSA PIPELINE                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   DREAMER    │───▶│  ARCHITECT   │───▶│    CRITIC    │          │
│  │    (LLM)     │    │(python-chess)│    │ (Stockfish)  │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                   │                   │                   │
│         ▼                   ▼                   ▼                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │   CURATOR    │◀───│ STORYTELLER  │◀───│   EXPORTER   │          │
│  │(Beauty Eval) │    │    (LLM)     │    │(PGN Builder) │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. The Dreamer (LLM) - `core/prompt_manager.py`

**Purpose**: Generates creative game concepts and narratives.

**Key Classes**:
- `GameContext`: Configuration dataclass (era, theme, aggression, chaos)
- `GameEra`: Enum for historical eras (ROMANTIC, HYPERMODERN, SOVIET, etc.)
- `GameTheme`: Enum for thematic concepts (QUEEN_SACRIFICE, KING_HUNT, etc.)
- `PromptManager`: Builds system/user prompts with Chain-of-Thought reasoning

**Chain-of-Thought Framework**:
1. **Concept Phase**: Define strategic theme and story arc
2. **Opening Phase**: Sound, era-appropriate opening moves
3. **Spark Phase**: Deviation into brilliance (the key sacrifice)
4. **Climax Phase**: Execution of decisive combination
5. **Conclusion Phase**: Forcing checkmate or decisive advantage

### 2. The Architect (Validator) - `engine/legality.py`

**Purpose**: Enforces chess rules with zero tolerance for hallucinations.

**Key Classes**:
- `LegalityValidator`: Main validation class
- `LegalityReport`: Dataclass with validation results

**Validation Pipeline**:
```python
# Move validation
report = validator.parse_and_validate_move("Nf3")
if report.is_legal:
    validator.apply_move(report.move_object)

# Game validation
is_valid, errors = validator.validate_game_pgn(pgn_text)
```

### 3. The Critic (Stockfish) - `engine/stockfish_client.py`

**Purpose**: Evaluates tactical soundness (planned for v0.3.0).

**Planned Features**:
- UCI protocol wrapper
- Position evaluation with configurable depth
- Sacrifice detection (material drop + stable/improving eval)
- Blunder detection

### 4. The Curator (Beauty) - `aesthetic/beauty_eval.py`

**Purpose**: Scores aesthetic quality of moves and games.

**Key Classes**:
- `BeautyEvaluator`: Main scoring class
- `BeautyMetrics`: Dataclass with component scores
- `MoveBeautyType`: Enum for move classifications

**Beauty Algorithm**:
```python
beauty_score = (
    sacrifice_bonus +      # Material sacrifice
    forcing_bonus +        # Checks, captures, threats
    checkmate_bonus +      # Game-ending moves
    tension_bonus +        # Complex positions
    quiet_killer_bonus     # Quiet moves that are devastating
)
```

### 5. The Style Slider - `aesthetic/style_slider.py`

**Purpose**: Maps style presets to generation parameters.

**Presets**:
| Style | Depth | Blunder Threshold | Complexity Bias |
|-------|-------|-------------------|-----------------|
| Tal | 10 | 200cp | 1.5x |
| Capablanca | 20 | 30cp | 0.5x |
| Morphy | 15 | 50cp | 1.2x |
| Coffee House | 5 | 500cp | 2.0x |
| Neural | 25 | 30cp | 1.8x |
| Karpov | 18 | 40cp | 0.7x |

### 6. The Exporter - `export/pgn_builder.py`

**Purpose**: Formats games into standard PGN with annotations.

**Key Classes**:
- `PGNBuilder`: Constructs PGN strings
- `PGNHeaders`: Standard PGN header fields

---

## Data Flow

```
User Input (style, theme, aggression)
         │
         ▼
┌─────────────────────┐
│   PromptManager     │ ──▶ Build system + user prompt
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│     LLM Client      │ ──▶ Generate PGN
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│  LegalityValidator  │ ──▶ Validate each move
└─────────────────────┘
         │
         ├──▶ If invalid: Retry with feedback
         │
         ▼
┌─────────────────────┐
│   BeautyEvaluator   │ ──▶ Score aesthetics
└─────────────────────┘
         │
         ▼
┌─────────────────────┐
│     PGNBuilder      │ ──▶ Format output
└─────────────────────┘
         │
         ▼
    game.pgn (output)
```

---

## File Structure

```
Caissa-Chess/
├── caissa.py                 # CLI entry point
├── core/
│   ├── __init__.py
│   ├── generator.py          # Main orchestrator
│   ├── prompt_manager.py     # LLM prompt construction
│   └── board_state.py        # Board state tracking
├── engine/
│   ├── __init__.py
│   ├── legality.py           # Move validation
│   └── stockfish_client.py   # (Planned) Engine integration
├── aesthetic/
│   ├── __init__.py
│   ├── beauty_eval.py        # Beauty scoring
│   └── style_slider.py       # Style presets
├── export/
│   ├── __init__.py
│   └── pgn_builder.py        # PGN formatting
├── tests/
│   ├── __init__.py
│   └── test_legality.py      # Unit tests
└── data/
    └── openings/             # (Planned) Opening books
```

---

## Design Principles

1. **Modularity**: Each component is independently testable
2. **Fail-Fast Validation**: Illegal moves caught immediately
3. **Configurable Aesthetics**: Style presets for different play styles
4. **Chain-of-Thought**: Structured LLM reasoning for better output
5. **Graceful Degradation**: Fallbacks when LLM output fails

---

## Extension Points

### Adding New Styles
```python
# In aesthetic/style_slider.py
class StylePreset(Enum):
    MY_STYLE = "my_style"

# Add configuration in STYLE_CONFIGS dict
```

### Adding New Themes
```python
# In core/prompt_manager.py
class GameTheme(Enum):
    MY_THEME = "My Custom Theme Description"
```

### Custom LLM Client
```python
# Implement the LLMClient protocol
class MyLLMClient:
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # Your implementation
        pass
```

---

## Performance Considerations

- **LLM Latency**: ~30 seconds per game (API-dependent)
- **Validation**: ~100ms per game
- **Beauty Scoring**: ~50ms per game
- **Stockfish**: ~500ms-5s per position (depth-dependent)

---

## Security Notes

- API keys stored in `.env` (never committed)
- `.gitignore` excludes sensitive files
- No user input directly executed

---

**Next Steps**: See [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) for planned features.
