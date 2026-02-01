"""
aesthetic/beauty_eval.py

The Beauty Score Algorithm: Mathematical evaluation of game aesthetics.

Formula:
    Beauty = (Sacrifices × 3) + (Tension × 2) + (Quiet Moves × 4) - (Draws × 5)
"""

import chess
from typing import List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class MoveBeautyType(str, Enum):
    """Classification of moves by aesthetic quality."""
    BRILLIANT_SACRIFICE = "brilliant_sacrifice"
    QUIET_KILLER = "quiet_killer"
    FORCING_MOVE = "forcing_move"
    POSITIONAL_SQUEEZE = "positional_squeeze"
    BORING = "boring"
    BLUNDER = "blunder"


@dataclass
class BeautyMetrics:
    """Breakdown of beauty score components."""
    sacrifice_score: float = 0.0
    tension_score: float = 0.0
    quiet_move_score: float = 0.0
    forcing_move_score: float = 0.0
    drama_penalty: float = 0.0
    total_score: float = 0.0


class BeautyEvaluator:
    """
    Evaluates the aesthetic beauty of chess moves and games.
    """

    SACRIFICE_BONUS = 15.0
    QUIET_KILLER_BONUS = 20.0
    FORCING_MOVE_BONUS = 5.0
    TENSION_MULTIPLIER = 0.5
    DRAW_PENALTY = 5.0

    def __init__(self):
        pass

    def evaluate_move(
        self,
        board: chess.Board,
        move: chess.Move,
        eval_before: Optional[float] = None,
        eval_after: Optional[float] = None,
    ) -> Tuple[float, MoveBeautyType]:
        """
        Evaluate a single move's beauty.
        
        Args:
            board: Board state before the move
            move: The move to evaluate
            eval_before: Engine evaluation before move (centipawns)
            eval_after: Engine evaluation after move (centipawns)
        
        Returns:
            (beauty_score, move_type)
        """
        beauty = 0.0
        move_type = MoveBeautyType.BORING
        
        # 1. SACRIFICE DETECTION
        if self._is_material_sacrifice(board, move, eval_before, eval_after):
            beauty += self.SACRIFICE_BONUS
            move_type = MoveBeautyType.BRILLIANT_SACRIFICE
        
        # 2. QUIET KILLER MOVE
        # Non-capturing, non-checking move in a sharp position with a forcing follow-up
        if (not board.is_capture(move) and 
            not board.gives_check(move) and
            self._is_position_sharp(board)):
            if self._has_forcing_continuation(board, move):
                beauty += self.QUIET_KILLER_BONUS
                move_type = MoveBeautyType.QUIET_KILLER
        
        # 3. FORCING MOVES (checks, captures in sharp positions)
        if board.gives_check(move):
            beauty += self.FORCING_MOVE_BONUS
            if move_type == MoveBeautyType.BORING:
                move_type = MoveBeautyType.FORCING_MOVE
        
        # 4. POSITIONAL SQUEEZE
        # Move that doesn't immediately win material but restricts opponent
        if self._is_positional_squeeze(board, move):
            beauty += 8.0
            if move_type == MoveBeautyType.BORING:
                move_type = MoveBeautyType.POSITIONAL_SQUEEZE
        
        # 5. TENSION BONUS
        tension = self._count_tension(board)
        beauty += tension * self.TENSION_MULTIPLIER
        
        # Negative beauty for blunders
        if eval_before and eval_after:
            eval_drop = eval_before - eval_after
            if eval_drop > 200:  # Drops by more than 2 pawns
                beauty = -10.0
                move_type = MoveBeautyType.BLUNDER
        
        return max(0.0, beauty), move_type

    def evaluate_game(
        self,
        moves: List[chess.Move],
        evaluations: Optional[List[Tuple[float, float]]] = None,  # (before, after)
    ) -> BeautyMetrics:
        """
        Evaluate the overall beauty of a game.
        
        Args:
            moves: List of moves in the game
            evaluations: Optional list of (eval_before, eval_after) tuples
        
        Returns:
            BeautyMetrics with total score
        """
        board = chess.Board()
        metrics = BeautyMetrics()
        
        for i, move in enumerate(moves):
            eval_before = evaluations[i][0] if evaluations else None
            eval_after = evaluations[i][1] if evaluations else None
            
            score, move_type = self.evaluate_move(
                board, move, eval_before, eval_after
            )
            
            if move_type == MoveBeautyType.BRILLIANT_SACRIFICE:
                metrics.sacrifice_score += score
            elif move_type == MoveBeautyType.QUIET_KILLER:
                metrics.quiet_move_score += score
            elif move_type == MoveBeautyType.FORCING_MOVE:
                metrics.forcing_move_score += score
            elif move_type == MoveBeautyType.POSITIONAL_SQUEEZE:
                metrics.tension_score += score
            
            board.push(move)
        
        # Cap and normalize
        metrics.total_score = min(
            metrics.sacrifice_score +
            metrics.tension_score +
            metrics.quiet_move_score +
            metrics.forcing_move_score -
            metrics.drama_penalty,
            100.0
        )
        
        return metrics

    def _is_material_sacrifice(
        self,
        board: chess.Board,
        move: chess.Move,
        eval_before: Optional[float] = None,
        eval_after: Optional[float] = None,
    ) -> bool:
        """
        Detect if a move is a sound sacrifice.
        Sound = Material drops but evaluation doesn't drop significantly.
        """
        if not board.is_capture(move):
            return False
        
        # Check if material is actually dropped (quality sacrifice, not a trade)
        moving_piece = board.piece_at(move.from_square)
        captured_piece = board.piece_at(move.to_square)
        
        if not moving_piece or not captured_piece:
            return False
        
        # Our piece is more valuable than what we're capturing
        our_value = self._piece_value(moving_piece)
        their_value = self._piece_value(captured_piece)
        
        if our_value <= their_value:
            return False
        
        # Evaluation doesn't drop too much (compensation exists)
        if eval_before and eval_after:
            eval_drop = eval_before - eval_after
            # Sound sacrifice: evaluation drops less than 1.5 pawns
            if eval_drop > 150:
                return False
        
        return True

    def _is_position_sharp(self, board: chess.Board) -> bool:
        """Is the position tactically sharp (not endgame)?"""
        # Count non-pawn pieces
        non_pawns = sum(1 for piece_type in chess.PIECE_TYPES[:-1]  # Exclude pawns
                       for square in chess.SQUARES
                       if board.piece_at(square) and board.piece_at(square).piece_type == piece_type)
        
        # Sharp if there are many pieces on board (not endgame)
        return non_pawns >= 6

    def _has_forcing_continuation(self, board: chess.Board, move: chess.Move) -> bool:
        """After this move, is there a forcing continuation?"""
        board.push(move)
        
        # Check if there are forcing moves available
        has_check = any(board.gives_check(m) for m in board.legal_moves)
        
        board.pop()
        return has_check

    def _is_positional_squeeze(self, board: chess.Board, move: chess.Move) -> bool:
        """Is this a positional move that squeezes the opponent?"""
        # Moves that are quiet but restrict opponent's pieces
        if board.is_capture(move) or board.gives_check(move):
            return False
        
        board.push(move)
        opponent_legal_count = len(list(board.legal_moves))
        board.pop()
        
        board_no_move = chess.Board(board.fen())
        board_no_move.turn = not board_no_move.turn
        opponent_no_move_count = len(list(board_no_move.legal_moves))
        board_no_move.turn = not board_no_move.turn
        
        # Move restricts opponent's options
        return opponent_legal_count < opponent_no_move_count - 1

    def _count_tension(self, board: chess.Board) -> int:
        """Count the number of pieces under mutual attack (tension)."""
        tension = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece:
                # Count attacks on this square
                attackers = len(board.attackers(not piece.color, square))
                defenders = len(board.attackers(piece.color, square))
                
                if attackers > 0 and defenders > 0:
                    tension += min(attackers, defenders)
        
        return tension

    @staticmethod
    def _piece_value(piece: chess.Piece) -> int:
        """Get the material value of a piece."""
        values = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 0,
        }
        return values.get(piece.piece_type, 0)


# Example usage
if __name__ == "__main__":
    evaluator = BeautyEvaluator()
    
    # Example: Scholar's Mate
    board = chess.Board()
    moves = [
        board.push_san("e4"),
        board.push_san("e5"),
        board.push_san("Bc4"),
        board.push_san("Nc6"),
        board.push_san("Qh5"),
        board.push_san("Nf6"),
        board.push_san("Qxf7"),  # Checkmate threat / Scholar's Mate
    ]
    
    print("Evaluating Scholar's Mate sequence...")
    
    # Note: In a real scenario, you'd have evaluations from Stockfish
    # For now, we just demonstrate the structure
