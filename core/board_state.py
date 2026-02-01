"""
core/board_state.py

Wrapper around python-chess Board with additional metadata and history tracking.
"""

import chess
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class MoveMetadata:
    """Metadata associated with a move."""
    move: chess.Move
    san: str
    position_before_fen: str
    position_after_fen: str
    is_capture: bool
    is_check: bool
    is_checkmate: bool
    is_sacrifice: bool = False
    evaluation_before: Optional[float] = None
    evaluation_after: Optional[float] = None


class BoardState:
    """
    Enhanced board state tracking.
    Keeps history of positions, evaluations, and metadata.
    """

    def __init__(self):
        self.board = chess.Board()
        self.move_history: List[MoveMetadata] = []

    def push_move(self, move: chess.Move, evaluation_before: Optional[float] = None) -> MoveMetadata:
        """
        Push a move onto the board and record metadata.
        """
        san = self.board.san(move)
        position_before = self.board.fen()
        
        self.board.push(move)
        
        position_after = self.board.fen()
        
        metadata = MoveMetadata(
            move=move,
            san=san,
            position_before_fen=position_before,
            position_after_fen=position_after,
            is_capture=self.board.is_capture(move),
            is_check=self.board.is_check(),
            is_checkmate=self.board.is_checkmate(),
            evaluation_before=evaluation_before,
        )
        
        self.move_history.append(metadata)
        return metadata

    def undo_move(self) -> Optional[MoveMetadata]:
        """Undo the last move."""
        if self.move_history:
            self.board.pop()
            return self.move_history.pop()
        return None

    def reset(self, fen: Optional[str] = None) -> None:
        """Reset the board."""
        if fen:
            self.board = chess.Board(fen)
        else:
            self.board = chess.Board()
        self.move_history = []

    def get_legal_moves_san(self) -> List[str]:
        """Get legal moves in SAN."""
        return [self.board.san(move) for move in self.board.legal_moves]

    def get_full_move_count(self) -> int:
        """Get the full move number (1-indexed)."""
        return self.board.fullmove_number

    def is_game_over(self) -> bool:
        """Is the game in a terminal state?"""
        return self.board.is_game_over()

    def get_game_result(self) -> str:
        """Get the game outcome."""
        if self.board.is_checkmate():
            return "CHECKMATE"
        elif self.board.is_stalemate():
            return "STALEMATE"
        elif self.board.is_insufficient_material():
            return "INSUFFICIENT_MATERIAL"
        else:
            return "ONGOING"
