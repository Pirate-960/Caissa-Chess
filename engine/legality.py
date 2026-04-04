"""Move legality validation using python-chess."""

from __future__ import annotations

import logging

import chess

logger = logging.getLogger(__name__)


class LegalityValidator:
    """Validates chess move legality."""

    def __init__(self) -> None:
        self._board: chess.Board | None = None

    def set_position(self, fen: str) -> None:
        """Set the board position from a FEN string."""
        self._board = chess.Board(fen)

    def is_legal(self, move_san: str, fen: str | None = None) -> bool:
        """Return True if the move is legal in the current (or given) position."""
        board = chess.Board(fen) if fen else self._board
        if board is None:
            raise RuntimeError("No position set. Call set_position() first or pass a FEN.")
        try:
            move = board.parse_san(move_san)
            return move in board.legal_moves
        except Exception:
            return False

    def get_legal_moves(self, fen: str | None = None) -> list[str]:
        """Return all legal moves in SAN notation."""
        board = chess.Board(fen) if fen else self._board
        if board is None:
            raise RuntimeError("No position set.")
        return [board.san(m) for m in board.legal_moves]

    def parse_move(self, text: str, fen: str | None = None) -> str | None:
        """Extract the first legal move from arbitrary text."""
        board = chess.Board(fen) if fen else self._board
        if board is None:
            raise RuntimeError("No position set.")
        for token in text.split():
            token = token.strip(".,!?;:()")
            try:
                move = board.parse_san(token)
                if move in board.legal_moves:
                    return board.san(move)
            except Exception:
                continue
        return None

    def validate_move_sequence(self, moves: list[str], start_fen: str | None = None) -> tuple[bool, int]:
        """Validate a sequence of moves. Returns (all_valid, first_invalid_index)."""
        board = chess.Board(start_fen) if start_fen else chess.Board()
        for i, san in enumerate(moves):
            try:
                move = board.parse_san(san)
                if move not in board.legal_moves:
                    return False, i
                board.push(move)
            except Exception:
                return False, i
        return True, len(moves)
