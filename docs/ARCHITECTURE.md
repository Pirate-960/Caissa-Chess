# System Architecture

## Executive Summary

CAISSA (Chess AI Artistic Interactive System Architecture) is a **Generative Artistic Chess Pipeline** that orchestrates multiple computational agents to generate beautiful, strategically sound chess games.

**Core Philosophy**: Unlike traditional engines optimized for playing strength, CAISSA optimizes for **Beauty** — the intersection of sound tactics, strategic coherence, and human memorability.

### Key Components

1. **The Dreamer (LLM)** — Generates high-entropy move proposals with narrative intent
2. **The Architect (python-chess)** — Enforces chess rule legality
3. **The Critic (Stockfish)** — Evaluates tactical soundness
4. **The Curator (Beauty Algorithm)** — Assigns aesthetic scoring

---

## System Architecture Overview

### High-Level Pipeline

```
Input: GameContext (era, theme, aggression, style)
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│ 1. THE DREAMER (LLM - OpenAI, Anthropic, etc.)                   │
│    - Reads system prompt with style parameters                   │
│    - Generates PGN with Chain-of-Thought reasoning               │
│    - Proposes moves with narrative arc                           │
│    Output: PGN Text (possibly with illegal moves)                │
└──────────────────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. THE ARCHITECT (python-chess)                                  │
│    - Parses move notation (SAN format)                           │
│    - Validates each move against current position                │
│    - Rejects if illegal                                          │
│    Output: Validated Move List OR Error                          │
└──────────────────────────────────────────────────────────────────┘
   │
   ├─ (On Error) → Fallback: Ask LLM to retry
   │
   ▼ (On Success)
┌──────────────────────────────────────────────────────────────────┐
│ 3. THE CRITIC (Stockfish) [OPTIONAL]                             │
│    - Evaluates each position in centipawns                       │
│    - Flags sacrifices (material drop without eval drop)          │
│    - Checks for soundness (based on style blunder threshold)     │
│    Output: Position Evaluations, Sacrifice Tags                  │
└──────────────────────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│ 4. THE CURATOR (Beauty Evaluation)                               │
│    - Scores sacrifices, quiet moves, forcing moves               │
│    - Calculates position tension                                 │
│    - Applies style weighting (Tal vs. Capablanca)                │
│    - Assigns BeautyScore (0-100)                                 │
│    Output: BeautyMetrics + Final PGN                             │
└──────────────────────────────────────────────────────────────────┘
   │
   ▼
Output: Professional PGN with annotations + Beauty metadata
```

---

## Core Packages

### 1. Core Package (`core/`)

#### `core/prompt_manager.py` — The Creative Director

**Responsibility**: Assemble contextual prompts for the LLM with era-specific guidelines.

**Key Classes**:
```python
class GameContext:
    """Holds all parameters for game generation."""
    era: GameEra              # Romantic, Classical, Hypermodern, Soviet, Computer, Neural
    theme: GameTheme          # QueenSacrifice, Windmill, MinorityAttack, etc.
    aggression_score: float   # 1-10 scale
    chaos_factor: float       # 1-10 scale (higher = more wild positions)
    move_limit: int          # Half-moves to generate

class GameEra(Enum):
    ROMANTIC       # 1850s - Embrace unsound sacrifices
    CLASSICAL      # 1870s - Solid, safe play
    HYPERMODERN    # 1920s - Quiet prophylactic moves
    SOVIET         # 1950s - Balanced fighting chess
    COMPUTER       # 1990s - Precise, tactical, computer-like
    NEURAL         # 2010s - AlphaZero-like alien logic

class PromptManager:
    def build_system_prompt(context: GameContext) -> str
    def build_user_prompt(context: GameContext) -> str
    def build_error_correction_prompt(error: str, context: GameContext) -> str
```

**Algorithm**:
- Constructs system prompt with era-specific behavioral guidelines
- Builds user prompt with game theme and requirements
- On error, generates targeted correction prompt for LLM to fix moves

**Example**:
```python
context = GameContext(
    era=GameEra.ROMANTIC,
    theme=GameTheme.QUEEN_SACRIFICE,
    aggression_score=8,
    move_limit=20
)
manager = PromptManager()
system_prompt = manager.build_system_prompt(context)
# Output: "You are Grandmaster Caissa. Generate a romantic chess game featuring a brilliant queen sacrifice..."
```

#### `core/generator.py` — The Orchestrator

**Responsibility**: Connect LLM → Parser → Validator → Board in a complete pipeline.

**Key Classes**:
```python
class GameGenerator:
    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_manager: PromptManager,
        max_retries: int = 3
    )
    
    def generate_game(
        self,
        aesthetic_goal: str,
        move_limit: int = 20,
        max_retries: int = 3
    ) -> Game
```

**Flow**:
```
1. Create GameContext from parameters
2. Build system + user prompts via PromptManager
3. Call LLM provider (OpenAI, Anthropic, Ollama, etc.)
4. Parse returned PGN
5. Validate all moves via LegalityValidator
6. If validation fails, ask LLM to correct (up to max_retries)
7. If successful, evaluate beauty and return
8. Return Game object with PGN, metadata, beauty score
```

**Error Handling**:
- LLM parsing fails → Log error, ask LLM to regenerate
- Illegal move detected → Fallback: provide move error to LLM for next attempt
- Game incomplete → Warn, but return partial game
- All retries exhausted → Return last best attempt with error flag

**Features**:
- Multi-provider support (OpenAI, Anthropic, Azure, Google Gemini, Ollama, Mock)
- Automatic retry with configurable limits
- Rich error messages for debugging
- Metadata tracking (timing, provider used, retries needed)

#### `core/board_state.py` — The Memory

**Responsibility**: Track board state with rich metadata about moves and positions.

**Key Classes**:
```python
class MoveMetadata:
    """Captures detailed information about a single move."""
    san_notation: str          # e.g., "e4", "Nf3+", "O-O"
    uci_notation: str          # e.g., "e2e4"
    fen_before: str            # Position before move
    fen_after: str             # Position after move
    is_sacrifice: bool         # Detected sacrifice
    is_forcing: bool           # Check, capture, or threat
    piece_moved: chess.PieceType
    piece_captured: Optional[chess.PieceType]
    evaluation_before: float   # Centipawns (if available)
    evaluation_after: float    # Centipawns (if available)
    beauty_score: float        # 0-100 beauty rating

class BoardState:
    """Wrapper around chess.Board with metadata history."""
    board: chess.Board
    move_history: List[MoveMetadata]
    
    def apply_move(self, move: chess.Move, metadata: MoveMetadata)
    def undo_move()
    def get_position_at_move(n: int) -> chess.Board
```

**Usage**:
```python
board_state = BoardState()
board_state.apply_move(
    move,
    MoveMetadata(
        san_notation="e4",
        is_sacrifice=False,
        is_forcing=False
    )
)
```

---

### 2. Engine Package (`engine/`)

#### `engine/legality.py` — The Enforcer

**Responsibility**: Validate all moves and games for legality and correct notation.

**Key Classes**:
```python
class LegalityValidator:
    def parse_and_validate_move(self, san: str) -> LegalityReport
    def apply_move(self, move: chess.Move) -> bool
    def validate_game_pgn(self, pgn_text: str) -> LegalityReport
    def parse_pgn_moves(self, pgn_text: str) -> List[str]

class LegalityReport:
    is_legal: bool
    move_object: Optional[chess.Move]
    error_message: Optional[str]
    suggestion: Optional[str]  # Suggestion if illegal
```

**Algorithms**:

1. **Move Validation**:
   ```
   Input: SAN notation (e.g., "Nf3")
   → Parse SAN using chess.Board.parse_san()
   → Check if move is in board.legal_moves
   → Return: Move object + legality flag
   ```

2. **PGN Parsing**:
   ```
   Input: PGN text
   → Use regex to extract moves (handles comments, variations)
   → For each move:
      → Validate legality
      → Apply to board if legal
   → Return: List of validated moves
   ```

3. **Game Validation**:
   ```
   Input: Complete PGN
   → Parse headers (Event, White, Black, etc.)
   → Parse moves
   → Apply each move sequentially
   → If any move is illegal, return error with context
   ```

**Example**:
```python
validator = LegalityValidator()
report = validator.parse_and_validate_move("e4")
if report.is_legal:
    validator.apply_move(report.move_object)
else:
    print(f"Illegal move: {report.error_message}")
    print(f"Try: {report.suggestion}")
```

---

### 3. Aesthetic Package (`aesthetic/`)

#### `aesthetic/beauty_eval.py` — The Mathematician

**Responsibility**: Quantify chess beauty through sacrifice, tension, and style analysis.

**Beauty Score Formula**:

$$\text{BeautyScore} = (S_{\text{sacrifice}} \times 3) + (S_{\text{tension}} \times 2) + (S_{\text{quiet}} \times 4) - (S_{\text{draw}} \times 5)$$

Where:
- $S_{\text{sacrifice}}$ = Sacrifice bonus (0-25): Material drop with stable evaluation
- $S_{\text{tension}}$ = Tension bonus (0-20): Pieces under mutual attack
- $S_{\text{quiet}}$ = Quiet killer bonus (0-15): Non-forcing move in sharp position
- $S_{\text{draw}}$ = Draw penalty (0-10): Penalties for fortress-like positions

**Key Classes**:
```python
class BeautyEvaluator:
    def evaluate_move(
        self,
        board: chess.Board,
        move: chess.Move,
        eval_before: float = None,
        eval_after: float = None
    ) -> Tuple[float, MoveBeautyType]
    
    def evaluate_game(self, moves: List[chess.Move]) -> GameBeautyMetrics

class MoveBeautyType(Enum):
    SACRIFICE              # Material drop for compensation
    QUIET_KILLER           # Subtle non-forcing move
    FORCING                # Check, capture, or major threat
    POSITIONAL_SQUEEZE     # Restricts opponent options
    NATURAL               # Ordinary developing move
    BLUNDER               # Illegal or losing move (beauty = 0)

class GameBeautyMetrics:
    total_beauty: float           # 0-100 overall score
    sacrifice_count: int
    quiet_killers: int
    forcing_moves: int
    average_move_beauty: float
    style_rating: str             # "Romantic", "Classical", etc.
```

**Move Detection Heuristics**:

1. **Sacrifice Detection**:
   ```python
   is_sacrifice = (
       material_value(moving_piece) > material_value(captured_piece) AND
       evaluation_drop < 200 centipawns  # Stable position after move
   )
   ```

2. **Quiet Killer Detection**:
   ```python
   is_quiet_killer = (
       not move.is_capture() AND
       not move.is_check() AND
       board.is_sharp_position() AND  # Lots of pieces, tension
       opponent_responses_limited() AND  # Move forces narrow continuation
       not obvious_move()  # Not the natural next move
   )
   ```

3. **Tension Scoring**:
   ```
   For each square:
     count = number of pieces attacking it
     defended = number of pieces defending it
   tension += count * defended
   ```

4. **Style Weighting**:
   ```
   If style == ROMANTIC:
      sacrifice_weight *= 1.5
      quiet_killer_weight *= 0.5
   If style == CAPABLANCA:
      sacrifice_weight *= 0.8
      quiet_killer_weight *= 1.5
   ```

**Example**:
```python
evaluator = BeautyEvaluator()
board = chess.Board()
move = board.push_san("e4")
beauty_score, move_type = evaluator.evaluate_move(board, move)
# Output: (15.5, MoveBeautyType.NATURAL)
```

#### `aesthetic/style_slider.py` — The Customizer

**Responsibility**: Map user style preferences to engine parameters.

**Style Presets**:

| Style | Description | Depth | Blunder Tolerance | Complexity Bias | Character |
|-------|-------------|-------|-------------------|-----------------|-----------|
| **Tal** | Intuitive, sacrificial | 10 | ±200 cp | 1.5 | Wild, imaginative attacks |
| **Capablanca** | Perfect, precise | 20 | ±50 cp | 0.5 | Technical mastery |
| **Fischer** | Fighting, no surrender | 18 | ±150 cp | 1.2 | Fortress-breaking tenacity |
| **Karpov** | Scientific, prophylactic | 22 | ±100 cp | 0.8 | Spiritual, solid control |
| **AlphaZero** | Alien, hypermodern | 25 | ±300 cp | 1.8 | Inhuman alien logic |
| **Coffee House** | Chaotic, gambits | 5 | ±500 cp | 2.0 | Pure chaos and adventure |

**Key Classes**:
```python
class StyleSlider:
    def get_config(self, style: StylePreset) -> StyleConfig
    def get_custom_config(
        self,
        sacrifice_weight: float = 1.0,
        complexity_bias: float = 1.0,
        blunder_threshold: float = 150.0
    ) -> StyleConfig

class StylePreset(Enum):
    TAL = "tal"
    CAPABLANCA = "capablanca"
    FISCHER = "fischer"
    KARPOV = "karpov"
    ALPHAZERO = "alphazero"
    COFFEE_HOUSE = "coffee_house"

class StyleConfig:
    depth: int                  # Evaluation depth for Stockfish
    blunder_threshold: float    # Centipawns tolerance
    complexity_bias: float      # 0.5 (simple) to 2.0 (complex)
    sacrifice_weight: float     # Multiplier for sacrifice bonuses
    quiet_killer_weight: float  # Multiplier for quiet moves
```

**Algorithm**:
```python
slider = StyleSlider()
config = slider.get_config(StylePreset.TAL)
# Returns: StyleConfig(
#     depth=10,
#     blunder_threshold=200.0,
#     complexity_bias=1.5,
#     sacrifice_weight=1.5,
#     quiet_killer_weight=0.5
# )
```

---

### 4. Export Package (`export/`)

#### `export/pgn_builder.py` — The Formatter

**Responsibility**: Generate professional PGN output with metadata and annotations.

**PGN Structure**:
```
[Event "CAISSA Generation"]
[White "Grandmaster Caissa"]
[Black "Your Opponent"]
[Date "2026.01.31"]
[Result "1-0"]
[Opening "Italian Game"]
[ECO "C50"]

1. e4 e5! 2. Nf3 Nc6 3. Bc4 Nf6?? 4. Ng5 d5 5. exd5 ...
```

**Key Classes**:
```python
class PGNBuilder:
    def __init__(self, white: str, black: str)
    def add_header(self, key: str, value: str)
    def add_moves_batch(self, moves: List[str])
    def add_annotation(self, move_number: int, annotation: str)
    def finalize() -> str

class PGNAnnotation(Enum):
    BRILLIANT = "!!"      # Excellent move
    GOOD = "!"            # Good move
    INTERESTING = "!?"    # Interesting but dubious
    DUBIOUS = "?!"        # Dubious but interesting
    MISTAKE = "?"         # Bad move
    BLUNDER = "??"        # Serious error
```

**Features**:
- Automatic header generation (Event, White, Black, Result, Date, ECO, Opening)
- Move annotation based on beauty scores
- Line breaks every 2 moves for readability
- PGN validation before output
- File export to `.pgn`
- HTML/Markdown export support (planned)

**Example**:
```python
builder = PGNBuilder(white="Caissa", black="Opponent")
builder.add_header("Event", "CAISSA Chess Generation")
builder.add_moves_batch(["e4", "e5", "Nf3", "Nc6"])
builder.add_annotation(1, "!!")  # Annotate first move as brilliant
pgn_str = builder.finalize()
```

---

### 5. Data Package (`data/`)

#### `openings.json` — Opening Reference

Contains:
- ECO codes (A00-H99) mapping to opening names
- First 8-10 moves of standard openings
- Used to guide LLM in early game generation
- Ensures adherence to recognized theory

**Example Entry**:
```json
{
  "opening": "Italian Game",
  "eco": "C50",
  "moves": ["e4", "e5", "Nf3", "Nc6", "Bc4"],
  "full_name": "Italian Game: Two Knights Defense"
}
```

---

## Multi-Provider LLM Support

CAISSA now supports **6 different LLM providers**, all through a unified interface:

### Available Providers

```python
from core.llm_provider import (
    OpenAIProvider,
    AnthropicProvider,
    AzureOpenAIProvider,
    GoogleGeminiProvider,
    OllamaProvider,
    MockProvider
)

# Each implements the same interface:
class LLMProvider(ABC):
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8
    ) -> str:
        """Generate a response from the LLM."""
        pass
```

### Provider Details

| Provider | Best For | Setup | Cost | Privacy |
|----------|----------|-------|------|---------|
| **OpenAI GPT-4** | Production quality | `OPENAI_API_KEY` | $0.014/game | ☁️ Cloud |
| **Anthropic Claude** | Long context (200K) | `ANTHROPIC_API_KEY` | $0.006/game | ☁️ Cloud |
| **Azure OpenAI** | Enterprise compliance | `AZURE_OPENAI_*` vars | $0.014/game | 🏢 Private |
| **Google Gemini** | Fast generation | `GOOGLE_API_KEY` | $0.0007/game | ☁️ Cloud |
| **Ollama** | FREE local models | Ollama server | $0.00 | 🔒 Local |
| **Mock** | Testing | None | $0.00 | N/A |

### Quick Start Examples

```python
# Production quality
provider = OpenAIProvider(model="gpt-4")

# Enterprise privacy
provider = AzureOpenAIProvider(deployment_name="gpt-4")

# FREE local model (no API key!)
provider = OllamaProvider(model="mixtral")

# Testing without API calls
provider = MockProvider(responses=["1. e4 e5 1-0"])

# Any provider works the same
generator = GameGenerator(provider, prompt_manager)
game = generator.generate_game("Romantic chess", 15)
```

---

## Repository Structure

```
caissa-chess/
│
├── 📚 Core Package
│   └── core/
│       ├── __init__.py
│       ├── llm_provider.py        (663 lines) - Multi-provider LLM interface
│       ├── prompt_manager.py      (400 lines) - Prompt assembly
│       ├── generator.py           (200 lines) - Pipeline orchestration
│       └── board_state.py         (100 lines) - Board tracking

├── 🛡️ Engine Package
│   └── engine/
│       ├── __init__.py
│       └── legality.py            (350 lines) - Move validation

├── 🎨 Aesthetic Package
│   └── aesthetic/
│       ├── __init__.py
│       ├── beauty_eval.py         (300 lines) - Beauty scoring
│       └── style_slider.py        (250 lines) - Style configuration

├── 📤 Export Package
│   └── export/
│       ├── __init__.py
│       └── pgn_builder.py         (150 lines) - PGN generation

├── 📊 Data
│   └── data/
│       └── openings.json          - Opening reference

├── 🧪 Testing
│   └── tests/
│       ├── __init__.py
│       ├── test_legality.py       (100 lines) - Move validation tests
│       └── test_multi_providers.py (365 lines) - Provider tests (26/26 passing)

├── 🎮 Entry Point
│   └── caissa.py                  (300 lines) - CLI interface

├── ⚙️ Configuration
│   ├── pyproject.toml             - Dependencies
│   ├── .env.example               - API key template
│   └── .gitignore                 - Security

└── 📚 Documentation
    └── docs/
        ├── SETUP.md               - Installation guide
        ├── PROVIDERS.md           - Multi-provider guide
        ├── ARCHITECTURE.md        - This file
        ├── DEVELOPMENT.md         - Contributing guide
        └── ROADMAP.md             - Project roadmap
```

---

## Data Flow Diagram

```
User Input
  ├─ style: "Tal"
  ├─ theme: "Queen Sacrifice"
  ├─ aggression: 8
  └─ move_limit: 20
   │
   ▼
GameContext
   │
   ▼
PromptManager
   └─ system_prompt: "You are Grandmaster Caissa..."
   └─ user_prompt: "Generate a Tal-style queen sacrifice game..."
   │
   ▼
LLMProvider.generate()
   ├─ OpenAI GPT-4 (cloud, $0.014/game)
   ├─ Anthropic Claude (cloud, $0.006/game)
   ├─ Azure OpenAI (private, $0.014/game)
   ├─ Google Gemini (cloud, $0.0007/game)
   ├─ Ollama (local, $0.00) ✨
   └─ Mock (testing, $0.00)
   │
   ▼
PGN Text (Raw)
   │ "1. e4 e5 2. Nf3 Nc6 3. Bb5!? ..."
   │
   ▼
LegalityValidator
   ├─ Parse each move
   ├─ Check legality
   └─ Build validated move list
   │
   ├─ (If any illegal) → Ask LLM to fix
   └─ (If all legal) → Continue
   │
   ▼
Move List (Validated)
   │
   ▼
StockfishEvaluator (Optional)
   ├─ Evaluate each position
   ├─ Detect sacrifices
   └─ Tag forcing moves
   │
   ▼
BeautyEvaluator
   ├─ Score each move (0-100)
   ├─ Calculate total beauty
   └─ Determine style rating
   │
   ▼
PGNBuilder
   ├─ Add headers
   ├─ Add annotations (!, !!, ?, etc.)
   └─ Format with line breaks
   │
   ▼
Output: Professional PGN
   └─ Beautiful, legal, annotated game
```

---

## Design Patterns

### 1. Dependency Injection
All major components receive dependencies via constructor:
```python
generator = GameGenerator(
    llm_provider=OllamaProvider(),
    prompt_manager=PromptManager()
)
```

### 2. Chain of Responsibility
Each component validates and passes to the next:
```
LLM → Validator → Evaluator → Builder → Output
```

### 3. Strategy Pattern
Multiple implementations of LLMProvider allow runtime selection:
```python
provider = OllamaProvider() if free_mode else OpenAIProvider()
```

### 4. Decorator Pattern
Retry logic wraps API calls with exponential backoff:
```python
@retry(wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(3))
def generate(self, system_prompt, user_prompt, temperature):
    # API call
```

---

## Error Handling Strategy

### 1. Graceful Degradation
- Missing optional provider → Continue with alternatives
- LLM error → Retry up to 3 times with exponential backoff
- Validation error → Return error with suggestion

### 2. Error Messages
All errors include:
- **What happened**: "Illegal move detected"
- **Why it happened**: "Knight on e2 cannot reach g4 in one move"
- **How to fix**: "Try Ne3, Ng3, or Ng1 instead"

### 3. Logging
All operations logged with:
- Timestamp
- Provider used
- Attempt number
- Duration
- Result (success/failure)

---

## Testing Strategy

### Unit Tests (26 passing)
```bash
pytest tests/test_multi_providers.py -v
```

Tests cover:
- Provider initialization with/without API keys
- Environment variable configuration
- API key validation
- Move generation and mocking
- Error handling for missing packages
- Interface compliance

### Integration Tests
```bash
pytest tests/test_legality.py -v
```

Tests cover:
- PGN parsing
- Move validation
- Game flow end-to-end
- Beauty evaluation

---

## Performance Characteristics

### Generation Speed
| Provider | Speed | Tokens/sec | Cost/game |
|----------|-------|------------|-----------|
| OpenAI GPT-4 | 🐢 Medium | 10-15 | $0.014 |
| Anthropic Claude | 🐇 Fast | 20-30 | $0.006 |
| Google Gemini | 🐇 Fast | 25-35 | $0.0007 |
| Ollama Mixtral | 🐌 Slow* | 5-10 | $0.00 |

*Local speed depends on hardware (GPU 5-10x faster)

### Memory Usage
- Base: ~100 MB
- With loaded model (Ollama): +2-26 GB depending on model size
- Per game generation: ~50 MB temporary

### Latency
- API providers: 2-30 seconds per game
- Ollama (CPU): 30-120 seconds per game
- Ollama (GPU): 5-30 seconds per game

---

## Future Enhancements

### Planned Features
- Real-time evaluation feedback from Stockfish
- Auto-annotation system with move analysis
- Board visualization (GIF generation)
- Master style database with few-shot examples
- Streaming LLM responses for faster feedback
- OpenRouter multi-provider support
- Fine-tuned models for chess

### Potential Providers
- LM Studio (local alternative to Ollama)
- Cohere Command-R
- Together AI
- Replicate

---

## Contributing

To add a new provider:

1. Create class inheriting from `LLMProvider`
2. Implement `generate(system_prompt, user_prompt, temperature) -> str` method
3. Add tests in `tests/test_multi_providers.py`
4. Add documentation section in [PROVIDERS.md](PROVIDERS.md)
5. Submit pull request

See [DEVELOPMENT.md](DEVELOPMENT.md) for full contributing guidelines.

---

## References

- [Multi-Provider Guide](PROVIDERS.md)
- [Setup Instructions](SETUP.md)
- [Development Guide](DEVELOPMENT.md)
- [Project Roadmap](ROADMAP.md)
