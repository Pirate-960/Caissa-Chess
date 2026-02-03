# ♟️ CAISSA Phase 3: The Engine's Eye - Comprehensive Execution Prompt

**Last Updated**: February 3, 2026  
**Phase Status**: Ready for Implementation  
**Target Version**: v0.3.0  
**Audience**: Senior Python/Chess Engineers, LLM Coding Assistants (Claude 3.5 Sonnet, GPT-4, Cursor)

---

## 📋 Executive Summary

**Mission**: Integrate the Stockfish chess engine into CAISSA to provide tactical analysis, sacrifice detection, and blunder filtering. This transforms CAISSA from a "legally valid game generator" into a "strategically sound game generator."

**Current State**:
- ✅ Phase 1: Core architecture, legality validation, prompt engineering
- ✅ Phase 2: Multi-provider LLM integration (6 providers, 49 tests)
- ⏳ Phase 3 (THIS): Stockfish integration for "chess vision"

**Deliverables**:
1. `engine/stockfish_client.py` - Robust UCI engine wrapper
2. `aesthetic/beauty_eval.py` - Refactored with real engine data
3. `core/generator.py` - Updated generation loop with soundness checks
4. `tests/test_stockfish.py` - Comprehensive test suite with mocking
5. `setup_stockfish.py` - Installation and configuration helper
6. Updated `pyproject.toml` and documentation

**Constraints**:
- Graceful degradation: Must work without Stockfish binary (Passive Mode)
- CI/CD safe: No crashes on missing binary
- Performance: Lightweight analysis suitable for game generation
- Type-safe: Full type hints for Python 3.11+

---

## 🎯 Part 1: Foundation & Architecture

### 1.1 Conceptual Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CAISSA Phase 3 Pipeline                      │
└─────────────────────────────────────────────────────────────────┘

Input: GameContext (era, theme, style, aggression)
   │
   ▼
┌──────────────────────────────────────────────────┐
│ 1. THE DREAMER (LLM)                             │
│    Suggests move: "e4" (from context)            │
└──────────────────────────────────────────────────┘
   │
   ▼
┌──────────────────────────────────────────────────┐
│ 2. THE ARCHITECT (python-chess Legality)         │
│    ✅ Is "e4" legal?                             │
└──────────────────────────────────────────────────┘
   │
   ├─ (Illegal) → Ask LLM to retry
   │
   ▼ (Legal)
┌──────────────────────────────────────────────────┐
│ 3. THE CRITIC (Stockfish Analysis) [NEW]         │
│    ✅ Is "e4" sound? (not a blunder?)            │
│    ✅ Material trade fair?                       │
│    ✅ Best move or suboptimal?                   │
└──────────────────────────────────────────────────┘
   │
   ├─ (Blunder) → Ask LLM to retry
   │
   ▼ (Sound)
┌──────────────────────────────────────────────────┐
│ 4. THE CURATOR (Beauty Evaluation) [ENHANCED]    │
│    Score = Stockfish analysis + Style weighting │
│    Sacrifice bonus, Drama bonus, Accuracy bonus  │
└──────────────────────────────────────────────────┘
   │
   ▼
Output: Beautiful, legal, sound chess game with Beauty Score
```

### 1.2 Key Design Decisions

| Decision | Rationale | Implementation |
|----------|-----------|-----------------|
| **Stockfish over alternatives** | Most accurate, widely available, free | UCI protocol via `python-chess` |
| **Passive Mode on missing binary** | CI/CD safe, developer-friendly | All methods return `None` or defaults |
| **Low-depth analysis (10-15)** | Fast enough for real-time generation | Configurable via `depth` parameter |
| **Centipawn threshold 300cp** | Distinguishes blunders from minor inaccuracies | Configurable per style |
| **Process pooling optional** | Avoid thread spawn overhead | Future optimization for batch games |

---

## 🏗️ Part 2: Implementation Specifications

### 2.1 File: `engine/stockfish_client.py`

**Purpose**: Unified interface to Stockfish via UCI protocol.

**Dependencies**:
```
python-chess >= 1.10.0  (Already in pyproject.toml)
stockfish (Binary, not pip; OR python-stockfish if needed for wrapper)
```

**Class Hierarchy**:

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, List
import chess
import chess.engine

@dataclass
class EvaluationResult:
    """Result of engine evaluation."""
    score_cp: int  # Centipawns (positive = White winning)
    is_mate: bool  # True if mate score
    mate_in: Optional[int] = None  # Moves until mate
    best_move: Optional[chess.Move] = None  # Top engine move
    principal_variation: List[chess.Move] = None  # PV line
    depth: int = 0  # Analysis depth reached
    time_used: float = 0.0  # Time spent (seconds)

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "score_cp": self.score_cp,
            "is_mate": self.is_mate,
            "mate_in": self.mate_in,
            "best_move": self.best_move.uci() if self.best_move else None,
            "depth": self.depth,
        }

class EngineMode(Enum):
    """Engine operational mode."""
    ACTIVE = "active"  # Stockfish available and running
    PASSIVE = "passive"  # Stockfish unavailable, fallback mode
    DISABLED = "disabled"  # User disabled engine


class StockfishClient:
    """
    Thread-safe wrapper around Stockfish UCI engine.
    
    Provides analysis for move evaluation, sacrifice detection, and blunder filtering.
    Gracefully degrades to Passive Mode if Stockfish binary is unavailable.
    """
    
    def __init__(
        self,
        binary_path: Optional[str] = None,
        depth: int = 15,
        time_limit: float = 0.1,
        threads: int = 1,
        hash_mb: int = 64,
    ):
        """
        Initialize Stockfish client.
        
        Args:
            binary_path: Path to Stockfish binary. If None, searches system PATH.
            depth: Default analysis depth (1-32).
            time_limit: Default time limit per position (seconds).
            threads: Number of CPU threads for engine.
            hash_mb: Transposition table size (MB).
        
        Raises:
            None (gracefully falls back to Passive Mode if binary missing).
        """
        
        self.mode = EngineMode.ACTIVE
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self.binary_path = binary_path
        self.depth = depth
        self.time_limit = time_limit
        self.threads = threads
        self.hash_mb = hash_mb
        self.analysis_cache = {}  # FEN -> EvaluationResult
        self._cache_hits = 0
        self._cache_misses = 0
        
        self._init_engine()
    
    def _init_engine(self) -> None:
        """Initialize engine process. Falls back to Passive Mode on failure."""
        try:
            # Try to find Stockfish binary
            if self.binary_path:
                engine_path = self.binary_path
            else:
                engine_path = self._find_stockfish_binary()
            
            if not engine_path:
                self._log_passive_mode("Stockfish binary not found")
                return
            
            # Start UCI engine
            self.engine = chess.engine.SimpleEngine.popen_uci(engine_path)
            self.engine.configure({
                "Threads": self.threads,
                "Hash": self.hash_mb,
            })
            
            logger.info(f"✅ Stockfish initialized: {engine_path}")
            self.mode = EngineMode.ACTIVE
            
        except Exception as e:
            self._log_passive_mode(f"Initialization failed: {str(e)}")
    
    def _find_stockfish_binary(self) -> Optional[str]:
        """Search system PATH for Stockfish binary."""
        import shutil
        import platform
        
        candidates = ["stockfish", "stockfish.exe"]
        if platform.system() == "Darwin":  # macOS
            candidates.append("stockfish-mac")
        
        for candidate in candidates:
            path = shutil.which(candidate)
            if path:
                return path
        
        return None
    
    def _log_passive_mode(self, reason: str) -> None:
        """Log transition to Passive Mode."""
        logger.warning(
            f"⚠️  Stockfish unavailable ({reason}). "
            "Falling back to Passive Mode (heuristic evaluation only)."
        )
        self.mode = EngineMode.PASSIVE
    
    def is_active(self) -> bool:
        """Check if engine is in Active Mode."""
        return self.mode == EngineMode.ACTIVE and self.engine is not None
    
    # ─────────────────────────────────────────────────────────────
    # Core Analysis Methods
    # ─────────────────────────────────────────────────────────────
    
    def evaluate(
        self,
        board: chess.Board,
        depth: Optional[int] = None,
    ) -> EvaluationResult:
        """
        Analyze a position and return evaluation from White's perspective.
        
        Args:
            board: Chess position to analyze.
            depth: Analysis depth (overrides default).
        
        Returns:
            EvaluationResult with score, best move, and metadata.
            In Passive Mode, returns neutral EvaluationResult.
        """
        
        if not self.is_active():
            return self._passive_evaluation(board)
        
        fen = board.fen()
        
        # Check cache
        if fen in self.analysis_cache:
            self._cache_hits += 1
            return self.analysis_cache[fen]
        
        self._cache_misses += 1
        
        try:
            analysis = self.engine.analyse(
                board,
                chess.engine.Limit(depth=depth or self.depth),
            )
            
            score = analysis.get("score")
            pv = analysis.get("pv", [])
            
            # Convert score to centipawns (from White's perspective)
            if score.is_mate():
                score_cp = 32000 if score.white() > 0 else -32000
                mate_in = abs(score.white()) if score.white() != 0 else None
                is_mate = True
            else:
                score_cp = score.white().cp
                mate_in = None
                is_mate = False
            
            result = EvaluationResult(
                score_cp=score_cp,
                is_mate=is_mate,
                mate_in=mate_in,
                best_move=pv[0] if pv else None,
                principal_variation=pv,
                depth=analysis.get("depth", depth or self.depth),
                time_used=analysis.get("time", 0),
            )
            
            self.analysis_cache[fen] = result
            return result
            
        except Exception as e:
            logger.error(f"Evaluation error: {str(e)}")
            return self._passive_evaluation(board)
    
    def evaluate_move(
        self,
        board: chess.Board,
        move: chess.Move,
    ) -> Dict[str, any]:
        """
        Analyze a specific move's impact.
        
        Returns:
            {
                "before": EvaluationResult (position before move),
                "after": EvaluationResult (position after move),
                "eval_change": int (centipawns, negative = worse),
                "is_best_move": bool,
                "move_quality": "Brilliant" | "Good" | "Adequate" | "Inaccuracy" | "Blunder",
            }
        """
        
        if not self.is_active():
            return self._passive_move_evaluation(board, move)
        
        before = self.evaluate(board)
        board.push(move)
        after = self.evaluate(board)
        board.pop()
        
        eval_change = after.score_cp - before.score_cp
        is_best = move == before.best_move if before.best_move else False
        
        # Classify move quality
        if is_best:
            quality = "Brilliant"
        elif eval_change > -50:
            quality = "Good"
        elif eval_change > -150:
            quality = "Adequate"
        elif eval_change > -300:
            quality = "Inaccuracy"
        else:
            quality = "Blunder"
        
        return {
            "before": before,
            "after": after,
            "eval_change": eval_change,
            "is_best_move": is_best,
            "move_quality": quality,
        }
    
    # ─────────────────────────────────────────────────────────────
    # Chess-Specific Analysis
    # ─────────────────────────────────────────────────────────────
    
    def is_blunder(
        self,
        board: chess.Board,
        move: chess.Move,
        threshold: int = 300,
    ) -> bool:
        """
        Detect if a move is a blunder (significant eval loss).
        
        Args:
            board: Current position.
            move: Move to evaluate.
            threshold: CP loss threshold to classify as blunder.
        
        Returns:
            True if eval drops by > threshold.
        """
        
        if not self.is_active():
            return False  # Passive Mode: assume no blunders
        
        analysis = self.evaluate_move(board, move)
        return analysis["eval_change"] < -threshold
    
    def is_sacrifice(
        self,
        board: chess.Board,
        move: chess.Move,
        safety_margin: int = 100,
    ) -> bool:
        """
        Detect if a move is a sound sacrifice.
        
        Logic:
            1. Did we lose material? (piece count drops)
            2. Did eval drop by < safety_margin? (engine approves)
            3. If both: it's a sound sacrifice
        
        Args:
            board: Current position.
            move: Move to evaluate.
            safety_margin: Max eval loss in CP to still consider "sound" (-100 = slight compensation ok).
        
        Returns:
            True if material is sacrificed but evaluation remains stable/positive.
        """
        
        if not self.is_active():
            # Fallback heuristic: check piece count only
            return self._heuristic_sacrifice(board, move)
        
        # Check material before/after
        before_material = self._material_count(board)
        board.push(move)
        after_material = self._material_count(board)
        board.pop()
        
        material_loss = before_material - after_material
        
        if material_loss <= 0:
            return False  # Not a sacrifice if no material lost
        
        # Check eval change
        analysis = self.evaluate_move(board, move)
        eval_change = analysis["eval_change"]
        
        # Sacrifice is "sound" if material lost but eval doesn't drop much
        is_sound = eval_change >= -safety_margin
        
        return is_sound and material_loss > 0
    
    def get_move_quality_analysis(
        self,
        board: chess.Board,
        move: chess.Move,
    ) -> Dict[str, any]:
        """
        Comprehensive move analysis for beauty/quality scoring.
        
        Returns:
            {
                "is_forced": bool (only legal move in response to check),
                "is_best_move": bool,
                "is_sound_sacrifice": bool,
                "eval_change_cp": int,
                "move_quality": str,
                "opportunity_cost": int (how much better is best move),
                "stunning_factor": float (0-1, how unexpected/good the move is),
            }
        """
        
        if not self.is_active():
            return self._passive_quality(board, move)
        
        analysis = self.evaluate_move(board, move)
        before = analysis["before"]
        
        # Calculate opportunity cost
        opportunity_cost = 0
        if before.best_move and before.best_move != move:
            board.push(before.best_move)
            best_eval = self.evaluate(board).score_cp
            board.pop()
            opportunity_cost = best_eval - analysis["after"].score_cp
        
        # Stunning factor: 0 = normal, 1 = brilliant sacrifice against odds
        is_sacrifice = self.is_sacrifice(board, move)
        eval_improves = analysis["eval_change"] > 0
        is_unexpected = move != before.best_move
        
        stunning = float(is_sacrifice and eval_improves and is_unexpected)
        
        return {
            "is_forced": len(list(board.legal_moves)) == 1,
            "is_best_move": analysis["is_best_move"],
            "is_sound_sacrifice": is_sacrifice,
            "eval_change_cp": analysis["eval_change"],
            "move_quality": analysis["move_quality"],
            "opportunity_cost": opportunity_cost,
            "stunning_factor": stunning,
        }
    
    # ─────────────────────────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────────────────────────
    
    @staticmethod
    def _material_count(board: chess.Board) -> int:
        """Count material value (in centipawns). White positive."""
        # Standard piece values
        values = {
            chess.PAWN: 100,
            chess.KNIGHT: 320,
            chess.BISHOP: 330,
            chess.ROOK: 500,
            chess.QUEEN: 900,
        }
        
        white_value = sum(len(board.pieces(piece, True)) * values[piece] 
                         for piece in values)
        black_value = sum(len(board.pieces(piece, False)) * values[piece] 
                         for piece in values)
        
        return white_value - black_value
    
    def _heuristic_sacrifice(self, board: chess.Board, move: chess.Move) -> bool:
        """Fallback heuristic when engine unavailable."""
        before = self._material_count(board)
        board.push(move)
        after = self._material_count(board)
        board.pop()
        return after < before
    
    def _passive_evaluation(self, board: chess.Board) -> EvaluationResult:
        """Return neutral evaluation in Passive Mode."""
        return EvaluationResult(
            score_cp=0,
            is_mate=False,
            best_move=None,
            depth=0,
        )
    
    def _passive_move_evaluation(self, board: chess.Board, move: chess.Move) -> Dict:
        """Return neutral move analysis in Passive Mode."""
        return {
            "before": self._passive_evaluation(board),
            "after": self._passive_evaluation(board),
            "eval_change": 0,
            "is_best_move": False,
            "move_quality": "Unknown",
        }
    
    def _passive_quality(self, board: chess.Board, move: chess.Move) -> Dict:
        """Return neutral quality in Passive Mode."""
        return {
            "is_forced": len(list(board.legal_moves)) == 1,
            "is_best_move": False,
            "is_sound_sacrifice": False,
            "eval_change_cp": 0,
            "move_quality": "Unknown",
            "opportunity_cost": 0,
            "stunning_factor": 0.0,
        }
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Return cache performance statistics."""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "total": total,
            "hit_rate_pct": round(hit_rate, 1),
            "cache_size": len(self.analysis_cache),
        }
    
    def clear_cache(self) -> None:
        """Clear evaluation cache."""
        self.analysis_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
    
    def quit(self) -> None:
        """Gracefully shutdown engine."""
        if self.engine:
            try:
                self.engine.quit()
                logger.info("✅ Stockfish engine shutdown")
            except Exception as e:
                logger.error(f"Error shutting down engine: {str(e)}")
        self.engine = None
    
    def __enter__(self):
        """Context manager support."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.quit()
```

---

### 2.2 File: `aesthetic/beauty_eval.py` (REFACTOR)

**Purpose**: Enhanced beauty evaluation using real engine data.

```python
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import chess
from engine.stockfish_client import StockfishClient, EvaluationResult

@dataclass
class MoveBeautyMetrics:
    """Beauty metrics for a single move."""
    sacrifice_beauty: float = 0.0  # 0-100, beauty of sacrifice if applicable
    accuracy: float = 0.0  # 0-100, how close to engine best move
    drama: float = 0.0  # 0-100, eval swing excitement
    creativity: float = 0.0  # 0-100, how unexpected the move is
    danger_factor: float = 0.0  # 0-100, how risky the move is
    
    @property
    def overall_beauty(self) -> float:
        """Weighted overall beauty score."""
        # Weights favor sacrifices and surprising good moves
        return (
            self.sacrifice_beauty * 0.3 +
            self.accuracy * 0.2 +
            self.drama * 0.25 +
            self.creativity * 0.15 +
            (100 - self.danger_factor) * 0.1
        )


class BeautyEvaluator:
    """
    Evaluates the aesthetic beauty of chess moves and games.
    
    Uses Stockfish engine data when available, falls back to heuristics.
    """
    
    def __init__(
        self,
        stockfish_client: Optional[StockfishClient] = None,
        style_config: Optional[Dict] = None,
    ):
        """
        Initialize evaluator.
        
        Args:
            stockfish_client: Optional engine for analysis.
            style_config: Style parameters (aggression, blunder_tolerance, etc).
        """
        self.engine = stockfish_client
        self.style = style_config or {}
        self.move_history: List[MoveBeautyMetrics] = []
    
    def evaluate_move(
        self,
        board: chess.Board,
        move: chess.Move,
    ) -> MoveBeautyMetrics:
        """
        Evaluate beauty of a single move.
        
        Returns:
            MoveBeautyMetrics with component scores.
        """
        
        metrics = MoveBeautyMetrics()
        
        if self.engine and self.engine.is_active():
            # Use engine-based evaluation
            analysis = self.engine.get_move_quality_analysis(board, move)
            
            # Sacrifice Beauty: up to 50 points
            if analysis["is_sound_sacrifice"]:
                metrics.sacrifice_beauty = 50.0
            
            # Accuracy: how close to best move (0-40 points)
            if analysis["is_best_move"]:
                metrics.accuracy = 40.0
            else:
                opportunity_cost = analysis["opportunity_cost"]
                metrics.accuracy = max(0, 40 - (opportunity_cost / 50))
            
            # Drama: eval swings create drama (0-30 points)
            eval_change = analysis["eval_change_cp"]
            if abs(eval_change) > 100:
                drama_intensity = min(100, abs(eval_change) / 10)
                metrics.drama = (drama_intensity / 100) * 30
            
            # Creativity: unexpected good moves (0-20 points)
            if not analysis["is_best_move"] and eval_change >= 0:
                metrics.creativity = min(20, analysis["stunning_factor"] * 20)
            
            # Danger: eval loss for risky moves (0-50 points)
            if eval_change < -100:
                metrics.danger_factor = min(100, abs(eval_change) / 10)
        
        else:
            # Fallback heuristic evaluation
            metrics = self._heuristic_evaluate(board, move)
        
        self.move_history.append(metrics)
        return metrics
    
    def evaluate_game(self, pgn_text: str) -> Dict[str, any]:
        """
        Analyze entire game and assign Beauty Score.
        
        Args:
            pgn_text: PGN notation of game.
        
        Returns:
            {
                "overall_beauty": float (0-100),
                "moves_analyzed": int,
                "sacrifice_count": int,
                "best_moves_played": int,
                "blunder_count": int,
                "avg_accuracy": float,
                "drama_peaks": List[int],
            }
        """
        
        game = chess.pgn.read_game(pgn_text)
        if not game:
            return {}
        
        board = game.board()
        move_count = 0
        sacrifice_count = 0
        best_move_count = 0
        blunder_count = 0
        drama_peaks = []
        
        for move in game.mainline_moves():
            metrics = self.evaluate_move(board, move)
            move_count += 1
            
            if metrics.sacrifice_beauty > 30:
                sacrifice_count += 1
            
            if metrics.accuracy > 35:
                best_move_count += 1
            
            if metrics.danger_factor > 70:
                blunder_count += 1
            
            if metrics.drama > 15:
                drama_peaks.append(move_count)
            
            board.push(move)
        
        # Calculate overall beauty
        move_beauties = [m.overall_beauty for m in self.move_history]
        avg_beauty = sum(move_beauties) / len(move_beauties) if move_beauties else 0
        
        # Bonus for sacrifice-heavy games
        sacrifice_multiplier = 1.0 + (sacrifice_count / move_count * 0.2)
        final_beauty = min(100, avg_beauty * sacrifice_multiplier)
        
        return {
            "overall_beauty": round(final_beauty, 1),
            "moves_analyzed": move_count,
            "sacrifice_count": sacrifice_count,
            "best_moves_played": best_move_count,
            "blunder_count": blunder_count,
            "accuracy_rate": round(best_move_count / move_count * 100, 1),
            "drama_peaks": drama_peaks,
            "move_metrics": [m.__dict__ for m in self.move_history],
        }
    
    def _heuristic_evaluate(self, board: chess.Board, move: chess.Move) -> MoveBeautyMetrics:
        """Fallback heuristic when engine unavailable."""
        # Placeholder: implement simple heuristics
        return MoveBeautyMetrics(
            accuracy=50.0,
            drama=25.0,
            creativity=15.0,
        )
    
    def reset(self) -> None:
        """Reset move history."""
        self.move_history.clear()
```

---

### 2.3 File: `core/generator.py` (UPDATE)

**Purpose**: Integrate Stockfish into the generation loop for soundness validation.

**Key Addition**:
```python
class CaissaGenerator:
    def __init__(
        self,
        llm_provider: LLMProvider,
        stockfish_client: Optional[StockfishClient] = None,
        max_retries: int = 3,
    ):
        self.llm = llm_provider
        self.stockfish = stockfish_client
        self.max_retries = max_retries
        self.legality_validator = LegalityValidator()
        self.beauty_evaluator = BeautyEvaluator(stockfish_client)
    
    def _validate_move(
        self,
        board: chess.Board,
        move_san: str,
        context: GameContext,
    ) -> tuple[bool, Optional[str]]:
        """
        Three-layer validation: Legality → Soundness → Style Alignment.
        
        Returns:
            (is_valid, error_reason)
        """
        
        # Layer 1: Legality
        try:
            move = board.parse_san(move_san)
            if move not in board.legal_moves:
                return False, f"Illegal move: {move_san}"
        except:
            return False, f"Invalid notation: {move_san}"
        
        # Layer 2: Soundness (if Stockfish available)
        if self.stockfish and self.stockfish.is_active():
            is_blunder = self.stockfish.is_blunder(
                board,
                move,
                threshold=context.blunder_threshold,
            )
            
            # Allow blunders based on style
            allow_blunders = context.style in ["Coffee House", "Romantic"]
            
            if is_blunder and not allow_blunders:
                eval_loss = self.stockfish.evaluate_move(board, move)["eval_change"]
                return False, f"Blunder detected (eval loss: {eval_loss}cp). Suggest alternative."
        
        # Layer 3: Style alignment
        # (E.g., "Kasparov" style should avoid perpetual checks)
        # TODO: Implement style-specific filters
        
        return True, None
    
    def generate_game(self, context: GameContext) -> tuple[bool, str, List[str]]:
        """
        Generate a game with integrated Stockfish validation.
        
        Generation loop:
            1. Get LLM move suggestion
            2. Validate legality
            3. Validate soundness (NEW)
            4. Apply move
            5. Repeat until game ends
        """
        
        board = chess.Board()
        moves = []
        retry_count = 0
        max_attempts = context.move_limit * self.max_retries
        attempt = 0
        
        while not board.is_game_over() and attempt < max_attempts:
            attempt += 1
            
            # Get LLM suggestion
            response = self.llm.generate(
                prompt=self._build_prompt(board, context),
                max_tokens=100,
            )
            
            # Parse move from response
            suggested_move = self._extract_move(response, board)
            if not suggested_move:
                if retry_count < self.max_retries:
                    retry_count += 1
                    continue
                else:
                    return False, "LLM failed to suggest valid move", moves
            
            # Validate move (3 layers)
            is_valid, error = self._validate_move(board, suggested_move, context)
            
            if not is_valid:
                if retry_count < self.max_retries:
                    # Send error feedback to LLM
                    self.llm.add_message(
                        role="assistant",
                        content=f"Error: {error}. Suggest a different move."
                    )
                    retry_count += 1
                    continue
                else:
                    return False, f"Move validation failed: {error}", moves
            
            # Move is valid and sound
            move = board.parse_san(suggested_move)
            board.push(move)
            moves.append(suggested_move)
            retry_count = 0  # Reset retry counter on success
        
        # Generate PGN
        pgn_text = self._generate_pgn(board, moves, context)
        
        return True, pgn_text, moves
```

---

### 2.4 File: `tests/test_stockfish.py` (NEW)

**Purpose**: Comprehensive test suite with mocking for CI/CD safety.

```python
import unittest
from unittest.mock import Mock, patch, MagicMock
import chess
from engine.stockfish_client import StockfishClient, EvaluationResult, EngineMode


class TestStockfishClient(unittest.TestCase):
    """Test Stockfish client initialization, analysis, and fallback modes."""
    
    def test_initialization_binary_missing(self):
        """Verify Passive Mode when binary is unavailable."""
        with patch("engine.stockfish_client.StockfishClient._find_stockfish_binary") as mock_find:
            mock_find.return_value = None
            
            client = StockfishClient(binary_path=None)
            
            self.assertEqual(client.mode, EngineMode.PASSIVE)
            self.assertFalse(client.is_active())
    
    def test_initialization_binary_found(self):
        """Verify Active Mode when binary is found."""
        with patch("chess.engine.SimpleEngine.popen_uci") as mock_engine:
            mock_engine.return_value = MagicMock()
            
            client = StockfishClient(binary_path="/usr/bin/stockfish")
            
            self.assertEqual(client.mode, EngineMode.ACTIVE)
            self.assertTrue(client.is_active())
            client.quit()
    
    def test_passive_evaluation(self):
        """Verify neutral evaluation in Passive Mode."""
        client = StockfishClient(binary_path="/nonexistent/path")
        board = chess.Board()
        
        result = client.evaluate(board)
        
        self.assertEqual(result.score_cp, 0)
        self.assertFalse(result.is_mate)
        self.assertIsNone(result.best_move)
    
    def test_blunder_detection(self):
        """Test blunder detection (eval drop > threshold)."""
        with patch("chess.engine.SimpleEngine.popen_uci") as mock_engine:
            # Mock engine analysis
            mock_analysis = {
                "score": MagicMock(),
                "pv": [chess.Move.from_uci("e2e4")],
                "depth": 15,
            }
            mock_analysis["score"].is_mate.return_value = False
            mock_analysis["score"].white.return_value = MagicMock(cp=50)  # +0.5
            
            mock_engine_instance = MagicMock()
            mock_engine_instance.analyse.return_value = mock_analysis
            mock_engine.return_value = mock_engine_instance
            
            client = StockfishClient(binary_path="/usr/bin/stockfish")
            board = chess.Board()
            board.push_san("e4")  # 1. e4
            
            # Simulate eval drop after bad move
            move = chess.Move.from_uci("e4e3")  # Bad move
            
            # Mock evaluate_move to return large eval drop
            with patch.object(client, "evaluate_move") as mock_eval:
                mock_eval.return_value = {
                    "before": EvaluationResult(score_cp=50, is_mate=False),
                    "after": EvaluationResult(score_cp=-300, is_mate=False),
                    "eval_change": -350,
                    "is_best_move": False,
                    "move_quality": "Blunder",
                }
                
                is_blunder = client.is_blunder(board, move, threshold=300)
                self.assertTrue(is_blunder)
            
            client.quit()
    
    def test_sacrifice_detection(self):
        """Test sacrifice detection (material loss + eval stability)."""
        with patch("chess.engine.SimpleEngine.popen_uci"):
            client = StockfishClient(binary_path="/usr/bin/stockfish")
            
            # Set up a position where a sacrifice makes sense
            board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
            
            with patch.object(client, "evaluate_move") as mock_eval:
                with patch.object(client, "_material_count") as mock_mat:
                    # Material before: equal
                    # Material after: down 1 pawn (100cp)
                    # Eval before: +0
                    # Eval after: +100 (compensation found!)
                    
                    mock_eval.return_value = {
                        "eval_change": 0,  # No eval drop = sound sacrifice
                        "is_best_move": False,
                    }
                    
                    move = chess.Move.from_uci("e2e4")
                    mock_mat.side_effect = [1000, 900]  # Material loss of 100cp
                    
                    is_sacrifice = client.is_sacrifice(board, move, safety_margin=50)
                    # This would be True if material loss > 0 and eval_change >= -safety_margin
            
            client.quit()
    
    def test_cache_performance(self):
        """Verify caching and cache statistics."""
        with patch("chess.engine.SimpleEngine.popen_uci"):
            client = StockfishClient(binary_path="/usr/bin/stockfish")
            board = chess.Board()
            
            with patch.object(client.engine, "analyse") as mock_analyse:
                mock_analyse.return_value = {
                    "score": MagicMock(is_mate=lambda: False, white=lambda: MagicMock(cp=20)),
                    "pv": [chess.Move.from_uci("e2e4")],
                    "depth": 15,
                }
                
                # First evaluation: cache miss
                result1 = client.evaluate(board)
                stats = client.get_cache_stats()
                self.assertEqual(stats["hits"], 0)
                self.assertEqual(stats["misses"], 1)
                
                # Second evaluation (same position): cache hit
                result2 = client.evaluate(board)
                stats = client.get_cache_stats()
                self.assertEqual(stats["hits"], 1)
                self.assertEqual(stats["misses"], 1)
            
            client.quit()
    
    def test_context_manager(self):
        """Verify context manager cleanup."""
        with patch("chess.engine.SimpleEngine.popen_uci"):
            with StockfishClient(binary_path="/usr/bin/stockfish") as client:
                self.assertTrue(client.is_active())
            
            # After context exit, engine should be quit
            # (Can't easily verify quit was called, but no exception is good)


class TestStockfishIntegration(unittest.TestCase):
    """Integration tests with actual chess positions."""
    
    def test_starting_position_evaluation(self):
        """Stockfish evaluation of starting position should be ~+0.2."""
        with patch("chess.engine.SimpleEngine.popen_uci") as mock_engine:
            mock_analysis = {
                "score": MagicMock(is_mate=lambda: False, white=lambda: MagicMock(cp=20)),
                "pv": [chess.Move.from_uci("e2e4")],
                "depth": 15,
            }
            mock_engine_instance = MagicMock()
            mock_engine_instance.analyse.return_value = mock_analysis
            mock_engine.return_value = mock_engine_instance
            
            client = StockfishClient(binary_path="/usr/bin/stockfish")
            board = chess.Board()
            result = client.evaluate(board)
            
            self.assertEqual(result.score_cp, 20)
            self.assertIsNotNone(result.best_move)
            client.quit()


if __name__ == "__main__":
    unittest.main()
```

---

### 2.5 File: `setup_stockfish.py` (NEW)

**Purpose**: Helper script to detect, install, and configure Stockfish.

```python
#!/usr/bin/env python3
"""
Setup and configuration helper for Stockfish chess engine.

Detects system, downloads appropriate binary, and configures .env.
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path


def check_stockfish() -> str | None:
    """Check if Stockfish is already installed."""
    path = shutil.which("stockfish")
    if path:
        print(f"✅ Stockfish found: {path}")
        return path
    print("❌ Stockfish not found in PATH")
    return None


def get_download_url() -> str:
    """Get appropriate Stockfish download URL for current system."""
    system = platform.system()
    arch = platform.machine()
    
    base_url = "https://github.com/official-stockfish/Stockfish/releases/download/sf16/stockfish"
    
    if system == "Windows":
        return f"{base_url}-windows-x86_64-avx2.exe"
    elif system == "Darwin":  # macOS
        if arch == "arm64":
            return f"{base_url}-mac-m1"
        else:
            return f"{base_url}-mac-x86_64"
    elif system == "Linux":
        return f"{base_url}-ubuntu-x86_64-avx2"
    else:
        raise ValueError(f"Unsupported platform: {system}")


def download_stockfish(url: str, destination: Path) -> bool:
    """Download Stockfish binary."""
    print(f"📥 Downloading Stockfish from: {url}")
    
    try:
        import requests
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        destination.chmod(0o755)
        print(f"✅ Downloaded to: {destination}")
        return True
    
    except ImportError:
        print("⚠️  requests library not found. Using curl instead...")
        subprocess.run(["curl", "-L", "-o", str(destination), url], check=True)
        destination.chmod(0o755)
        return True
    except Exception as e:
        print(f"❌ Download failed: {str(e)}")
        return False


def setup_env() -> None:
    """Configure .env file with Stockfish path."""
    env_file = Path(".env")
    stockfish_path = shutil.which("stockfish")
    
    if not stockfish_path:
        print("⚠️  Stockfish path not found. Skipping .env setup.")
        return
    
    env_content = f"STOCKFISH_PATH={stockfish_path}\n"
    
    if env_file.exists():
        with open(env_file, "r") as f:
            content = f.read()
        
        if "STOCKFISH_PATH" in content:
            print("ℹ️  STOCKFISH_PATH already in .env")
            return
    
    with open(env_file, "a") as f:
        f.write(env_content)
    
    print(f"✅ Added to .env: {env_content.strip()}")


def main():
    """Main setup routine."""
    print("="*60)
    print("⚙️  CAISSA Stockfish Setup")
    print("="*60)
    
    # Check if already installed
    if check_stockfish():
        setup_env()
        return 0
    
    # Suggest installation methods
    print("\n📖 Installation Options:")
    print("  1. Download directly (script)")
    print("  2. Manual installation")
    print("  3. Package manager (apt, brew, choco)")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == "1":
        try:
            url = get_download_url()
            dest = Path("./bin/stockfish")
            dest.parent.mkdir(exist_ok=True)
            
            if download_stockfish(url, dest):
                print(f"✅ Stockfish ready at: {dest}")
                setup_env()
            else:
                print("❌ Setup failed")
                return 1
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return 1
    
    elif choice == "2":
        system = platform.system()
        print(f"\nFor {system}, visit: https://stockfishchess.org/download/")
        print("After installation, run this script again.")
    
    elif choice == "3":
        system = platform.system()
        if system == "Darwin":
            print("  brew install stockfish")
        elif system == "Linux":
            print("  sudo apt-get install stockfish")
        elif system == "Windows":
            print("  choco install stockfish")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

### 2.6 File: `pyproject.toml` (UPDATE)

Add the `stockfish` dependency (optional, for pip-installed wrapper):

```toml
[tool.poetry.dependencies]
python = "^3.11"
python-chess = "^1.10.0"
openai = "^1.3.0"
anthropic = "^0.7.0"
google-generativeai = "^0.3.0"
requests = "^2.31.0"
pydantic = "^2.0"
python-dotenv = "^1.0.0"
tenacity = "^8.2.3"
stockfish = "^3.28.0"  # Optional: if using pip-installed wrapper

[tool.poetry.dev-dependencies]
pytest = "^7.4.0"
pytest-cov = "^4.1.0"
black = "^23.0.0"
isort = "^5.12.0"
mypy = "^1.5.0"
```

---

## 🧪 Part 3: Integration Guide

### 3.1 Integration with Generator

```python
# core/generator.py

from engine.stockfish_client import StockfishClient
from aesthetic.beauty_eval import BeautyEvaluator

class CaissaGenerator:
    def __init__(self, llm_provider, stockfish_path=None):
        self.llm = llm_provider
        self.stockfish = StockfishClient(binary_path=stockfish_path)
        self.beauty = BeautyEvaluator(self.stockfish)
    
    def generate_game(self, context):
        board = chess.Board()
        moves = []
        
        while not board.is_game_over():
            # Get LLM move
            move_san = self.llm.generate_move(board, context)
            
            # Validate (legality + soundness)
            if not self._validate_move(board, move_san, context):
                # Ask LLM to retry with error feedback
                continue
            
            # Apply move
            move = board.parse_san(move_san)
            board.push(move)
            moves.append(move_san)
        
        # Score the game
        pgn = self._to_pgn(board, moves)
        beauty_score = self.beauty.evaluate_game(pgn)
        
        return pgn, beauty_score
```

---

## 🎬 Part 4: Execution Steps for LLM

When pasting this into Claude/GPT-4/Cursor, follow these steps:

### Step 1: Create Files
Create the following files in order:
1. `engine/stockfish_client.py` - Core engine wrapper
2. `aesthetic/beauty_eval.py` - Refactored evaluator
3. `core/generator.py` - Updated with soundness checks
4. `tests/test_stockfish.py` - Test suite
5. `setup_stockfish.py` - Setup helper

### Step 2: Update Dependencies
Add `stockfish` to `pyproject.toml` (optional, can use UCI via `python-chess`).

### Step 3: Install & Test
```bash
poetry install
python setup_stockfish.py  # Install Stockfish
poetry run pytest tests/test_stockfish.py -v
```

### Step 4: Git Commit
```bash
git add -A
git commit -m "feat(phase-3): Stockfish integration with sacrifice detection"
git push origin feature/stockfish-integration
```

### Step 5: Create PR
Create a pull request to `develop` with description:
```
Phase 3: The Engine's Eye - Stockfish Integration

Implements tactical analysis, sacrifice detection, and blunder filtering.

- StockfishClient: Robust UCI wrapper with Passive Mode fallback
- BeautyEvaluator: Enhanced with real engine data
- Generator: Three-layer validation (legality → soundness → style)
- 100% CI/CD safe with graceful degradation

Closes #[phase-3]
```

---

## ✅ Validation Checklist

Before marking Phase 3 complete:

- [ ] `test_stockfish.py` passes with 100% coverage
- [ ] Generator integrates Stockfish without breaking existing tests
- [ ] Passive Mode works (no crashes on missing binary)
- [ ] Cache performance is good (> 70% hit rate in typical games)
- [ ] Documentation updated with setup instructions
- [ ] PR reviewed and merged to `develop`

---

## 🚀 Next Steps (Phase 3.1)

After Phase 3 merges:
1. Add real-time Stockfish eval display in CLI
2. Implement style-specific blunder thresholds
3. Add batch game generation with caching
4. Performance benchmarking (games per second)

---

**"We don't generate chess games. We generate immortality."** ♟️👁️
