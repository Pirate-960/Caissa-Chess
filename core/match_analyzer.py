"""
core/match_analyzer.py

Post-Match Analysis Pipeline for LLM vs LLM Matches

This module enriches raw LLM vs LLM match results with the same depth and quality 
as batch-generated games. It runs after a match completes and performs:

1. Stockfish Analysis - Evaluations, blunders, missed tactics
2. Beauty Score Calculation - Using existing aesthetics engine
3. Strategic Commentary - LLM-generated insights for critical positions
4. Move Annotations - NAGs (!!,!,?!,?,??), evaluations, comments
5. Phase Detection - Opening, Middlegame, Endgame markers
6. Critical Moments - Turning points, brilliancies, blunders

This bridges the gap between LLM battles (real-time, raw moves) and 
batch generation (post-processed, rich annotations).

Author: CAISSA Team
Version: 0.5.0
"""

import asyncio
import chess
import chess.pgn
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from io import StringIO
from typing import Optional, List, Tuple, Dict, Any

from core.match_engine import MatchResult, MoveRecord, GameResult, TerminationReason
from core.llm_provider import LLMProvider
from engine.stockfish_client import StockfishClient
from aesthetic.beauty_eval import (
    BeautyEvaluator, 
    BeautyMetrics, 
    MoveBeautyType,
    GamePhase
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYSIS RESULT CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CriticalMoment:
    """Represents a critical turning point in the game."""
    move_number: int
    san: str
    fen: str
    moment_type: str  # "blunder", "brilliancy", "turning_point", "missed_win"
    eval_before: float
    eval_after: float
    eval_swing: float  # Centipawn change
    commentary: str
    severity: int = 5  # 1-10 scale


@dataclass
class PositionPhase:
    """Game phase markers for annotation."""
    phase: GamePhase  # OPENING, MIDDLEGAME, ENDGAME
    start_move: int
    end_move: Optional[int] = None
    description: str = ""


@dataclass
class MoveAnnotation:
    """Complete annotation for a single move."""
    move_number: int
    san: str
    
    # Stockfish analysis
    evaluation: float  # Centipawn score
    best_move: Optional[str] = None  # Engine's top choice
    is_best: bool = False  # Did player play the best move?
    centipawn_loss: float = 0.0  # Accuracy metric
    
    # Beauty analysis
    beauty_score: float = 0.0
    beauty_type: MoveBeautyType = MoveBeautyType.BORING
    is_sacrifice: bool = False
    is_quiet_killer: bool = False
    
    # Tactical patterns
    tactical_motifs: List[str] = field(default_factory=list)  # ["pin", "fork", "skewer"]
    
    # Symbols and commentary
    nags: List[str] = field(default_factory=list)  # ["!!", "!", "?!", "?", "??"]
    comment: str = ""
    
    # Critical moments
    is_critical: bool = False
    critical_type: Optional[str] = None  # "blunder", "brilliancy", etc.


@dataclass
class GameNarrative:
    """Overall story/narrative of the game."""
    summary: str  # 2-3 sentence game summary
    opening_name: Optional[str] = None
    opening_description: str = ""
    
    key_phases: List[str] = field(default_factory=list)
    critical_moments: List[CriticalMoment] = field(default_factory=list)
    
    white_style_assessment: str = ""  # "Aggressive, tactical play"
    black_style_assessment: str = ""
    
    drama_score: float = 0.0  # 0-100
    complexity_score: float = 0.0  # 0-100
    
    winner_reason: str = ""  # "White won due to superior endgame technique"


@dataclass
class MatchAnalysis:
    """Complete post-match analysis result."""
    match_id: str
    
    # Beauty metrics
    beauty_score: float = 0.0
    beauty_metrics: Optional[BeautyMetrics] = None
    
    # Move-by-move analysis
    move_annotations: List[MoveAnnotation] = field(default_factory=list)
    
    # Game phases
    phases: List[PositionPhase] = field(default_factory=list)
    
    # Critical moments
    critical_moments: List[CriticalMoment] = field(default_factory=list)
    
    # Accuracy metrics
    white_avg_centipawn_loss: float = 0.0
    black_avg_centipawn_loss: float = 0.0
    white_accuracy: float = 0.0  # 0-100%
    black_accuracy: float = 0.0
    
    # Complexity and drama
    complexity_score: float = 0.0
    drama_score: float = 0.0
    
    # Narrative
    narrative: Optional[GameNarrative] = None
    
    # Metadata
    analysis_time: float = 0.0  # Seconds spent analyzing
    stockfish_depth: int = 15
    commentary_enabled: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# MATCH ANALYZER CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class MatchAnalyzer:
    """
    Post-match analysis pipeline for LLM vs LLM matches.
    
    Takes a raw MatchResult and enriches it with:
    - Stockfish evaluations
    - Beauty scores
    - Strategic commentary
    - Move annotations
    - Critical moment detection
    
    Example:
        analyzer = MatchAnalyzer(
            stockfish_path="path/to/stockfish",
            commentary_provider=my_llm,  # Optional
            depth=15
        )
        
        analysis = await analyzer.analyze_match(match_result)
        print(f"Beauty Score: {analysis.beauty_score}")
        print(f"Critical Moments: {len(analysis.critical_moments)}")
    """
    
    def __init__(
        self,
        stockfish_path: Optional[str] = None,
        commentary_provider: Optional[LLMProvider] = None,
        depth: int = 15,
        time_limit: float = 0.1,
        enable_commentary: bool = True,
        commentary_style: str = "grandmaster",
        threads: int = 1,
        hash_mb: int = 64,
    ):
        """
        Initialize the match analyzer.
        
        Args:
            stockfish_path: Path to Stockfish binary (optional but recommended)
            commentary_provider: LLM for generating strategic commentary (optional)
            depth: Stockfish analysis depth (default 15)
            time_limit: Max time per position in seconds
            enable_commentary: Whether to generate LLM commentary
            commentary_style: "grandmaster", "entertaining", "dramatic", etc.
            threads: Stockfish threads
            hash_mb: Stockfish hash table size in MB
        """
        self.stockfish_path = stockfish_path
        self.commentary_provider = commentary_provider
        self.enable_commentary = enable_commentary and commentary_provider is not None
        self.commentary_style = commentary_style
        self.depth = depth
        self.time_limit = time_limit
        
        # Initialize Stockfish client if path provided
        self.stockfish: Optional[StockfishClient] = None
        if stockfish_path:
            try:
                self.stockfish = StockfishClient(
                    binary_path=stockfish_path,
                    depth=depth,
                    time_limit=time_limit,
                    threads=threads,
                    hash_mb=hash_mb
                )
                logger.info(f"✅ MatchAnalyzer initialized WITH Stockfish (depth={depth}, path={stockfish_path})")
            except Exception as e:
                logger.warning(f"❌ Failed to initialize Stockfish: {e}. Continuing without engine analysis.")
                logger.info("ℹ️  MatchAnalyzer will use heuristic-only analysis (no engine evaluations)")
                self.stockfish = None
        else:
            logger.info("ℹ️  MatchAnalyzer initialized WITHOUT Stockfish (no path provided)")
            logger.info("ℹ️  Analysis will be heuristic-only - beauty scoring and pattern detection only")
        
        # Initialize beauty evaluator
        self.beauty_evaluator = BeautyEvaluator(stockfish_client=self.stockfish)
    
    def __enter__(self):
        """Context manager support."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup resources."""
        self.cleanup()
    
    def cleanup(self):
        """Clean up Stockfish process."""
        if self.stockfish:
            try:
                self.stockfish.cleanup()
                logger.debug("Cleaned up Stockfish process")
            except Exception as e:
                logger.warning(f"Error cleaning up Stockfish: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN ANALYSIS PIPELINE
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def analyze_match(self, match_result: MatchResult) -> MatchAnalysis:
        """
        Perform complete post-match analysis.
        
        Pipeline:
        1. Reconstruct board positions from move list
        2. Run Stockfish analysis on each position
        3. Calculate beauty scores
        4. Detect critical moments
        5. Generate phase markers
        6. Create move annotations
        7. Generate strategic commentary (if enabled)
        8. Compute accuracy metrics
        9. Build game narrative
        
        Args:
            match_result: Raw match result from MatchEngine
        
        Returns:
            MatchAnalysis with complete enrichment
        """
        logger.info(f"Starting post-match analysis for {match_result.match_id}")
        logger.info(f"  Match: {match_result.white.name} vs {match_result.black.name}")
        logger.info(f"  Moves: {len(match_result.moves)}, Result: {match_result.result.value}")
        logger.info(f"  Engine: {'Stockfish' if self.stockfish else 'Heuristic-only'}")
        logger.info(f"  Commentary: {'Enabled' if self.enable_commentary else 'Disabled'}")
        
        start_time = time.time()
        logger.info(f"[{match_result.match_id}] Starting post-match analysis...")
        
        analysis = MatchAnalysis(match_id=match_result.match_id)
        
        # Step 1: Reconstruct positions and evaluate with Stockfish
        logger.debug(f"[{match_result.match_id}] Reconstructing positions...")
        positions = self._reconstruct_positions(match_result)
        
        if self.stockfish:
            logger.debug(f"[{match_result.match_id}] Running Stockfish analysis on {len(positions)} positions...")
            evaluations = await self._analyze_positions(positions)
        else:
            logger.debug(f"[{match_result.match_id}] No Stockfish - using heuristic evaluation")
            evaluations = [None] * len(positions)
        
        # Step 2: Calculate beauty scores
        logger.debug(f"[{match_result.match_id}] Calculating beauty scores...")
        beauty_data = self._calculate_beauty(match_result, positions, evaluations)
        analysis.beauty_score = beauty_data["total_score"]
        analysis.beauty_metrics = beauty_data["metrics"]
        
        # Step 3: Detect game phases
        logger.debug(f"[{match_result.match_id}] Detecting game phases...")
        analysis.phases = self._detect_phases(match_result, positions)
        
        # Step 4: Annotate moves
        logger.debug(f"[{match_result.match_id}] Annotating moves...")
        analysis.move_annotations = await self._annotate_moves(
            match_result, 
            positions, 
            evaluations, 
            beauty_data["move_beauty"]
        )
        
        # Step 5: Detect critical moments
        logger.debug(f"[{match_result.match_id}] Detecting critical moments...")
        analysis.critical_moments = self._detect_critical_moments(
            match_result,
            analysis.move_annotations
        )
        
        # Step 6: Calculate accuracy metrics
        logger.debug(f"[{match_result.match_id}] Computing accuracy metrics...")
        accuracy = self._calculate_accuracy(match_result, analysis.move_annotations)
        analysis.white_avg_centipawn_loss = accuracy["white_cpl"]
        analysis.black_avg_centipawn_loss = accuracy["black_cpl"]
        analysis.white_accuracy = accuracy["white_accuracy"]
        analysis.black_accuracy = accuracy["black_accuracy"]
        
        # Step 7: Calculate complexity and drama scores
        analysis.complexity_score = self._calculate_complexity(positions)
        analysis.drama_score = self._calculate_drama(analysis.critical_moments, evaluations)
        
        # Step 8: Generate strategic commentary (if enabled)
        if self.enable_commentary:
            logger.debug(f"[{match_result.match_id}] Generating strategic commentary...")
            commentary = await self._generate_commentary(
                match_result,
                analysis.critical_moments,
                analysis.move_annotations
            )
            
            # Attach commentary to move annotations
            for i, annotation in enumerate(analysis.move_annotations):
                if i < len(commentary):
                    annotation.comment = commentary[i]
        
        # Step 9: Build game narrative
        logger.debug(f"[{match_result.match_id}] Building game narrative...")
        analysis.narrative = await self._build_narrative(match_result, analysis)
        
        analysis.analysis_time = time.time() - start_time
        analysis.stockfish_depth = self.depth
        analysis.commentary_enabled = self.enable_commentary
        
        logger.info(
            f"[{match_result.match_id}] Analysis complete in {analysis.analysis_time:.2f}s "
            f"(beauty={analysis.beauty_score:.1f}, drama={analysis.drama_score:.1f})"
        )
        
        return analysis
    
    # ═══════════════════════════════════════════════════════════════════════════
    # POSITION RECONSTRUCTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _reconstruct_positions(self, match_result: MatchResult) -> List[Tuple[chess.Board, chess.Move]]:
        """
        Reconstruct all board positions from move history.
        
        Returns:
            List of (board_before_move, move) tuples
        """
        positions = []
        board = chess.Board()
        
        for move_record in match_result.moves:
            try:
                # Parse the move
                move = board.parse_san(move_record.san)
                
                # Store position before move
                positions.append((board.copy(), move))
                
                # Apply move
                board.push(move)
                
            except Exception as e:
                logger.warning(
                    f"[{match_result.match_id}] Failed to reconstruct move {move_record.move_number}. "
                    f"{move_record.san}: {e}"
                )
                continue
        
        return positions
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STOCKFISH ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _analyze_positions(
        self, 
        positions: List[Tuple[chess.Board, chess.Move]]
    ) -> List[Optional[Dict[str, Any]]]:
        """
        Analyze all positions with Stockfish.
        
        Returns:
            List of evaluation dictionaries with:
            - eval_before: float (centipawns)
            - eval_after: float
            - best_move: str (UCI)
            - is_best: bool
            - mate_in: Optional[int]
        """
        if not self.stockfish:
            return [None] * len(positions)
        
        evaluations = []
        
        for i, (board, move) in enumerate(positions):
            try:
                # Evaluate position before move
                eval_before = self.stockfish.evaluate(board)
                
                # Apply move
                board_after = board.copy()
                board_after.push(move)
                
                # Evaluate position after move
                eval_after = self.stockfish.evaluate(board_after)
                
                # Get best move
                best_move = eval_before.best_move.uci() if eval_before.best_move else None
                
                # Check if played move matches best move
                is_best = (move.uci() == best_move) if best_move else False
                
                evaluations.append({
                    "eval_before": eval_before.score_cp,
                    "eval_after": -eval_after.score_cp,  # Flip sign (perspective change)
                    "best_move": best_move,
                    "is_best": is_best,
                    "mate_in": eval_before.mate_in,
                })
                
            except Exception as e:
                logger.warning(f"Stockfish evaluation failed for position {i}: {e}")
                evaluations.append(None)
        
        return evaluations
    
    # ═══════════════════════════════════════════════════════════════════════════
    # BEAUTY SCORING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _calculate_beauty(
        self,
        match_result: MatchResult,
        positions: List[Tuple[chess.Board, chess.Move]],
        evaluations: List[Optional[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Calculate beauty score for the entire game.
        
        Returns:
            {
                "total_score": float,
                "metrics": BeautyMetrics,
                "move_beauty": List[Tuple[float, MoveBeautyType]]
            }
        """
        move_beauty_scores = []
        
        for i, (board, move) in enumerate(positions):
            eval_data = evaluations[i] if evaluations else None
            
            if eval_data:
                eval_before = eval_data["eval_before"]
                eval_after = eval_data["eval_after"]
            else:
                eval_before = None
                eval_after = None
            
            # Use the BeautyEvaluator instance's evaluate_move method
            beauty_score, move_type = self.beauty_evaluator.evaluate_move(
                board=board,
                move=move,
                eval_before=eval_before,
                eval_after=eval_after
            )
            
            move_beauty_scores.append((beauty_score, move_type))
        
        # Use BeautyEvaluator instance's evaluate_game method for overall metrics
        moves_list = [move for _, move in positions]
        
        if evaluations and any(e is not None for e in evaluations):
            evals_tuples = [
                (e["eval_before"], e["eval_after"]) if e else (None, None)
                for e in evaluations
            ]
        else:
            evals_tuples = None
        
        beauty_metrics = self.beauty_evaluator.evaluate_game(moves=moves_list, evaluations=evals_tuples)
        
        return {
            "total_score": beauty_metrics.total_score,
            "metrics": beauty_metrics,
            "move_beauty": move_beauty_scores
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE DETECTION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _detect_phases(
        self,
        match_result: MatchResult,
        positions: List[Tuple[chess.Board, chess.Move]]
    ) -> List[PositionPhase]:
        """
        Detect game phases (opening, middlegame, endgame).
        
        Heuristics:
        - Opening: Moves 1-10 (or until castling + minor development)
        - Endgame: <= 13 pieces on board OR queens traded
        - Middlegame: Everything in between
        """
        phases = []
        current_phase = None
        phase_start = 1
        
        for i, (board, move) in enumerate(positions):
            move_num = i + 1
            
            # Detect current phase based on position
            piece_count = len(board.piece_map())
            queens_on_board = len(list(board.pieces(chess.QUEEN, chess.WHITE))) + \
                             len(list(board.pieces(chess.QUEEN, chess.BLACK)))
            
            if move_num <= 10:
                detected_phase = GamePhase.OPENING
            elif piece_count <= 13 or queens_on_board == 0:
                detected_phase = GamePhase.ENDGAME
            else:
                detected_phase = GamePhase.MIDDLEGAME
            
            # Track phase transitions
            if current_phase != detected_phase:
                # Close previous phase
                if current_phase is not None:
                    phases[-1].end_move = move_num - 1
                
                # Start new phase
                phases.append(PositionPhase(
                    phase=detected_phase,
                    start_move=move_num,
                    description=f"{detected_phase.value.title()} begins"
                ))
                current_phase = detected_phase
                phase_start = move_num
        
        # Close final phase
        if phases:
            phases[-1].end_move = len(positions)
        
        return phases
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MOVE ANNOTATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _annotate_moves(
        self,
        match_result: MatchResult,
        positions: List[Tuple[chess.Board, chess.Move]],
        evaluations: List[Optional[Dict[str, Any]]],
        move_beauty: List[Tuple[float, MoveBeautyType]]
    ) -> List[MoveAnnotation]:
        """
        Create detailed annotations for each move.
        
        Includes:
        - Stockfish evaluation
        - Beauty classification
        - NAG symbols (!!,!,?!,?,??)
        - Tactical motifs
        """
        annotations = []
        
        for i, (board, move) in enumerate(positions):
            move_record = match_result.moves[i]
            eval_data = evaluations[i] if evaluations else None
            beauty_score, beauty_type = move_beauty[i] if i < len(move_beauty) else (0.0, MoveBeautyType.BORING)
            
            annotation = MoveAnnotation(
                move_number=move_record.move_number,
                san=move_record.san,
                evaluation=eval_data.get("eval_before", 0.0) if eval_data else 0.0,
            )
            
            # Stockfish analysis
            if eval_data:
                annotation.evaluation = eval_data["eval_before"]
                annotation.best_move = eval_data["best_move"]
                annotation.is_best = eval_data["is_best"]
                
                # Calculate centipawn loss
                if eval_data["eval_after"] is not None:
                    annotation.centipawn_loss = abs(
                        eval_data["eval_before"] - eval_data["eval_after"]
                    )
            
            # Beauty analysis
            annotation.beauty_score = beauty_score
            annotation.beauty_type = beauty_type
            annotation.is_sacrifice = beauty_type in [
                MoveBeautyType.BRILLIANT_SACRIFICE,
                MoveBeautyType.EXCHANGE_SACRIFICE,
                MoveBeautyType.QUEEN_SACRIFICE
            ]
            annotation.is_quiet_killer = beauty_type == MoveBeautyType.QUIET_KILLER
            
            # Assign NAG symbols
            annotation.nags = self._assign_nags(annotation, eval_data)
            
            # Detect tactical motifs
            annotation.tactical_motifs = self._detect_tactical_motifs(board, move)
            
            annotations.append(annotation)
        
        return annotations
    
    def _assign_nags(
        self, 
        annotation: MoveAnnotation, 
        eval_data: Optional[Dict[str, Any]]
    ) -> List[str]:
        """
        Assign NAG symbols based on evaluation and beauty.
        
        Symbols:
        - !! = Brilliant move (best move + high beauty OR only move in critical position)
        - !  = Good move (best move OR high beauty)
        - !? = Interesting move (not best but creative)
        - ?! = Dubious move (questionable but not terrible)
        - ?  = Mistake (centipawn loss 100-300)
        - ?? = Blunder (centipawn loss > 300)
        """
        nags = []
        
        if not eval_data:
            # Without engine, judge by beauty alone
            if annotation.beauty_score >= 40:
                nags.append("!")
            return nags
        
        cpl = annotation.centipawn_loss
        
        # Blunders and mistakes
        if cpl >= 300:
            nags.append("??")
        elif cpl >= 100:
            nags.append("?")
        elif cpl >= 50:
            nags.append("?!")
        
        # Good moves
        elif annotation.is_best:
            if annotation.beauty_score >= 30 or annotation.is_sacrifice:
                nags.append("!!")
            else:
                nags.append("!")
        
        # Interesting moves
        elif annotation.beauty_score >= 25:
            nags.append("!?")
        
        return nags
    
    def _detect_tactical_motifs(self, board: chess.Board, move: chess.Move) -> List[str]:
        """
        Detect tactical patterns in the move.
        
        Returns list of motifs: ["pin", "fork", "skewer", "discovery", etc.]
        
        Note: This is a simplified heuristic. Full tactical detection requires
        deep engine analysis or pattern recognition.
        """
        motifs = []
        
        # Simple heuristic checks
        if board.is_check():
            motifs.append("check")
        
        if board.is_capture(move):
            motifs.append("capture")
        
        # More sophisticated detection would require Stockfish tactical analysis
        # For now, keep it simple
        
        return motifs
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CRITICAL MOMENTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _detect_critical_moments(
        self,
        match_result: MatchResult,
        annotations: List[MoveAnnotation]
    ) -> List[CriticalMoment]:
        """
        Detect turning points, blunders, and brilliancies.
        
        Critical moments:
        - Blunders (centipawn loss > 300)
        - Brilliancies (best move + high beauty)
        - Turning points (evaluation swing > 200 centipawns)
        - Missed wins (best continuation leads to mate but not played)
        """
        critical_moments = []
        
        for i, annotation in enumerate(annotations):
            move_record = match_result.moves[i]
            
            # Detect blunders
            if "??" in annotation.nags:
                critical_moments.append(CriticalMoment(
                    move_number=annotation.move_number,
                    san=annotation.san,
                    fen=move_record.fen_before,
                    moment_type="blunder",
                    eval_before=annotation.evaluation or 0.0,
                    eval_after=(annotation.evaluation or 0.0) - annotation.centipawn_loss,
                    eval_swing=annotation.centipawn_loss,
                    commentary=f"Major blunder! {annotation.san} loses {annotation.centipawn_loss:.0f} centipawns.",
                    severity=10
                ))
            
            # Detect brilliancies
            elif "!!" in annotation.nags:
                critical_moments.append(CriticalMoment(
                    move_number=annotation.move_number,
                    san=annotation.san,
                    fen=move_record.fen_before,
                    moment_type="brilliancy",
                    eval_before=annotation.evaluation or 0.0,
                    eval_after=annotation.evaluation or 0.0,
                    eval_swing=0.0,
                    commentary=f"Brilliant move! {annotation.san} is the best choice.",
                    severity=8
                ))
            
            # Detect turning points (large eval swings)
            if i > 0:
                prev_eval = annotations[i-1].evaluation or 0.0
                curr_eval = annotation.evaluation or 0.0
                swing = abs(curr_eval - prev_eval)
                
                if swing >= 200:
                    critical_moments.append(CriticalMoment(
                        move_number=annotation.move_number,
                        san=annotation.san,
                        fen=move_record.fen_before,
                        moment_type="turning_point",
                        eval_before=prev_eval,
                        eval_after=curr_eval,
                        eval_swing=swing,
                        commentary=f"The game shifts dramatically after {annotation.san}.",
                        severity=7
                    ))
        
        return critical_moments
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ACCURACY METRICS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _calculate_accuracy(
        self,
        match_result: MatchResult,
        annotations: List[MoveAnnotation]
    ) -> Dict[str, float]:
        """
        Calculate average centipawn loss and accuracy percentage.
        
        Returns:
            {
                "white_cpl": float,
                "black_cpl": float,
                "white_accuracy": float (0-100),
                "black_accuracy": float (0-100)
            }
        """
        white_cpls = []
        black_cpls = []
        
        for i, annotation in enumerate(annotations):
            if annotation.centipawn_loss > 0:
                move_record = match_result.moves[i]
                
                if move_record.color == "white":
                    white_cpls.append(annotation.centipawn_loss)
                else:
                    black_cpls.append(annotation.centipawn_loss)
        
        white_cpl = sum(white_cpls) / len(white_cpls) if white_cpls else 0.0
        black_cpl = sum(black_cpls) / len(black_cpls) if black_cpls else 0.0
        
        # Accuracy formula: 100% - (CPL / 10)
        # CPL of 0 = 100% accuracy
        # CPL of 100 = 90% accuracy
        # CPL of 500 = 50% accuracy
        white_accuracy = max(0, 100 - (white_cpl / 10))
        black_accuracy = max(0, 100 - (black_cpl / 10))
        
        return {
            "white_cpl": white_cpl,
            "black_cpl": black_cpl,
            "white_accuracy": white_accuracy,
            "black_accuracy": black_accuracy
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # COMPLEXITY AND DRAMA
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _calculate_complexity(self, positions: List[Tuple[chess.Board, chess.Move]]) -> float:
        """
        Calculate game complexity score (0-100).
        
        Based on:
        - Average number of legal moves per position
        - Piece activity
        - Pawn structure complexity
        """
        if not positions:
            return 0.0
        
        legal_move_counts = []
        
        for board, _ in positions:
            legal_move_counts.append(board.legal_moves.count())
        
        avg_legal_moves = sum(legal_move_counts) / len(legal_move_counts)
        
        # Normalize: 20 legal moves = 50 complexity, 40 legal moves = 100 complexity
        complexity = min(100, (avg_legal_moves / 40) * 100)
        
        return complexity
    
    def _calculate_drama(
        self,
        critical_moments: List[CriticalMoment],
        evaluations: List[Optional[Dict[str, Any]]]
    ) -> float:
        """
        Calculate drama score (0-100).
        
        Based on:
        - Number of critical moments
        - Severity of eval swings
        - Game balance (close vs one-sided)
        """
        if not critical_moments:
            return 20.0  # Base drama
        
        # Count blunders and brilliancies
        blunder_count = sum(1 for m in critical_moments if m.moment_type == "blunder")
        brilliancy_count = sum(1 for m in critical_moments if m.moment_type == "brilliancy")
        turning_point_count = sum(1 for m in critical_moments if m.moment_type == "turning_point")
        
        # Calculate drama score
        drama = 20.0  # Base
        drama += blunder_count * 15  # Blunders are dramatic
        drama += brilliancy_count * 10  # Brilliancies add flair
        drama += turning_point_count * 20  # Turning points are peak drama
        
        # Cap at 100
        return min(100, drama)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STRATEGIC COMMENTARY
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _generate_commentary(
        self,
        match_result: MatchResult,
        critical_moments: List[CriticalMoment],
        annotations: List[MoveAnnotation]
    ) -> List[str]:
        """
        Generate strategic commentary for critical positions.
        
        Uses the commentary LLM to provide insights on:
        - Critical moments
        - Turning points
        - Phase transitions
        """
        if not self.commentary_provider or not self.enable_commentary:
            return []
        
        commentary_list = []
        
        # Generate commentary for critical moments only (to reduce LLM calls)
        for moment in critical_moments[:5]:  # Limit to top 5 moments
            try:
                prompt = self._build_commentary_prompt(match_result, moment)
                response = await self.commentary_provider.generate(prompt)
                commentary_list.append(response.strip())
            except Exception as e:
                logger.warning(f"Failed to generate commentary for move {moment.move_number}: {e}")
                commentary_list.append("")
        
        return commentary_list
    
    def _build_commentary_prompt(
        self,
        match_result: MatchResult,
        moment: CriticalMoment
    ) -> str:
        """Build LLM prompt for strategic commentary."""
        return f"""You are a chess commentator analyzing a game between {match_result.white.name} (White) and {match_result.black.name} (Black).

POSITION (FEN): {moment.fen}
MOVE JUST PLAYED: {moment.move_number}. {moment.san}
MOMENT TYPE: {moment.moment_type}
EVALUATION CHANGE: {moment.eval_before:.1f} → {moment.eval_after:.1f} (swing: {moment.eval_swing:.0f} centipawns)

Provide a 1-2 sentence {self.commentary_style} commentary on this {moment.moment_type}.
Explain what happened and why it matters.

Commentary:"""
    
    # ═══════════════════════════════════════════════════════════════════════════
    # GAME NARRATIVE
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def _build_narrative(
        self,
        match_result: MatchResult,
        analysis: MatchAnalysis
    ) -> GameNarrative:
        """
        Build overall game narrative/summary.
        
        Includes:
        - Game summary
        - Opening identification
        - Key phases
        - Style assessments
        - Winner's path to victory
        """
        narrative = GameNarrative(summary="")
        
        # Build summary
        winner = "White" if match_result.result == GameResult.WHITE_WINS else \
                 "Black" if match_result.result == GameResult.BLACK_WINS else "Draw"
        
        narrative.summary = (
            f"{match_result.white.name} vs {match_result.black.name} ended in {winner} "
            f"after {match_result.total_moves} moves. "
            f"The game featured {len(analysis.critical_moments)} critical moments "
            f"with a beauty score of {analysis.beauty_score:.1f}/100."
        )
        
        # Opening name (placeholder - would need opening book)
        narrative.opening_name = "Unknown Opening"
        narrative.opening_description = f"Game opened with standard development in the first {min(10, match_result.total_moves)} moves."
        
        # Key phases
        narrative.key_phases = [
            f"{phase.phase.value.title()}: moves {phase.start_move}-{phase.end_move or match_result.total_moves}"
            for phase in analysis.phases
        ]
        
        # Complexity and drama
        narrative.complexity_score = analysis.complexity_score
        narrative.drama_score = analysis.drama_score
        
        # Winner reason
        narrative.winner_reason = self._determine_winner_reason(match_result, analysis)
        
        return narrative
    
    def _determine_winner_reason(
        self,
        match_result: MatchResult,
        analysis: MatchAnalysis
    ) -> str:
        """Determine why the winner won (or why it was a draw)."""
        if match_result.result == GameResult.DRAW:
            return f"Game ended in a draw by {match_result.termination.value}"
        
        winner_name = match_result.white.name if match_result.result == GameResult.WHITE_WINS else match_result.black.name
        
        # Check termination reason
        if match_result.termination == TerminationReason.CHECKMATE:
            return f"{winner_name} delivered checkmate"
        elif match_result.termination == TerminationReason.RESIGNATION:
            return f"{winner_name} won by resignation"
        elif match_result.termination == TerminationReason.FORFEIT:
            return f"{winner_name} won due to opponent's excessive illegal moves"
        elif match_result.termination == TerminationReason.TIMEOUT:
            return f"{winner_name} won on time"
        else:
            return f"{winner_name} won by {match_result.termination.value}"


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def create_analyzer_from_config(config: Dict[str, Any]) -> MatchAnalyzer:
    """
    Create MatchAnalyzer from configuration dictionary.
    
    Example config:
        {
            "stockfish_path": "/usr/bin/stockfish",
            "depth": 15,
            "enable_commentary": True,
            "commentary_provider": my_llm_provider,
            "commentary_style": "grandmaster"
        }
    """
    return MatchAnalyzer(
        stockfish_path=config.get("stockfish_path"),
        commentary_provider=config.get("commentary_provider"),
        depth=config.get("depth", 15),
        time_limit=config.get("time_limit", 0.1),
        enable_commentary=config.get("enable_commentary", True),
        commentary_style=config.get("commentary_style", "grandmaster"),
        threads=config.get("threads", 1),
        hash_mb=config.get("hash_mb", 64),
    )
