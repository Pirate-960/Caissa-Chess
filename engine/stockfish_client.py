"""
Stockfish Chess Engine Integration
===================================

Provides a robust UCI wrapper around Stockfish for tactical analysis,
move evaluation, and sacrifice detection.

Features:
- Thread-safe evaluation caching
- Graceful degradation (Passive Mode when binary unavailable)
- CI/CD safe (no crashes on missing engine)
- Type hints for Python 3.11+
"""

import logging
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
import chess
import chess.engine

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Result of engine evaluation."""
    score_cp: int  # Centipawns (positive = White winning)
    is_mate: bool = False  # True if mate score
    mate_in: Optional[int] = None  # Moves until mate
    best_move: Optional[chess.Move] = None  # Top engine move
    principal_variation: List[chess.Move] = field(default_factory=list)  # PV line
    depth: int = 0  # Analysis depth reached
    time_used: float = 0.0  # Time spent (seconds)

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "score_cp": self.score_cp,
            "is_mate": self.is_mate,
            "mate_in": self.mate_in,
            "best_move": str(self.best_move) if self.best_move else None,
            "principal_variation": [str(m) for m in self.principal_variation],
            "depth": self.depth,
            "time_used": self.time_used,
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
            depth: Analysis depth in half-moves.
            time_limit: Maximum time per analysis (seconds).
            threads: Number of threads to use.
            hash_mb: Transposition table size (MB).
        
        Falls back to Passive Mode if binary missing.
        """
        
        self.mode = EngineMode.ACTIVE
        self.engine: Optional[chess.engine.SimpleEngine] = None
        self.binary_path = binary_path
        self.depth = depth
        self.time_limit = time_limit
        self.threads = threads
        self.hash_mb = hash_mb
        self.analysis_cache: Dict[str, EvaluationResult] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        
        self._init_engine()
    
    def _init_engine(self) -> None:
        """Initialize engine process. Falls back to Passive Mode on failure."""
        try:
            # Try to find Stockfish binary
            binary = self.binary_path or self._find_stockfish_binary()
            
            if not binary:
                raise FileNotFoundError("Stockfish binary not found in PATH")
            
            # Launch engine
            self.engine = chess.engine.SimpleEngine.popen_uci(binary)
            
            # Configure engine
            self.engine.configure({
                "Threads": self.threads,
                "Hash": self.hash_mb,
            })
            
            self.mode = EngineMode.ACTIVE
            logger.info(f"✅ Stockfish initialized: {binary}")
            
        except Exception as e:
            self._log_passive_mode(str(e))
    
    def _find_stockfish_binary(self) -> Optional[str]:
        """Search system PATH for Stockfish binary."""
        candidates = ["stockfish", "stockfish.exe"]
        
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
                chess.engine.Limit(depth=depth or self.depth, time=self.time_limit),
            )
            
            score = analysis.get("score")
            pv = analysis.get("pv", [])
            
            # Convert score to centipawns
            if score.is_mate():
                score_cp = 32000 if score.white() > 0 else -32000  # Mate value
                is_mate = True
                mate_in = score.mate()
            else:
                score_cp = score.white().cp
                is_mate = False
                mate_in = None
            
            result = EvaluationResult(
                score_cp=score_cp,
                is_mate=is_mate,
                mate_in=mate_in,
                best_move=pv[0] if pv else None,
                principal_variation=list(pv),
                depth=analysis.get("depth", 0),
                time_used=analysis.get("time", 0.0),
            )
            
            # Cache result
            self.analysis_cache[fen] = result
            return result
            
        except Exception as e:
            logger.error(f"Evaluation error: {str(e)}")
            return self._passive_evaluation(board)
    
    def evaluate_move(
        self,
        board: chess.Board,
        move: chess.Move,
    ) -> Dict:
        """
        Analyze a specific move's impact.
        
        Returns:
            {
                "before": EvaluationResult,
                "after": EvaluationResult,
                "eval_change": int (centipawns),
                "move_quality": str,
            }
        """
        
        if not self.is_active():
            return self._passive_move_evaluation(board, move)
        
        before = self.evaluate(board)
        board.push(move)
        after = self.evaluate(board)
        board.pop()
        
        # Evaluation change from mover's perspective
        if board.turn:  # White to move originally
            eval_change = after.score_cp - before.score_cp
        else:  # Black to move originally
            eval_change = before.score_cp - after.score_cp
        
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
            "move_quality": quality,
            "is_best_move": is_best,
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
            2. Did evaluation remain stable/positive? (within safety margin)
            3. If both: it's a sound sacrifice
        
        Args:
            board: Current position.
            move: Move to evaluate.
            safety_margin: Max eval loss in CP to still consider "sound".
        
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
    ) -> Dict:
        """
        Comprehensive move analysis for beauty/quality scoring.
        
        Returns:
            {
                "is_forced": bool,
                "is_sacrifice": bool,
                "is_check": bool,
                "eval_swing": int,
                "opportunity_cost": int,
                "stunning_factor": float,
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
            best_eval = self.evaluate(board)
            board.pop()
            opportunity_cost = best_eval.score_cp - analysis["after"].score_cp
        
        # Stunning factor: 0 = normal, 1 = brilliant sacrifice against odds
        is_sacrifice = self.is_sacrifice(board, move)
        eval_improves = analysis["eval_change"] > 0
        is_unexpected = move != before.best_move
        
        stunning = float(is_sacrifice and eval_improves and is_unexpected)
        
        return {
            "is_forced": len(list(board.legal_moves)) == 1,
            "is_sacrifice": is_sacrifice,
            "is_check": board.is_check() if board.is_check() else move.uci().endswith("+"),
            "eval_swing": abs(analysis["eval_change"]),
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
            principal_variation=[],
            depth=0,
        )
    
    def _passive_move_evaluation(self, board: chess.Board, move: chess.Move) -> Dict:
        """Return neutral move analysis in Passive Mode."""
        return {
            "before": self._passive_evaluation(board),
            "after": self._passive_evaluation(board),
            "eval_change": 0,
            "move_quality": "Unknown",
            "is_best_move": False,
        }
    
    def _passive_quality(self, board: chess.Board, move: chess.Move) -> Dict:
        """Return neutral quality in Passive Mode."""
        return {
            "is_forced": len(list(board.legal_moves)) == 1,
            "is_sacrifice": False,
            "is_check": board.is_check() or move.uci().endswith("+"),
            "eval_swing": 0,
            "opportunity_cost": 0,
            "stunning_factor": 0.0,
        }
    
    def get_cache_stats(self) -> Dict:
        """Return cache performance statistics."""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": hit_rate,
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
                logger.info("✅ Stockfish engine closed")
            except Exception as e:
                logger.error(f"Error closing engine: {str(e)}")
        
        self.engine = None

    def close(self) -> None:
        """Alias for quit() - gracefully shutdown engine."""
        self.quit()

    def __del__(self):
        """Destructor - ensure engine is closed on garbage collection."""
        try:
            self.quit()
        except Exception:
            pass  # Ignore errors during destruction

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.quit()
