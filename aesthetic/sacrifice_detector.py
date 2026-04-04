"""Sacrifice detection in chess games."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import chess

logger = logging.getLogger(__name__)


@dataclass
class Sacrifice:
    """A detected sacrifice."""

    move_number: int
    san: str
    color: str
    material_lost: int
    sacrifice_type: str
    description: str


PIECE_VALUES: dict[int, int] = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


class SacrificeDetector:
    """Detects sacrifices in chess games."""

    def __init__(self, threshold: int = 1) -> None:
        """threshold: minimum material loss to consider it a sacrifice."""
        self._threshold = threshold

    def detect_in_game(self, moves: list[str]) -> list[Sacrifice]:
        """Detect all sacrifices in a game given its SAN move list."""
        board = chess.Board()
        sacrifices: list[Sacrifice] = []

        for i, san in enumerate(moves):
            try:
                move = board.parse_san(san)
                sacrifice = self._check_move(board, move, i + 1)
                if sacrifice:
                    sacrifices.append(sacrifice)
                board.push(move)
            except Exception:
                continue
        return sacrifices

    def _check_move(
        self, board: chess.Board, move: chess.Move, move_number: int
    ) -> Sacrifice | None:
        if not board.is_capture(move):
            return None
        attacker = board.piece_at(move.from_square)
        captured = board.piece_at(move.to_square)
        if not attacker or not captured:
            return None

        attacker_val = PIECE_VALUES.get(attacker.piece_type, 0)
        captured_val = PIECE_VALUES.get(captured.piece_type, 0)
        material_lost = attacker_val - captured_val

        if material_lost < self._threshold:
            return None

        color = "White" if attacker.color == chess.WHITE else "Black"
        sacrifice_type = self._classify(attacker, captured, board, move)
        san = board.san(move)

        return Sacrifice(
            move_number=move_number,
            san=san,
            color=color,
            material_lost=material_lost,
            sacrifice_type=sacrifice_type,
            description=f"{color} sacrifices a {chess.piece_name(attacker.piece_type)} for a {chess.piece_name(captured.piece_type)}",
        )

    def _classify(
        self,
        attacker: chess.Piece,
        captured: chess.Piece,
        board: chess.Board,
        move: chess.Move,
    ) -> str:
        if attacker.piece_type == chess.QUEEN:
            return "queen_sacrifice"
        if attacker.piece_type == chess.ROOK:
            return "rook_sacrifice"
        if board.gives_check(move):
            return "check_sacrifice"
        return "positional_sacrifice"
