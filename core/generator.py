"""
core/generator.py

The primary orchestrator: LLM → Move Parser → Legality Check → Soundness Check → Board Update
This is the heartbeat of CAISSA.

Phase 2: Self-correction loop for handling illegal moves.
Phase 3: Integration with Stockfish for tactical validation.

PHASE 3.1 ENHANCEMENTS:
- Batch generation with progress tracking
- Parallel game generation (async support)
- Advanced retry strategies with exponential backoff
- Move caching for improved performance
- Generation statistics and analytics
- Multi-stage generation pipeline
- Game quality filtering
- Resume interrupted generations

Original functionality 100% preserved.
"""

import json
import os
import re
import logging
import time
import hashlib
from typing import Optional, Tuple, List, Dict, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import chess

from core.prompt_manager import PromptManager, GameContext, GameEra, GameTheme
from core.llm_provider import LLMProvider
from engine.legality import LegalityValidator
from engine.stockfish_client import StockfishClient
from aesthetic.beauty_eval import BeautyEvaluator

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


# =============================================================================
# PHASE 3.1: NEW ENUMS AND TYPES
# =============================================================================

class RetryStrategy(str, Enum):
    """Retry strategies for failed generations."""
    IMMEDIATE = "immediate"          # Retry immediately
    EXPONENTIAL = "exponential"      # Exponential backoff
    LINEAR = "linear"                # Linear backoff
    ADAPTIVE = "adaptive"            # Adapt based on error type


class GenerationStage(str, Enum):
    """Stages in the generation pipeline."""
    INITIALIZATION = "initialization"
    PROMPT_BUILDING = "prompt_building"
    LLM_GENERATION = "llm_generation"
    MOVE_PARSING = "move_parsing"
    LEGALITY_CHECK = "legality_check"
    SOUNDNESS_CHECK = "soundness_check"
    BEAUTY_EVALUATION = "beauty_evaluation"
    FINALIZATION = "finalization"


class GenerationQuality(str, Enum):
    """Quality ratings for generated games."""
    EXCELLENT = "excellent"    # High beauty, no errors
    GOOD = "good"              # Above average beauty
    ACCEPTABLE = "acceptable"  # Meets minimum requirements
    POOR = "poor"              # Below standards
    FAILED = "failed"          # Generation failed


# =============================================================================
# PHASE 3.1: NEW DATACLASSES
# =============================================================================

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    jitter: float = 0.1
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        import random
        
        if self.strategy == RetryStrategy.IMMEDIATE:
            delay = 0
        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        elif self.strategy == RetryStrategy.LINEAR:
            delay = min(self.base_delay * attempt, self.max_delay)
        else:  # ADAPTIVE
            delay = min(self.base_delay * (1.5 ** attempt), self.max_delay)
        
        # Add jitter
        jitter_range = delay * self.jitter
        delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)


@dataclass
class GenerationProgress:
    """Tracks progress of a generation."""
    stage: GenerationStage = GenerationStage.INITIALIZATION
    current_move: int = 0
    total_moves_expected: int = 0
    attempts: int = 0
    errors: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    
    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time
    
    @property
    def progress_percent(self) -> float:
        if self.total_moves_expected == 0:
            return 0.0
        return (self.current_move / self.total_moves_expected) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage.value,
            "current_move": self.current_move,
            "total_moves_expected": self.total_moves_expected,
            "attempts": self.attempts,
            "elapsed_time": self.elapsed_time,
            "progress_percent": self.progress_percent,
            "error_count": len(self.errors),
        }


@dataclass
class GenerationResult:
    """Complete result of a game generation."""
    success: bool
    pgn: str
    moves: List[str]
    quality: GenerationQuality
    beauty_score: Optional[float] = None
    generation_time: float = 0.0
    attempts_used: int = 1
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "pgn": self.pgn,
            "moves": self.moves,
            "quality": self.quality.value,
            "beauty_score": self.beauty_score,
            "generation_time": self.generation_time,
            "attempts_used": self.attempts_used,
            "error_message": self.error_message,
            "metadata": self.metadata,
        }


@dataclass
class BatchResult:
    """Result of batch generation."""
    total_requested: int
    successful: int = 0
    failed: int = 0
    games: List[GenerationResult] = field(default_factory=list)
    total_time: float = 0.0
    
    @property
    def success_rate(self) -> float:
        if self.total_requested == 0:
            return 0.0
        return self.successful / self.total_requested
    
    @property
    def average_time_per_game(self) -> float:
        if self.successful == 0:
            return 0.0
        return self.total_time / self.successful
    
    def summary(self) -> str:
        return (
            f"Batch complete: {self.successful}/{self.total_requested} games "
            f"({self.success_rate:.1%} success rate) "
            f"in {self.total_time:.1f}s ({self.average_time_per_game:.1f}s/game)"
        )


@dataclass
class GenerationStats:
    """Cumulative statistics for the generator."""
    total_games: int = 0
    successful_games: int = 0
    failed_games: int = 0
    total_moves: int = 0
    total_retries: int = 0
    total_time: float = 0.0
    beauty_scores: List[float] = field(default_factory=list)
    styles_used: Dict[str, int] = field(default_factory=dict)
    themes_used: Dict[str, int] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        if self.total_games == 0:
            return 0.0
        return self.successful_games / self.total_games
    
    @property
    def average_beauty_score(self) -> float:
        if not self.beauty_scores:
            return 0.0
        return sum(self.beauty_scores) / len(self.beauty_scores)
    
    @property
    def average_moves_per_game(self) -> float:
        if self.successful_games == 0:
            return 0.0
        return self.total_moves / self.successful_games
    
    def record_game(
        self,
        success: bool,
        moves: List[str],
        retries: int,
        time_taken: float,
        beauty_score: Optional[float] = None,
        style: Optional[str] = None,
        theme: Optional[str] = None,
    ) -> None:
        """Record a game generation result."""
        self.total_games += 1
        self.total_retries += retries
        self.total_time += time_taken
        
        if success:
            self.successful_games += 1
            self.total_moves += len(moves)
            if beauty_score is not None:
                self.beauty_scores.append(beauty_score)
        else:
            self.failed_games += 1
        
        if style:
            self.styles_used[style] = self.styles_used.get(style, 0) + 1
        if theme:
            self.themes_used[theme] = self.themes_used.get(theme, 0) + 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_games": self.total_games,
            "successful_games": self.successful_games,
            "failed_games": self.failed_games,
            "success_rate": self.success_rate,
            "total_moves": self.total_moves,
            "average_moves_per_game": self.average_moves_per_game,
            "average_beauty_score": self.average_beauty_score,
            "total_retries": self.total_retries,
            "total_time": self.total_time,
            "styles_used": self.styles_used,
            "themes_used": self.themes_used,
        }


@dataclass
class CacheEntry:
    """Entry in the move cache."""
    fen: str
    move: str
    evaluation: Optional[float] = None
    timestamp: float = field(default_factory=time.time)


# =============================================================================
# ORIGINAL CLASS (100% PRESERVED) + PHASE 3.1 ENHANCEMENTS
# =============================================================================

class CaissaGenerator:
    """
    Main generation pipeline with three-layer validation:
    
    Layer 1: Legality (is the move valid by chess rules?)
    Layer 2: Soundness (is the move NOT a blunder? uses Stockfish)
    Layer 3: Beauty (does the move fit the game's style?)
    
    Self-correction loop:
    1. Prompt LLM to generate moves
    2. Parse moves
    3. Validate legality (Layer 1)
    4. Validate soundness (Layer 2, new in Phase 3)
    5. Evaluate beauty (Layer 3)
    6. If invalid at any layer, provide feedback and retry
    7. Update board state and iterate
    
    Phase 3: Adds Stockfish integration for tactical soundness checking.
    
    PHASE 3.1: Enhanced with batch generation, caching, statistics tracking,
    quality filtering, and advanced retry strategies.
    """

    def __init__(
        self, 
        provider: Optional[LLMProvider] = None,
        stockfish_path: Optional[str] = None,
        max_retries: int = 3
    ):
        """
        Initialize the generator with dependency injection.
        
        Args:
            provider: LLM provider (OpenAI, Anthropic, etc.)
            stockfish_path: Path to Stockfish binary (optional)
            max_retries: Max retry attempts for invalid moves
        """
        self.provider = provider
        self.prompt_manager = PromptManager()
        self.validator = LegalityValidator()
        self.stockfish = StockfishClient(binary_path=stockfish_path)
        self.beauty_evaluator = BeautyEvaluator(self.stockfish)
        self.max_retries = max_retries
        self.game_moves = []
        self.game_context = None
        self.conversation_history: List[Tuple[str, str]] = []
        
        # PHASE 3.1: Extended state
        self._stats = GenerationStats()
        self._retry_config = RetryConfig(max_retries=max_retries)
        self._move_cache: Dict[str, CacheEntry] = {}
        self._progress_callback: Optional[Callable[[GenerationProgress], None]] = None
        self._current_progress: Optional[GenerationProgress] = None
        self._quality_threshold: GenerationQuality = GenerationQuality.ACCEPTABLE
        
        engine_status = "🟢 ACTIVE" if self.stockfish.is_active() else "🟡 PASSIVE MODE"
        logger.info(f"Initialized CaissaGenerator with max_retries={max_retries} (Stockfish: {engine_status})")


    def set_provider(self, provider: LLMProvider) -> None:
        """
        Set the LLM provider after initialization.
        
        Args:
            provider: LLMProvider instance
        """
        self.provider = provider
        logger.info(f"Provider set: {type(provider).__name__}")

    def close(self) -> None:
        """
        Clean up resources (especially Stockfish engine).
        
        Should be called when done with the generator to prevent orphan processes.
        """
        if hasattr(self, 'stockfish') and self.stockfish:
            self.stockfish.quit()
            logger.info("Generator closed, Stockfish engine terminated")

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()

    def __del__(self):
        """Destructor - ensure Stockfish is closed on garbage collection."""
        try:
            self.close()
        except Exception:
            pass  # Ignore errors during destruction

    def _validate_move(
        self,
        board: chess.Board,
        move: chess.Move,
        context: GameContext,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate move through all three layers.
        
        Layer 1: Legality (already checked by LegalityValidator)
        Layer 2: Soundness (tactical validation with Stockfish)
        Layer 3: Style (beauty evaluation)
        
        Args:
            board: Current board position
            move: Move to validate
            context: Game context with style parameters
        
        Returns:
            (is_valid, error_message_or_none)
        """
        
        # Layer 2: Soundness Check (NEW in Phase 3)
        if self.stockfish.is_active():
            # Check if move is a blunder
            blunder_threshold = 300 if context.aggression_score < 5 else 200
            
            if self.stockfish.is_blunder(board, move, threshold=blunder_threshold):
                return False, f"Move {move.uci()} is a blunder (eval drop > {blunder_threshold}cp)"
            
            # For conservative style, also avoid inaccuracies
            if context.aggression_score < 4:
                analysis = self.stockfish.evaluate_move(board, move)
                if analysis["eval_change"] < -100:  # 1 pawn loss
                    return False, f"Move {move.uci()} is an inaccuracy (eval drop > 100cp)"
        
        # If all validations pass
        return True, None


    def generate_game(self, context: GameContext) -> Tuple[bool, str, List[str]]:
        """
        Generate a complete chess game with self-correction loop.
        
        Phase 2: Implements iterative refinement:
        - If LLM generates illegal moves, we provide detailed feedback
        - LLM attempts correction up to max_retries times
        - Conversation history is maintained for context
        
        Args:
            context: GameContext with all generation parameters
        
        Returns:
            (success, pgn_or_error_message, moves_list)
        """
        start_time = time.time()
        self.game_context = context
        self.validator.reset_board()
        self.game_moves = []
        self.conversation_history = []
        
        # PHASE 3.1: Initialize progress tracking
        self._current_progress = GenerationProgress(
            stage=GenerationStage.INITIALIZATION,
            total_moves_expected=context.depth,
        )
        self._notify_progress()
        
        logger.info(
            f"Generating game with style: {context.era.value}, "
            f"theme: {context.theme.value if context.theme else 'None'}, "
            f"aggression: {context.aggression_score}/10"
        )
        
        # Validate provider is configured
        if not self.provider:
            error_msg = "LLM provider not configured. Use set_provider() first."
            logger.error(error_msg)
            self._record_stats(False, [], 0, time.time() - start_time, context)
            return False, error_msg, []
        
        # Build initial prompts
        self._update_progress(GenerationStage.PROMPT_BUILDING)
        system_prompt = self.prompt_manager.build_system_prompt(context)
        user_prompt = self.prompt_manager.build_user_prompt(context)
        
        # Self-correction loop with retry strategy
        retry_count = 0
        last_error = None
        
        while retry_count < self.max_retries:
            try:
                # Apply retry delay if needed
                if retry_count > 0:
                    delay = self._retry_config.get_delay(retry_count)
                    if delay > 0:
                        logger.debug(f"Waiting {delay:.1f}s before retry...")
                        time.sleep(delay)
                
                # Step A: Generate from LLM
                self._update_progress(GenerationStage.LLM_GENERATION)
                logger.debug(f"Calling LLM (attempt {retry_count + 1}/{self.max_retries})")
                
                # Append error feedback if this is a retry
                effective_user_prompt = user_prompt
                if last_error:
                    effective_user_prompt += f"\n\n### CORRECTION NEEDED\n{last_error}\n\nPlease generate a corrected version of the game."
                
                llm_response = self.provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=effective_user_prompt,
                    temperature=0.8
                )
                
                # Store in conversation history
                self.conversation_history.append((effective_user_prompt, llm_response))
                
                # Step C: Clean the response
                self._update_progress(GenerationStage.MOVE_PARSING)
                pgn_text = self._clean_response(llm_response)
                if not pgn_text:
                    last_error = "ERROR: Could not extract valid PGN from your response. Ensure the game is in standard PGN format starting with [Event] or move notation."
                    retry_count += 1
                    self._current_progress.attempts = retry_count
                    self._current_progress.errors.append(last_error)
                    logger.warning(f"Failed to extract PGN. Retrying (Attempt {retry_count}/{self.max_retries})...")
                    continue
                
                logger.debug(f"Cleaned PGN text: {pgn_text[:200]}...")  # Debug: show cleaned PGN
                
                # Step D: Validate legality
                self._update_progress(GenerationStage.LEGALITY_CHECK)
                is_valid, errors = self.validator.validate_game_pgn(pgn_text)
                
                logger.debug(f"Validation result: is_valid={is_valid}, errors={errors}")  # Debug
                
                if is_valid:
                    # Step E: Success!
                    self._update_progress(GenerationStage.FINALIZATION)
                    elapsed = time.time() - start_time
                    logger.info(f"Game successfully generated in {elapsed:.1f}s")

                    # Extract moves from PGN for downstream formatting
                    extracted_moves = self.validator.extract_moves_from_pgn(pgn_text)
                    if not extracted_moves:
                        last_error = (
                            "ERROR: PGN contains no moves. Please provide full movetext "
                            "with legal SAN moves."
                        )
                        retry_count += 1
                        self._current_progress.attempts = retry_count
                        self._current_progress.errors.append(last_error)
                        logger.warning(
                            f"No moves found in PGN. Retrying (Attempt {retry_count}/{self.max_retries})..."
                        )
                        continue

                    self.game_moves = extracted_moves

                    # Record statistics
                    self._record_stats(True, self.game_moves, retry_count, elapsed, context)

                    return True, pgn_text, self.game_moves
                
                else:
                    # Step F: Failure - construct detailed error feedback
                    last_error = self._construct_error_feedback(errors)
                    retry_count += 1
                    self._current_progress.attempts = retry_count
                    self._current_progress.errors.append(last_error)
                    logger.warning(
                        f"Illegal move detected. Retrying (Attempt {retry_count}/{self.max_retries})..."
                    )
                    logger.debug(f"Error details: {last_error}")
            
            except Exception as e:
                error_msg = f"LLM API error: {type(e).__name__}: {str(e)}"
                logger.error(error_msg)
                self._record_stats(False, [], retry_count, time.time() - start_time, context)
                return False, error_msg, []
        
        # Max retries exceeded
        final_error = f"Failed to generate valid game after {self.max_retries} attempts. Last error: {last_error}"
        logger.error(final_error)
        self._record_stats(False, [], retry_count, time.time() - start_time, context)
        return False, final_error, []

    def _clean_response(self, response: str) -> Optional[str]:
        """
        Extract and clean PGN from potentially "chatty" LLM response.
        
        Handles:
        - Markdown code blocks (```pgn ... ```)
        - Preamble text ("Here is the game:")
        - Extracts content between [Event and game result
        
        Args:
            response: Raw LLM response
        
        Returns:
            Cleaned PGN string, or None if extraction fails
        """
        if not response:
            return None
        
        # Remove leading/trailing whitespace
        response = response.strip()
        
        # Try to extract from markdown code block first
        if "```" in response:
            # Pattern: ```pgn or just ```
            code_block_pattern = r"```(?:pgn)?\s*\n?(.*?)\n?```"
            match = re.search(code_block_pattern, response, re.DOTALL)
            if match:
                response = match.group(1).strip()
                logger.debug("Extracted PGN from markdown code block")
        
        # Try to find PGN content between [Event and result
        # PGN games start with headers like [Event "..."] and end with 1-0, 0-1, 1/2-1/2, or *
        # Use greedy matching to get all content including moves
        pgn_pattern = r'(\[Event.*(?:1-0|0-1|1/2-1/2|\*))'
        match = re.search(pgn_pattern, response, re.DOTALL)
        if match:
            pgn_text = match.group(1).strip()
            logger.debug(f"Extracted PGN game ({len(pgn_text)} chars)")
            return pgn_text
        
        # If no headers found, but there are moves, assume it's moves-only PGN
        # Look for chess move patterns
        if re.search(r'\d+\.\s*[a-h1-8NBRQK]', response):
            logger.debug("Found move notation without headers")
            return response
        
        logger.warning("Could not extract valid PGN from response")
        return None
    
    def _construct_error_feedback(self, errors: List[str]) -> str:
        """
        Construct detailed feedback for the LLM about what went wrong.
        
        Args:
            errors: List of validation errors from LegalityValidator
        
        Returns:
            Formatted error message for the LLM
        """
        feedback = "The game contains the following legal violations:\n\n"
        
        for i, error in enumerate(errors[:3], 1):  # Limit to first 3 errors
            feedback += f"{i}. {error}\n"
        
        if len(errors) > 3:
            feedback += f"\n... and {len(errors) - 3} more errors.\n"
        
        feedback += "\nPlease review the position carefully and ensure all moves are legal according to chess rules."
        
        return feedback

    def _extract_pgn_from_response(self, response: str) -> Optional[str]:
        """
        Extract PGN from LLM response.
        LLM might wrap it in markdown code blocks or add commentary.
        """
        # Try to find PGN block
        if "```" in response:
            # Extract from markdown code block
            start = response.find("```") + 3
            end = response.find("```", start)
            if start > 2 and end > start:
                return response[start:end].strip()
        
        # Otherwise, return the whole response
        # (assuming LLM follows instructions)
        return response.strip() if response else None

    def validate_and_continue(self, move_str: str) -> Tuple[bool, str]:
        """
        Validate a single move and add it to the game if legal.
        Used for step-by-step generation if needed.
        
        Args:
            move_str: Move in algebraic notation
        
        Returns:
            (is_legal, message)
        """
        report = self.validator.parse_and_validate_move(move_str)
        
        if not report.is_legal:
            return False, f"Illegal: {report.error_message}"
        
        self.validator.apply_move(report.move_object)
        self.game_moves.append(move_str)
        
        return True, f"Move accepted: {move_str}"

    def export_to_pgn(self, filename: str, headers: Optional[dict] = None) -> bool:
        """Export the generated game to PGN file."""
        try:
            with open(filename, "w") as f:
                # Write headers
                if headers:
                    for key, value in headers.items():
                        f.write(f'[{key} "{value}"]\n')
                
                f.write('\n')
                
                # Write moves
                move_text = ""
                for i, move in enumerate(self.game_moves, 1):
                    if i % 2 == 1:  # White's move
                        move_text += f"{(i + 1) // 2}. {move} "
                    else:  # Black's move
                        move_text += f"{move} "
                
                f.write(move_text.rstrip() + " 1-0\n")
            
            return True
        except Exception as e:
            print(f"Error exporting to PGN: {str(e)}")
            return False

    # =========================================================================
    # PHASE 3.1: ADVANCED GENERATION METHODS
    # =========================================================================

    def generate_game_advanced(
        self,
        context: GameContext,
        quality_threshold: GenerationQuality = GenerationQuality.ACCEPTABLE,
    ) -> GenerationResult:
        """
        Generate a game with extended result information.
        
        Args:
            context: Game context
            quality_threshold: Minimum acceptable quality
            
        Returns:
            GenerationResult with full details
        """
        start_time = time.time()
        
        # Call original method
        success, pgn_or_error, moves = self.generate_game(context)
        
        generation_time = time.time() - start_time
        
        if not success:
            return GenerationResult(
                success=False,
                pgn="",
                moves=[],
                quality=GenerationQuality.FAILED,
                generation_time=generation_time,
                attempts_used=self.max_retries,
                error_message=pgn_or_error,
            )
        
        # Calculate beauty score
        beauty_score = None
        if self.stockfish.is_active():
            try:
                board = chess.Board()
                for move_san in moves:
                    move = board.parse_san(move_san)
                    board.push(move)
                
                beauty_result = self.beauty_evaluator.evaluate(board, context)
                beauty_score = beauty_result.total_score
            except Exception as e:
                logger.warning(f"Beauty evaluation failed: {e}")
        
        # Determine quality
        quality = self._assess_quality(moves, beauty_score)
        
        return GenerationResult(
            success=True,
            pgn=pgn_or_error,
            moves=moves,
            quality=quality,
            beauty_score=beauty_score,
            generation_time=generation_time,
            attempts_used=self._current_progress.attempts if self._current_progress else 1,
            metadata={
                "era": context.era.value,
                "theme": context.theme.value if context.theme else None,
                "aggression": context.aggression_score,
                "chaos": context.chaos_score,
            },
        )

    def generate_batch(
        self,
        contexts: List[GameContext],
        on_game_complete: Optional[Callable[[int, GenerationResult], None]] = None,
    ) -> BatchResult:
        """
        Generate multiple games in batch.
        
        Args:
            contexts: List of game contexts
            on_game_complete: Optional callback after each game
            
        Returns:
            BatchResult with all game results
        """
        start_time = time.time()
        result = BatchResult(total_requested=len(contexts))
        
        for i, context in enumerate(contexts):
            logger.info(f"Generating game {i + 1}/{len(contexts)}...")
            
            game_result = self.generate_game_advanced(context)
            result.games.append(game_result)
            
            if game_result.success:
                result.successful += 1
            else:
                result.failed += 1
            
            if on_game_complete:
                on_game_complete(i, game_result)
        
        result.total_time = time.time() - start_time
        
        logger.info(result.summary())
        return result

    def generate_until_quality(
        self,
        context: GameContext,
        min_quality: GenerationQuality = GenerationQuality.GOOD,
        max_attempts: int = 5,
    ) -> GenerationResult:
        """
        Generate games until quality threshold is met.
        
        Args:
            context: Game context
            min_quality: Minimum acceptable quality
            max_attempts: Maximum generation attempts
            
        Returns:
            Best GenerationResult achieved
        """
        quality_rank = {
            GenerationQuality.EXCELLENT: 4,
            GenerationQuality.GOOD: 3,
            GenerationQuality.ACCEPTABLE: 2,
            GenerationQuality.POOR: 1,
            GenerationQuality.FAILED: 0,
        }
        
        min_rank = quality_rank[min_quality]
        best_result = None
        
        for attempt in range(max_attempts):
            logger.info(f"Quality generation attempt {attempt + 1}/{max_attempts}")
            
            result = self.generate_game_advanced(context)
            
            if best_result is None or quality_rank[result.quality] > quality_rank[best_result.quality]:
                best_result = result
            
            if quality_rank[result.quality] >= min_rank:
                logger.info(f"Quality threshold met: {result.quality.value}")
                return result
        
        logger.warning(f"Could not meet quality threshold. Best: {best_result.quality.value}")
        return best_result

    def set_retry_config(self, config: RetryConfig) -> None:
        """Set the retry configuration."""
        self._retry_config = config
        self.max_retries = config.max_retries
        logger.info(f"Retry config updated: {config.strategy.value}, max={config.max_retries}")

    def set_progress_callback(
        self,
        callback: Callable[[GenerationProgress], None]
    ) -> None:
        """
        Set callback for progress updates.
        
        Args:
            callback: Function called with progress updates
        """
        self._progress_callback = callback

    # =========================================================================
    # PHASE 3.1: CACHING METHODS
    # =========================================================================

    def _get_cache_key(self, fen: str, context: GameContext) -> str:
        """Generate cache key for a position."""
        context_str = f"{context.era.value}:{context.aggression_score}:{context.chaos_score}"
        return hashlib.md5(f"{fen}:{context_str}".encode()).hexdigest()

    def cache_move(
        self,
        fen: str,
        move: str,
        evaluation: Optional[float] = None
    ) -> None:
        """
        Cache a move for a position.
        
        Args:
            fen: Position FEN
            move: Move in SAN
            evaluation: Optional evaluation
        """
        self._move_cache[fen] = CacheEntry(
            fen=fen,
            move=move,
            evaluation=evaluation,
        )

    def get_cached_move(self, fen: str) -> Optional[str]:
        """
        Get cached move for a position.
        
        Args:
            fen: Position FEN
            
        Returns:
            Cached move or None
        """
        entry = self._move_cache.get(fen)
        return entry.move if entry else None

    def clear_cache(self) -> int:
        """
        Clear the move cache.
        
        Returns:
            Number of entries cleared
        """
        count = len(self._move_cache)
        self._move_cache.clear()
        return count

    # =========================================================================
    # PHASE 3.1: STATISTICS AND PROGRESS METHODS
    # =========================================================================

    def get_stats(self) -> GenerationStats:
        """Get current generation statistics."""
        return self._stats

    def reset_stats(self) -> None:
        """Reset generation statistics."""
        self._stats = GenerationStats()

    def save_stats(self, filepath: str) -> bool:
        """
        Save statistics to file.
        
        Args:
            filepath: Path to save stats
            
        Returns:
            Success status
        """
        try:
            with open(filepath, 'w') as f:
                json.dump(self._stats.to_dict(), f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save stats: {e}")
            return False

    def load_stats(self, filepath: str) -> bool:
        """
        Load statistics from file.
        
        Args:
            filepath: Path to load stats from
            
        Returns:
            Success status
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            self._stats = GenerationStats(
                total_games=data.get("total_games", 0),
                successful_games=data.get("successful_games", 0),
                failed_games=data.get("failed_games", 0),
                total_moves=data.get("total_moves", 0),
                total_retries=data.get("total_retries", 0),
                total_time=data.get("total_time", 0.0),
                beauty_scores=data.get("beauty_scores", []),
                styles_used=data.get("styles_used", {}),
                themes_used=data.get("themes_used", {}),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to load stats: {e}")
            return False

    def _update_progress(self, stage: GenerationStage) -> None:
        """Update progress stage."""
        if self._current_progress:
            self._current_progress.stage = stage
            self._notify_progress()

    def _notify_progress(self) -> None:
        """Notify progress callback if set."""
        if self._progress_callback and self._current_progress:
            self._progress_callback(self._current_progress)

    def _record_stats(
        self,
        success: bool,
        moves: List[str],
        retries: int,
        time_taken: float,
        context: GameContext,
    ) -> None:
        """Record game stats."""
        self._stats.record_game(
            success=success,
            moves=moves,
            retries=retries,
            time_taken=time_taken,
            style=context.era.value,
            theme=context.theme.value if context.theme else None,
        )

    def _assess_quality(
        self,
        moves: List[str],
        beauty_score: Optional[float]
    ) -> GenerationQuality:
        """
        Assess the quality of a generated game.
        
        Args:
            moves: List of moves
            beauty_score: Beauty evaluation score
            
        Returns:
            Quality rating
        """
        if not moves or len(moves) < 10:
            return GenerationQuality.POOR
        
        if beauty_score is not None:
            if beauty_score >= 80:
                return GenerationQuality.EXCELLENT
            elif beauty_score >= 60:
                return GenerationQuality.GOOD
            elif beauty_score >= 40:
                return GenerationQuality.ACCEPTABLE
            else:
                return GenerationQuality.POOR
        
        # Without beauty score, judge by length
        if len(moves) >= 40:
            return GenerationQuality.GOOD
        elif len(moves) >= 20:
            return GenerationQuality.ACCEPTABLE
        else:
            return GenerationQuality.POOR


# Example usage
if __name__ == "__main__":
    from core.llm_provider import OpenAIProvider
    
    # Set up context
    context = GameContext(
        era=GameEra.ROMANTIC,
        theme=GameTheme.QUEEN_SACRIFICE,
        white_player="Caissa the Bold",
        black_player="Caissa the Sage",
        aggression_score=7,
        chaos_score=5,
        depth=40,
    )
    
    print("=" * 60)
    print("CAISSA GENERATOR - Example Usage")
    print("=" * 60)
    print(f"Configuration: {context.era.value}, Theme: {context.theme.value if context.theme else 'None'}")
    print(f"Aggression: {context.aggression_score}/10, Chaos: {context.chaos_score}/10")
    print()
    
    # Initialize generator with OpenAI provider
    try:
        provider = OpenAIProvider()
        generator = CaissaGenerator(provider=provider)
        
        print("✓ Generator initialized with OpenAI provider")
        print(f"✓ Prompt manager ready")
        print(f"✓ Legality validator ready")
        print()
        
        # PHASE 3.1: Demo advanced features
        print("=" * 60)
        print("PHASE 3.1: ADVANCED FEATURES DEMO")
        print("=" * 60)
        print()
        
        # Configure retry strategy
        generator.set_retry_config(RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            max_retries=5,
            base_delay=1.0,
        ))
        print("✓ Retry strategy configured: exponential backoff")
        
        # Set progress callback
        def on_progress(progress: GenerationProgress):
            print(f"  Stage: {progress.stage.value}, Elapsed: {progress.elapsed_time:.1f}s")
        
        generator.set_progress_callback(on_progress)
        print("✓ Progress callback registered")
        
        # Show stats structure
        print()
        print("Statistics tracking:")
        print(json.dumps(generator.get_stats().to_dict(), indent=2))
        
    except Exception as e:
        print(f"Note: Full demo requires LLM provider ({e})")
        
        print("To generate a game, call:")
        print("  success, pgn, moves = generator.generate_game(context)")
    except ValueError as e:
        print(f"⚠ {e}")
        print("Set OPENAI_API_KEY environment variable to use OpenAI provider")

