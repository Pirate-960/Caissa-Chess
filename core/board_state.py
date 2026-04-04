"""Board state wrapper providing a clean interface over python-chess."""

from __future__ import annotations

import chess
import chess.pgn


class BoardState:
    """Immutable snapshot of a chess board state."""

    def __init__(self, board: chess.Board) -> None:
        self._board = board.copy()

    @property
    def fen(self) -> str:
        return self._board.fen()

    @property
    def turn_is_white(self) -> bool:
        return self._board.turn == chess.WHITE

    @property
    def is_check(self) -> bool:
        return self._board.is_check()

    @property
    def is_checkmate(self) -> bool:
        return self._board.is_checkmate()

    @property
    def is_stalemate(self) -> bool:
        return self._board.is_stalemate()

    @property
    def is_game_over(self) -> bool:
        return self._board.is_game_over()

    @property
    def legal_move_count(self) -> int:
        return self._board.legal_moves.count()

    @property
    def legal_moves(self) -> list[str]:
        return [self._board.san(m) for m in self._board.legal_moves]

    @property
    def move_stack(self) -> list[str]:
        board = chess.Board()
        result: list[str] = []
        for move in self._board.move_stack:
            result.append(board.san(move))
            board.push(move)
        return result

    @property
    def fullmove_number(self) -> int:
        return self._board.fullmove_number

    @property
    def halfmove_clock(self) -> int:
        return self._board.halfmove_clock

    @property
    def material_balance(self) -> int:
        """Positive = white advantage in centipawns (rough estimate)."""
        piece_values = {
            chess.PAWN: 100,
            chess.KNIGHT: 320,
            chess.BISHOP: 330,
            chess.ROOK: 500,
            chess.QUEEN: 900,
        }
        score = 0
        for piece_type, value in piece_values.items():
            score += value * len(self._board.pieces(piece_type, chess.WHITE))
            score -= value * len(self._board.pieces(piece_type, chess.BLACK))
        return score

    def copy(self) -> "BoardState":
        return BoardState(self._board)

    def __repr__(self) -> str:
        return f"BoardState(fen={self.fen!r})"
