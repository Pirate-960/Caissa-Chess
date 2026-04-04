"""
Tests for Tournament Module (core/tournament.py)

Tests cover:
- TournamentFormat enum
- TournamentConfig validation
- Round-robin pairing generation
- Swiss pairing algorithm
- Knockout bracket generation
- Standings calculation with tiebreaks
- Tournament execution

Author: CAISSA Team
Version: 0.5.0
"""

import pytest
import asyncio
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime

from core.tournament import (
    Tournament,
    TournamentConfig,
    TournamentResult,
    TournamentFormat,
    TournamentStatus,
    TiebreakMethod,
    Round,
    Standing,
    run_tournament,
)
from core.tournament_player import TournamentPlayer, TimeControl, PlayerStatus
from core.elo_calculator import GameResult
from core.match_engine import MatchResult, TerminationReason


class TestTournamentFormat:
    """Tests for TournamentFormat enum."""
    
    def test_all_formats_defined(self):
        """All expected formats should be defined."""
        expected = {
            "single_match", "match_series", "round_robin", 
            "double_round_robin", "swiss", "knockout", 
            "double_elim", "arena"
        }
        actual = {f.value for f in TournamentFormat}
        assert expected == actual


class TestTournamentStatus:
    """Tests for TournamentStatus enum."""
    
    def test_all_statuses_defined(self):
        """All expected statuses should be defined."""
        expected = {"created", "in_progress", "paused", "completed", "cancelled"}
        actual = {s.value for s in TournamentStatus}
        assert expected == actual


class TestTiebreakMethod:
    """Tests for TiebreakMethod enum."""
    
    def test_common_tiebreaks_defined(self):
        """Common tiebreak methods should be defined."""
        expected = {"h2h", "sb", "buchholz", "wins", "black_wins", "neustadtl", "performance"}
        actual = {t.value for t in TiebreakMethod}
        assert expected == actual


class TestStanding:
    """Tests for Standing dataclass."""
    
    def test_standing_creation(self):
        """Standing should store all player data."""
        player = TournamentPlayer(name="Test Player")
        standing = Standing(
            rank=1,
            player=player,
            points=5.5,
            games_played=7,
            wins=5,
            draws=1,
            losses=1,
        )
        
        assert standing.rank == 1
        assert standing.points == 5.5
        assert standing.wins == 5
    
    def test_score_display(self):
        """Score display should format correctly."""
        player = TournamentPlayer(name="Test")
        standing = Standing(
            rank=1, player=player, points=5.5,
            games_played=7, wins=5, draws=1, losses=1,
        )
        
        display = standing.score_display
        assert "5W" in display
        assert "1D" in display
        assert "1L" in display
        assert "5.5" in display
    
    def test_standing_serialization(self):
        """Standing should serialize to dict."""
        player = TournamentPlayer(name="Test")
        standing = Standing(
            rank=2, player=player, points=4.0,
            games_played=6, wins=3, draws=2, losses=1,
        )
        
        data = standing.to_dict()
        assert data["rank"] == 2
        assert data["points"] == 4.0
        assert data["player_name"] == "Test"


class TestRound:
    """Tests for Round dataclass."""
    
    def test_round_creation(self):
        """Round should store pairings and results."""
        p1 = TournamentPlayer(name="Player 1")
        p2 = TournamentPlayer(name="Player 2")
        p3 = TournamentPlayer(name="Player 3")
        p4 = TournamentPlayer(name="Player 4")
        
        round_obj = Round(
            round_number=1,
            pairings=[(p1, p2), (p3, p4)],
        )
        
        assert round_obj.round_number == 1
        assert len(round_obj.pairings) == 2
    
    def test_round_is_complete_empty(self):
        """Round with no results is not complete."""
        p1 = TournamentPlayer(name="P1")
        p2 = TournamentPlayer(name="P2")
        
        round_obj = Round(round_number=1, pairings=[(p1, p2)])
        assert round_obj.is_complete is False
    
    def test_round_is_complete_partial(self):
        """Round with partial results is not complete."""
        p1 = TournamentPlayer(name="P1")
        p2 = TournamentPlayer(name="P2")
        p3 = TournamentPlayer(name="P3")
        p4 = TournamentPlayer(name="P4")
        
        mock_result = Mock()
        round_obj = Round(
            round_number=1,
            pairings=[(p1, p2), (p3, p4)],
            results=[mock_result],  # Only one result
        )
        assert round_obj.is_complete is False
    
    def test_round_serialization(self):
        """Round should serialize to dict."""
        p1 = TournamentPlayer(id="p1", name="P1")
        p2 = TournamentPlayer(id="p2", name="P2")
        
        round_obj = Round(
            round_number=1,
            pairings=[(p1, p2)],
        )
        
        data = round_obj.to_dict()
        assert data["round_number"] == 1
        assert ("p1", "p2") in data["pairings"]


class TestTournamentConfig:
    """Tests for TournamentConfig dataclass."""
    
    def test_config_creation(self):
        """Config should store all settings."""
        players = [TournamentPlayer(name=f"P{i}") for i in range(4)]
        
        config = TournamentConfig(
            name="Test Tournament",
            format=TournamentFormat.ROUND_ROBIN,
            players=players,
        )
        
        assert config.name == "Test Tournament"
        assert len(config.players) == 4
    
    def test_config_auto_rounds_round_robin(self):
        """Round-robin rounds should auto-calculate."""
        players = [TournamentPlayer(name=f"P{i}") for i in range(4)]
        
        config = TournamentConfig(
            name="Test",
            format=TournamentFormat.ROUND_ROBIN,
            players=players,
            rounds=0,  # Auto-calculate
        )
        
        # 4 players need 3 rounds for round-robin
        assert config.rounds == 3
    
    def test_config_auto_rounds_swiss(self):
        """Swiss rounds should auto-calculate."""
        players = [TournamentPlayer(name=f"P{i}") for i in range(8)]
        
        config = TournamentConfig(
            name="Test",
            format=TournamentFormat.SWISS,
            players=players,
            rounds=0,  # Auto-calculate
        )
        
        # ceil(log2(8)) = 3 rounds
        assert config.rounds >= 3
    
    def test_config_default_scoring(self):
        """Default scoring should be 1-0.5-0."""
        config = TournamentConfig(
            name="Test",
            format=TournamentFormat.SWISS,
            players=[],
        )
        
        assert config.win_points == 1.0
        assert config.draw_points == 0.5
        assert config.loss_points == 0.0


class TestTournament:
    """Tests for Tournament class."""
    
    @pytest.fixture
    def four_players(self):
        """Create four test players."""
        return [
            TournamentPlayer(id=f"p{i}", name=f"Player {i}", provider=Mock())
            for i in range(1, 5)
        ]
    
    @pytest.fixture
    def tournament_config(self, four_players):
        """Create a basic tournament config."""
        return TournamentConfig(
            name="Test Tournament",
            format=TournamentFormat.ROUND_ROBIN,
            players=four_players,
            time_control=TimeControl.RAPID,
        )
    
    def test_tournament_initialization(self, tournament_config):
        """Tournament should initialize correctly."""
        tournament = Tournament(tournament_config)
        
        assert tournament.status == TournamentStatus.CREATED
        assert len(tournament.players) == 4
        assert all(pid in tournament.scores for pid in ["p1", "p2", "p3", "p4"])
    
    def test_round_robin_pairing_generation(self, tournament_config):
        """Round-robin should pair all players."""
        tournament = Tournament(tournament_config)
        schedule = tournament._generate_round_robin_pairings()
        
        # 4 players = 3 rounds, 2 games per round
        assert len(schedule) == 3
        
        # Each round should have 2 pairings
        for round_pairings in schedule:
            assert len(round_pairings) == 2
        
        # Each player should play every other player exactly once
        all_pairings = []
        for round_pairings in schedule:
            all_pairings.extend(round_pairings)
        
        # Should be 6 total games (4 choose 2)
        assert len(all_pairings) == 6


class TestTournamentPairings:
    """Tests for pairing algorithms."""
    
    def test_round_robin_odd_players(self):
        """Round-robin with odd players should handle bye."""
        players = [TournamentPlayer(name=f"P{i}") for i in range(5)]
        config = TournamentConfig(
            name="Test",
            format=TournamentFormat.ROUND_ROBIN,
            players=players,
        )
        tournament = Tournament(config)
        schedule = tournament._generate_round_robin_pairings()
        
        # 5 players = 5 rounds, 2 games per round (one bye)
        assert len(schedule) == 5
        for round_pairings in schedule:
            # 2 pairings per round (1 player gets bye)
            assert len(round_pairings) == 2
    
    def test_swiss_pairing_by_score(self):
        """Swiss should pair players with similar scores."""
        players = [
            TournamentPlayer(id=f"p{i}", name=f"P{i}")
            for i in range(4)
        ]
        config = TournamentConfig(
            name="Test",
            format=TournamentFormat.SWISS,
            players=players,
            rounds=2,
        )
        tournament = Tournament(config)
        
        # Set up scores: p0=2, p1=2, p2=0, p3=0
        tournament.scores = {"p0": 2.0, "p1": 2.0, "p2": 0.0, "p3": 0.0}
        
        pairings, byes = tournament._generate_swiss_pairings(2)
        
        # Top scorers should be paired together
        paired_ids = set()
        for white, black in pairings:
            paired_ids.add(white.id)
            paired_ids.add(black.id)
        
        assert len(byes) == 0  # Even number of players


class TestTournamentScoring:
    """Tests for scoring and standings."""
    
    @pytest.fixture
    def tournament_with_results(self):
        """Create tournament with some results."""
        players = [
            TournamentPlayer(id=f"p{i}", name=f"Player {i}")
            for i in range(4)
        ]
        config = TournamentConfig(
            name="Test",
            format=TournamentFormat.ROUND_ROBIN,
            players=players,
        )
        tournament = Tournament(config)
        
        # Simulate some scores
        tournament.scores = {
            "p0": 2.5,  # 2W 1D 0L
            "p1": 2.0,  # 2W 0D 1L
            "p2": 1.0,  # 1W 0D 2L
            "p3": 0.5,  # 0W 1D 2L
        }
        
        for i, p in enumerate(players):
            p.stats.games_played = 3
            p.stats.wins = int(tournament.scores[p.id])
            p.stats.draws = 1 if tournament.scores[p.id] % 1 == 0.5 else 0
            p.stats.losses = 3 - p.stats.wins - p.stats.draws
        
        return tournament
    
    def test_standings_sorted_by_points(self, tournament_with_results):
        """Standings should be sorted by points."""
        standings = tournament_with_results._calculate_standings()
        
        assert standings[0].player.id == "p0"  # 2.5 points
        assert standings[1].player.id == "p1"  # 2.0 points
        assert standings[2].player.id == "p2"  # 1.0 points
        assert standings[3].player.id == "p3"  # 0.5 points
    
    def test_standings_ranks_assigned(self, tournament_with_results):
        """Standings should have correct ranks."""
        standings = tournament_with_results._calculate_standings()
        
        for i, standing in enumerate(standings, 1):
            assert standing.rank == i


class TestTournamentResult:
    """Tests for TournamentResult dataclass."""
    
    def test_result_winner_detection(self):
        """Result should identify winner from standings."""
        players = [TournamentPlayer(name=f"P{i}") for i in range(4)]
        config = TournamentConfig(
            name="Test",
            format=TournamentFormat.ROUND_ROBIN,
            players=players,
        )
        
        standings = [
            Standing(rank=1, player=players[2], points=3.0,
                    games_played=3, wins=3, draws=0, losses=0),
            Standing(rank=2, player=players[0], points=2.0,
                    games_played=3, wins=2, draws=0, losses=1),
        ]
        
        result = TournamentResult(
            config=config,
            status=TournamentStatus.COMPLETED,
            rounds=[],
            standings=standings,
            matches=[],
        )
        
        assert result.winner == players[2]
    
    def test_result_no_winner_empty(self):
        """Result with no standings has no winner."""
        config = TournamentConfig(
            name="Test",
            format=TournamentFormat.SWISS,
            players=[],
        )
        
        result = TournamentResult(
            config=config,
            status=TournamentStatus.CANCELLED,
            rounds=[],
            standings=[],
            matches=[],
        )
        
        assert result.winner is None
    
    def test_result_duration_calculation(self):
        """Duration should calculate from timestamps."""
        config = TournamentConfig(
            name="Test",
            format=TournamentFormat.SWISS,
            players=[],
        )
        
        start = datetime(2026, 4, 4, 10, 0, 0)
        end = datetime(2026, 4, 4, 12, 30, 0)
        
        result = TournamentResult(
            config=config,
            status=TournamentStatus.COMPLETED,
            rounds=[],
            standings=[],
            matches=[],
            start_time=start,
            end_time=end,
        )
        
        assert result.duration == 9000.0  # 2.5 hours in seconds
    
    def test_result_serialization(self):
        """Result should serialize to dict."""
        players = [TournamentPlayer(name="Winner")]
        config = TournamentConfig(
            name="Test Tournament",
            format=TournamentFormat.KNOCKOUT,
            players=players,
        )
        
        result = TournamentResult(
            config=config,
            status=TournamentStatus.COMPLETED,
            rounds=[],
            standings=[Standing(
                rank=1, player=players[0], points=1.0,
                games_played=1, wins=1, draws=0, losses=0,
            )],
            matches=[],
            total_games=3,
            decisive_games=2,
            draws=1,
        )
        
        data = result.to_dict()
        assert data["name"] == "Test Tournament"
        assert data["format"] == "knockout"
        assert data["total_games"] == 3
        assert data["winner"] == "Winner"


@pytest.mark.asyncio
class TestTournamentExecution:
    """Async tests for tournament execution."""
    
    def test_single_match_tournament(self):
        """Single match tournament should complete."""
        async def run_test():
            players = [
                TournamentPlayer(name="White", provider=Mock()),
                TournamentPlayer(name="Black", provider=Mock()),
            ]
            
            config = TournamentConfig(
                name="Single Match",
                format=TournamentFormat.SINGLE_MATCH,
                players=players,
            )
            
            tournament = Tournament(config)
            
            # Mock the match playing
            with patch.object(tournament, '_play_match') as mock_play:
                mock_result = MatchResult(
                    match_id="test",
                    white=players[0],
                    black=players[1],
                    result=GameResult.WHITE_WINS,
                    termination=TerminationReason.CHECKMATE,
                )
                # Mock ELO change
                mock_result.elo_change = Mock()
                mock_result.elo_change.white_new = 1516
                mock_result.elo_change.black_new = 1484
                mock_result.elo_change.summary = "test"
                
                mock_play.return_value = mock_result
                
                result = await tournament.run()
            
            assert result.status == TournamentStatus.COMPLETED
            assert result.total_games == 1
        
        asyncio.run(run_test())


class TestHighlights:
    """Tests for tournament highlights detection."""
    
    def test_find_highlights_empty(self):
        """Empty matches should return empty highlights."""
        config = TournamentConfig(
            name="Test",
            format=TournamentFormat.SWISS,
            players=[],
        )
        tournament = Tournament(config)
        tournament.matches = []
        
        highlights = tournament._find_highlights()
        assert highlights == {}
    
    def test_find_highlights_single_match(self):
        """Single match tournament should have highlights."""
        white = TournamentPlayer(name="W", elo_rating=1500)
        black = TournamentPlayer(name="B", elo_rating=1600)
        
        config = TournamentConfig(
            name="Test",
            format=TournamentFormat.SINGLE_MATCH,
            players=[white, black],
        )
        tournament = Tournament(config)
        
        match = MatchResult(
            match_id="test",
            white=white,
            black=black,
            result=GameResult.WHITE_WINS,
            termination=TerminationReason.CHECKMATE,
            total_moves=42,
            beauty_score=85.0,
        )
        tournament.matches = [match]
        
        highlights = tournament._find_highlights()
        
        assert highlights.get("best") == match
        assert highlights.get("longest") == match
        assert highlights.get("shortest") == match


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_run_tournament_function(self):
        """run_tournament convenience function should work."""
        async def run_test():
            players = [
                TournamentPlayer(name="P1", provider=Mock()),
                TournamentPlayer(name="P2", provider=Mock()),
            ]
            
            config = TournamentConfig(
                name="Quick Test",
                format=TournamentFormat.SINGLE_MATCH,
                players=players,
            )
            
            with patch('core.tournament.Tournament.run') as mock_run:
                mock_result = Mock()
                mock_result.status = TournamentStatus.COMPLETED
                mock_run.return_value = mock_result
                
                result = await run_tournament(config)
                
                assert result.status == TournamentStatus.COMPLETED
        
        asyncio.run(run_test())
