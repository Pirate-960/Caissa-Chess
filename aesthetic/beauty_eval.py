"""
aesthetic/beauty_eval.py

The Beauty Score Algorithm: Mathematical evaluation of game aesthetics.

Formula:
    Beauty = (Sacrifices × 3) + (Tension × 2) + (Quiet Moves × 4) - (Draws × 5)

Phase 3 Enhancement: NOW WITH STOCKFISH INTEGRATION for engine-assisted scoring.
When Stockfish is available, combines heuristic evaluation with tactical accuracy.

Phase 3.1 Enhancement: ADVANCED BEAUTY METRICS
- Game phase awareness (opening/middlegame/endgame)
- Tactical pattern recognition (pins, forks, discoveries, etc.)
- Style profile scoring (Tal-aggressive, Petrosian-prophylactic, Capablanca-technical)
- Drama and momentum tracking
- Brilliancy detection with multi-factor analysis
- Game narrative arc (story of the game)
"""

import chess
import logging
import re
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

# Phase 3: Import Stockfish client (gracefully handles missing import)
try:
    from engine.stockfish_client import StockfishClient
    STOCKFISH_AVAILABLE = True
except ImportError:
    STOCKFISH_AVAILABLE = False
    StockfishClient = None

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS: Move Classifications & Game Phases
# ═══════════════════════════════════════════════════════════════════════════════

class MoveBeautyType(str, Enum):
    """Classification of moves by aesthetic quality."""
    # Original Phase 1 types
    BRILLIANT_SACRIFICE = "brilliant_sacrifice"
    QUIET_KILLER = "quiet_killer"
    FORCING_MOVE = "forcing_move"
    POSITIONAL_SQUEEZE = "positional_squeeze"
    BORING = "boring"
    BLUNDER = "blunder"
    
    # Phase 3.1: Advanced move types
    ZWISCHENZUG = "zwischenzug"  # Intermezzo - in-between move
    PROPHYLAXIS = "prophylaxis"  # Preventing opponent's plan
    DEFENSIVE_RESOURCE = "defensive_resource"  # Saving a lost position
    EXCHANGE_SACRIFICE = "exchange_sacrifice"  # Rook for minor piece
    QUEEN_SACRIFICE = "queen_sacrifice"  # The ultimate sacrifice
    PAWN_BREAKTHROUGH = "pawn_breakthrough"  # Pawn storm or promotion threat
    KING_HUNT = "king_hunt"  # Attacking exposed king
    SIMPLIFICATION = "simplification"  # Trading into winning endgame
    MYSTERIOUS_ROOK_MOVE = "mysterious_rook_move"  # Nimzowitsch's concept


class GamePhase(str, Enum):
    """Phase of the game for context-aware evaluation."""
    OPENING = "opening"
    EARLY_MIDDLEGAME = "early_middlegame"
    MIDDLEGAME = "middlegame"
    LATE_MIDDLEGAME = "late_middlegame"
    ENDGAME = "endgame"


class TacticalPattern(str, Enum):
    """Recognized tactical patterns."""
    PIN = "pin"
    FORK = "fork"
    SKEWER = "skewer"
    DISCOVERY = "discovery"
    DOUBLE_CHECK = "double_check"
    BACK_RANK = "back_rank"
    SMOTHERED_MATE = "smothered_mate"
    DEFLECTION = "deflection"
    DECOY = "decoy"
    OVERLOAD = "overload"
    CLEARANCE = "clearance"
    WINDMILL = "windmill"
    NONE = "none"


class PlayingStyle(str, Enum):
    """Chess playing styles for style-matched scoring."""
    TAL = "tal"  # Aggressive, sacrificial
    PETROSIAN = "petrosian"  # Prophylactic, positional
    CAPABLANCA = "capablanca"  # Technical, simple
    KASPAROV = "kasparov"  # Dynamic, energetic
    CARLSEN = "carlsen"  # Universal, grinding
    MORPHY = "morphy"  # Classical attacking
    FISCHER = "fischer"  # Precise, perfectionist


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASSES: Metrics & Analysis Results
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BeautyMetrics:
    """Breakdown of beauty score components (Original Phase 1)."""
    sacrifice_score: float = 0.0
    tension_score: float = 0.0
    quiet_move_score: float = 0.0
    forcing_move_score: float = 0.0
    drama_penalty: float = 0.0
    total_score: float = 0.0


@dataclass
class AdvancedMoveMetrics:
    """
    Phase 3.1: Advanced metrics for a single move.
    Extends basic beauty scoring with tactical and stylistic analysis.
    """
    # Core beauty (from original)
    beauty_score: float = 0.0
    move_type: MoveBeautyType = MoveBeautyType.BORING
    
    # Phase 3.1: Advanced metrics
    tactical_pattern: TacticalPattern = TacticalPattern.NONE
    game_phase: GamePhase = GamePhase.MIDDLEGAME
    
    # Drama & Momentum
    drama_score: float = 0.0  # 0-100: How exciting is this moment?
    momentum_shift: float = 0.0  # -100 to +100: Swing in game direction
    
    # Brilliancy factors
    is_only_move: bool = False  # Was this the only good move?
    is_unexpected: bool = False  # Engine didn't see it at low depth?
    depth_required: int = 0  # How deep to find this move?
    
    # Style scores (0-100 for each style)
    style_scores: Dict[str, float] = field(default_factory=dict)
    
    # Engine data (if available)
    engine_eval_before: Optional[float] = None
    engine_eval_after: Optional[float] = None
    engine_best_move: Optional[str] = None
    is_engine_best: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "beauty_score": self.beauty_score,
            "move_type": self.move_type.value,
            "tactical_pattern": self.tactical_pattern.value,
            "game_phase": self.game_phase.value,
            "drama_score": self.drama_score,
            "momentum_shift": self.momentum_shift,
            "is_only_move": self.is_only_move,
            "is_unexpected": self.is_unexpected,
            "depth_required": self.depth_required,
            "style_scores": self.style_scores,
            "engine_eval_before": self.engine_eval_before,
            "engine_eval_after": self.engine_eval_after,
            "is_engine_best": self.is_engine_best,
        }


@dataclass
class GameNarrative:
    """
    Phase 3.1: Story arc of the game.
    Tracks the narrative flow for commentary generation.
    """
    opening_name: str = "Unknown Opening"
    critical_moments: List[int] = field(default_factory=list)  # Move numbers
    turning_points: List[int] = field(default_factory=list)
    brilliant_moves: List[int] = field(default_factory=list)
    blunders: List[int] = field(default_factory=list)
    
    # Narrative phases
    opening_advantage: str = "equal"  # "white", "black", "equal"
    middlegame_character: str = "balanced"  # "tactical", "positional", "closed", "open"
    endgame_type: str = "none"  # "king_pawn", "rook", "minor_piece", etc.
    
    # Drama arc
    drama_peak_move: int = 0
    max_drama: float = 0.0
    total_momentum_swings: int = 0
    
    # Final assessment
    game_quality: str = "average"  # "masterpiece", "excellent", "good", "average", "flawed"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "opening_name": self.opening_name,
            "critical_moments": self.critical_moments,
            "turning_points": self.turning_points,
            "brilliant_moves": self.brilliant_moves,
            "blunders": self.blunders,
            "opening_advantage": self.opening_advantage,
            "middlegame_character": self.middlegame_character,
            "endgame_type": self.endgame_type,
            "drama_peak_move": self.drama_peak_move,
            "max_drama": self.max_drama,
            "total_momentum_swings": self.total_momentum_swings,
            "game_quality": self.game_quality,
        }


@dataclass
class AdvancedGameMetrics:
    """
    Phase 3.1: Comprehensive game-level metrics.
    Combines original BeautyMetrics with advanced analysis.
    """
    # Original metrics (preserved)
    basic_metrics: BeautyMetrics = field(default_factory=BeautyMetrics)
    
    # Move-by-move analysis
    move_metrics: List[AdvancedMoveMetrics] = field(default_factory=list)
    
    # Aggregate scores
    total_beauty: float = 0.0
    average_beauty: float = 0.0
    
    # Phase 3.1: Advanced aggregates
    tactical_complexity: float = 0.0  # 0-100
    positional_depth: float = 0.0  # 0-100
    drama_index: float = 0.0  # 0-100
    accuracy_score: float = 0.0  # 0-100 (engine-based)
    
    # Style profile
    dominant_style: PlayingStyle = PlayingStyle.CARLSEN
    style_breakdown: Dict[str, float] = field(default_factory=dict)
    
    # Game narrative
    narrative: GameNarrative = field(default_factory=GameNarrative)
    
    # Brilliancy assessment
    brilliancy_score: float = 0.0  # 0-100
    is_brilliancy: bool = False  # Qualifies as a "brilliant game"?
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "basic_metrics": {
                "sacrifice_score": self.basic_metrics.sacrifice_score,
                "tension_score": self.basic_metrics.tension_score,
                "quiet_move_score": self.basic_metrics.quiet_move_score,
                "forcing_move_score": self.basic_metrics.forcing_move_score,
                "total_score": self.basic_metrics.total_score,
            },
            "total_beauty": self.total_beauty,
            "average_beauty": self.average_beauty,
            "tactical_complexity": self.tactical_complexity,
            "positional_depth": self.positional_depth,
            "drama_index": self.drama_index,
            "accuracy_score": self.accuracy_score,
            "dominant_style": self.dominant_style.value,
            "style_breakdown": self.style_breakdown,
            "narrative": self.narrative.to_dict(),
            "brilliancy_score": self.brilliancy_score,
            "is_brilliancy": self.is_brilliancy,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CLASS: BeautyEvaluator
# ═══════════════════════════════════════════════════════════════════════════════

class BeautyEvaluator:
    """
    Evaluates the aesthetic beauty of chess moves and games.
    
    Phase 3: NOW WITH OPTIONAL STOCKFISH INTEGRATION
    - If stockfish_client provided: Uses engine + heuristics (hybrid mode)
    - If no stockfish_client: Falls back to pure heuristics (original behavior)
    
    Phase 3.1: ADVANCED BEAUTY METRICS
    - Game phase detection
    - Tactical pattern recognition
    - Style profile analysis
    - Drama and momentum tracking
    - Brilliancy detection
    - Game narrative generation
    """

    # ═══════════════════════════════════════════════════════════════════════════
    # ORIGINAL CONSTANTS (Phase 1 - Preserved)
    # ═══════════════════════════════════════════════════════════════════════════
    
    SACRIFICE_BONUS = 15.0
    QUIET_KILLER_BONUS = 20.0
    FORCING_MOVE_BONUS = 5.0
    TENSION_MULTIPLIER = 0.5
    DRAW_PENALTY = 5.0
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 3.1 CONSTANTS: Advanced Scoring
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Move type bonuses (building on original)
    ZWISCHENZUG_BONUS = 18.0
    PROPHYLAXIS_BONUS = 12.0
    DEFENSIVE_RESOURCE_BONUS = 15.0
    EXCHANGE_SACRIFICE_BONUS = 20.0
    QUEEN_SACRIFICE_BONUS = 35.0
    PAWN_BREAKTHROUGH_BONUS = 14.0
    KING_HUNT_BONUS = 22.0
    MYSTERIOUS_ROOK_BONUS = 16.0
    
    # Tactical pattern bonuses
    TACTICAL_PATTERN_BONUSES = {
        TacticalPattern.PIN: 8.0,
        TacticalPattern.FORK: 10.0,
        TacticalPattern.SKEWER: 9.0,
        TacticalPattern.DISCOVERY: 12.0,
        TacticalPattern.DOUBLE_CHECK: 15.0,
        TacticalPattern.BACK_RANK: 14.0,
        TacticalPattern.SMOTHERED_MATE: 25.0,
        TacticalPattern.DEFLECTION: 11.0,
        TacticalPattern.DECOY: 10.0,
        TacticalPattern.OVERLOAD: 9.0,
        TacticalPattern.CLEARANCE: 8.0,
        TacticalPattern.WINDMILL: 30.0,
        TacticalPattern.NONE: 0.0,
    }
    
    # Style weights for different move characteristics
    STYLE_WEIGHTS = {
        PlayingStyle.TAL: {
            "sacrifice": 2.0, "attack": 1.8, "complexity": 1.5, "risk": 1.5
        },
        PlayingStyle.PETROSIAN: {
            "prophylaxis": 2.0, "exchange": 1.5, "safety": 1.8, "squeeze": 1.5
        },
        PlayingStyle.CAPABLANCA: {
            "simplicity": 2.0, "endgame": 1.8, "technique": 1.5, "clarity": 1.5
        },
        PlayingStyle.KASPAROV: {
            "dynamics": 2.0, "initiative": 1.8, "energy": 1.5, "calculation": 1.5
        },
        PlayingStyle.CARLSEN: {
            "universality": 1.5, "grinding": 1.8, "precision": 1.5, "endgame": 1.5
        },
        PlayingStyle.MORPHY: {
            "development": 2.0, "attack": 1.8, "sacrifice": 1.5, "king_hunt": 1.8
        },
        PlayingStyle.FISCHER: {
            "precision": 2.0, "clarity": 1.8, "opening_prep": 1.5, "technique": 1.5
        },
    }

    def __init__(
        self,
        stockfish_client: Optional['StockfishClient'] = None,
        target_style: Optional[PlayingStyle] = None,
    ):
        """
        Initialize beauty evaluator.
        
        Args:
            stockfish_client: Optional Stockfish engine for enhanced evaluation.
                             If None, uses pure heuristics (Phase 1/2 behavior).
            target_style: Optional target playing style for style-matched scoring.
        """
        self.stockfish = stockfish_client
        self.engine_enhanced = stockfish_client is not None and stockfish_client.is_active()
        self.target_style = target_style
        
        # State tracking for game-level analysis
        self._move_history: List[AdvancedMoveMetrics] = []
        self._eval_history: List[float] = []
        self._momentum_history: List[float] = []
        
        if self.engine_enhanced:
            logger.info("🎨 BeautyEvaluator initialized with Stockfish enhancement")
        else:
            logger.info("🎨 BeautyEvaluator initialized with heuristics only")
        
        if target_style:
            logger.info(f"🎯 Target style: {target_style.value}")

    # ═══════════════════════════════════════════════════════════════════════════
    # ORIGINAL METHODS (Phase 1 - Preserved Exactly)
    # ═══════════════════════════════════════════════════════════════════════════

    def evaluate_move(
        self,
        board: chess.Board,
        move: chess.Move,
        eval_before: Optional[float] = None,
        eval_after: Optional[float] = None,
    ) -> Tuple[float, MoveBeautyType]:
        """
        Evaluate a single move's beauty.
        
        Phase 3: If Stockfish available, fetches evals automatically.
        Otherwise uses provided evals or pure heuristics.
        
        Args:
            board: Board state before the move
            move: The move to evaluate
            eval_before: Engine evaluation before move (centipawns) - optional
            eval_after: Engine evaluation after move (centipawns) - optional
        
        Returns:
            (beauty_score, move_type)
        """
        beauty = 0.0
        move_type = MoveBeautyType.BORING
        
        # Phase 3: Auto-fetch evals from Stockfish if available
        if self.engine_enhanced and (eval_before is None or eval_after is None):
            try:
                before_result = self.stockfish.evaluate(board)
                board.push(move)
                after_result = self.stockfish.evaluate(board)
                board.pop()
                
                eval_before = before_result.score_cp
                eval_after = after_result.score_cp
                
                logger.debug(f"Auto-fetched evals: {eval_before}cp → {eval_after}cp")
            except Exception as e:
                logger.warning(f"Failed to fetch evals from Stockfish: {e}")
        
        # 1. SACRIFICE DETECTION (Phase 1 heuristic)
        if self._is_material_sacrifice(board, move, eval_before, eval_after):
            beauty += self.SACRIFICE_BONUS
            move_type = MoveBeautyType.BRILLIANT_SACRIFICE
            
            # Phase 3: Bonus if Stockfish confirms it's sound
            if self.engine_enhanced:
                try:
                    if self.stockfish.is_sacrifice(board, move):
                        beauty += 10.0  # Extra bonus for engine-confirmed sacrifice
                        logger.debug(f"🎯 Sacrifice confirmed by engine")
                except Exception:
                    pass
        
        # 2. QUIET KILLER MOVE (Phase 1 heuristic)
        # Non-capturing, non-checking move in a sharp position with a forcing follow-up
        if (not board.is_capture(move) and 
            not board.gives_check(move) and
            self._is_position_sharp(board)):
            if self._has_forcing_continuation(board, move):
                beauty += self.QUIET_KILLER_BONUS
                move_type = MoveBeautyType.QUIET_KILLER
        
        # 3. FORCING MOVES (checks, captures in sharp positions)
        if board.gives_check(move):
            beauty += self.FORCING_MOVE_BONUS
            if move_type == MoveBeautyType.BORING:
                move_type = MoveBeautyType.FORCING_MOVE
        
        # 4. POSITIONAL SQUEEZE (Phase 1 heuristic)
        # Move that doesn't immediately win material but restricts opponent
        if self._is_positional_squeeze(board, move):
            beauty += 8.0
            if move_type == MoveBeautyType.BORING:
                move_type = MoveBeautyType.POSITIONAL_SQUEEZE
        
        # 5. TENSION BONUS (Phase 1 heuristic)
        tension = self._count_tension(board)
        beauty += tension * self.TENSION_MULTIPLIER
        
        # 6. BLUNDER DETECTION
        # Phase 3: Use Stockfish if available, otherwise eval comparison
        if self.engine_enhanced:
            try:
                if self.stockfish.is_blunder(board, move):
                    beauty = -10.0
                    move_type = MoveBeautyType.BLUNDER
            except Exception:
                pass
        elif eval_before and eval_after:
            # Fallback: manual eval comparison
            eval_drop = eval_before - eval_after
            if eval_drop > 200:  # Drops by more than 2 pawns
                beauty = -10.0
                move_type = MoveBeautyType.BLUNDER
        
        # Phase 3: ACCURACY BONUS (engine-only feature)
        if self.engine_enhanced and move_type != MoveBeautyType.BLUNDER:
            try:
                analysis = self.stockfish.evaluate_move(board, move)
                if analysis["is_best_move"]:
                    beauty += 5.0  # Bonus for finding the best move
                    logger.debug(f"✨ Best move found")
            except Exception:
                pass
        
        return max(0.0, beauty), move_type

    def evaluate_game(
        self,
        moves: List[chess.Move],
        evaluations: Optional[List[Tuple[float, float]]] = None,  # (before, after)
    ) -> BeautyMetrics:
        """
        Evaluate the overall beauty of a game.
        
        Args:
            moves: List of moves in the game
            evaluations: Optional list of (eval_before, eval_after) tuples
        
        Returns:
            BeautyMetrics with total score
        """
        board = chess.Board()
        metrics = BeautyMetrics()
        
        for i, move in enumerate(moves):
            eval_before = evaluations[i][0] if evaluations else None
            eval_after = evaluations[i][1] if evaluations else None
            
            score, move_type = self.evaluate_move(
                board, move, eval_before, eval_after
            )
            
            if move_type == MoveBeautyType.BRILLIANT_SACRIFICE:
                metrics.sacrifice_score += score
            elif move_type == MoveBeautyType.QUIET_KILLER:
                metrics.quiet_move_score += score
            elif move_type == MoveBeautyType.FORCING_MOVE:
                metrics.forcing_move_score += score
            elif move_type == MoveBeautyType.POSITIONAL_SQUEEZE:
                metrics.tension_score += score
            
            board.push(move)
        
        # Cap and normalize
        metrics.total_score = min(
            metrics.sacrifice_score +
            metrics.tension_score +
            metrics.quiet_move_score +
            metrics.forcing_move_score -
            metrics.drama_penalty,
            100.0
        )
        
        return metrics

    def _is_material_sacrifice(
        self,
        board: chess.Board,
        move: chess.Move,
        eval_before: Optional[float] = None,
        eval_after: Optional[float] = None,
    ) -> bool:
        """
        Detect if a move is a sound sacrifice.
        Sound = Material drops but evaluation doesn't drop significantly.
        """
        if not board.is_capture(move):
            return False
        
        # Check if material is actually dropped (quality sacrifice, not a trade)
        moving_piece = board.piece_at(move.from_square)
        captured_piece = board.piece_at(move.to_square)
        
        if not moving_piece or not captured_piece:
            return False
        
        # Our piece is more valuable than what we're capturing
        our_value = self._piece_value(moving_piece)
        their_value = self._piece_value(captured_piece)
        
        if our_value <= their_value:
            return False
        
        # Evaluation doesn't drop too much (compensation exists)
        if eval_before and eval_after:
            eval_drop = eval_before - eval_after
            # Sound sacrifice: evaluation drops less than 1.5 pawns
            if eval_drop > 150:
                return False
        
        return True

    def _is_position_sharp(self, board: chess.Board) -> bool:
        """Is the position tactically sharp (not endgame)?"""
        # Count non-pawn pieces
        non_pawns = sum(1 for piece_type in chess.PIECE_TYPES[:-1]  # Exclude pawns
                       for square in chess.SQUARES
                       if board.piece_at(square) and board.piece_at(square).piece_type == piece_type)
        
        # Sharp if there are many pieces on board (not endgame)
        return non_pawns >= 6

    def _has_forcing_continuation(self, board: chess.Board, move: chess.Move) -> bool:
        """After this move, is there a forcing continuation?"""
        board.push(move)
        
        # Check if there are forcing moves available
        has_check = any(board.gives_check(m) for m in board.legal_moves)
        
        board.pop()
        return has_check

    def _is_positional_squeeze(self, board: chess.Board, move: chess.Move) -> bool:
        """Is this a positional move that squeezes the opponent?"""
        # Moves that are quiet but restrict opponent's pieces
        if board.is_capture(move) or board.gives_check(move):
            return False
        
        board.push(move)
        opponent_legal_count = len(list(board.legal_moves))
        board.pop()
        
        board_no_move = chess.Board(board.fen())
        board_no_move.turn = not board_no_move.turn
        opponent_no_move_count = len(list(board_no_move.legal_moves))
        board_no_move.turn = not board_no_move.turn
        
        # Move restricts opponent's options
        return opponent_legal_count < opponent_no_move_count - 1

    def _count_tension(self, board: chess.Board) -> int:
        """Count the number of pieces under mutual attack (tension)."""
        tension = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                # Count attacks on this square
                attackers = len(board.attackers(not piece.color, square))
                defenders = len(board.attackers(piece.color, square))
                
                if attackers > 0 and defenders > 0:
                    tension += min(attackers, defenders)
        
        return tension

    @staticmethod
    def _piece_value(piece: chess.Piece) -> int:
        """Get the material value of a piece."""
        values = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 0,
        }
        return values.get(piece.piece_type, 0)

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 3.1: ADVANCED MOVE EVALUATION
    # ═══════════════════════════════════════════════════════════════════════════

    def evaluate_move_advanced(
        self,
        board: chess.Board,
        move: chess.Move,
        move_number: int = 1,
        eval_before: Optional[float] = None,
        eval_after: Optional[float] = None,
    ) -> AdvancedMoveMetrics:
        """
        Phase 3.1: Advanced move evaluation with full metrics.
        
        Builds on original evaluate_move() with:
        - Tactical pattern detection
        - Game phase awareness
        - Style scoring
        - Drama/momentum tracking
        - Brilliancy factors
        
        Args:
            board: Board state before the move
            move: The move to evaluate
            move_number: Current move number (for phase detection)
            eval_before: Engine evaluation before move (centipawns)
            eval_after: Engine evaluation after move (centipawns)
        
        Returns:
            AdvancedMoveMetrics with comprehensive analysis
        """
        # Start with original evaluation
        beauty_score, basic_move_type = self.evaluate_move(
            board, move, eval_before, eval_after
        )
        
        # Fetch evals if not provided and engine available
        if self.engine_enhanced and (eval_before is None or eval_after is None):
            try:
                before_result = self.stockfish.evaluate(board)
                eval_before = before_result.score_cp
                
                board.push(move)
                after_result = self.stockfish.evaluate(board)
                eval_after = after_result.score_cp
                board.pop()
            except Exception:
                pass
        
        # Determine game phase
        game_phase = self._detect_game_phase(board, move_number)
        
        # Detect tactical patterns
        tactical_pattern = self._detect_tactical_pattern(board, move)
        beauty_score += self.TACTICAL_PATTERN_BONUSES.get(tactical_pattern, 0.0)
        
        # Check for advanced move types (Phase 3.1)
        move_type = self._classify_advanced_move_type(
            board, move, basic_move_type, eval_before, eval_after
        )
        beauty_score += self._get_advanced_move_bonus(move_type)
        
        # Calculate drama score
        drama_score = self._calculate_drama(board, move, eval_before, eval_after)
        
        # Calculate momentum shift
        momentum_shift = self._calculate_momentum(eval_before, eval_after, board.turn)
        
        # Check brilliancy factors
        is_only_move = self._is_only_good_move(board, move)
        is_unexpected = self._is_unexpected_move(board, move)
        depth_required = self._estimate_depth_required(board, move)
        
        # Calculate style scores
        style_scores = self._calculate_style_scores(
            board, move, move_type, tactical_pattern, game_phase
        )
        
        # Determine if this is the engine's best move
        is_engine_best = False
        engine_best_move = None
        if self.engine_enhanced:
            try:
                analysis = self.stockfish.evaluate_move(board, move)
                is_engine_best = analysis.get("is_best_move", False)
                before_eval = self.stockfish.evaluate(board)
                if before_eval.best_move:
                    engine_best_move = before_eval.best_move.uci()
            except Exception:
                pass
        
        metrics = AdvancedMoveMetrics(
            beauty_score=max(0.0, beauty_score),
            move_type=move_type,
            tactical_pattern=tactical_pattern,
            game_phase=game_phase,
            drama_score=drama_score,
            momentum_shift=momentum_shift,
            is_only_move=is_only_move,
            is_unexpected=is_unexpected,
            depth_required=depth_required,
            style_scores=style_scores,
            engine_eval_before=eval_before,
            engine_eval_after=eval_after,
            engine_best_move=engine_best_move,
            is_engine_best=is_engine_best,
        )
        
        # Track for game-level analysis
        self._move_history.append(metrics)
        if eval_after is not None:
            self._eval_history.append(eval_after)
        self._momentum_history.append(momentum_shift)
        
        return metrics

    def _detect_game_phase(self, board: chess.Board, move_number: int) -> GamePhase:
        """Detect current game phase based on material and move number."""
        # Count total material (excluding kings)
        total_material = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.piece_type != chess.KING:
                total_material += self._piece_value(piece)
        
        # Check for queens
        has_queens = (
            len(board.pieces(chess.QUEEN, chess.WHITE)) > 0 or
            len(board.pieces(chess.QUEEN, chess.BLACK)) > 0
        )
        
        if move_number <= 10:
            return GamePhase.OPENING
        elif move_number <= 15:
            return GamePhase.EARLY_MIDDLEGAME
        elif total_material <= 20:  # Endgame threshold
            return GamePhase.ENDGAME
        elif move_number >= 30 or not has_queens:
            return GamePhase.LATE_MIDDLEGAME
        else:
            return GamePhase.MIDDLEGAME

    def _detect_tactical_pattern(
        self,
        board: chess.Board,
        move: chess.Move,
    ) -> TacticalPattern:
        """Detect tactical patterns in the move."""
        moving_piece = board.piece_at(move.from_square)
        if not moving_piece:
            return TacticalPattern.NONE
        
        # Make the move temporarily
        board.push(move)
        
        try:
            # Double check detection
            if board.is_check():
                checkers = board.checkers()
                if len(checkers) >= 2:
                    board.pop()
                    return TacticalPattern.DOUBLE_CHECK
            
            # Fork detection (piece attacks multiple valuable pieces)
            attacked_squares = board.attacks(move.to_square)
            valuable_targets = 0
            for sq in attacked_squares:
                target = board.piece_at(sq)
                if target and target.color != moving_piece.color:
                    if target.piece_type in [chess.QUEEN, chess.ROOK, chess.KING]:
                        valuable_targets += 1
                    elif target.piece_type in [chess.KNIGHT, chess.BISHOP]:
                        valuable_targets += 0.5
            
            if valuable_targets >= 2:
                board.pop()
                return TacticalPattern.FORK
            
            # Discovery detection (moving piece reveals attack)
            # Check if a piece behind the moved piece now attacks something
            from_file = chess.square_file(move.from_square)
            from_rank = chess.square_rank(move.from_square)
            to_file = chess.square_file(move.to_square)
            to_rank = chess.square_rank(move.to_square)
            
            if from_file != to_file or from_rank != to_rank:
                # Check diagonal/file/rank for discovered attacks
                for direction in [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]:
                    scan_file, scan_rank = from_file, from_rank
                    while True:
                        scan_file += direction[0]
                        scan_rank += direction[1]
                        if not (0 <= scan_file <= 7 and 0 <= scan_rank <= 7):
                            break
                        scan_square = chess.square(scan_file, scan_rank)
                        piece = board.piece_at(scan_square)
                        if piece:
                            if piece.color == moving_piece.color:
                                # Our piece behind - check if it's a long-range piece
                                if piece.piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                                    board.pop()
                                    return TacticalPattern.DISCOVERY
                            break
            
            # Pin detection
            opponent_king = board.king(not moving_piece.color)
            if opponent_king:
                for sq in board.attacks(move.to_square):
                    target = board.piece_at(sq)
                    if target and target.color != moving_piece.color:
                        # Check if piece is pinned to king
                        if self._is_pinned_to_king(board, sq, opponent_king):
                            board.pop()
                            return TacticalPattern.PIN
            
            # Skewer detection (attack through a piece to another behind it)
            if moving_piece.piece_type in [chess.BISHOP, chess.ROOK, chess.QUEEN]:
                for direction in self._get_piece_directions(moving_piece.piece_type):
                    first_piece = None
                    scan_file = chess.square_file(move.to_square) + direction[0]
                    scan_rank = chess.square_rank(move.to_square) + direction[1]
                    
                    while 0 <= scan_file <= 7 and 0 <= scan_rank <= 7:
                        scan_square = chess.square(scan_file, scan_rank)
                        piece = board.piece_at(scan_square)
                        if piece:
                            if piece.color != moving_piece.color:
                                if first_piece is None:
                                    first_piece = piece
                                elif self._piece_value(first_piece) > self._piece_value(piece):
                                    board.pop()
                                    return TacticalPattern.SKEWER
                            break
                        scan_file += direction[0]
                        scan_rank += direction[1]
            
            # Back rank mate threat
            if board.is_check():
                king_sq = board.king(not moving_piece.color)
                if king_sq:
                    king_rank = chess.square_rank(king_sq)
                    if king_rank == 0 or king_rank == 7:
                        # Check if king is trapped
                        escape_squares = board.attacks(king_sq)
                        trapped = True
                        for esc in escape_squares:
                            if not board.is_attacked_by(moving_piece.color, esc):
                                trapped = False
                                break
                        if trapped:
                            board.pop()
                            return TacticalPattern.BACK_RANK
            
            # Smothered mate
            if board.is_checkmate():
                king_sq = board.king(not moving_piece.color)
                if king_sq and moving_piece.piece_type == chess.KNIGHT:
                    # Check if all squares around king are blocked by own pieces
                    king_attacks = chess.SquareSet(chess.BB_KING_ATTACKS[king_sq])
                    all_blocked = True
                    for adj_sq in king_attacks:
                        adj_piece = board.piece_at(adj_sq)
                        if not adj_piece or adj_piece.color == moving_piece.color:
                            all_blocked = False
                            break
                    if all_blocked:
                        board.pop()
                        return TacticalPattern.SMOTHERED_MATE
        
        finally:
            if board.move_stack and board.peek() == move:
                board.pop()
        
        return TacticalPattern.NONE

    def _is_pinned_to_king(
        self,
        board: chess.Board,
        piece_square: int,
        king_square: int,
    ) -> bool:
        """Check if a piece is pinned to its king."""
        piece = board.piece_at(piece_square)
        if not piece:
            return False
        
        # Check if there's a line between piece and king
        piece_file = chess.square_file(piece_square)
        piece_rank = chess.square_rank(piece_square)
        king_file = chess.square_file(king_square)
        king_rank = chess.square_rank(king_square)
        
        # Must be on same file, rank, or diagonal
        if piece_file != king_file and piece_rank != king_rank:
            if abs(piece_file - king_file) != abs(piece_rank - king_rank):
                return False
        
        # Check if removing the piece would expose king to attack
        return board.is_pinned(piece.color, piece_square)

    def _get_piece_directions(self, piece_type: chess.PieceType) -> List[Tuple[int, int]]:
        """Get movement directions for a piece type."""
        if piece_type == chess.ROOK:
            return [(1, 0), (-1, 0), (0, 1), (0, -1)]
        elif piece_type == chess.BISHOP:
            return [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        elif piece_type == chess.QUEEN:
            return [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        return []

    def _classify_advanced_move_type(
        self,
        board: chess.Board,
        move: chess.Move,
        basic_type: MoveBeautyType,
        eval_before: Optional[float],
        eval_after: Optional[float],
    ) -> MoveBeautyType:
        """Classify move into advanced types (Phase 3.1)."""
        moving_piece = board.piece_at(move.from_square)
        captured_piece = board.piece_at(move.to_square)
        
        # Keep original type if it's a blunder
        if basic_type == MoveBeautyType.BLUNDER:
            return basic_type
        
        # Queen sacrifice detection
        if moving_piece and moving_piece.piece_type == chess.QUEEN:
            if captured_piece:
                their_value = self._piece_value(captured_piece)
                if their_value < 9:  # Less than queen value
                    # Check if it's sound
                    if eval_before and eval_after:
                        if eval_after >= eval_before - 150:
                            return MoveBeautyType.QUEEN_SACRIFICE
        
        # Exchange sacrifice (rook for minor piece)
        if moving_piece and moving_piece.piece_type == chess.ROOK:
            if captured_piece and captured_piece.piece_type in [chess.KNIGHT, chess.BISHOP]:
                if eval_before and eval_after:
                    if eval_after >= eval_before - 100:
                        return MoveBeautyType.EXCHANGE_SACRIFICE
        
        # Zwischenzug detection (in-between move during exchange)
        if board.is_check():
            # If we're giving check while pieces are hanging, it might be a zwischenzug
            for sq in chess.SQUARES:
                piece = board.piece_at(sq)
                if piece and piece.color == board.turn:
                    if board.is_attacked_by(not board.turn, sq):
                        return MoveBeautyType.ZWISCHENZUG
        
        # Prophylaxis (preventing opponent's plan)
        if self._is_prophylactic_move(board, move):
            return MoveBeautyType.PROPHYLAXIS
        
        # King hunt detection
        if self._is_king_hunt_move(board, move):
            return MoveBeautyType.KING_HUNT
        
        # Pawn breakthrough
        if moving_piece and moving_piece.piece_type == chess.PAWN:
            if self._is_pawn_breakthrough(board, move):
                return MoveBeautyType.PAWN_BREAKTHROUGH
        
        # Mysterious rook move (rook to closed file with no immediate threat)
        if moving_piece and moving_piece.piece_type == chess.ROOK:
            if self._is_mysterious_rook_move(board, move):
                return MoveBeautyType.MYSTERIOUS_ROOK_MOVE
        
        # Defensive resource (saving a losing position)
        if eval_before and eval_before < -200:  # We were losing
            if eval_after and eval_after > eval_before + 100:  # We improved significantly
                return MoveBeautyType.DEFENSIVE_RESOURCE
        
        return basic_type

    def _get_advanced_move_bonus(self, move_type: MoveBeautyType) -> float:
        """Get bonus for advanced move types."""
        bonuses = {
            MoveBeautyType.ZWISCHENZUG: self.ZWISCHENZUG_BONUS,
            MoveBeautyType.PROPHYLAXIS: self.PROPHYLAXIS_BONUS,
            MoveBeautyType.DEFENSIVE_RESOURCE: self.DEFENSIVE_RESOURCE_BONUS,
            MoveBeautyType.EXCHANGE_SACRIFICE: self.EXCHANGE_SACRIFICE_BONUS,
            MoveBeautyType.QUEEN_SACRIFICE: self.QUEEN_SACRIFICE_BONUS,
            MoveBeautyType.PAWN_BREAKTHROUGH: self.PAWN_BREAKTHROUGH_BONUS,
            MoveBeautyType.KING_HUNT: self.KING_HUNT_BONUS,
            MoveBeautyType.MYSTERIOUS_ROOK_MOVE: self.MYSTERIOUS_ROOK_BONUS,
        }
        return bonuses.get(move_type, 0.0)

    def _is_prophylactic_move(self, board: chess.Board, move: chess.Move) -> bool:
        """Detect prophylactic moves (preventing opponent's plan)."""
        if board.is_capture(move) or board.gives_check(move):
            return False
        
        # Make the move
        board.push(move)
        our_legal_after = len(list(board.legal_moves))
        board.pop()
        
        # What if we didn't make this move?
        board.push(chess.Move.null())
        if board.is_valid():
            opponent_best_options = len(list(board.legal_moves))
            board.pop()
            
            # If our move significantly reduced opponent's options
            board.push(move)
            board.push(chess.Move.null())
            if board.is_valid():
                opponent_after_our_move = len(list(board.legal_moves))
                board.pop()
                board.pop()
                
                if opponent_after_our_move < opponent_best_options - 5:
                    return True
            else:
                board.pop()
        else:
            board.pop()
        
        return False

    def _is_king_hunt_move(self, board: chess.Board, move: chess.Move) -> bool:
        """Detect king hunt moves (attacking exposed king)."""
        board.push(move)
        
        # Check if opponent's king is exposed (not castled, in center or wandering)
        opponent_king = board.king(not board.turn)
        if opponent_king:
            king_file = chess.square_file(opponent_king)
            king_rank = chess.square_rank(opponent_king)
            
            # King is exposed if not on back rank or in center
            is_exposed = (
                (board.turn == chess.WHITE and king_rank > 1) or
                (board.turn == chess.BLACK and king_rank < 6)
            )
            
            if is_exposed:
                # Check if we're attacking near the king
                attackers = board.attackers(board.turn, opponent_king)
                adjacent_attacks = 0
                for adj_sq in chess.SquareSet(chess.BB_KING_ATTACKS[opponent_king]):
                    if board.is_attacked_by(board.turn, adj_sq):
                        adjacent_attacks += 1
                
                board.pop()
                return len(attackers) >= 1 or adjacent_attacks >= 3
        
        board.pop()
        return False

    def _is_pawn_breakthrough(self, board: chess.Board, move: chess.Move) -> bool:
        """Detect pawn breakthrough moves."""
        moving_piece = board.piece_at(move.from_square)
        if not moving_piece or moving_piece.piece_type != chess.PAWN:
            return False
        
        to_rank = chess.square_rank(move.to_square)
        
        # Pawn is advancing deep into enemy territory
        if moving_piece.color == chess.WHITE and to_rank >= 5:
            return True
        if moving_piece.color == chess.BLACK and to_rank <= 2:
            return True
        
        # Check for connected passed pawns
        to_file = chess.square_file(move.to_square)
        for adj_file in [to_file - 1, to_file + 1]:
            if 0 <= adj_file <= 7:
                for rank in range(8):
                    sq = chess.square(adj_file, rank)
                    adj_piece = board.piece_at(sq)
                    if adj_piece and adj_piece.piece_type == chess.PAWN:
                        if adj_piece.color == moving_piece.color:
                            return True
        
        return False

    def _is_mysterious_rook_move(self, board: chess.Board, move: chess.Move) -> bool:
        """Detect Nimzowitsch's 'mysterious rook move' concept."""
        moving_piece = board.piece_at(move.from_square)
        if not moving_piece or moving_piece.piece_type != chess.ROOK:
            return False
        
        to_file = chess.square_file(move.to_square)
        
        # Rook moves to a closed or semi-closed file
        pawns_on_file = 0
        for rank in range(8):
            sq = chess.square(to_file, rank)
            piece = board.piece_at(sq)
            if piece and piece.piece_type == chess.PAWN:
                pawns_on_file += 1
        
        # Mysterious if file has pawns (closed) but rook has no immediate targets
        if pawns_on_file >= 2:
            board.push(move)
            attacks = board.attacks(move.to_square)
            valuable_targets = sum(
                1 for sq in attacks
                if board.piece_at(sq) and self._piece_value(board.piece_at(sq)) >= 3
            )
            board.pop()
            
            return valuable_targets == 0  # No immediate targets = mysterious
        
        return False

    def _calculate_drama(
        self,
        board: chess.Board,
        move: chess.Move,
        eval_before: Optional[float],
        eval_after: Optional[float],
    ) -> float:
        """Calculate drama score for a move (0-100)."""
        drama = 30.0  # Base drama
        
        # Eval swing drama
        if eval_before is not None and eval_after is not None:
            swing = abs(eval_after - eval_before)
            drama += min(swing / 5, 30)  # Up to 30 points for big swings
        
        # Check drama
        if board.gives_check(move):
            drama += 10
            board.push(move)
            if board.is_checkmate():
                drama = 100.0  # Maximum drama for checkmate
            board.pop()
        
        # Sacrifice drama
        if board.is_capture(move):
            moving_piece = board.piece_at(move.from_square)
            captured = board.piece_at(move.to_square)
            if moving_piece and captured:
                if self._piece_value(moving_piece) > self._piece_value(captured):
                    drama += 15  # Sacrifice is dramatic
        
        # Tension drama
        tension = self._count_tension(board)
        drama += min(tension * 2, 15)
        
        # Time pressure simulation (more moves = more drama in endgame)
        piece_count = len(board.piece_map())
        if piece_count <= 10:
            drama += 10  # Endgame tension
        
        return min(100.0, drama)

    def _calculate_momentum(
        self,
        eval_before: Optional[float],
        eval_after: Optional[float],
        white_to_move: bool,
    ) -> float:
        """Calculate momentum shift (-100 to +100, positive = toward current player)."""
        if eval_before is None or eval_after is None:
            return 0.0
        
        # From mover's perspective
        if white_to_move:
            shift = eval_after - eval_before
        else:
            shift = eval_before - eval_after
        
        # Normalize to -100 to +100
        return max(-100.0, min(100.0, shift / 3))

    def _is_only_good_move(self, board: chess.Board, move: chess.Move) -> bool:
        """Check if this was the only good move in the position."""
        if not self.engine_enhanced:
            return False
        
        try:
            # Get evaluation for this move
            this_eval = self.stockfish.evaluate_move(board, move)
            
            # Check other moves
            good_alternatives = 0
            for legal_move in board.legal_moves:
                if legal_move == move:
                    continue
                
                alt_eval = self.stockfish.evaluate_move(board, legal_move)
                if alt_eval["eval_change"] > -50:  # Within 0.5 pawn
                    good_alternatives += 1
                    if good_alternatives >= 1:
                        return False
            
            return True
        except Exception:
            return False

    def _is_unexpected_move(self, board: chess.Board, move: chess.Move) -> bool:
        """Check if move is unexpected (not immediately obvious)."""
        if not self.engine_enhanced:
            return False
        
        try:
            before_eval = self.stockfish.evaluate(board)
            # If this isn't the engine's first choice, it's somewhat unexpected
            if before_eval.best_move and before_eval.best_move != move:
                return True
        except Exception:
            pass
        
        return False

    def _estimate_depth_required(self, board: chess.Board, move: chess.Move) -> int:
        """Estimate depth required to find this move (heuristic)."""
        # This is a heuristic based on move characteristics
        depth = 5  # Base depth
        
        # Sacrifices need more depth
        if board.is_capture(move):
            moving = board.piece_at(move.from_square)
            captured = board.piece_at(move.to_square)
            if moving and captured:
                if self._piece_value(moving) > self._piece_value(captured):
                    depth += 5
        
        # Quiet moves in sharp positions need depth
        if not board.is_capture(move) and not board.gives_check(move):
            if self._is_position_sharp(board):
                depth += 3
        
        # Long forcing sequences need depth
        if board.gives_check(move):
            board.push(move)
            if len(list(board.legal_moves)) <= 3:  # Limited responses
                depth += 2
            board.pop()
        
        return min(20, depth)

    def _calculate_style_scores(
        self,
        board: chess.Board,
        move: chess.Move,
        move_type: MoveBeautyType,
        pattern: TacticalPattern,
        phase: GamePhase,
    ) -> Dict[str, float]:
        """Calculate how well the move matches each playing style."""
        scores = {}
        
        for style in PlayingStyle:
            score = 50.0  # Base score
            weights = self.STYLE_WEIGHTS[style]
            
            # Sacrifice bonus
            if "sacrifice" in weights:
                if move_type in [MoveBeautyType.BRILLIANT_SACRIFICE, 
                                MoveBeautyType.EXCHANGE_SACRIFICE,
                                MoveBeautyType.QUEEN_SACRIFICE]:
                    score += 20 * weights["sacrifice"]
            
            # Attack bonus
            if "attack" in weights:
                if board.gives_check(move) or move_type == MoveBeautyType.KING_HUNT:
                    score += 15 * weights["attack"]
            
            # Prophylaxis bonus
            if "prophylaxis" in weights:
                if move_type == MoveBeautyType.PROPHYLAXIS:
                    score += 20 * weights["prophylaxis"]
            
            # Simplicity bonus (Capablanca style)
            if "simplicity" in weights:
                if move_type == MoveBeautyType.SIMPLIFICATION:
                    score += 15 * weights["simplicity"]
                if not board.is_capture(move) and not board.gives_check(move):
                    score += 5 * weights["simplicity"]
            
            # Endgame bonus
            if "endgame" in weights:
                if phase == GamePhase.ENDGAME:
                    score += 10 * weights["endgame"]
            
            # Complexity bonus (Tal style)
            if "complexity" in weights:
                if pattern != TacticalPattern.NONE:
                    score += 15 * weights["complexity"]
            
            # Dynamics bonus (Kasparov style)
            if "dynamics" in weights:
                if self._count_tension(board) >= 4:
                    score += 10 * weights["dynamics"]
            
            scores[style.value] = min(100.0, max(0.0, score))
        
        return scores

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 3.1: ADVANCED GAME EVALUATION
    # ═══════════════════════════════════════════════════════════════════════════

    def evaluate_game_advanced(
        self,
        moves: List[chess.Move],
        evaluations: Optional[List[Tuple[float, float]]] = None,
    ) -> AdvancedGameMetrics:
        """
        Phase 3.1: Comprehensive game evaluation with full metrics.
        
        Builds on original evaluate_game() with:
        - Game narrative generation
        - Style profile analysis
        - Brilliancy detection
        - Drama arc tracking
        
        Args:
            moves: List of moves in the game
            evaluations: Optional list of (eval_before, eval_after) tuples
        
        Returns:
            AdvancedGameMetrics with comprehensive analysis
        """
        # Reset tracking
        self._move_history = []
        self._eval_history = []
        self._momentum_history = []
        
        board = chess.Board()
        
        # Get basic metrics first (preserves original functionality)
        basic_metrics = self.evaluate_game(moves, evaluations)
        
        # Reset board for advanced analysis
        board = chess.Board()
        
        # Evaluate each move with advanced metrics
        for i, move in enumerate(moves):
            eval_before = evaluations[i][0] if evaluations and i < len(evaluations) else None
            eval_after = evaluations[i][1] if evaluations and i < len(evaluations) else None
            
            self.evaluate_move_advanced(
                board, move, i + 1, eval_before, eval_after
            )
            
            board.push(move)
        
        # Calculate aggregate metrics
        total_beauty = sum(m.beauty_score for m in self._move_history)
        avg_beauty = total_beauty / len(self._move_history) if self._move_history else 0
        
        # Tactical complexity
        tactical_moves = sum(1 for m in self._move_history if m.tactical_pattern != TacticalPattern.NONE)
        tactical_complexity = min(100, tactical_moves * 10)
        
        # Positional depth
        positional_moves = sum(
            1 for m in self._move_history 
            if m.move_type in [MoveBeautyType.PROPHYLAXIS, MoveBeautyType.POSITIONAL_SQUEEZE, 
                              MoveBeautyType.MYSTERIOUS_ROOK_MOVE]
        )
        positional_depth = min(100, positional_moves * 15)
        
        # Drama index
        drama_index = sum(m.drama_score for m in self._move_history) / len(self._move_history) if self._move_history else 0
        
        # Accuracy score (engine-based)
        if self.engine_enhanced:
            best_moves = sum(1 for m in self._move_history if m.is_engine_best)
            accuracy_score = (best_moves / len(self._move_history) * 100) if self._move_history else 0
        else:
            accuracy_score = 0
        
        # Style breakdown
        style_breakdown = self._aggregate_style_scores()
        dominant_style = max(style_breakdown.items(), key=lambda x: x[1])[0] if style_breakdown else PlayingStyle.CARLSEN.value
        
        # Generate narrative
        narrative = self._generate_narrative(moves, board)
        
        # Brilliancy detection
        brilliancy_score, is_brilliancy = self._assess_brilliancy()
        
        return AdvancedGameMetrics(
            basic_metrics=basic_metrics,
            move_metrics=self._move_history.copy(),
            total_beauty=total_beauty,
            average_beauty=avg_beauty,
            tactical_complexity=tactical_complexity,
            positional_depth=positional_depth,
            drama_index=drama_index,
            accuracy_score=accuracy_score,
            dominant_style=PlayingStyle(dominant_style),
            style_breakdown=style_breakdown,
            narrative=narrative,
            brilliancy_score=brilliancy_score,
            is_brilliancy=is_brilliancy,
        )

    def _aggregate_style_scores(self) -> Dict[str, float]:
        """Aggregate style scores across all moves."""
        if not self._move_history:
            return {}
        
        aggregated = {}
        for style in PlayingStyle:
            scores = [m.style_scores.get(style.value, 50) for m in self._move_history]
            aggregated[style.value] = sum(scores) / len(scores)
        
        return aggregated

    def _generate_narrative(
        self,
        moves: List[chess.Move],
        final_board: chess.Board,
    ) -> GameNarrative:
        """Generate the story arc of the game."""
        narrative = GameNarrative()
        
        # Find critical moments
        for i, metrics in enumerate(self._move_history):
            if metrics.beauty_score >= 20:
                narrative.critical_moments.append(i + 1)
            
            if metrics.move_type in [MoveBeautyType.BRILLIANT_SACRIFICE, 
                                     MoveBeautyType.QUEEN_SACRIFICE]:
                narrative.brilliant_moves.append(i + 1)
            
            if metrics.move_type == MoveBeautyType.BLUNDER:
                narrative.blunders.append(i + 1)
            
            if abs(metrics.momentum_shift) >= 50:
                narrative.turning_points.append(i + 1)
            
            if metrics.drama_score > narrative.max_drama:
                narrative.max_drama = metrics.drama_score
                narrative.drama_peak_move = i + 1
        
        # Count momentum swings
        narrative.total_momentum_swings = sum(
            1 for m in self._move_history if abs(m.momentum_shift) >= 30
        )
        
        # Determine middlegame character
        tactical_count = sum(1 for m in self._move_history if m.tactical_pattern != TacticalPattern.NONE)
        positional_count = sum(1 for m in self._move_history if m.move_type == MoveBeautyType.POSITIONAL_SQUEEZE)
        
        if tactical_count > positional_count * 2:
            narrative.middlegame_character = "tactical"
        elif positional_count > tactical_count:
            narrative.middlegame_character = "positional"
        else:
            narrative.middlegame_character = "balanced"
        
        # Assess game quality
        if len(narrative.brilliant_moves) >= 3 and len(narrative.blunders) == 0:
            narrative.game_quality = "masterpiece"
        elif len(narrative.brilliant_moves) >= 2:
            narrative.game_quality = "excellent"
        elif len(narrative.blunders) <= 1:
            narrative.game_quality = "good"
        elif len(narrative.blunders) >= 3:
            narrative.game_quality = "flawed"
        else:
            narrative.game_quality = "average"
        
        return narrative

    def _assess_brilliancy(self) -> Tuple[float, bool]:
        """Assess if the game qualifies as a brilliancy."""
        if not self._move_history:
            return 0.0, False
        
        score = 0.0
        
        # Sacrifice count
        sacrifices = sum(
            1 for m in self._move_history 
            if m.move_type in [MoveBeautyType.BRILLIANT_SACRIFICE, 
                              MoveBeautyType.EXCHANGE_SACRIFICE,
                              MoveBeautyType.QUEEN_SACRIFICE]
        )
        score += sacrifices * 15
        
        # Tactical patterns
        patterns = sum(1 for m in self._move_history if m.tactical_pattern != TacticalPattern.NONE)
        score += patterns * 5
        
        # "Only moves" found
        only_moves = sum(1 for m in self._move_history if m.is_only_move)
        score += only_moves * 10
        
        # Drama factor
        avg_drama = sum(m.drama_score for m in self._move_history) / len(self._move_history)
        score += avg_drama * 0.3
        
        # Unexpected moves
        unexpected = sum(1 for m in self._move_history if m.is_unexpected)
        score += unexpected * 5
        
        # No blunders
        blunders = sum(1 for m in self._move_history if m.move_type == MoveBeautyType.BLUNDER)
        if blunders == 0:
            score += 20
        else:
            score -= blunders * 15
        
        score = min(100.0, max(0.0, score))
        is_brilliancy = score >= 70
        
        return score, is_brilliancy

    def reset(self) -> None:
        """Reset all state for new game analysis."""
        self._move_history = []
        self._eval_history = []
        self._momentum_history = []


# ═══════════════════════════════════════════════════════════════════════════════
# EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    evaluator = BeautyEvaluator()
    
    # Example: Scholar's Mate
    board = chess.Board()
    moves = [
        board.push_san("e4"),
        board.push_san("e5"),
        board.push_san("Bc4"),
        board.push_san("Nc6"),
        board.push_san("Qh5"),
        board.push_san("Nf6"),
        board.push_san("Qxf7"),  # Checkmate threat / Scholar's Mate
    ]
    
    print("Evaluating Scholar's Mate sequence...")
    print("\n🎨 BASIC EVALUATION (Phase 1 preserved):")
    board = chess.Board()
    basic_metrics = evaluator.evaluate_game(moves)
    print(f"  Total Score: {basic_metrics.total_score:.1f}")
    print(f"  Sacrifice Score: {basic_metrics.sacrifice_score:.1f}")
    print(f"  Forcing Move Score: {basic_metrics.forcing_move_score:.1f}")
    
    print("\n🚀 ADVANCED EVALUATION (Phase 3.1):")
    board = chess.Board()
    advanced_metrics = evaluator.evaluate_game_advanced(moves)
    print(f"  Total Beauty: {advanced_metrics.total_beauty:.1f}")
    print(f"  Average Beauty: {advanced_metrics.average_beauty:.1f}")
    print(f"  Tactical Complexity: {advanced_metrics.tactical_complexity:.1f}")
    print(f"  Drama Index: {advanced_metrics.drama_index:.1f}")
    print(f"  Dominant Style: {advanced_metrics.dominant_style.value}")
    print(f"  Brilliancy Score: {advanced_metrics.brilliancy_score:.1f}")
    print(f"  Is Brilliancy: {advanced_metrics.is_brilliancy}")
    print(f"  Game Quality: {advanced_metrics.narrative.game_quality}")
    
    print("\n✨ Phase 3.1 enhancements added while preserving all Phase 1 logic!")
