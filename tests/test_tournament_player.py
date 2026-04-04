"""
Tests for Tournament Player Module (core/tournament_player.py)

Tests cover:
- TournamentPlayer dataclass
- PlayerStats tracking
- TimeControl enum
- StylePersona and persona prompts
- Player serialization/deserialization
- Factory functions

Author: CAISSA Team
Version: 0.5.0
"""

import pytest
from unittest.mock import Mock, MagicMock
from core.tournament_player import (
    TournamentPlayer,
    PlayerStats,
    TimeControl,
    PlayerStatus,
    StylePersona,
    PERSONA_PROMPTS,
    create_player_from_provider,
)


class TestTimeControl:
    """Tests for TimeControl enum."""
    
    def test_time_control_values(self):
        """Time control values should be in seconds."""
        assert TimeControl.BULLET.value == 5
        assert TimeControl.BLITZ.value == 15
        assert TimeControl.RAPID.value == 30
        assert TimeControl.CLASSICAL.value == 60
        assert TimeControl.UNLIMITED.value == -1
    
    def test_correspondence_longest(self):
        """Correspondence should be longest finite time."""
        finite_controls = [tc for tc in TimeControl if tc.value > 0]
        assert TimeControl.CORRESPONDENCE == max(finite_controls, key=lambda x: x.value)


class TestPlayerStatus:
    """Tests for PlayerStatus enum."""
    
    def test_all_statuses_defined(self):
        """All expected statuses should be defined."""
        expected = {"active", "in_match", "eliminated", "withdrawn", "disqualified"}
        actual = {s.value for s in PlayerStatus}
        assert expected == actual


class TestStylePersona:
    """Tests for StylePersona enum and prompts."""
    
    def test_legendary_players_defined(self):
        """All legendary player styles should be defined."""
        legends = ["TAL", "KARPOV", "KASPAROV", "FISCHER", "CARLSEN", 
                   "MORPHY", "CAPABLANCA", "PETROSIAN", "ALEKHINE", "BOTVINNIK"]
        for legend in legends:
            assert hasattr(StylePersona, legend)
    
    def test_all_personas_have_prompts(self):
        """All personas should have corresponding prompts."""
        for persona in StylePersona:
            assert persona in PERSONA_PROMPTS
    
    def test_neutral_has_empty_prompt(self):
        """NEUTRAL persona should have empty prompt."""
        assert PERSONA_PROMPTS[StylePersona.NEUTRAL] == ""
    
    def test_tal_prompt_mentions_sacrifice(self):
        """Tal's prompt should mention sacrifices."""
        prompt = PERSONA_PROMPTS[StylePersona.TAL]
        assert "sacrific" in prompt.lower()
    
    def test_karpov_prompt_mentions_positional(self):
        """Karpov's prompt should mention positional play."""
        prompt = PERSONA_PROMPTS[StylePersona.KARPOV]
        assert "position" in prompt.lower()


class TestPlayerStats:
    """Tests for PlayerStats tracking."""
    
    def test_initial_stats_zeroed(self):
        """New stats should be all zeros."""
        stats = PlayerStats()
        assert stats.games_played == 0
        assert stats.wins == 0
        assert stats.losses == 0
        assert stats.draws == 0
        assert stats.points == 0.0
    
    def test_win_rate_calculation(self):
        """Win rate should calculate correctly."""
        stats = PlayerStats(games_played=10, wins=7, losses=2, draws=1)
        assert stats.win_rate == 70.0
    
    def test_win_rate_zero_games(self):
        """Win rate with zero games should be 0."""
        stats = PlayerStats()
        assert stats.win_rate == 0.0
    
    def test_draw_rate_calculation(self):
        """Draw rate should calculate correctly."""
        stats = PlayerStats(games_played=10, wins=5, losses=3, draws=2)
        assert stats.draw_rate == 20.0
    
    def test_avg_move_time(self):
        """Average move time should calculate correctly."""
        stats = PlayerStats(total_moves=100, total_think_time=300.0)
        assert stats.avg_move_time == 3.0
    
    def test_avg_move_time_zero_moves(self):
        """Average move time with zero moves should be 0."""
        stats = PlayerStats()
        assert stats.avg_move_time == 0.0
    
    def test_illegal_move_rate(self):
        """Illegal move rate should calculate correctly."""
        stats = PlayerStats(total_moves=100, illegal_move_attempts=5)
        assert stats.illegal_move_rate == 5.0
    
    def test_update_from_game_win(self):
        """Stats should update correctly after a win."""
        stats = PlayerStats()
        stats.update_from_game(
            won=True, drew=False, as_white=True,
            moves=40, illegal_attempts=1, think_time=120.0,
            centipawn_loss=25.0, blunders=0, mistakes=1
        )
        
        assert stats.games_played == 1
        assert stats.wins == 1
        assert stats.wins_as_white == 1
        assert stats.points == 1.0
        assert stats.total_moves == 40
        assert stats.mistakes == 1
    
    def test_update_from_game_draw(self):
        """Stats should update correctly after a draw."""
        stats = PlayerStats()
        stats.update_from_game(
            won=False, drew=True, as_white=False,
            moves=50, illegal_attempts=0, think_time=150.0,
            centipawn_loss=30.0
        )
        
        assert stats.draws == 1
        assert stats.draws_as_black == 1
        assert stats.points == 0.5
    
    def test_update_from_game_loss_forfeit(self):
        """Stats should track forfeits correctly."""
        stats = PlayerStats()
        stats.update_from_game(
            won=False, drew=False, as_white=True,
            moves=15, illegal_attempts=4, think_time=30.0,
            centipawn_loss=100.0, forfeit=True
        )
        
        assert stats.losses == 1
        assert stats.forfeits_given == 1
    
    def test_running_centipawn_average(self):
        """Centipawn loss should be running average."""
        stats = PlayerStats()
        stats.update_from_game(
            won=True, drew=False, as_white=True,
            moves=30, illegal_attempts=0, think_time=90.0,
            centipawn_loss=20.0
        )
        stats.update_from_game(
            won=True, drew=False, as_white=False,
            moves=40, illegal_attempts=0, think_time=100.0,
            centipawn_loss=40.0
        )
        
        # Average of 20 and 40 should be 30
        assert stats.avg_centipawn_loss == 30.0


class TestTournamentPlayer:
    """Tests for TournamentPlayer dataclass."""
    
    def test_auto_generate_id(self):
        """ID should be auto-generated if not provided."""
        player = TournamentPlayer()
        assert player.id is not None
        assert len(player.id) == 8
    
    def test_auto_generate_name(self):
        """Name should be auto-generated from provider/model."""
        player = TournamentPlayer(provider_name="openai", model_name="gpt-4")
        assert "openai" in player.name
        assert "gpt-4" in player.name
    
    def test_default_elo(self):
        """Default ELO should be 1500."""
        player = TournamentPlayer()
        assert player.elo_rating == 1500
    
    def test_default_status_active(self):
        """Default status should be ACTIVE."""
        player = TournamentPlayer()
        assert player.status == PlayerStatus.ACTIVE
    
    def test_display_name_includes_elo(self):
        """Display name should include ELO rating."""
        player = TournamentPlayer(name="Test Player", elo_rating=1600)
        assert "1600" in player.display_name
    
    def test_persona_prompt_property(self):
        """Persona prompt should return correct string."""
        player = TournamentPlayer(persona=StylePersona.TAL)
        assert player.persona_prompt == PERSONA_PROMPTS[StylePersona.TAL]
    
    def test_custom_persona_overrides(self):
        """Custom persona should override preset."""
        custom = "Play like a wild romantic"
        player = TournamentPlayer(persona=StylePersona.TAL, custom_persona=custom)
        assert player.persona_prompt == custom
    
    def test_is_available(self):
        """is_available should reflect status."""
        player = TournamentPlayer(status=PlayerStatus.ACTIVE)
        assert player.is_available is True
        
        player.status = PlayerStatus.ELIMINATED
        assert player.is_available is False
    
    def test_update_elo(self):
        """update_elo should update rating and adjust K-factor."""
        player = TournamentPlayer(elo_rating=1500)
        player.stats.games_played = 5
        
        player.update_elo(1550)
        assert player.elo_rating == 1550
        assert player.elo_k_factor == 32  # Still new player
        
        player.stats.games_played = 35
        player.update_elo(1600)
        assert player.elo_k_factor == 16  # Experienced player
    
    def test_record_match(self):
        """record_match should add to history."""
        player = TournamentPlayer()
        assert len(player.match_history) == 0
        
        player.record_match("match-001")
        assert "match-001" in player.match_history
    
    def test_serialization_roundtrip(self):
        """Player should serialize and deserialize correctly."""
        player = TournamentPlayer(
            name="Test Player",
            provider_name="openai",
            model_name="gpt-4",
            elo_rating=1650,
            persona=StylePersona.AGGRESSIVE,
            temperature=0.8,
        )
        player.stats.games_played = 5
        player.stats.wins = 3
        player.record_match("match-001")
        
        data = player.to_dict()
        restored = TournamentPlayer.from_dict(data)
        
        assert restored.name == player.name
        assert restored.elo_rating == player.elo_rating
        assert restored.persona == player.persona
        assert restored.temperature == player.temperature
        assert restored.stats.wins == 3
        assert "match-001" in restored.match_history
    
    def test_hash_by_id(self):
        """Players should hash by ID for set operations."""
        player1 = TournamentPlayer(id="abc123")
        player2 = TournamentPlayer(id="abc123")
        player3 = TournamentPlayer(id="xyz789")
        
        assert hash(player1) == hash(player2)
        assert hash(player1) != hash(player3)
    
    def test_equality_by_id(self):
        """Players should be equal if IDs match."""
        player1 = TournamentPlayer(id="abc123", name="Player 1")
        player2 = TournamentPlayer(id="abc123", name="Player 2")
        player3 = TournamentPlayer(id="xyz789", name="Player 1")
        
        assert player1 == player2
        assert player1 != player3
    
    def test_repr(self):
        """repr should be informative."""
        player = TournamentPlayer(id="abc", name="Test", elo_rating=1600)
        r = repr(player)
        assert "abc" in r
        assert "Test" in r
        assert "1600" in r


class TestCreatePlayerFromProvider:
    """Tests for factory function."""
    
    def test_create_with_defaults(self):
        """Should create player with defaults."""
        mock_provider = Mock()
        player = create_player_from_provider(
            provider=mock_provider,
            provider_name="openai",
            model_name="gpt-4",
        )
        
        assert player.provider == mock_provider
        assert player.provider_name == "openai"
        assert player.model_name == "gpt-4"
        assert player.elo_rating == 1500
        assert player.persona == StylePersona.NEUTRAL
    
    def test_create_with_custom_name(self):
        """Should use custom name if provided."""
        mock_provider = Mock()
        player = create_player_from_provider(
            provider=mock_provider,
            provider_name="openai",
            model_name="gpt-4",
            name="GPT-4 Turbo",
        )
        
        assert player.name == "GPT-4 Turbo"
    
    def test_create_with_persona(self):
        """Should set persona correctly."""
        mock_provider = Mock()
        player = create_player_from_provider(
            provider=mock_provider,
            provider_name="anthropic",
            model_name="claude-3",
            persona=StylePersona.KASPAROV,
            elo_rating=1700,
        )
        
        assert player.persona == StylePersona.KASPAROV
        assert player.elo_rating == 1700


class TestPlayerStatsPerformanceScore:
    """Tests for composite performance score calculation."""
    
    def test_perfect_performance(self):
        """High wins, low ACL, no illegals = high score."""
        stats = PlayerStats(
            games_played=10,
            wins=9,
            draws=1,
            losses=0,
            total_moves=400,
            illegal_move_attempts=0,
            avg_centipawn_loss=15.0,
            brilliancies=3,
        )
        
        score = stats.performance_score
        assert score > 70  # Should be high
    
    def test_poor_performance(self):
        """Low wins, high ACL, many illegals = low score."""
        stats = PlayerStats(
            games_played=10,
            wins=1,
            draws=1,
            losses=8,
            total_moves=400,
            illegal_move_attempts=40,  # 10% illegal rate
            avg_centipawn_loss=80.0,
            brilliancies=0,
        )
        
        score = stats.performance_score
        assert score < 40  # Should be low
    
    def test_zero_games_zero_score(self):
        """Zero games should give zero score."""
        stats = PlayerStats()
        assert stats.performance_score == 0.0
