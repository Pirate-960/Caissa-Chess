"""
Live Commentary System for CAISSA Chess v0.5.0

This module provides real-time AI-powered commentary for chess matches.
A third LLM watches the game and provides analysis, narration, and insights.

Author: CAISSA Team
Version: 0.5.0
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
import chess

from core.llm_provider import LLMProvider
from core.match_engine import MoveRecord


logger = logging.getLogger(__name__)


class CommentaryStyle(Enum):
    """
    Commentary style presets.
    
    Each style produces different tone and focus in the commentary.
    """
    GRANDMASTER = "grandmaster"       # Technical, analytical
    ENTERTAINING = "entertaining"     # Casual, accessible
    DRAMATIC = "dramatic"             # High tension, storytelling
    EDUCATIONAL = "educational"       # Explain concepts for beginners
    CONCISE = "concise"               # Brief, to-the-point
    VERBOSE = "verbose"               # Detailed analysis
    HUMOROUS = "humorous"             # Light-hearted, jokes
    POETIC = "poetic"                 # Literary, metaphorical


# Style-specific prompt modifiers
STYLE_PROMPTS: Dict[CommentaryStyle, str] = {
    CommentaryStyle.GRANDMASTER: (
        "You are a chess grandmaster providing expert analysis. "
        "Focus on strategic concepts, tactical patterns, and professional-level insights. "
        "Reference similar positions from famous games when relevant."
    ),
    CommentaryStyle.ENTERTAINING: (
        "You are a fun and engaging chess commentator like a sports broadcaster. "
        "Keep the energy up, use exclamations, and make the game exciting for casual viewers. "
        "Avoid overly technical jargon."
    ),
    CommentaryStyle.DRAMATIC: (
        "You are a dramatic chess narrator building tension and excitement. "
        "Treat each move as part of an epic battle. Use vivid imagery and suspense. "
        "Build narrative arcs and highlight turning points."
    ),
    CommentaryStyle.EDUCATIONAL: (
        "You are a patient chess teacher explaining the game to beginners. "
        "Explain why moves are good or bad in simple terms. "
        "Define any chess terms you use. Focus on learning value."
    ),
    CommentaryStyle.CONCISE: (
        "Be extremely brief. One short sentence per move maximum. "
        "Only mention the most important aspects. Skip routine moves."
    ),
    CommentaryStyle.VERBOSE: (
        "Provide comprehensive analysis of each move. "
        "Discuss multiple candidate moves, variations, and plans. "
        "No detail is too small if it adds to understanding."
    ),
    CommentaryStyle.HUMOROUS: (
        "You are a witty chess commentator who uses humor and jokes. "
        "Make puns about chess, playfully mock questionable moves, "
        "and keep the atmosphere light and fun."
    ),
    CommentaryStyle.POETIC: (
        "You are a literary chess commentator who writes in a poetic style. "
        "Use metaphors, similes, and beautiful language to describe the game. "
        "Treat the chess board as a canvas and the game as art."
    ),
}


@dataclass
class CriticalMoment:
    """
    A critical moment in the game worth highlighting.
    """
    move_number: int
    move_san: str
    moment_type: str  # "blunder", "brilliancy", "turning_point", "missed_win", etc.
    eval_before: float
    eval_after: float
    eval_swing: float
    description: str
    alternative_moves: List[str] = field(default_factory=list)


@dataclass
class PositionAnalysis:
    """
    Analysis of a chess position.
    """
    fen: str
    evaluation: Optional[float]
    best_moves: List[str]
    themes: List[str]  # "open file", "weak squares", "king safety", etc.
    white_advantages: List[str]
    black_advantages: List[str]
    tension_level: float  # 0-10 scale
    complexity: float  # 0-10 scale


@dataclass
class GameSummary:
    """
    Summary of a completed game.
    """
    opening_name: str
    opening_assessment: str
    middlegame_themes: List[str]
    turning_point: Optional[CriticalMoment]
    key_moments: List[CriticalMoment]
    decisive_factor: str
    winner_played_well: str
    loser_could_improve: str
    beauty_highlights: List[str]
    lessons: List[str]
    overall_narrative: str


class LiveCommentator:
    """
    AI-powered live commentary system for chess matches.
    
    Features:
    - Move-by-move analysis and commentary
    - Critical moment detection
    - Style-based narration (GM, dramatic, educational, etc.)
    - Position evaluation integration
    - Game summaries and highlights
    - Prediction and anticipation
    
    Example:
        ```python
        commentator = LiveCommentator(
            provider=claude_provider,
            style=CommentaryStyle.DRAMATIC,
        )
        
        for move in game_moves:
            comment = await commentator.comment_on_move(board, move)
            print(comment)
        
        summary = await commentator.generate_game_summary(match_result)
        ```
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        style: CommentaryStyle = CommentaryStyle.GRANDMASTER,
        temperature: float = 0.7,
        stockfish_client: Optional[Any] = None,
        comment_every_n_moves: int = 1,
        critical_threshold: float = 1.5,  # Centipawn threshold for critical moments
    ):
        """
        Initialize the commentator.
        
        Args:
            provider: LLM provider for generating commentary
            style: Commentary style preset
            temperature: Generation temperature
            stockfish_client: Optional Stockfish for position evaluation
            comment_every_n_moves: Only comment every N moves (1 = every move)
            critical_threshold: Eval swing threshold for critical moments
        """
        self.provider = provider
        self.style = style
        self.temperature = temperature
        self.stockfish_client = stockfish_client
        self.comment_every_n_moves = comment_every_n_moves
        self.critical_threshold = critical_threshold
        
        # Game state
        self.move_comments: List[str] = []
        self.critical_moments: List[CriticalMoment] = []
        self.predictions: List[Dict[str, Any]] = []
        self.eval_history: List[float] = []
        
        # Context tracking
        self.white_name: str = ""
        self.black_name: str = ""
        self.game_context: Dict[str, Any] = {}
        
        logger.info(f"Commentator initialized with style: {style.value}")
    
    def set_players(self, white_name: str, black_name: str):
        """Set the player names for personalized commentary."""
        self.white_name = white_name
        self.black_name = black_name
    
    def reset(self):
        """Reset state for a new game."""
        self.move_comments = []
        self.critical_moments = []
        self.predictions = []
        self.eval_history = []
        self.game_context = {}
    
    async def comment_on_move(
        self,
        board: chess.Board,
        move: chess.Move,
        move_record: Optional[MoveRecord] = None,
        eval_before: Optional[float] = None,
        eval_after: Optional[float] = None,
    ) -> str:
        """
        Generate commentary for a single move.
        
        Args:
            board: Board state AFTER the move
            move: The move that was played
            move_record: Optional detailed move record
            eval_before: Position evaluation before move
            eval_after: Position evaluation after move
        
        Returns:
            str: Commentary for the move
        """
        move_num = board.fullmove_number
        san = board.san(move) if move in board.legal_moves else str(move)
        
        # Build the commentary prompt
        prompt = self._build_move_prompt(
            board, move, san, move_num,
            eval_before, eval_after, move_record,
        )
        
        try:
            comment = await self._generate(prompt)
            self.move_comments.append(comment)
            
            # Detect critical moments
            if eval_before is not None and eval_after is not None:
                swing = abs(eval_after - eval_before)
                if swing >= self.critical_threshold:
                    moment = CriticalMoment(
                        move_number=move_num,
                        move_san=san,
                        moment_type=self._classify_moment(eval_before, eval_after),
                        eval_before=eval_before,
                        eval_after=eval_after,
                        eval_swing=swing,
                        description=comment,
                    )
                    self.critical_moments.append(moment)
            
            return comment
        
        except Exception as e:
            logger.error(f"Commentary generation failed: {e}")
            return ""
    
    def _build_move_prompt(
        self,
        board: chess.Board,
        move: chess.Move,
        san: str,
        move_num: int,
        eval_before: Optional[float],
        eval_after: Optional[float],
        move_record: Optional[MoveRecord],
    ) -> str:
        """Build the prompt for move commentary."""
        
        # Determine who moved
        # After the move, it's the other player's turn
        color_moved = "Black" if board.turn == chess.WHITE else "White"
        player_moved = self.white_name if color_moved == "White" else self.black_name
        
        # Format move string
        move_str = f"{move_num}{'.' if color_moved == 'White' else '...'} {san}"
        
        # Evaluation string
        eval_str = ""
        if eval_before is not None and eval_after is not None:
            swing = eval_after - eval_before
            swing_str = f"+{swing:.2f}" if swing > 0 else f"{swing:.2f}"
            eval_str = f"\nEVALUATION: {eval_before:.2f} → {eval_after:.2f} (swing: {swing_str})"
        
        # Move characteristics
        characteristics = []
        if move_record:
            if move_record.is_check:
                characteristics.append("CHECK")
            if move_record.is_capture:
                characteristics.append("CAPTURE")
            if move_record.is_promotion:
                characteristics.append("PROMOTION")
        
        char_str = f"\nMOVE TYPE: {', '.join(characteristics)}" if characteristics else ""
        
        # Context from previous comments
        recent_context = ""
        if len(self.move_comments) >= 2:
            recent_context = f"\nRECENT COMMENTARY:\n- {self.move_comments[-2]}\n- {self.move_comments[-1]}"
        
        # Build full prompt
        prompt = f"""{STYLE_PROMPTS.get(self.style, '')}

GAME: {self.white_name or 'White'} vs {self.black_name or 'Black'}
MOVE PLAYED: {move_str} by {player_moved}
POSITION (FEN): {board.fen()}{eval_str}{char_str}{recent_context}

Generate commentary for this move. Be {self.style.value} in your delivery.
Keep your response to 1-3 sentences unless this is a critical moment."""

        return prompt
    
    def _classify_moment(
        self,
        eval_before: float,
        eval_after: float,
    ) -> str:
        """Classify the type of critical moment based on evaluation swing."""
        swing = eval_after - eval_before
        
        # Large negative swing = blunder by the player who just moved
        if swing <= -2.0:
            return "blunder"
        elif swing <= -1.0:
            return "mistake"
        elif swing <= -0.5:
            return "inaccuracy"
        
        # Large positive swing = brilliancy or opponent's blunder
        if swing >= 2.0:
            return "brilliancy"
        elif swing >= 1.0:
            return "strong_move"
        
        return "turning_point"
    
    async def detect_critical_moment(
        self,
        board: chess.Board,
        eval_before: float,
        eval_after: float,
    ) -> bool:
        """
        Detect if the current position represents a critical moment.
        
        Args:
            board: Current board position
            eval_before: Evaluation before last move
            eval_after: Evaluation after last move
        
        Returns:
            bool: True if this is a critical moment
        """
        swing = abs(eval_after - eval_before)
        return swing >= self.critical_threshold
    
    async def generate_halftime_report(
        self,
        board: chess.Board,
        moves: List[MoveRecord],
    ) -> str:
        """
        Generate a mid-game summary report.
        
        Args:
            board: Current position
            moves: Moves played so far
        
        Returns:
            str: Halftime report
        """
        move_count = len(moves)
        
        prompt = f"""{STYLE_PROMPTS.get(self.style, '')}

HALFTIME REPORT - Move {move_count}

GAME: {self.white_name} vs {self.black_name}
CURRENT POSITION (FEN): {board.fen()}

GAME SO FAR:
{self._format_move_history(moves)}

CRITICAL MOMENTS SO FAR:
{self._format_critical_moments()}

Generate a halftime report covering:
1. How the opening went for each player
2. Key moments so far
3. Current assessment - who stands better and why
4. What to watch for in the remainder of the game

Be {self.style.value} in your delivery. Keep to 4-6 sentences."""

        return await self._generate(prompt)
    
    async def generate_game_summary(
        self,
        result: str,
        moves: List[MoveRecord],
        final_position: chess.Board,
    ) -> str:
        """
        Generate a complete game summary.
        
        Args:
            result: Game result (e.g., "1-0", "0-1", "1/2-1/2")
            moves: All moves played
            final_position: Final board position
        
        Returns:
            str: Complete game summary
        """
        prompt = f"""{STYLE_PROMPTS.get(self.style, '')}

POST-GAME SUMMARY

GAME: {self.white_name} vs {self.black_name}
RESULT: {result}
TOTAL MOVES: {len(moves)}
FINAL POSITION (FEN): {final_position.fen()}

GAME MOVES:
{self._format_move_history(moves)}

CRITICAL MOMENTS:
{self._format_critical_moments()}

Generate a complete game summary covering:
1. Opening - what was played and how it went
2. Middlegame - key strategic and tactical battles
3. Turning point - when did the game's direction become clear?
4. Endgame (if applicable) - how was the win converted or draw achieved
5. What each player did well and could improve
6. Key takeaways and lessons from this game

Be {self.style.value} in your delivery. This is the final word on the game."""

        return await self._generate(prompt)
    
    async def predict_next_moves(
        self,
        board: chess.Board,
        num_predictions: int = 3,
    ) -> List[str]:
        """
        Predict likely next moves.
        
        Args:
            board: Current position
            num_predictions: Number of moves to predict
        
        Returns:
            List[str]: Predicted moves in SAN notation
        """
        legal_moves = [board.san(m) for m in board.legal_moves]
        
        prompt = f"""You are predicting chess moves.

POSITION (FEN): {board.fen()}
SIDE TO MOVE: {"White" if board.turn else "Black"}
LEGAL MOVES: {', '.join(legal_moves[:20])}{'...' if len(legal_moves) > 20 else ''}

Predict the {num_predictions} most likely moves in this position.
Return only the moves separated by commas, nothing else.
Example: e4, Nf3, d4"""

        try:
            response = await self._generate(prompt)
            predictions = [m.strip() for m in response.split(",")]
            return predictions[:num_predictions]
        except Exception:
            return []
    
    async def compare_players(
        self,
        moves: List[MoveRecord],
        white_stats: Dict[str, Any],
        black_stats: Dict[str, Any],
    ) -> str:
        """
        Generate a comparative analysis of both players.
        
        Args:
            moves: All moves played
            white_stats: White's performance stats
            black_stats: Black's performance stats
        
        Returns:
            str: Comparative analysis
        """
        prompt = f"""{STYLE_PROMPTS.get(self.style, '')}

PLAYER COMPARISON

WHITE: {self.white_name}
- Think time: {white_stats.get('think_time', 0):.1f}s total
- Illegal attempts: {white_stats.get('illegal_attempts', 0)}
- Avg centipawn loss: {white_stats.get('acpl', 0):.1f}

BLACK: {self.black_name}
- Think time: {black_stats.get('think_time', 0):.1f}s total
- Illegal attempts: {black_stats.get('illegal_attempts', 0)}
- Avg centipawn loss: {black_stats.get('acpl', 0):.1f}

Compare these two players based on their performance in this game.
Discuss playing style differences, strengths, and weaknesses.
Be {self.style.value} in your delivery."""

        return await self._generate(prompt)
    
    def _format_move_history(self, moves: List[MoveRecord]) -> str:
        """Format move history for prompts."""
        lines = []
        for i, move in enumerate(moves):
            if move.color == "white":
                lines.append(f"{move.move_number}. {move.san}")
            else:
                if lines:
                    lines[-1] += f" {move.san}"
                else:
                    lines.append(f"{move.move_number}... {move.san}")
        return " ".join(lines) if lines else "(No moves yet)"
    
    def _format_critical_moments(self) -> str:
        """Format critical moments for prompts."""
        if not self.critical_moments:
            return "(No critical moments detected yet)"
        
        lines = []
        for cm in self.critical_moments[-5:]:  # Last 5
            lines.append(
                f"- Move {cm.move_number}: {cm.move_san} ({cm.moment_type}) "
                f"Swing: {cm.eval_swing:+.2f}"
            )
        return "\n".join(lines)
    
    async def _generate(self, prompt: str) -> str:
        """Generate text from the LLM."""
        if self.provider is None:
            raise ValueError("No provider configured for commentary")
        
        response = self.provider.generate(
            system_prompt=f"You are a chess commentator with a {self.style.value} style.",
            user_prompt=prompt,
            temperature=self.temperature,
        )
        return response.strip()
    
    def get_commentary_transcript(self) -> str:
        """Get full transcript of all commentary."""
        return "\n\n".join(self.move_comments)
    
    def get_critical_moments_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all critical moments."""
        return [
            {
                "move_number": cm.move_number,
                "move": cm.move_san,
                "type": cm.moment_type,
                "swing": cm.eval_swing,
                "description": cm.description,
            }
            for cm in self.critical_moments
        ]


class MultiCommentatorPanel:
    """
    Panel of multiple commentators with different styles.
    
    Creates a broadcast-style experience with different perspectives.
    """
    
    def __init__(
        self,
        commentators: List[LiveCommentator],
        moderator: Optional[LiveCommentator] = None,
    ):
        """
        Initialize the panel.
        
        Args:
            commentators: List of commentators with different styles
            moderator: Optional moderator to synthesize views
        """
        self.commentators = commentators
        self.moderator = moderator
    
    async def panel_discussion(
        self,
        board: chess.Board,
        move: chess.Move,
        move_record: Optional[MoveRecord] = None,
    ) -> Dict[str, str]:
        """
        Get commentary from all panel members.
        
        Returns:
            Dict mapping commentator style to their comment
        """
        comments = {}
        
        for commentator in self.commentators:
            comment = await commentator.comment_on_move(board, move, move_record)
            comments[commentator.style.value] = comment
        
        if self.moderator:
            # Moderator synthesizes all views
            synthesis_prompt = f"""As the panel moderator, synthesize these different perspectives:

{chr(10).join(f'- {style}: {comment}' for style, comment in comments.items())}

Provide a balanced summary of the panel's views on this move."""
            
            comments["moderator"] = await self.moderator._generate(synthesis_prompt)
        
        return comments


async def create_commentator(
    provider: LLMProvider,
    style: str = "grandmaster",
) -> LiveCommentator:
    """
    Factory function to create a commentator.
    
    Args:
        provider: LLM provider
        style: Style name (e.g., "grandmaster", "dramatic", "educational")
    
    Returns:
        LiveCommentator: Configured commentator
    """
    try:
        style_enum = CommentaryStyle(style)
    except ValueError:
        style_enum = CommentaryStyle.GRANDMASTER
    
    return LiveCommentator(provider=provider, style=style_enum)
