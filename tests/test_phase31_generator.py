"""
tests/test_phase31_generator.py

Tests for Phase 3.1 generator enhancements:
- RetryStrategy and RetryConfig
- GenerationProgress and callbacks
- Batch generation
- Caching and statistics
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import time

from core.generator import (
    CaissaGenerator,
    RetryStrategy,
    RetryConfig,
    GenerationProgress,
    GenerationResult,
    BatchResult,
    GenerationStats,
    GenerationQuality,
    GenerationStage,
    CacheEntry,
)
from core.prompt_manager import GameContext, GameEra, GameTheme


class TestRetryConfig(unittest.TestCase):
    """Tests for RetryConfig class."""

    def test_immediate_delay(self):
        """Immediate strategy should return 0 delay."""
        config = RetryConfig(strategy=RetryStrategy.IMMEDIATE)
        delay = config.get_delay(1)
        self.assertEqual(delay, 0)

    def test_exponential_backoff(self):
        """Exponential strategy should double delay each attempt."""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay=1.0,
            max_delay=30.0,
            jitter=0,
        )
        delay_1 = config.get_delay(1)
        delay_2 = config.get_delay(2)
        delay_3 = config.get_delay(3)

        self.assertAlmostEqual(delay_1, 2.0, places=1)  # 1 * 2^1
        self.assertAlmostEqual(delay_2, 4.0, places=1)  # 1 * 2^2
        self.assertAlmostEqual(delay_3, 8.0, places=1)  # 1 * 2^3

    def test_linear_backoff(self):
        """Linear strategy should increase linearly."""
        config = RetryConfig(
            strategy=RetryStrategy.LINEAR,
            base_delay=2.0,
            max_delay=30.0,
            jitter=0,
        )
        delay_1 = config.get_delay(1)
        delay_2 = config.get_delay(2)
        delay_3 = config.get_delay(3)

        self.assertAlmostEqual(delay_1, 2.0, places=1)
        self.assertAlmostEqual(delay_2, 4.0, places=1)
        self.assertAlmostEqual(delay_3, 6.0, places=1)

    def test_max_delay_cap(self):
        """Delay should be capped at max_delay."""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay=1.0,
            max_delay=10.0,
            jitter=0,
        )
        # 2^10 = 1024, should be capped at 10
        delay = config.get_delay(10)
        self.assertLessEqual(delay, 10.0)


class TestGenerationProgress(unittest.TestCase):
    """Tests for GenerationProgress class."""

    def test_initial_state(self):
        """Progress should start at initialization stage."""
        progress = GenerationProgress()
        self.assertEqual(progress.stage, GenerationStage.INITIALIZATION)
        self.assertEqual(progress.current_move, 0)
        self.assertEqual(progress.attempts, 0)
        self.assertEqual(len(progress.errors), 0)

    def test_elapsed_time(self):
        """Elapsed time should increase."""
        progress = GenerationProgress()
        time.sleep(0.1)
        elapsed = progress.elapsed_time
        self.assertGreater(elapsed, 0.09)

    def test_progress_percent(self):
        """Progress percent should calculate correctly."""
        progress = GenerationProgress(
            current_move=10,
            total_moves_expected=40,
        )
        self.assertEqual(progress.progress_percent, 25.0)

    def test_progress_percent_zero_total(self):
        """Progress percent should be 0 when total is 0."""
        progress = GenerationProgress(
            current_move=5,
            total_moves_expected=0,
        )
        self.assertEqual(progress.progress_percent, 0.0)

    def test_to_dict(self):
        """to_dict should return proper dictionary."""
        progress = GenerationProgress(
            stage=GenerationStage.LLM_GENERATION,
            current_move=5,
            total_moves_expected=40,
        )
        result = progress.to_dict()
        self.assertEqual(result["stage"], "llm_generation")
        self.assertEqual(result["current_move"], 5)


class TestGenerationStats(unittest.TestCase):
    """Tests for GenerationStats class."""

    def test_initial_stats(self):
        """Stats should start at zero."""
        stats = GenerationStats()
        self.assertEqual(stats.total_games, 0)
        self.assertEqual(stats.successful_games, 0)
        self.assertEqual(stats.success_rate, 0.0)

    def test_record_successful_game(self):
        """Recording successful game should update stats."""
        stats = GenerationStats()
        stats.record_game(
            success=True,
            moves=["e4", "e5", "Nf3"],
            retries=1,
            time_taken=5.0,
            beauty_score=75.0,
            style="romantic",
            theme="queen_sacrifice",
        )
        self.assertEqual(stats.total_games, 1)
        self.assertEqual(stats.successful_games, 1)
        self.assertEqual(stats.total_moves, 3)
        self.assertEqual(stats.average_beauty_score, 75.0)
        self.assertEqual(stats.styles_used["romantic"], 1)

    def test_record_failed_game(self):
        """Recording failed game should update stats."""
        stats = GenerationStats()
        stats.record_game(
            success=False,
            moves=[],
            retries=3,
            time_taken=10.0,
        )
        self.assertEqual(stats.total_games, 1)
        self.assertEqual(stats.failed_games, 1)
        self.assertEqual(stats.success_rate, 0.0)

    def test_success_rate_calculation(self):
        """Success rate should be calculated correctly."""
        stats = GenerationStats()
        stats.record_game(True, ["e4"], 0, 1.0)
        stats.record_game(True, ["e4"], 0, 1.0)
        stats.record_game(False, [], 0, 1.0)
        self.assertAlmostEqual(stats.success_rate, 2/3, places=3)


class TestBatchResult(unittest.TestCase):
    """Tests for BatchResult class."""

    def test_success_rate(self):
        """Success rate should calculate correctly."""
        result = BatchResult(
            total_requested=10,
            successful=7,
            failed=3,
        )
        self.assertAlmostEqual(result.success_rate, 0.7, places=3)

    def test_average_time_per_game(self):
        """Average time should calculate correctly."""
        result = BatchResult(
            total_requested=10,
            successful=5,
            total_time=50.0,
        )
        self.assertEqual(result.average_time_per_game, 10.0)

    def test_summary_format(self):
        """Summary should return formatted string."""
        result = BatchResult(
            total_requested=10,
            successful=8,
            failed=2,
            total_time=80.0,
        )
        summary = result.summary()
        self.assertIn("8/10", summary)
        self.assertIn("80.0%", summary)


class TestCacheEntry(unittest.TestCase):
    """Tests for CacheEntry class."""

    def test_cache_entry_creation(self):
        """Cache entry should store FEN and move."""
        entry = CacheEntry(
            fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            move="e4",
            evaluation=20.0,
        )
        self.assertEqual(entry.move, "e4")
        self.assertEqual(entry.evaluation, 20.0)
        self.assertIsNotNone(entry.timestamp)


class TestGeneratorAdvancedMethods(unittest.TestCase):
    """Tests for CaissaGenerator advanced methods."""

    def setUp(self):
        """Set up mock generator."""
        with patch('core.generator.StockfishClient'):
            with patch('core.generator.BeautyEvaluator'):
                self.mock_provider = Mock()
                self.generator = CaissaGenerator(
                    provider=self.mock_provider,
                    max_retries=3
                )

    def test_set_retry_config(self):
        """set_retry_config should update configuration."""
        config = RetryConfig(
            strategy=RetryStrategy.ADAPTIVE,
            max_retries=5,
        )
        self.generator.set_retry_config(config)
        self.assertEqual(self.generator.max_retries, 5)

    def test_progress_callback(self):
        """Progress callback should be called."""
        callback_called = []

        def callback(progress):
            callback_called.append(progress)

        self.generator.set_progress_callback(callback)
        self.assertEqual(self.generator._progress_callback, callback)

    def test_cache_operations(self):
        """Cache operations should work correctly."""
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        
        # Cache a move
        self.generator.cache_move(fen, "e5", evaluation=0.0)
        
        # Retrieve cached move
        cached = self.generator.get_cached_move(fen)
        self.assertEqual(cached, "e5")
        
        # Clear cache
        count = self.generator.clear_cache()
        self.assertEqual(count, 1)
        
        # Cache should be empty
        cached = self.generator.get_cached_move(fen)
        self.assertIsNone(cached)

    def test_get_stats(self):
        """get_stats should return GenerationStats."""
        stats = self.generator.get_stats()
        self.assertIsInstance(stats, GenerationStats)

    def test_reset_stats(self):
        """reset_stats should reset to initial state."""
        self.generator._stats.total_games = 10
        self.generator.reset_stats()
        self.assertEqual(self.generator._stats.total_games, 0)


class TestGenerationQuality(unittest.TestCase):
    """Tests for GenerationQuality enum."""

    def test_quality_levels(self):
        """All quality levels should be defined."""
        self.assertEqual(GenerationQuality.EXCELLENT.value, "excellent")
        self.assertEqual(GenerationQuality.GOOD.value, "good")
        self.assertEqual(GenerationQuality.ACCEPTABLE.value, "acceptable")
        self.assertEqual(GenerationQuality.POOR.value, "poor")
        self.assertEqual(GenerationQuality.FAILED.value, "failed")


if __name__ == "__main__":
    unittest.main()
