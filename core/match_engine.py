"""
Match Engine for CAISSA Chess v0.5.0

This module conducts single chess matches between two LLM players.
It handles move generation, validation, time tracking, and game termination.

Author: CAISSA Team
Version: 0.5.0
"""

import asyncio
import chess
import chess.pgn
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from io import StringIO
from typing import Optional, List, Tuple, Dict, Any, Callable

from core.tournament_player import TournamentPlayer, TimeControl, PERSONA_PROMPTS
from core.elo_calculator import GameResult, EloCalculator, EloChange
from core.llm_provider import LLMProvider
from engine.legality import LegalityValidator


logger = logging.getLogger(__name__)


class MoveOutcome(Enum):
    """Outcome of a single move attempt."""
    SUCCESS = "success"
    ILLEGAL = "illegal"
    PARSE_ERROR = "parse_error"
    TIMEOUT = "timeout"
    API_ERROR = "api_error"
    FORFEIT = "forfeit"


class TerminationReason(Enum):
    """Reason for game termination."""
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    INSUFFICIENT = "insufficient"
    FIFTY_MOVE = "fifty_move"
    THREEFOLD = "threefold"
    FIVEFOLD = "fivefold"
    RESIGNATION = "resignation"
    TIMEOUT = "timeout"
    FORFEIT = "forfeit"  # Exceeded illegal move limit
    AGREEMENT = "agreement"  # Draw by agreement
    MAX_MOVES = "max_moves"  # Hit move limit
    ADJUDICATION = "adjudication"  # Engine adjudication


@dataclass
class MoveRecord:
    """Record of a single move in the game."""
    move_number: int
    player: str  # Player ID
    color: str  # "white" or "black"
    san: str  # Standard algebraic notation
    uci: str  # Universal chess interface notation
    fen_before: str
    fen_after: str
    think_time: float  # Seconds
    attempt: int  # Which attempt (1 = first, 2 = retry, etc.)
    evaluation: Optional[float] = None  # Stockfish eval if available
    is_check: bool = False
    is_capture: bool = False
    is_promotion: bool = False
    commentary: Optional[str] = None


@dataclass
class MatchResult:
    """
    Complete result of a match between two players.
    
    Contains all information about the game including moves,
    timing, evaluation, and metadata.
    """
    match_id: str
    white: TournamentPlayer
    black: TournamentPlayer
    result: GameResult
    termination: TerminationReason
    
    # Game data
    moves: List[MoveRecord] = field(default_factory=list)
    pgn: str = ""
    final_fen: str = ""
    
    # Statistics
    total_moves: int = 0
    white_illegal_attempts: int = 0
    black_illegal_attempts: int = 0
    white_think_time: float = 0.0
    black_think_time: float = 0.0
    
    # Evaluation metrics (if Stockfish available)
    white_avg_centipawn_loss: float = 0.0
    black_avg_centipawn_loss: float = 0.0
    white_blunders: int = 0
    black_blunders: int = 0
    white_mistakes: int = 0
    black_mistakes: int = 0
    white_inaccuracies: int = 0
    black_inaccuracies: int = 0
    
    # Beauty score
    beauty_score: float = 0.0
    
    # Timing
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    # Commentary (if enabled)
    commentary: List[str] = field(default_factory=list)
    
    # ELO change
    elo_change: Optional[EloChange] = None
    
    # Metadata
    time_control: TimeControl = TimeControl.RAPID
    opening_name: str = ""
    eco_code: str = ""
    
    @property
    def duration(self) -> float:
        """Total game duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    @property
    def winner_name(self) -> Optional[str]:
        """Name of the winner, or None for draw."""
        if self.result == GameResult.WHITE_WINS:
            return self.white.name
        elif self.result == GameResult.BLACK_WINS:
            return self.black.name
        return None
    
    @property
    def is_decisive(self) -> bool:
        """True if game had a winner (not a draw)."""
        return self.result in (GameResult.WHITE_WINS, GameResult.BLACK_WINS)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "match_id": self.match_id,
            "white": self.white.to_dict(),
            "black": self.black.to_dict(),
            "result": self.result.value,
            "termination": self.termination.value,
            "pgn": self.pgn,
            "final_fen": self.final_fen,
            "total_moves": self.total_moves,
            "white_illegal_attempts": self.white_illegal_attempts,
            "black_illegal_attempts": self.black_illegal_attempts,
            "white_think_time": self.white_think_time,
            "black_think_time": self.black_think_time,
            "white_avg_centipawn_loss": self.white_avg_centipawn_loss,
            "black_avg_centipawn_loss": self.black_avg_centipawn_loss,
            "beauty_score": self.beauty_score,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "time_control": self.time_control.value,
            "opening_name": self.opening_name,
            "eco_code": self.eco_code,
            "elo_change": self.elo_change.summary if self.elo_change else None,
        }


class MatchEngine:
    """
    Conducts a single chess match between two LLM players.
    
    The match engine handles:
    - Move generation via LLM prompting
    - Move validation and parsing
    - Illegal move retry logic
    - Game termination detection
    - Time tracking
    - PGN generation
    - Optional commentary
    
    Example:
        ```python
        engine = MatchEngine(white_player, black_player)
        result = await engine.play_match()
        print(f"Result: {result.result.value}")
        print(result.pgn)
        ```
    """
    
    # Move extraction patterns (order matters - more specific first)
    MOVE_PATTERNS = [
        # Explicit move format: "My move is: e4" or "Move: Nf3"
        r"(?:my\s+)?move(?:\s+is)?[:\s]+([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)",
        # SAN at start of line
        r"^([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)\s*$",
        # SAN in response (last resort)
        r"([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?|O-O-O|O-O)",
    ]
    
    # Castling normalization
    CASTLING_PATTERNS = {
        r"[oO0]-[oO0]-[oO0]": "O-O-O",
        r"[oO0]-[oO0]": "O-O",
        r"0-0-0": "O-O-O",
        r"0-0": "O-O",
    }
    
    def __init__(
        self,
        white: TournamentPlayer,
        black: TournamentPlayer,
        time_control: TimeControl = TimeControl.RAPID,
        max_moves: int = 500,
        max_retries: int = 3,
        starting_fen: str = chess.STARTING_FEN,
        arbiter: Optional[LLMProvider] = None,
        on_move: Optional[Callable[[MoveRecord], None]] = None,
        stockfish_client: Optional[Any] = None,
        beauty_evaluator: Optional[Any] = None,
    ):
        """
        Initialize the match engine.
        
        Args:
            white: White player
            black: Black player
            time_control: Time control for the match
            max_moves: Maximum moves before draw adjudication
            max_retries: Max illegal move retries before forfeit
            starting_fen: Starting position (default: standard)
            arbiter: Optional LLM for commentary/adjudication
            on_move: Callback for each move (for live updates)
            stockfish_client: Optional Stockfish for evaluation
            beauty_evaluator: Optional beauty evaluator
        """
        self.white = white
        self.black = black
        self.time_control = time_control
        self.max_moves = max_moves
        self.max_retries = max_retries
        self.starting_fen = starting_fen
        self.arbiter = arbiter
        self.on_move = on_move
        self.stockfish_client = stockfish_client
        self.beauty_evaluator = beauty_evaluator
        
        # Game state
        self.board = chess.Board(starting_fen)
        self.move_history: List[MoveRecord] = []
        self.match_id = str(uuid.uuid4())[:8]
        
        # Tracking
        self.white_illegal_attempts = 0
        self.black_illegal_attempts = 0
        self.white_think_time = 0.0
        self.black_think_time = 0.0
        
        # Validation
        self.validator = LegalityValidator()
        
        # Commentary
        self.commentary: List[str] = []
        
        logger.info(f"Match initialized: {white.name} vs {black.name} (ID: {self.match_id})")
    
    async def play_match(self) -> MatchResult:
        """
        Play a complete match between the two players.
        
        Returns:
            MatchResult: Complete game result with all metadata
        """
        start_time = datetime.now()
        logger.info(f"[{self.match_id}] Starting match: {self.white.name} (White, {self.white.elo_rating}) vs {self.black.name} (Black, {self.black.elo_rating})")
        logger.info(f"[{self.match_id}] Time control: {self.time_control.name} ({self.time_control.value}s per move)")
        logger.info(f"[{self.match_id}] Max moves: {self.max_moves}, Max retries: {self.max_retries}")
        
        termination_reason = None
        game_result = GameResult.IN_PROGRESS
        
        try:
            while not self._is_game_over():
                # Determine current player
                current_player = self.white if self.board.turn == chess.WHITE else self.black
                color = "white" if self.board.turn == chess.WHITE else "black"
                move_number = self.board.fullmove_number
                
                logger.info(f"[{self.match_id}] Move {move_number} - {current_player.name} ({color}) to play")
                
                # Get move from player
                move_record = await self._get_player_move(current_player, color)
                
                if move_record is None:
                    # Player forfeited (exceeded retries)
                    if color == "white":
                        game_result = GameResult.BLACK_WINS
                    else:
                        game_result = GameResult.WHITE_WINS
                    termination_reason = TerminationReason.FORFEIT
                    logger.warning(f"[{self.match_id}] {current_player.name} forfeited due to {self.max_retries} failed move attempts")
                    logger.info(f"[{self.match_id}] Match ended by forfeit - {self.black.name if color == 'white' else self.white.name} wins")
                    break
                
                # Record the move
                self.move_history.append(move_record)
                
                # Update tracking
                if color == "white":
                    self.white_think_time += move_record.think_time
                else:
                    self.black_think_time += move_record.think_time
                
                # Log successful move with details
                logger.info(f"[{self.match_id}] Move {move_number}: {move_record.san} by {current_player.name} (think time: {move_record.think_time:.2f}s, attempt: {move_record.attempt})")
                logger.debug(
                    "[%s] Move record details: move=%d color=%s san=%s uci=%s attempt=%d think_time=%.2fs check=%s capture=%s promotion=%s eval=%s",
                    self.match_id,
                    move_record.move_number,
                    move_record.color,
                    move_record.san,
                    move_record.uci,
                    move_record.attempt,
                    move_record.think_time,
                    move_record.is_check,
                    move_record.is_capture,
                    move_record.is_promotion,
                    move_record.evaluation if move_record.evaluation is not None else "n/a",
                )
                if move_record.is_check:
                    logger.info(f"[{self.match_id}] ✓ Check!")
                if move_record.is_capture:
                    logger.debug(f"[{self.match_id}] Capture on {move_record.san}")
                if move_record.is_promotion:
                    logger.info(f"[{self.match_id}] Promotion: {move_record.san}")
                
                # Callback for live updates
                if self.on_move:
                    self.on_move(move_record)
                
                # Check move limit
                if len(self.move_history) >= self.max_moves * 2:
                    game_result = GameResult.DRAW
                    termination_reason = TerminationReason.MAX_MOVES
                    logger.info(f"[{self.match_id}] Match ended by move limit ({self.max_moves} moves)")
                    break
            
            # Determine final result if not already set
            if game_result == GameResult.IN_PROGRESS:
                game_result, termination_reason = self._determine_result()
                logger.info(f"[{self.match_id}] Game over: {termination_reason.value}")
        
        except Exception as e:
            logger.error(f"[{self.match_id}] Error during match: {e}", exc_info=True)
            game_result = GameResult.DRAW
            termination_reason = TerminationReason.ADJUDICATION
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Generate PGN
        pgn = self._generate_pgn(game_result, termination_reason)
        
        # Calculate ELO change
        elo_calc = EloCalculator()
        elo_change = elo_calc.calculate(
            self.white.elo_rating,
            self.black.elo_rating,
            game_result,
            self.white.stats.games_played,
            self.black.stats.games_played,
        )
        
        # Log final statistics
        logger.info(f"[{self.match_id}] ═══════════════════════════════════════════════════")
        logger.info(f"[{self.match_id}] Match completed: {game_result.value} ({termination_reason.value})")
        logger.info(f"[{self.match_id}] Duration: {duration:.1f}s | Total moves: {len(self.move_history)}")
        logger.info(f"[{self.match_id}] White ({self.white.name}) - Think time: {self.white_think_time:.1f}s, Illegal attempts: {self.white_illegal_attempts}")
        logger.info(f"[{self.match_id}] Black ({self.black.name}) - Think time: {self.black_think_time:.1f}s, Illegal attempts: {self.black_illegal_attempts}")
        if elo_change:
            logger.info(f"[{self.match_id}] ELO changes - White: {self.white.elo_rating} → {self.white.elo_rating + elo_change.white_delta} ({elo_change.white_delta:+d})")
            logger.info(f"[{self.match_id}] ELO changes - Black: {self.black.elo_rating} → {self.black.elo_rating + elo_change.black_delta} ({elo_change.black_delta:+d})")
        logger.info(f"[{self.match_id}] ═══════════════════════════════════════════════════")
        
        # Build result
        result = MatchResult(
            match_id=self.match_id,
            white=self.white,
            black=self.black,
            result=game_result,
            termination=termination_reason,
            moves=self.move_history,
            pgn=pgn,
            final_fen=self.board.fen(),
            total_moves=len(self.move_history),
            white_illegal_attempts=self.white_illegal_attempts,
            black_illegal_attempts=self.black_illegal_attempts,
            white_think_time=self.white_think_time,
            black_think_time=self.black_think_time,
            start_time=start_time,
            end_time=end_time,
            time_control=self.time_control,
            elo_change=elo_change,
            commentary=self.commentary,
        )
        
        return result
    
    async def _get_player_move(
        self,
        player: TournamentPlayer,
        color: str,
    ) -> Optional[MoveRecord]:
        """
        Get a valid move from a player.
        
        Handles retries for illegal moves up to max_retries.
        
        Args:
            player: The player to get move from
            color: "white" or "black"
        
        Returns:
            MoveRecord if valid move obtained, None if forfeited
        """
        move_number = self.board.fullmove_number
        fen_before = self.board.fen()
        
        logger.debug(f"[{self.match_id}] Getting move from {player.name} ({color}), move {move_number}")
        
        for attempt in range(1, self.max_retries + 1):
            start_time = time.time()
            
            try:
                # Build prompt
                prompt = self._build_move_prompt(player, is_retry=(attempt > 1))
                
                if attempt > 1:
                    logger.warning(f"[{self.match_id}] {player.name} retry attempt {attempt}/{self.max_retries} for move {move_number}")
                
                # Get response from LLM
                logger.debug(f"[{self.match_id}] Calling LLM for {player.name} (move {move_number}, attempt {attempt})")
                response = await self._call_llm(player, prompt)
                
                # Parse move from response
                parsed_move = self._parse_move_response(response)
                
                think_time = time.time() - start_time
                
                if parsed_move is None:
                    logger.warning(f"[{self.match_id}] {player.name} - Could not parse move from response (attempt {attempt}): {response[:100]}")
                    self._record_illegal_attempt(color)
                    continue
                
                # Validate move
                try:
                    move = self.board.parse_san(parsed_move)
                except ValueError:
                    logger.warning(f"[{self.match_id}] {player.name} - Invalid SAN notation: '{parsed_move}' (attempt {attempt})")
                    self._record_illegal_attempt(color)
                    continue
                
                if move not in self.board.legal_moves:
                    logger.warning(f"[{self.match_id}] {player.name} - Illegal move: '{parsed_move}' (attempt {attempt})")
                    logger.info(f"[{self.match_id}] 🚫 VALIDATION FAILED - Move '{parsed_move}' not in legal moves for {color}")
                    logger.debug(f"[{self.match_id}] Legal moves were: {[self.board.san(m) for m in list(self.board.legal_moves)[:10]]}")
                    self._record_illegal_attempt(color)
                    continue
                
                # Move is valid - apply it
                san = self.board.san(move)
                uci = move.uci()
                is_check = self.board.gives_check(move)
                is_capture = self.board.is_capture(move)
                is_promotion = move.promotion is not None
                
                logger.debug(f"[{self.match_id}] {player.name} - Valid move: {san} ({think_time:.2f}s, attempt {attempt})")
                logger.info(f"[{self.match_id}] ✅ VALIDATION PASSED - {player.name} ({color}) plays {san}")
                
                self.board.push(move)
                
                return MoveRecord(
                    move_number=move_number,
                    player=player.id,
                    color=color,
                    san=san,
                    uci=uci,
                    fen_before=fen_before,
                    fen_after=self.board.fen(),
                    think_time=think_time,
                    attempt=attempt,
                    is_check=is_check,
                    is_capture=is_capture,
                    is_promotion=is_promotion,
                )
            
            except asyncio.TimeoutError:
                think_time = time.time() - start_time
                logger.warning(f"[{self.match_id}] {player.name} timed out on move {move_number} (attempt {attempt}, {think_time:.1f}s)")
                logger.info(f"[{self.match_id}] Time control limit: {self.time_control.value}s, actual time: {think_time:.1f}s")
                self._record_illegal_attempt(color)
            
            except Exception as e:
                logger.error(f"[{self.match_id}] Error getting move from {player.name} (move {move_number}, attempt {attempt}): {e}", exc_info=True)
                self._record_illegal_attempt(color)
        
        # Exceeded max retries
        logger.error(f"[{self.match_id}] {player.name} exhausted all {self.max_retries} attempts for move {move_number} - forfeiting")
        return None
    
    def _build_move_prompt(
        self,
        player: TournamentPlayer,
        is_retry: bool = False,
    ) -> str:
        """
        Build the prompt for move generation.
        
        Args:
            player: The player to prompt
            is_retry: True if this is a retry after illegal move
        
        Returns:
            str: Complete prompt for the LLM
        """
        color = "White" if self.board.turn == chess.WHITE else "Black"
        move_number = self.board.fullmove_number
        
        # Build move history string
        history_lines = []
        for i, record in enumerate(self.move_history[-20:]):  # Last 20 moves for context
            if record.color == "white":
                history_lines.append(f"{record.move_number}. {record.san}")
            else:
                if history_lines:
                    history_lines[-1] += f" {record.san}"
                else:
                    history_lines.append(f"{record.move_number}... {record.san}")
        
        history = " ".join(history_lines) if history_lines else "(Game start)"
        
        # Legal moves
        legal_moves = [self.board.san(m) for m in self.board.legal_moves]
        legal_moves_str = ", ".join(sorted(legal_moves)[:30])  # Limit for context
        if len(legal_moves) > 30:
            legal_moves_str += f" ... ({len(legal_moves)} total)"
        
        # Persona
        persona_text = ""
        if player.persona_prompt:
            persona_text = f"\n\nPLAYING STYLE: {player.persona_prompt}"
        
        # Opponent info
        opponent = self.black if self.board.turn == chess.WHITE else self.white
        opponent_color = "Black" if self.board.turn == chess.WHITE else "White"
        
        # Build prompt
        prompt = f"""You are playing a chess game as {color}.

CURRENT POSITION (FEN): {self.board.fen()}

MOVE HISTORY: {history}

MOVE NUMBER: {move_number}
YOUR COLOR: {color}
OPPONENT: {opponent.name} ({opponent_color})

LEGAL MOVES: {legal_moves_str}
{persona_text}

{"IMPORTANT: Your previous move was ILLEGAL. Please carefully check the legal moves list and respond with a VALID move." if is_retry else ""}

Respond with ONLY your chosen move in standard algebraic notation (e.g., "e4", "Nf3", "Bxc6", "O-O", "e8=Q").
Do not include any explanation or commentary. Just the move."""
        
        return prompt
    
    async def _call_llm(self, player: TournamentPlayer, prompt: str) -> str:
        """
        Call the player's LLM with the prompt.
        
        Args:
            player: The player
            prompt: The prompt to send
        
        Returns:
            str: LLM response
        """
        if player.provider is None:
            raise ValueError(f"Player {player.name} has no provider configured")
        
        # Apply time limit based on time control
        timeout = self.time_control.value if self.time_control.value > 0 else 300
        
        # System prompt for chess move generation
        system_prompt = """You are a chess player. Respond with ONLY your move in standard algebraic notation.
Examples: e4, Nf3, Bxc6, O-O, e8=Q
No explanations, no commentary. Just the move."""
        
        provider_name = player.provider.__class__.__name__
        model_name = getattr(player.provider, 'model', 'Unknown')
        
        logger.debug(f"[{self.match_id}] LLM call: {player.name} using {provider_name}/{model_name} (timeout: {timeout}s)")
        
        call_start = time.time()
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    player.provider.generate,
                    system_prompt,
                    prompt,
                    player.temperature,
                ),
                timeout=timeout,
            )
            call_duration = time.time() - call_start
            logger.debug(f"[{self.match_id}] LLM response received from {player.name} in {call_duration:.2f}s: '{response[:50]}...'")
            return response
        except asyncio.TimeoutError:
            call_duration = time.time() - call_start
            logger.warning(f"[{self.match_id}] LLM call timed out for {player.name} after {call_duration:.1f}s (limit: {timeout}s)")
            raise
    
    def _parse_move_response(self, response: str) -> Optional[str]:
        """
        Extract a chess move from an LLM response.
        
        Handles various formats and normalizes castling notation.
        
        Args:
            response: Raw LLM response
        
        Returns:
            Optional[str]: Extracted move in SAN, or None
        """
        if not response:
            return None
        
        # Clean up response
        response = response.strip()
        
        # Normalize castling notation
        for pattern, replacement in self.CASTLING_PATTERNS.items():
            response = re.sub(pattern, replacement, response, flags=re.IGNORECASE)
        
        # Try each pattern
        for pattern in self.MOVE_PATTERNS:
            match = re.search(pattern, response, re.IGNORECASE | re.MULTILINE)
            if match:
                move = match.group(1).strip()
                # Validate basic structure
                if self._looks_like_move(move):
                    return move
        
        # Last resort: if response is very short, treat as move
        if len(response) <= 7 and self._looks_like_move(response):
            return response
        
        return None
    
    def _looks_like_move(self, text: str) -> bool:
        """Check if text looks like a valid move."""
        if not text:
            return False
        text = text.strip()
        # Castling
        if text in ("O-O", "O-O-O"):
            return True
        # Standard moves
        if re.match(r"^[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?[+#]?$", text):
            return True
        return False
    
    def _record_illegal_attempt(self, color: str):
        """Record an illegal move attempt."""
        if color == "white":
            self.white_illegal_attempts += 1
        else:
            self.black_illegal_attempts += 1
    
    def _is_game_over(self) -> bool:
        """Check if the game is over."""
        return self.board.is_game_over()
    
    def _determine_result(self) -> Tuple[GameResult, TerminationReason]:
        """Determine the game result based on board state."""
        if self.board.is_checkmate():
            if self.board.turn == chess.WHITE:
                return GameResult.BLACK_WINS, TerminationReason.CHECKMATE
            else:
                return GameResult.WHITE_WINS, TerminationReason.CHECKMATE
        
        if self.board.is_stalemate():
            return GameResult.DRAW, TerminationReason.STALEMATE
        
        if self.board.is_insufficient_material():
            return GameResult.DRAW, TerminationReason.INSUFFICIENT
        
        if self.board.is_fifty_moves():
            return GameResult.DRAW, TerminationReason.FIFTY_MOVE
        
        if self.board.is_repetition(3):
            return GameResult.DRAW, TerminationReason.THREEFOLD
        
        if self.board.is_fivefold_repetition():
            return GameResult.DRAW, TerminationReason.FIVEFOLD
        
        # Default to adjudication
        return GameResult.DRAW, TerminationReason.ADJUDICATION
    
    def _generate_pgn(
        self,
        result: GameResult,
        termination: TerminationReason,
    ) -> str:
        """Generate PGN for the game."""
        game = chess.pgn.Game()
        
        # Set headers
        game.headers["Event"] = "CAISSA LLM vs LLM Tournament"
        game.headers["Site"] = "CAISSA Engine"
        game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
        game.headers["Round"] = "1"
        game.headers["White"] = self.white.name
        game.headers["Black"] = self.black.name
        game.headers["Result"] = result.value
        game.headers["Termination"] = termination.value
        game.headers["TimeControl"] = self.time_control.name
        game.headers["WhiteElo"] = str(self.white.elo_rating)
        game.headers["BlackElo"] = str(self.black.elo_rating)
        
        if self.starting_fen != chess.STARTING_FEN:
            game.headers["FEN"] = self.starting_fen
            game.headers["SetUp"] = "1"
        
        # Add moves
        node = game
        board = chess.Board(self.starting_fen)
        for record in self.move_history:
            move = board.parse_san(record.san)
            node = node.add_variation(move)
            if record.commentary:
                node.comment = record.commentary
            board.push(move)
        
        # Generate PGN string
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True)
        return game.accept(exporter)
    
    @property
    def move_count(self) -> int:
        """Number of moves played."""
        return len(self.move_history)
    
    @property
    def current_turn(self) -> str:
        """Current side to move."""
        return "white" if self.board.turn == chess.WHITE else "black"


async def play_single_match(
    white: TournamentPlayer,
    black: TournamentPlayer,
    time_control: TimeControl = TimeControl.RAPID,
    max_moves: int = 500,
) -> MatchResult:
    """
    Convenience function to play a single match.
    
    Args:
        white: White player
        black: Black player
        time_control: Time control setting
        max_moves: Maximum moves before draw
    
    Returns:
        MatchResult: Complete game result
    """
    engine = MatchEngine(white, black, time_control, max_moves)
    return await engine.play_match()
