"""
Tests for Match Engine Module (core/match_engine.py)

Tests cover:
- Move parsing and extraction
- Move validation
- Game termination detection
- MatchEngine orchestration
- MatchResult generation
- PGN generation

Author: CAISSA Team
Version: 0.5.0
"""

import pytest
import chess
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime

from core.match_engine import (
    MatchEngine,
    MatchResult,
    MoveRecord,
    MoveOutcome,
    TerminationReason,
)
from core.tournament_player import TournamentPlayer, TimeControl, PlayerStatus
from core.elo_calculator import GameResult


class TestMoveOutcome:
    """Tests for MoveOutcome enum."""
    
    def test_all_outcomes_defined(self):
        """All expected outcomes should be defined."""
        expected = {"success", "illegal", "parse_error", "timeout", "api_error", "forfeit"}
        actual = {o.value for o in MoveOutcome}
        assert expected == actual


class TestTerminationReason:
    """Tests for TerminationReason enum."""
    
    def test_chess_terminations(self):
        """Standard chess terminations should be defined."""
        chess_terminations = ["checkmate", "stalemate", "insufficient", 
                              "fifty_move", "threefold", "fivefold"]
        for term in chess_terminations:
            assert any(t.value == term for t in TerminationReason)
    
    def test_tournament_terminations(self):
        """Tournament-specific terminations should be defined."""
        tournament_terminations = ["forfeit", "timeout", "max_moves", "adjudication"]
        for term in tournament_terminations:
            assert any(t.value == term for t in TerminationReason)


class TestMoveRecord:
    """Tests for MoveRecord dataclass."""
    
    def test_move_record_creation(self):
        """MoveRecord should store all move data."""
        record = MoveRecord(
            move_number=1,
            player="player-1",
            color="white",
            san="e4",
            uci="e2e4",
            fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            fen_after="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            think_time=2.5,
            attempt=1,
            is_check=False,
            is_capture=False,
        )
        
        assert record.san == "e4"
        assert record.move_number == 1
        assert record.think_time == 2.5


class TestMatchResult:
    """Tests for MatchResult dataclass."""
    
    def test_match_result_winner_white(self):
        """White winning should report white as winner."""
        white = TournamentPlayer(name="White")
        black = TournamentPlayer(name="Black")
        result = MatchResult(
            match_id="test",
            white=white,
            black=black,
            result=GameResult.WHITE_WINS,
            termination=TerminationReason.CHECKMATE,
        )
        
        assert result.winner_name == "White"
        assert result.is_decisive is True
    
    def test_match_result_winner_black(self):
        """Black winning should report black as winner."""
        white = TournamentPlayer(name="White")
        black = TournamentPlayer(name="Black")
        result = MatchResult(
            match_id="test",
            white=white,
            black=black,
            result=GameResult.BLACK_WINS,
            termination=TerminationReason.RESIGNATION,
        )
        
        assert result.winner_name == "Black"
        assert result.is_decisive is True
    
    def test_match_result_draw(self):
        """Draw should report no winner."""
        white = TournamentPlayer(name="White")
        black = TournamentPlayer(name="Black")
        result = MatchResult(
            match_id="test",
            white=white,
            black=black,
            result=GameResult.DRAW,
            termination=TerminationReason.STALEMATE,
        )
        
        assert result.winner_name is None
        assert result.is_decisive is False
    
    def test_match_result_duration(self):
        """Duration should calculate from timestamps."""
        white = TournamentPlayer(name="White")
        black = TournamentPlayer(name="Black")
        
        start = datetime(2026, 4, 4, 10, 0, 0)
        end = datetime(2026, 4, 4, 10, 5, 30)
        
        result = MatchResult(
            match_id="test",
            white=white,
            black=black,
            result=GameResult.DRAW,
            termination=TerminationReason.AGREEMENT,
            start_time=start,
            end_time=end,
        )
        
        assert result.duration == 330.0  # 5 minutes 30 seconds
    
    def test_match_result_serialization(self):
        """MatchResult should serialize to dict."""
        white = TournamentPlayer(name="White Player")
        black = TournamentPlayer(name="Black Player")
        result = MatchResult(
            match_id="test-123",
            white=white,
            black=black,
            result=GameResult.WHITE_WINS,
            termination=TerminationReason.CHECKMATE,
            total_moves=42,
        )
        
        data = result.to_dict()
        assert data["match_id"] == "test-123"
        assert data["result"] == "1-0"
        assert data["total_moves"] == 42
        assert data["prompt_variant"] == "A"
        assert isinstance(data["prompt_trace"], dict)


class TestMatchEngineMovePatterns:
    """Tests for move pattern matching."""
    
    @pytest.fixture
    def engine(self):
        """Create a basic match engine for testing."""
        white = TournamentPlayer(name="White", provider=Mock())
        black = TournamentPlayer(name="Black", provider=Mock())
        return MatchEngine(white, black)
    
    def test_parse_simple_move(self, engine):
        """Should parse simple pawn moves."""
        assert engine._parse_move_response("e4") == "e4"
        assert engine._parse_move_response("d4") == "d4"
    
    def test_parse_piece_move(self, engine):
        """Should parse piece moves."""
        assert engine._parse_move_response("Nf3") == "Nf3"
        assert engine._parse_move_response("Bc4") == "Bc4"
    
    def test_parse_capture(self, engine):
        """Should parse captures."""
        assert engine._parse_move_response("Bxc6") == "Bxc6"
        assert engine._parse_move_response("exd5") == "exd5"
    
    def test_parse_castling(self, engine):
        """Should parse and normalize castling."""
        assert engine._parse_move_response("O-O") == "O-O"
        assert engine._parse_move_response("O-O-O") == "O-O-O"
        # Normalize alternative notations
        assert engine._parse_move_response("0-0") == "O-O"
        assert engine._parse_move_response("0-0-0") == "O-O-O"
    
    def test_parse_promotion(self, engine):
        """Should parse promotion moves."""
        assert engine._parse_move_response("e8=Q") == "e8=Q"
        assert engine._parse_move_response("a1=R") == "a1=R"
    
    def test_parse_check(self, engine):
        """Should parse moves with check."""
        assert engine._parse_move_response("Qh5+") == "Qh5+"
        assert engine._parse_move_response("Nf7#") == "Nf7#"
    
    def test_parse_with_context(self, engine):
        """Should extract move from conversational text."""
        response = "I'll play e4 to control the center."
        assert engine._parse_move_response(response) == "e4"
        
        response = "My move is: Nf3"
        assert engine._parse_move_response(response) == "Nf3"
    
    def test_parse_move_prefix(self, engine):
        """Should handle 'Move:' prefix."""
        assert engine._parse_move_response("Move: Bc4") == "Bc4"
        assert engine._parse_move_response("My move: Qd3") == "Qd3"
    
    def test_parse_empty_response(self, engine):
        """Empty response should return None."""
        assert engine._parse_move_response("") is None
        assert engine._parse_move_response("   ") is None
    
    def test_parse_invalid_response(self, engine):
        """Invalid chess notation should return None."""
        assert engine._parse_move_response("hello world") is None
        assert engine._parse_move_response("z99") is None


class TestMatchEngineMoveValidation:
    """Tests for move validation logic."""
    
    @pytest.fixture
    def engine(self):
        """Create match engine for testing."""
        white = TournamentPlayer(name="White", provider=Mock())
        black = TournamentPlayer(name="Black", provider=Mock())
        return MatchEngine(white, black)
    
    def test_looks_like_move_valid(self, engine):
        """Valid moves should be recognized."""
        assert engine._looks_like_move("e4") is True
        assert engine._looks_like_move("Nf3") is True
        assert engine._looks_like_move("O-O") is True
        assert engine._looks_like_move("Bxc6+") is True
    
    def test_looks_like_move_invalid(self, engine):
        """Invalid strings should be rejected."""
        assert engine._looks_like_move("") is False
        assert engine._looks_like_move("hello") is False
        assert engine._looks_like_move("z9") is False
        assert engine._looks_like_move("1234") is False


class TestMatchEngineGameState:
    """Tests for game state management."""
    
    @pytest.fixture
    def engine(self):
        """Create match engine with fresh board."""
        white = TournamentPlayer(name="White", provider=Mock())
        black = TournamentPlayer(name="Black", provider=Mock())
        return MatchEngine(white, black)
    
    def test_initial_board_state(self, engine):
        """Engine should start with standard position."""
        assert engine.board.fen() == chess.STARTING_FEN
    
    def test_custom_starting_position(self):
        """Should support custom starting FEN."""
        custom_fen = "r1bqkbnr/pppppppp/2n5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 1 2"
        white = TournamentPlayer(name="White", provider=Mock())
        black = TournamentPlayer(name="Black", provider=Mock())
        engine = MatchEngine(white, black, starting_fen=custom_fen)
        
        assert engine.board.fen() == custom_fen
    
    def test_current_turn_white(self, engine):
        """Initial turn should be white."""
        assert engine.current_turn == "white"
    
    def test_move_count_initial(self, engine):
        """Move count should start at 0."""
        assert engine.move_count == 0
    
    def test_record_illegal_attempt_white(self, engine):
        """Should track illegal attempts for white."""
        assert engine.white_illegal_attempts == 0
        engine._record_illegal_attempt("white")
        assert engine.white_illegal_attempts == 1
    
    def test_record_illegal_attempt_black(self, engine):
        """Should track illegal attempts for black."""
        assert engine.black_illegal_attempts == 0
        engine._record_illegal_attempt("black")
        assert engine.black_illegal_attempts == 1


class TestMatchEngineGameTermination:
    """Tests for game termination detection."""
    
    def test_checkmate_detection(self):
        """Should detect checkmate."""
        # Scholar's mate position after 1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6 4.Qxf7#
        mate_fen = "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4"
        
        white = TournamentPlayer(name="White", provider=Mock())
        black = TournamentPlayer(name="Black", provider=Mock())
        engine = MatchEngine(white, black, starting_fen=mate_fen)
        
        assert engine._is_game_over() is True
        result, reason = engine._determine_result()
        assert result == GameResult.WHITE_WINS
        assert reason == TerminationReason.CHECKMATE
    
    def test_stalemate_detection(self):
        """Should detect stalemate."""
        # Classic stalemate: Black king h8, White king f7, White queen g6
        # Black has no legal moves but is not in check
        stalemate_fen = "7k/5K2/6Q1/8/8/8/8/8 b - - 0 1"
        
        white = TournamentPlayer(name="White", provider=Mock())
        black = TournamentPlayer(name="Black", provider=Mock())
        engine = MatchEngine(white, black, starting_fen=stalemate_fen)
        
        assert engine._is_game_over() is True
        result, reason = engine._determine_result()
        assert result == GameResult.DRAW
        assert reason == TerminationReason.STALEMATE
    
    def test_insufficient_material_detection(self):
        """Should detect insufficient material."""
        # King vs King - no mating material
        insufficient_fen = "8/8/4k3/8/8/4K3/8/8 w - - 0 1"
        
        white = TournamentPlayer(name="White", provider=Mock())
        black = TournamentPlayer(name="Black", provider=Mock())
        engine = MatchEngine(white, black, starting_fen=insufficient_fen)
        
        assert engine._is_game_over() is True


class TestMatchEnginePGNGeneration:
    """Tests for PGN generation."""
    
    def test_basic_pgn_generation(self):
        """Should generate valid PGN with headers."""
        white = TournamentPlayer(name="White Player", elo_rating=1500)
        black = TournamentPlayer(name="Black Player", elo_rating=1600)
        engine = MatchEngine(white, black, time_control=TimeControl.RAPID)
        
        pgn = engine._generate_pgn(GameResult.DRAW, TerminationReason.AGREEMENT)
        
        assert "[Event" in pgn
        assert "[White \"White Player\"]" in pgn
        assert "[Black \"Black Player\"]" in pgn
        assert "[Result \"1/2-1/2\"]" in pgn
        assert "[WhiteElo \"1500\"]" in pgn
        assert "[BlackElo \"1600\"]" in pgn
    
    def test_pgn_with_moves(self):
        """PGN should include move history."""
        white = TournamentPlayer(name="White", provider=Mock())
        black = TournamentPlayer(name="Black", provider=Mock())
        engine = MatchEngine(white, black)
        
        # Simulate some moves
        engine.move_history = [
            MoveRecord(1, "w", "white", "e4", "e2e4", "", "", 1.0, 1),
            MoveRecord(1, "b", "black", "e5", "e7e5", "", "", 1.0, 1),
            MoveRecord(2, "w", "white", "Nf3", "g1f3", "", "", 1.0, 1),
        ]
        
        # Make moves on board for PGN generation
        engine.board.push_san("e4")
        engine.board.push_san("e5")
        engine.board.push_san("Nf3")
        
        pgn = engine._generate_pgn(GameResult.IN_PROGRESS, TerminationReason.ADJUDICATION)
        
        assert "e4" in pgn
        assert "e5" in pgn
        assert "Nf3" in pgn


class TestMatchEnginePromptBuilding:
    """Tests for move prompt generation."""
    
    @pytest.fixture
    def engine(self):
        """Create match engine for testing."""
        white = TournamentPlayer(name="GPT-4", provider=Mock())
        black = TournamentPlayer(name="Claude", provider=Mock())
        return MatchEngine(white, black)
    
    def test_prompt_includes_fen(self, engine):
        """Prompt should include current FEN."""
        prompt = engine._build_move_prompt(engine.white, is_retry=False)
        assert engine.board.fen() in prompt
    
    def test_prompt_includes_legal_moves(self, engine):
        """Prompt should list some legal moves."""
        prompt = engine._build_move_prompt(engine.white, is_retry=False)
        assert "LEGAL MOVES" in prompt
        assert "e4" in prompt  # e4 is legal from start
    
    def test_prompt_includes_color(self, engine):
        """Prompt should indicate side to move."""
        prompt = engine._build_move_prompt(engine.white, is_retry=False)
        assert "White" in prompt
    
    def test_retry_prompt_warns(self, engine):
        """Retry prompt should warn about illegal move."""
        prompt = engine._build_move_prompt(engine.white, is_retry=True)
        assert "ILLEGAL" in prompt.upper() or "invalid" in prompt.lower()
    
    def test_prompt_includes_opponent(self, engine):
        """Prompt should mention opponent."""
        prompt = engine._build_move_prompt(engine.white, is_retry=False)
        assert "Claude" in prompt  # Opponent name


@pytest.mark.asyncio
class TestMatchEngineAsync:
    """Async tests for match execution."""
    
    def test_match_completes(self):
        """Match should complete and return result."""
        async def run_test():
            # Create mock providers that return valid moves
            white_provider = Mock()
            white_provider.generate = Mock(return_value="e4")
            
            black_provider = Mock()
            black_provider.generate = Mock(return_value="e5")
            
            white = TournamentPlayer(name="White", provider=white_provider)
            black = TournamentPlayer(name="Black", provider=black_provider)
            
            engine = MatchEngine(white, black, max_moves=5)
            
            with patch.object(engine, '_call_llm', side_effect=[
                "e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "d3", "Be7", "O-O", "O-O"
            ]):
                result = await engine.play_match()
            
            assert result is not None
            assert isinstance(result, MatchResult)
            assert result.total_moves <= 10  # max_moves * 2
        
        asyncio.run(run_test())
    
    def test_forfeit_on_repeated_illegal(self):
        """Player should forfeit after max retries."""
        async def run_test():
            white_provider = Mock()
            white_provider.generate = Mock(return_value="invalid_move")
            
            black_provider = Mock()
            black_provider.generate = Mock(return_value="e5")
            
            white = TournamentPlayer(name="White", provider=white_provider)
            black = TournamentPlayer(name="Black", provider=black_provider)
            
            engine = MatchEngine(white, black, max_retries=3)
            
            # Always return invalid move
            with patch.object(engine, '_call_llm', return_value="zzz99"):
                result = await engine.play_match()
            
            # White should forfeit
            assert result.result == GameResult.BLACK_WINS
            assert result.termination == TerminationReason.FORFEIT
        
        asyncio.run(run_test())


class TestPlaySingleMatch:
    """Tests for convenience function."""
    
    def test_play_single_match_function(self):
        """play_single_match should work."""
        async def run_test():
            from core.match_engine import play_single_match
            
            white = TournamentPlayer(name="White", provider=Mock())
            black = TournamentPlayer(name="Black", provider=Mock())
            
            with patch('core.match_engine.MatchEngine.play_match') as mock_play:
                mock_result = MatchResult(
                    match_id="test",
                    white=white,
                    black=black,
                    result=GameResult.DRAW,
                    termination=TerminationReason.AGREEMENT,
                )
                mock_play.return_value = mock_result
                
                result = await play_single_match(white, black)
                
                assert result == mock_result
        
        asyncio.run(run_test())
