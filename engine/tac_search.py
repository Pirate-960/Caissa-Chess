"""Tactical search engine for finding combinations and sacrifices."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import chess

logger = logging.getLogger(__name__)


@dataclass
class TacticalMotive:
    """A detected tactical motive."""

    motive_type: str
    moves: list[str]
    description: str
    score: float = 0.0


class TacticalSearchEngine:
    """Searches for tactical motives in chess positions."""

    TACTICAL_MOTIVES = [
        "fork", "pin", "skewer", "discovered_attack", "double_check",
        "back_rank_mate", "smothered_mate", "sacrifice",
    ]

    def __init__(self, depth: int = 3) -> None:
        self._depth = depth

    def find_tactics(self, fen: str) -> list[TacticalMotive]:
        """Find tactical motives in the given position."""
        board = chess.Board(fen)
        motives: list[TacticalMotive] = []
        motives.extend(self._find_forks(board))
        motives.extend(self._find_checks(board))
        motives.extend(self._find_captures(board))
        return motives

    def _find_forks(self, board: chess.Board) -> list[TacticalMotive]:
        """Find knight/pawn forks."""
        motives: list[TacticalMotive] = []
        for move in board.legal_moves:
            piece = board.piece_at(move.from_square)
            if piece and piece.piece_type == chess.KNIGHT:
                board.push(move)
                attacked = 0
                for sq in chess.SQUARES:
                    p = board.piece_at(sq)
                    if p and p.color != piece.color:
                        if board.is_attacked_by(piece.color, sq):
                            attacked += 1
                board.pop()
                if attacked >= 2:
                    motives.append(TacticalMotive(
                        motive_type="fork",
                        moves=[board.san(move)],
                        description=f"Knight fork attacking {attacked} pieces",
                        score=0.7,
                    ))
        return motives

    def _find_checks(self, board: chess.Board) -> list[TacticalMotive]:
        """Find check-giving moves."""
        motives: list[TacticalMotive] = []
        for move in board.legal_moves:
            if board.gives_check(move):
                board.push(move)
                is_mate = board.is_checkmate()
                board.pop()
                if is_mate:
                    motives.append(TacticalMotive(
                        motive_type="checkmate",
                        moves=[board.san(move)],
                        description="Checkmate in one",
                        score=1.0,
                    ))
        return motives

    def _find_captures(self, board: chess.Board) -> list[TacticalMotive]:
        """Find winning captures."""
        motives: list[TacticalMotive] = []
        piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
                        chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}
        for move in board.legal_moves:
            if board.is_capture(move):
                captured = board.piece_at(move.to_square)
                attacker = board.piece_at(move.from_square)
                if captured and attacker:
                    gain = piece_values.get(captured.piece_type, 0) - piece_values.get(attacker.piece_type, 0)
                    if gain > 0:
                        motives.append(TacticalMotive(
                            motive_type="winning_capture",
                            moves=[board.san(move)],
                            description=f"Winning capture gaining ~{gain} material",
                            score=min(1.0, gain / 8.0),
                        ))
        return motives

    def score_position_tactically(self, fen: str) -> float:
        """Return a tactical richness score between 0 and 1."""
        motives = self.find_tactics(fen)
        if not motives:
            return 0.0
        return min(1.0, sum(m.score for m in motives) / max(1, len(motives)))
