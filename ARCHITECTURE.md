# 🏗️ CAISSA System Architecture Document

> **📖 Quick Reference** | For the comprehensive architecture guide, see **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**

**Version**: 3.1  
**Date**: February 2026  
**Status**: v0.3.1 - Phase 3.2 Quality & Testing Complete

---

## Executive Summary

CAISSA (Chess AI Artistic Interactive System Architecture) is a **Generative Adversarial-Cooperative Pipeline (GACP)** that orchestrates four computational agents:

1. **The Dreamer (LLM)** — Generates high-entropy move proposals with narrative intent
2. **The Architect (python-chess)** — Enforces chess rule legality
3. **The Critic (Stockfish)** — Evaluates tactical soundness and compensation
4. **The Curator (Beauty Algorithm)** — Assigns aesthetic scoring

Unlike traditional engines optimized for strength, **CAISSA optimizes for Beauty**: the intersection of sound tactics, strategic coherence, and human memorability.

---

## 1. System Architecture Overview

### 1.1 The Pipeline (High Level)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CAISSA GENERATION PIPELINE                   │
└─────────────────────────────────────────────────────────────────┘

Input: GameContext (era, theme, aggression, chaos)
   │
   ▼
┌──────────────────────────────────────────────────────────────────┐
│ 1. THE DREAMER (LLM)                                             │
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
│ 3. THE CRITIC (Stockfish)                                        │
│    - Evaluates each position in centipawns                       │
│    - Flags sacrifices (material drop without eval drop)          │
│    - Checks for soundness (based on style blunder threshold)     │
│    - Provides evaluation feedback to LLM (future)                │
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

## 2. Component Architecture

### 2.1 Core Package (`core/`)

#### `core/prompt_manager.py` — The Creative Director
**Responsibility**: Assemble contextual prompts for the LLM.

**Key Classes**:
- `GameContext` - Dataclass holding era, theme, aggression, chaos, player names
- `GameEra` - Enum: Romantic, Classical, Hypermodern, Soviet, Computer, Neural
- `GameTheme` - Enum: QueenSacrifice, Windmill, MinorityAttack, etc.
- `PromptManager` - Builds system and user prompts with era-specific guidelines

**Algorithm** (Chain-of-Thought):
```
SYSTEM_PROMPT = """
You are Grandmaster Caissa. Think in 5 stages:
1. Concept: Define the narrative arc
2. Opening: Play standard theory moves (moves 1-8)
3. Spark: Introduce the key idea (moves 9-15)
4. Climax: Execute the combination (moves 16-half_depth)
5. Conclusion: Force the win (final moves)

Generate the PGN now.
"""
```

**Configuration by Era**:
- Romantic (1850s): Embrace unsound sacrifices
- Hypermodern (1920s): Quiet prophylactic moves
- Neural (2010s): AlphaZero-like alien logic

#### `core/generator.py` — The Orchestrator
**Responsibility**: Connect LLM → Parser → Validator → Board.

**Key Classes**:
- `CaissaGenerator` - Main pipeline
- `SimpleOpenAIClient` - LLM API wrapper

**Flow**:
```python
context = GameContext(era=ROMANTIC, theme=QUEEN_SACRIFICE, ...)
generator = CaissaGenerator()
generator.set_llm_client(SimpleOpenAIClient())
success, pgn, moves = generator.generate_game(context)
```

**Error Handling**:
- LLM parsing fails → Return error message
- Illegal move detected → Fallback: ask LLM to regenerate
- Game incomplete → Warn, but return partial game

#### `core/board_state.py` — The Memory
**Responsibility**: Track board state with rich metadata.

**Key Classes**:
- `MoveMetadata` - Captures move info (SAN, FEN before/after, sacrifice flag, evals)
- `BoardState` - Wrapper around `chess.Board` with history

---

### 2.2 Engine Package (`engine/`)

#### `engine/legality.py` — The Enforcer
**Responsibility**: Ensure every move is legal.

**Key Classes**:
- `LegalityValidator` - Move/game validation
- `LegalityReport` - Detailed validation result with error messages

**Algorithms**:
1. **Move Validation**: SAN notation → `board.parse_san()` → legality check
2. **PGN Parsing**: Extract moves from PGN with regex, handling comments/variations
3. **Game Validation**: Apply each move sequentially, stop on first illegal

**Example**:
```python
validator = LegalityValidator()
report = validator.parse_and_validate_move("e4")
if report.is_legal:
    validator.apply_move(report.move_object)
```

#### `engine/stockfish_client.py` — The Critic Engine
**Responsibility**: UCI protocol communication with Stockfish for tactical validation.

**Status**: ✅ Complete (Phase 3.1)

**Key Classes**:
- `StockfishClient` - Thread-safe UCI wrapper with graceful degradation
- `EvaluationResult` - Dataclass holding score, mate info, PV, best move
- `EngineMode` - Enum: ACTIVE (Stockfish available), PASSIVE (fallback)

**Features**:
- Graceful degradation to Passive Mode if Stockfish unavailable
- Thread-safe evaluation caching for performance
- CI/CD safe (no crashes on missing binary)

**Interface**:
```python
client = StockfishClient(depth=15)

# Evaluate position
result = client.evaluate(board)  # Returns EvaluationResult

# Evaluate specific move
analysis = client.evaluate_move(board, move)
# Returns: {before, after, eval_change, move_quality, is_best_move}

# Detection methods
client.is_blunder(board, move, threshold=300)  # True if loses > 3 pawns
client.is_sacrifice(board, move)  # True if material down but eval stable
```

---

### 2.3 Aesthetic Package (`aesthetic/`)

#### `aesthetic/beauty_eval.py` — The Mathematician
**Responsibility**: Quantify chess beauty.

**Beauty Score Formula**:
$$\text{Beauty} = S_s \times 3 + S_t \times 2 + S_q \times 4 - S_d \times 5$$

Where:
- $S_s$ = Sacrifice bonus (material drop with stable eval)
- $S_t$ = Tension bonus (pieces under mutual attack)
- $S_q$ = Quiet killer bonus (non-forcing move in sharp position)
- $S_d$ = Draw penalty

**Key Classes**:
- `BeautyEvaluator` - Score moves and games
- `BeautyMetrics` - Breakdown of components
- `MoveBeautyType` - Enum classifying move aesthetic quality

**Move Detection Heuristics**:
1. **Sacrifice**: `material_value(moving_piece) > material_value(captured)` AND `eval_drop < 150 cp`
2. **Quiet Killer**: `not capture AND not check AND sharp_position AND forces_continuation`
3. **Forcing**: `gives_check OR undefended_capture`
4. **Positional Squeeze**: `restricts_opponent_options`

#### `aesthetic/style_slider.py` — The Customizer
**Responsibility**: Map user styles to engine parameters.

**Style Presets**:
| Style | Depth | Blunder Tolerance | Complexity Bias | Use Case |
|-------|-------|-------------------|-----------------|----------|
| Tal | 10 | ±2.0 pawns | 1.5 | Intuitive attacks |
| Capablanca | 20 | ±0.3 pawns | 0.5 | Perfect precision |
| Neural | 25 | ±0.3 pawns | 1.8 | Alien logic |
| Coffee House | 5 | ±5.0 pawns | 2.0 | Chaos & gambits |

**Phase 3.1 Enhancements**:
- `ExtendedStylePreset` - 20 additional player styles (Morphy, Karpov, Kasparov, etc.)
- `StyleBlender` - Mix multiple styles with configurable weights
- Advanced style configuration with positional/tactical modifiers

**Algorithm**:
```python
slider = StyleSlider()
config = slider.get_config(style=StylePreset.TAL)
# Returns: depth=10, blunder_threshold=200, complexity_bias=1.5

# Phase 3.1: Blend styles
blender = StyleBlender()
hybrid = blender.blend([
    (StylePreset.TAL, 0.6),
    (StylePreset.CAPABLANCA, 0.4),
])
```

---

### 2.4 Export Package (`export/`)

#### `export/pgn_builder.py` — The Formatter
**Responsibility**: Professional PGN output with multi-format support.

**Phase 3.1 Enhancements**:
- **NAG Support**: Standard Numeric Annotation Glyphs (!!, !, ?!, $14, etc.)
- **Variations**: Alternative lines with nested variations
- **Multi-Format Export**: PGN, HTML, Markdown, JSON, Lichess

**Key Classes**:
- `NAG` - IntEnum of all standard annotation glyphs
- `ExportFormat` - Enum: PGN, MARKDOWN, HTML, JSON, LICHESS
- `MoveAnnotation` - NAG codes, comments, evaluations, clock times
- `Variation` - Alternative line representation
- `GameMetadata` - Extended header fields (ECO, Elo, TimeControl, etc.)
- `AdvancedMoveEntry` - Complete move with all metadata

**PGN Structure**:
```
[Event "CAISSA Generation"]
[ECO "B90"]
[Opening "Sicilian Defense"]
[White "Player Name"]
[Black "Opponent Name"]
[Result "1-0"]

1. e4! {The king's pawn opening} e5 2. Nf3 Nc6 3. Bb5!! ...
```

**Multi-Format Export**:
```python
builder = PGNBuilder(white="Tal", black="Petrosian")
builder.add_move_advanced("e4", nags=[NAG.GOOD_MOVE])

print(builder.export(ExportFormat.PGN))       # Standard PGN
print(builder.export(ExportFormat.MARKDOWN))  # Documentation-ready
print(builder.export(ExportFormat.HTML))      # Web display
print(builder.export(ExportFormat.JSON))      # API integration
```

---

### 2.5 Data Package (`data/`)

#### `openings.json` — Opening Reference
Contains ECO codes and common opening moves to guide early-game generation.

---

## 3. Data Flow Diagram

```
User Input (CLI)
  │
  ├─ style: tal
  ├─ theme: Queen Sacrifice
  ├─ aggression: 8
  ├─ chaos: 6
  └─ depth: 40 (half-moves)
  │
  ▼
GameContext Object
  │
  ▼
PromptManager.build_system_prompt()
  │ (Builds: "You are Grandmaster Caissa...")
  ▼
LLM API Call
  │ Input: system + user prompt
  │ Output: PGN text
  ▼
PGN String (Raw)
  │
  ├─ [Event "..."]
  ├─ [White "..."]
  └─ 1. e4 e5 2. Nf3 Nc6 ...
  │
  ▼
LegalityValidator.validate_game_pgn()
  │ Check each move:
  │ ├─ Parse SAN notation
  │ ├─ Apply to board
  │ └─ Check legality
  │
  ├─ (If illegal) → Return error
  └─ (If legal) → Continue
  │
  ▼
Move List (Validated)
  │
  ▼
StockfishClient.evaluate() [Pending]
  │ Evaluate each position
  │ Detect sacrifices
  ▼
Evaluations + Sacrifices
  │
  ▼
BeautyEvaluator.evaluate_game()
  │ Calculate beauty score
  ▼
BeautyMetrics (0-100)
  │
  ▼
PGNBuilder.build_pgn()
  │ Format with annotations
  │ Add beauty metadata
  ▼
Final PGN File
  │
  └─ Saved to disk (game.pgn)
```

---

## 4. Key Algorithms

### 4.1 Sacrifice Detection
```python
def is_sound_sacrifice(move, board, eval_before, eval_after):
    """
    Material drops but eval doesn't drop significantly.
    """
    material_drop = (
        piece_value(board.piece_at(move.to_square)) <
        piece_value(board.piece_at(move.from_square))
    )
    
    eval_stable = (eval_before - eval_after) < 150  # 1.5 pawns
    
    return material_drop and eval_stable
```

### 4.2 Position Sharpness
```python
def is_position_sharp(board):
    """
    Count non-pawn pieces. If >= 6, it's sharp.
    """
    non_pawns = sum(1 for square in board.SQUARES
                   if board.piece_at(square) 
                   and board.piece_at(square).piece_type != PAWN)
    return non_pawns >= 6
```

### 4.3 Tension Calculation
```python
def count_tension(board):
    """
    Pieces under mutual attack (both attackers AND defenders).
    """
    tension = 0
    for square in board.SQUARES:
        piece = board.piece_at(square)
        if piece:
            attackers = len(board.attackers(not piece.color, square))
            defenders = len(board.attackers(piece.color, square))
            if attackers > 0 and defenders > 0:
                tension += min(attackers, defenders)
    return tension
```

---

## 5. Error Handling Strategy

### 5.1 LLM Output Parsing
- **Failure**: LLM generates invalid PGN format
- **Recovery**: Extract moves from raw text with regex, attempt reconstruction

### 5.2 Illegal Moves
- **Failure**: Move not legal in current position
- **Recovery**: Log error, halt game, return partial game + error

### 5.3 Incomplete Games
- **Failure**: LLM stops generating before reaching desired depth
- **Warning**: Return game as-is with lower beauty score

---

## 6. Extensibility Points

### 6.1 LLM Providers
Currently supports OpenAI. Easy to add:
- Anthropic Claude
- DeepSeek
- Open-source (Llama via Ollama)

**Interface**:
```python
class LLMClient(ABC):
    @abstractmethod
    def generate(self, system: str, user: str) -> str:
        pass
```

### 6.2 Evaluation Engines
Currently designed for Stockfish. Can add:
- Leela Chess Zero (NNUE)
- Komodo
- Multiple engines voting

### 6.3 Beauty Metrics
Add new aesthetic scoring dimensions:
- Sacrifice elegance (e.g., quiet sacrifice vs. forcing)
- Endgame purity (e.g., minimize pieces)
- Opening principle adherence

---

## 7. Performance Considerations

### 7.1 LLM Costs
- 40-move game ≈ 4000-5000 tokens
- OpenAI GPT-4: ~$0.15-0.20 per game
- Batch generation: ~5 games/minute

### 7.2 Validation Speed
- `python-chess` move validation: ~1ms per move
- Full game validation (40 moves): ~40ms

### 7.3 Stockfish Evaluation
- Depth 15: ~1 second per position
- Full game (40 moves): ~40 seconds
- **Optimization**: Parallel evaluation, caching

---

## 8. Testing Strategy

### 8.1 Unit Tests
- `test_legality.py`: Move validation, PGN parsing
- `test_beauty_eval.py`: Score calculation
- `test_style_slider.py`: Style configuration

### 8.2 Integration Tests
- LLM → Parser → Validator pipeline
- Full game generation end-to-end
- PGN export and file integrity

### 8.3 Sanity Checks
- No move appears twice in a row
- Game terminates (checkmate or stalemate)
- Beauty score is always 0-100

### 8.4 Turing Tests (Future)
- Generate 50 games
- Mix with real GM games (1900-2400 ELO)
- Have humans rate for creativity/soundness/memorability

---

## 9. Security & Robustness

### 9.1 Input Validation
- LLM output size limits (prevent token waste)
- Timeout on generation (avoid infinite loops)
- Sandboxing (no file access, network limitations)

### 9.2 API Key Management
- Stored in `.env` (never committed to Git)
- Rate limiting to prevent abuse
- Fallback to mock client for testing

---

## 10. Future Directions

### 10.1 Real-Time Feedback Loop
Currently: LLM → Validator → Curator  
Future: LLM ↔ Stockfish (iterative refinement)

"This move loses 2 pawns. Reconsider. Or proceed with tactical compensation?"

### 10.2 Game Narrative
Auto-generate GM commentary:
- "A bold sacrifice in the Romantic style"
- "Karpov would approve of this squeeze"
- "The queen maneuver from d1-h5 creates an unstoppable attack"

### 10.3 Style Transfer
Learn style from master games:
- Tal: Analyze 100 Tal games, extract tactical patterns
- Capablanca: Extract positional principles
- Neural: Learn from AlphaZero games

### 10.4 Multi-Agent Tournaments
Generate games between competing personas:
- Tal vs. Capablanca
- Morphy vs. Fischer
- Human vs. CAISSA

---

## 11. Phase 3.1 Enhancements Summary

### 11.1 Generator Enhancements (`core/generator.py`)
- **RetryStrategy** - Enum: IMMEDIATE, EXPONENTIAL, LINEAR, ADAPTIVE
- **RetryConfig** - Configurable retry behavior with jitter
- **GenerationProgress** - Real-time progress tracking with callbacks
- **GenerationResult** - Rich result with quality, beauty score, metadata
- **BatchResult** - Aggregate results for multi-game generation
- **GenerationStats** - Cumulative statistics tracking
- **CacheEntry** - Move caching for improved performance

**New Methods**:
- `generate_game_advanced()` - Extended result information
- `generate_batch()` - Multi-game batch generation
- `generate_until_quality()` - Quality-threshold generation
- `set_retry_config()`, `set_progress_callback()`
- `cache_move()`, `get_cached_move()`, `clear_cache()`
- `get_stats()`, `save_stats()`, `load_stats()`

### 11.2 Prompt Manager Enhancements (`core/prompt_manager.py`)
- **HistoricalPlayer** - 15 chess masters (Morphy to AlphaZero)
- **NarrativeArc** - 7 story templates (Blitzkrieg, Comeback, Brilliancy, etc.)
- **PromptStage** - Multi-stage generation pipeline
- **DifficultyLevel** - Beginner to Grandmaster complexity
- **PlayerPersonality** - Full personality profiles with style data
- **AdvancedGameContext** - Extended context with personalities/narratives

**New Methods**:
- `build_system_prompt_advanced()` - Personality-injected prompts
- `build_multi_stage_prompts()` - Staged generation approach
- `build_commentary_prompt()` - GM commentary generation
- `create_context_for_matchup()` - Historical player matchups

### 11.3 Legality Enhancements (`engine/legality.py`)
- **MoveClassification** - Tactical, positional, quiet, forcing, etc.
- **TacticalMotif** - Fork, pin, skewer, discovered attack, etc.
- **ValidationSeverity** - Error, warning, info, suggestion
- **MoveQualityHint** - Quality assessment for validated moves
- **CandidateMove** - Alternative move suggestions
- **AdvancedLegalityReport** - Extended validation with hints

**New Methods**:
- `parse_and_validate_move_advanced()` - Full quality analysis
- `validate_game_pgn_advanced()` - Rich game validation
- `get_move_candidates()` - Get candidate moves by classification
- `suggest_repairs_for_game()` - Repair suggestions for illegal moves

### 11.4 PGN Builder Enhancements (`export/pgn_builder.py`)
- **NAG** - 50+ Numeric Annotation Glyphs
- **ExportFormat** - PGN, Markdown, HTML, JSON
- **MoveAnnotation** - Full annotation with NAGs, comments, evals
- **Variation** - Alternative line support
- **GameMetadata** - Extended headers (ECO, Elo, TimeControl)

**New Methods**:
- `add_move_advanced()` - Move with annotations/variations
- `annotate_move()` - Add annotations to existing moves
- `add_variation()` - Add alternative lines
- `build_pgn_advanced()` - Full-featured PGN output
- `export_markdown()`, `export_html()`, `export_json()`
- `generate_evaluation_annotations()` - Auto-annotate from evals

---

## 12. Phase 3.2 Enhancements Summary

Phase 3.2 adds comprehensive metrics, benchmarking, and end-to-end testing.

### 12.1 Provider Metrics (`core/llm_provider.py`)
- **CostTier** - FREE, BUDGET, STANDARD, PREMIUM
- **TokenUsage** - Input/output token tracking
- **CostEstimate** - USD cost estimation per generation
- **GenerationMetrics** - Full metrics for each LLM call
- **ProviderMetrics** - Aggregate metrics for providers

**New Methods**:
- `generate_with_metrics()` - Generate with full metrics tracking
- `enable_metrics()` - Enable aggregate metrics collection
- `get_metrics()` - Get current aggregate metrics
- `reset_metrics()` - Reset aggregate metrics

**Utility Functions**:
- `estimate_cost()` - Estimate cost for model/tokens
- `estimate_tokens()` - Estimate tokens from text

**MODEL_PRICING** - Pricing database for all supported models

### 12.2 Benchmarking (`benchmarks/provider_benchmark.py`)
- **ProviderPricing** - Cost estimation per model
- **LatencyMetrics** - Min/max/mean/median/p95/p99 latency
- **QualityMetrics** - Response quality assessment
- **BenchmarkResult** - Complete benchmark for one provider
- **BenchmarkSuite** - Multi-provider benchmark results
- **BenchmarkEngine** - Run benchmarks with configurable prompts

**CLI Usage**:
```bash
python -m benchmarks.provider_benchmark --providers openai,anthropic --runs 5
python -m benchmarks.provider_benchmark --all --output results.json
```

### 12.3 Live Provider Testing (`tests/test_live_providers.py`)
- Tests for OpenAI, Anthropic, Azure, Gemini, Ollama
- Skipped in CI (requires `--run-live` flag)
- Provider comparison tests
- Response quality validation

### 12.4 End-to-End Testing (`tests/test_e2e_generation.py`)
- Full pipeline tests (Prompt → LLM → Parser → Validator → PGN)
- Batch generation testing
- Advanced context generation
- Progress tracking integration
- Multi-format export validation

---

## 13. Conclusion

CAISSA represents a paradigm shift in chess AI:

**Old Paradigm**: Engines optimize for winning (ELO rating)  
**New Paradigm**: Engines optimize for beauty and instruction

By combining LLM creativity, chess rule enforcement, tactical soundness, and aesthetic evaluation, CAISSA generates chess games that are:

✓ **Legally valid**  
✓ **Strategically coherent**  
✓ **Aesthetically stunning**  
✓ **Humanly memorable**  

The system is modular, testable, and extensible. The foundation is solid. The frontier awaits. 🚀

---

**Next Phase**: Phase 4.0 - Web Interface, Game Database, Research Paper Integration

**"We don't generate chess games. We generate immortality."** ♟️
