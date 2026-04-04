"""
Tests for ELO Calculator Module (core/elo_calculator.py)

Tests cover:
- Expected score calculation
- ELO rating changes for wins/losses/draws
- K-factor strategies
- Performance rating calculation
- ELO leaderboard management
- Edge cases and boundary conditions

Author: CAISSA Team
Version: 0.5.0
"""

import pytest
from core.elo_calculator import (
    EloCalculator,
    EloLeaderboard,
    EloChange,
    GameResult,
    KFactorStrategy,
    calculate_elo_change,
    estimate_win_probability,
)


class TestExpectedScore:
    """Tests for expected score calculation."""
    
    def test_equal_ratings_expect_half(self):
        """Equal ratings should yield 0.5 expected score."""
        calc = EloCalculator()
        expected = calc.expected_score(1500, 1500)
        assert expected == pytest.approx(0.5, abs=0.001)
    
    def test_higher_rating_expects_more(self):
        """Higher rated player should expect > 0.5."""
        calc = EloCalculator()
        expected = calc.expected_score(1600, 1400)
        assert expected > 0.5
        assert expected < 1.0
    
    def test_lower_rating_expects_less(self):
        """Lower rated player should expect < 0.5."""
        calc = EloCalculator()
        expected = calc.expected_score(1400, 1600)
        assert expected < 0.5
        assert expected > 0.0
    
    def test_400_point_advantage(self):
        """400 point advantage should yield ~0.91 expected score."""
        calc = EloCalculator()
        expected = calc.expected_score(1900, 1500)
        assert expected == pytest.approx(0.909, abs=0.01)
    
    def test_symmetric_expectations(self):
        """Expected scores should sum to 1.0."""
        calc = EloCalculator()
        e1 = calc.expected_score(1600, 1400)
        e2 = calc.expected_score(1400, 1600)
        assert e1 + e2 == pytest.approx(1.0, abs=0.001)


class TestEloCalculation:
    """Tests for ELO change calculation."""
    
    def test_white_wins_gains_rating(self):
        """White winning should gain rating points."""
        calc = EloCalculator()
        change = calc.calculate(1500, 1500, GameResult.WHITE_WINS)
        assert change.white_new > change.white_old
        assert change.black_new < change.black_old
    
    def test_black_wins_gains_rating(self):
        """Black winning should gain rating points."""
        calc = EloCalculator()
        change = calc.calculate(1500, 1500, GameResult.BLACK_WINS)
        assert change.black_new > change.black_old
        assert change.white_new < change.white_old
    
    def test_draw_minimal_change(self):
        """Draw between equal players should have minimal change."""
        calc = EloCalculator()
        change = calc.calculate(1500, 1500, GameResult.DRAW)
        assert abs(change.white_delta) <= 1
        assert abs(change.black_delta) <= 1
    
    def test_upset_win_gains_more(self):
        """Lower-rated player winning gains more points."""
        calc = EloCalculator()
        change = calc.calculate(1300, 1700, GameResult.WHITE_WINS)
        assert change.white_delta > 20  # Significant gain for upset
    
    def test_expected_win_gains_less(self):
        """Higher-rated player winning gains fewer points."""
        calc = EloCalculator()
        change = calc.calculate(1700, 1300, GameResult.WHITE_WINS)
        assert change.white_delta < 16  # Minimal gain for expected win
    
    def test_forfeit_treated_as_win(self):
        """Forfeit should be treated like a normal win."""
        calc = EloCalculator()
        change1 = calc.calculate(1500, 1500, GameResult.WHITE_WINS)
        change2 = calc.calculate(1500, 1500, GameResult.FORFEIT_WHITE)
        assert change1.white_delta == change2.white_delta
    
    def test_in_progress_no_change(self):
        """In-progress game should have no rating change."""
        calc = EloCalculator()
        change = calc.calculate(1500, 1500, GameResult.IN_PROGRESS)
        assert change.white_delta == 0
        assert change.black_delta == 0
    
    def test_rating_floor(self):
        """Rating should not go below minimum."""
        calc = EloCalculator(min_rating=100)
        change = calc.calculate(100, 2000, GameResult.BLACK_WINS)
        assert change.white_new >= 100
    
    def test_rating_ceiling(self):
        """Rating should not exceed maximum."""
        calc = EloCalculator(max_rating=3000)
        change = calc.calculate(2999, 500, GameResult.WHITE_WINS)
        assert change.white_new <= 3000


class TestKFactorStrategies:
    """Tests for K-factor determination strategies."""
    
    def test_fixed_k_factor(self):
        """Fixed strategy should always return same K."""
        calc = EloCalculator(k_factor=24, k_strategy=KFactorStrategy.FIXED)
        k = calc.get_k_factor(1500, 100)
        assert k == 24
    
    def test_fide_high_rating_low_k(self):
        """FIDE: High-rated players get K=10."""
        calc = EloCalculator(k_strategy=KFactorStrategy.FIDE)
        k = calc.get_k_factor(2500, 100)
        assert k == 10
    
    def test_fide_new_player_high_k(self):
        """FIDE: New players (<30 games) get K=40."""
        calc = EloCalculator(k_strategy=KFactorStrategy.FIDE)
        k = calc.get_k_factor(1500, 10)
        assert k == 40
    
    def test_dynamic_reduces_with_games(self):
        """Dynamic K should reduce as player plays more games."""
        calc = EloCalculator(k_strategy=KFactorStrategy.DYNAMIC)
        k_new = calc.get_k_factor(1500, 5)
        k_experienced = calc.get_k_factor(1500, 200)
        assert k_new > k_experienced
    
    def test_k_override(self):
        """K-factor override should take precedence."""
        calc = EloCalculator(k_factor=32, k_strategy=KFactorStrategy.FIXED)
        k = calc.get_k_factor(1500, 50, k_override=16)
        assert k == 16


class TestPerformanceRating:
    """Tests for performance rating calculation."""
    
    def test_perfect_score(self):
        """Perfect score should yield ~400 above average."""
        calc = EloCalculator()
        performance = calc.performance_rating([1500, 1500, 1500], 3.0)
        assert performance == pytest.approx(1900, abs=50)
    
    def test_zero_score(self):
        """Zero score should yield ~400 below average."""
        calc = EloCalculator()
        performance = calc.performance_rating([1500, 1500, 1500], 0.0)
        assert performance == pytest.approx(1100, abs=50)
    
    def test_half_score(self):
        """50% score should match average opponent rating."""
        calc = EloCalculator()
        performance = calc.performance_rating([1500, 1500, 1500], 1.5)
        assert performance == pytest.approx(1500, abs=10)
    
    def test_empty_opponents(self):
        """Empty opponent list should return default rating."""
        calc = EloCalculator()
        performance = calc.performance_rating([], 0)
        assert performance == 1500


class TestEloLeaderboard:
    """Tests for ELO leaderboard management."""
    
    def test_initial_rating(self):
        """New players should have initial rating."""
        board = EloLeaderboard(initial_rating=1500)
        board.add_players(["p1", "p2"])
        assert board.get_rating("p1") == 1500
    
    def test_record_game_updates_ratings(self):
        """Recording a game should update both players' ratings."""
        board = EloLeaderboard()
        board.add_players(["p1", "p2"])
        
        initial_p1 = board.get_rating("p1")
        board.record_game("p1", "p2", GameResult.WHITE_WINS)
        
        assert board.get_rating("p1") > initial_p1
    
    def test_games_played_increments(self):
        """Games played should increment after each game."""
        board = EloLeaderboard()
        board.add_players(["p1", "p2"])
        
        assert board.get_games_played("p1") == 0
        board.record_game("p1", "p2", GameResult.DRAW)
        assert board.get_games_played("p1") == 1
        assert board.get_games_played("p2") == 1
    
    def test_rankings_sorted_by_rating(self):
        """Rankings should be sorted by rating descending."""
        board = EloLeaderboard()
        board.set_rating("p1", 1600)
        board.set_rating("p2", 1800)
        board.set_rating("p3", 1400)
        
        rankings = board.get_rankings()
        assert rankings[0][0] == "p2"
        assert rankings[1][0] == "p1"
        assert rankings[2][0] == "p3"
    
    def test_history_tracking(self):
        """Rating history should be tracked."""
        board = EloLeaderboard()
        board.add_players(["p1", "p2"])
        board.record_game("p1", "p2", GameResult.WHITE_WINS, "game1")
        
        history = board.get_history("p1")
        assert len(history) >= 1
    
    def test_serialization(self):
        """Leaderboard should serialize/deserialize correctly."""
        board = EloLeaderboard()
        board.add_players(["p1", "p2"])
        board.record_game("p1", "p2", GameResult.WHITE_WINS)
        
        data = board.to_dict()
        restored = EloLeaderboard.from_dict(data)
        
        assert restored.get_rating("p1") == board.get_rating("p1")
        assert restored.get_games_played("p1") == board.get_games_played("p1")


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_calculate_elo_change_simple(self):
        """Simple ELO change function should work."""
        new_white, new_black = calculate_elo_change(1500, 1500, GameResult.WHITE_WINS)
        assert new_white > 1500
        assert new_black < 1500
    
    def test_estimate_win_probability(self):
        """Win probability estimation should work."""
        prob = estimate_win_probability(1600, 1400)
        assert 0.5 < prob < 1.0


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""
    
    def test_very_high_rating_difference(self):
        """Should handle extreme rating differences."""
        calc = EloCalculator()
        change = calc.calculate(3000, 100, GameResult.BLACK_WINS)
        # Should still produce valid results
        assert change.white_new >= 100
        assert change.black_new <= 4000
    
    def test_double_forfeit(self):
        """Double forfeit should give both 0 points."""
        calc = EloCalculator()
        change = calc.calculate(1500, 1500, GameResult.DOUBLE_FORFEIT)
        # Both lose points for double forfeit
        assert change.white_new <= 1500
        assert change.black_new <= 1500
    
    def test_elo_change_summary(self):
        """EloChange summary should be formatted correctly."""
        calc = EloCalculator()
        change = calc.calculate(1500, 1500, GameResult.WHITE_WINS)
        summary = change.summary
        assert "White:" in summary
        assert "Black:" in summary
        assert "→" in summary


class TestRatingChangeHelpers:
    """Tests for rating change helper methods."""
    
    def test_rating_change_if_win(self):
        """Should calculate potential gain for winning."""
        calc = EloCalculator()
        delta = calc.rating_change_if_win(1500, 1600)
        assert delta > 0
    
    def test_rating_change_if_loss(self):
        """Should calculate potential loss for losing."""
        calc = EloCalculator()
        delta = calc.rating_change_if_loss(1500, 1400)
        assert delta < 0
    
    def test_rating_change_if_draw(self):
        """Should calculate change for draw."""
        calc = EloCalculator()
        delta_low = calc.rating_change_if_draw(1400, 1600)
        delta_high = calc.rating_change_if_draw(1600, 1400)
        # Lower-rated player gains from draw with higher-rated
        assert delta_low > 0
        assert delta_high < 0
