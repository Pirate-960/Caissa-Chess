"""Beauty evaluation for chess positions and games."""

from __future__ import annotations

import math
from dataclasses import dataclass

import chess


@dataclass
class BeautyScore:
    """Composite beauty score for a chess game or position."""

    tactical_score: float = 0.0
    aesthetic_score: float = 0.0
    complexity_score: float = 0.0
    sacrifice_score: float = 0.0
    overall: float = 0.0

    def __post_init__(self) -> None:
        if self.overall == 0.0:
            self.overall = (
                0.3 * self.tactical_score
                + 0.3 * self.aesthetic_score
                + 0.2 * self.complexity_score
                + 0.2 * self.sacrifice_score
            )


class BeautyEvaluator:
    """Evaluates the aesthetic beauty of chess games and positions."""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or {
            "tactical": 0.3,
            "aesthetic": 0.3,
            "complexity": 0.2,
            "sacrifice": 0.2,
        }

    def evaluate_game(self, moves: list[str]) -> BeautyScore:
        """Evaluate the overall beauty of a game given its moves."""
        board = chess.Board()
        complexity_sum = 0.0
        sacrifice_sum = 0.0
        move_count = 0

        for san in moves:
            try:
                move = board.parse_san(san)
                complexity_sum += self._move_complexity(board, move)
                sacrifice_sum += self._sacrifice_value(board, move)
                board.push(move)
                move_count += 1
            except Exception:
                break

        complexity = complexity_sum / max(1, move_count)
        sacrifice = min(1.0, sacrifice_sum / max(1, move_count) * 10)
        tactical = self._tactical_density(moves)
        aesthetic = self._positional_harmony(board)

        overall = (
            self._weights["tactical"] * tactical
            + self._weights["aesthetic"] * aesthetic
            + self._weights["complexity"] * complexity
            + self._weights["sacrifice"] * sacrifice
        )
        return BeautyScore(
            tactical_score=tactical,
            aesthetic_score=aesthetic,
            complexity_score=complexity,
            sacrifice_score=sacrifice,
            overall=overall,
        )

    def evaluate_position(self, fen: str) -> BeautyScore:
        """Evaluate the aesthetic quality of a single position."""
        board = chess.Board(fen)
        legal_count = board.legal_moves.count()
        complexity = min(1.0, legal_count / 40.0)
        aesthetic = self._positional_harmony(board)
        return BeautyScore(
            tactical_score=0.0,
            aesthetic_score=aesthetic,
            complexity_score=complexity,
            sacrifice_score=0.0,
            overall=0.5 * aesthetic + 0.5 * complexity,
        )

    def _move_complexity(self, board: chess.Board, move: chess.Move) -> float:
        """Score how complex a move is (0-1)."""
        score = 0.0
        if board.is_capture(move):
            score += 0.4
        if board.gives_check(move):
            score += 0.3
        piece = board.piece_at(move.from_square)
        if piece and piece.piece_type in (chess.QUEEN, chess.ROOK):
            score += 0.1
        return min(1.0, score)

    def _sacrifice_value(self, board: chess.Board, move: chess.Move) -> float:
        """Detect material sacrifice."""
        if not board.is_capture(move):
            return 0.0
        piece_values = {
            chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
            chess.ROOK: 5, chess.QUEEN: 9,
        }
        attacker = board.piece_at(move.from_square)
        captured = board.piece_at(move.to_square)
        if not attacker or not captured:
            return 0.0
        loss = piece_values.get(attacker.piece_type, 0) - piece_values.get(captured.piece_type, 0)
        return max(0.0, loss / 9.0)

    def _tactical_density(self, moves: list[str]) -> float:
        """Estimate the tactical density of a game."""
        board = chess.Board()
        checks = captures = 0
        total = 0
        for san in moves:
            try:
                move = board.parse_san(san)
                if board.gives_check(move):
                    checks += 1
                if board.is_capture(move):
                    captures += 1
                board.push(move)
                total += 1
            except Exception:
                break
        if total == 0:
            return 0.0
        return min(1.0, (checks * 2 + captures) / total * 0.3)

    def _positional_harmony(self, board: chess.Board) -> float:
        """Score the harmony/activity of pieces."""
        total_attacks = 0
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece:
                total_attacks += len(board.attacks(sq))
        return min(1.0, total_attacks / 200.0)
