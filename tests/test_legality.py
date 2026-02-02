"""
tests/test_legality.py

Unit tests for the legality validator.
"""

import pytest
import chess
from engine.legality import LegalityValidator


class TestLegalityValidator:
    """Test suite for legality validation."""

    @pytest.fixture
    def validator(self):
        """Create a fresh validator for each test."""
        return LegalityValidator()

    def test_valid_opening_moves(self, validator):
        """Test standard opening moves."""
        moves = ["e4", "c5", "Nf3", "d6"]
        
        for move_str in moves:
            report = validator.parse_and_validate_move(move_str)
            assert report.is_legal, f"Move {move_str} should be legal"
            validator.apply_move(report.move_object)

    def test_invalid_notation(self, validator):
        """Test invalid algebraic notation rejection."""
        invalid_moves = ["xyz", "1234", "!!"]
        
        for move_str in invalid_moves:
            report = validator.parse_and_validate_move(move_str)
            assert not report.is_legal, f"Move {move_str} should be invalid notation"

    def test_illegal_move_detection(self, validator):
        """Test detection of illegal moves."""
        validator.reset_board()
        
        # First move, only valid white moves are certain pawns and knights
        invalid_first_move = "e5"  # Black pawn move, white's turn
        report = validator.parse_and_validate_move(invalid_first_move)
        assert not report.is_legal, "e5 should be illegal on white's first move"

    def test_game_validation(self, validator):
        """Test full game validation."""
        pgn = """
        [Event "Test"]
        [Site "Test"]
        
        1. e4 e5 2. Nf3 Nc6 3. Bb5 a6
        """
        
        is_valid, errors = validator.validate_game_pgn(pgn)
        assert is_valid, f"Game should be valid, errors: {errors}"

    def test_illegal_game_detection(self, validator):
        """Test detection of illegal moves in game."""
        pgn = """
        [Event "Test"]
        
        1. e5 e5 2. Nf3
        """
        
        is_valid, errors = validator.validate_game_pgn(pgn)
        assert not is_valid, "Game with illegal moves should fail validation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
