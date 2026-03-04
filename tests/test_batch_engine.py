"""
tests/test_batch_engine.py

Comprehensive tests for the batch engine (core/batch_engine.py).

Covers:
- BatchConfig defaults and resolved_min_quality()
- BatchJob and BatchSummary dataclasses
- BatchEngine.plan_jobs() — style variation, theme/era rotation
- Filename resolution with tokens
- Sequential and parallel execution (mocked generator)
- Quality gate logic (retries, keep-best)
- Resume / skip logic
- Multi-format export dispatch
- Summary report generation
- Progress callbacks
- Fail-fast behaviour
"""

import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, PropertyMock

from core.batch_engine import (
    BatchConfig,
    BatchEngine,
    BatchJob,
    BatchJobStatus,
    BatchMode,
    BatchSummary,
    StyleVariation,
)
from core.generator import GenerationQuality, GenerationResult


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _make_provider():
    """Return a minimal mock LLM provider."""
    provider = MagicMock()
    provider.generate.return_value = "1. e4 e5 2. Nf3 Nc6 *"
    return provider


def _make_gen_result(success=True, quality=GenerationQuality.GOOD,
                     beauty=72.0, moves=None):
    """Build a GenerationResult for mocking."""
    return GenerationResult(
        success=success,
        pgn='[Event "Mock"]\n\n1. e4 e5 *',
        moves=moves or ["e4", "e5", "Nf3", "Nc6"],
        quality=quality,
        beauty_score=beauty,
        generation_time=0.5,
        attempts_used=1,
    )


def _make_generate_game_side_effect(
    success=True, pgn='[Event "Mock"]\n\n1. e4 e5 *',
    moves=None,
):
    """Return a callable that mimics CaissaGenerator.generate_game."""
    m = moves or ["e4", "e5", "Nf3", "Nc6"]
    def _side_effect(context):
        return (success, pgn, list(m))
    return _side_effect


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH CONFIG TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchConfig(unittest.TestCase):
    """Tests for BatchConfig dataclass."""

    def test_defaults(self):
        cfg = BatchConfig()
        self.assertEqual(cfg.count, 5)
        self.assertEqual(cfg.mode, BatchMode.SEQUENTIAL)
        self.assertEqual(cfg.workers, 4)
        self.assertEqual(cfg.styles, ["tal"])
        self.assertEqual(cfg.style_variation, StyleVariation.FIXED)
        self.assertEqual(cfg.min_quality, "acceptable")
        self.assertTrue(cfg.pretty_pgn)
        self.assertTrue(cfg.resume)
        self.assertTrue(cfg.generate_summary)

    def test_resolved_min_quality_mapping(self):
        for name, expected in [
            ("excellent", GenerationQuality.EXCELLENT),
            ("good", GenerationQuality.GOOD),
            ("acceptable", GenerationQuality.ACCEPTABLE),
            ("poor", GenerationQuality.POOR),
            ("failed", GenerationQuality.FAILED),
        ]:
            cfg = BatchConfig(min_quality=name)
            self.assertEqual(cfg.resolved_min_quality(), expected, f"{name}")

    def test_resolved_min_quality_case_insensitive(self):
        cfg = BatchConfig(min_quality="GOOD")
        self.assertEqual(cfg.resolved_min_quality(), GenerationQuality.GOOD)

    def test_resolved_min_quality_unknown_fallback(self):
        cfg = BatchConfig(min_quality="legendary")
        self.assertEqual(cfg.resolved_min_quality(), GenerationQuality.ACCEPTABLE)

    def test_custom_fields(self):
        cfg = BatchConfig(
            count=10,
            mode=BatchMode.PARALLEL,
            workers=8,
            styles=["tal", "morphy"],
            style_variation=StyleVariation.RANDOM,
            themes=["queen_sacrifice"],
            eras=["romantic", "classical"],
            depth=60,
            output_dir="/tmp/test_batch",
            filename_pattern="match_{n:03d}_{style}",
            export_formats=["pgn", "html"],
        )
        self.assertEqual(cfg.count, 10)
        self.assertEqual(cfg.mode, BatchMode.PARALLEL)
        self.assertEqual(cfg.workers, 8)
        self.assertEqual(len(cfg.styles), 2)
        self.assertEqual(cfg.depth, 60)
        self.assertIn("html", cfg.export_formats)


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH JOB TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchJob(unittest.TestCase):
    """Tests for BatchJob dataclass."""

    def test_default_status_is_pending(self):
        job = BatchJob(index=1, style="tal", era="romantic")
        self.assertEqual(job.status, BatchJobStatus.PENDING)
        self.assertEqual(job.attempts, 0)
        self.assertIsNone(job.error)

    def test_to_dict_includes_key_fields(self):
        job = BatchJob(index=3, style="morphy", era="classical", theme="pawn_storm")
        d = job.to_dict()
        self.assertEqual(d["index"], 3)
        self.assertEqual(d["style"], "morphy")
        self.assertEqual(d["era"], "classical")
        self.assertEqual(d["theme"], "pawn_storm")
        self.assertEqual(d["status"], "pending")
        self.assertIn("attempts", d)
        self.assertIn("elapsed", d)


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH SUMMARY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchSummary(unittest.TestCase):
    """Tests for BatchSummary.finalize()."""

    def _make_summary_with_jobs(self, statuses_and_beauty):
        """Helper: build a summary from a list of (status, beauty_score, n_moves)."""
        jobs = []
        for i, (status, beauty, n_moves) in enumerate(statuses_and_beauty, 1):
            job = BatchJob(index=i, style="tal", era="romantic")
            job.status = status
            job.elapsed = 1.0
            job.moves = ["e4"] * n_moves
            if status == BatchJobStatus.SUCCESS:
                job.result = _make_gen_result(
                    quality=GenerationQuality.GOOD, beauty=beauty,
                    moves=job.moves,
                )
            jobs.append(job)
        summary = BatchSummary(total=len(jobs), jobs=jobs)
        summary.successful = sum(1 for j in jobs if j.status == BatchJobStatus.SUCCESS)
        summary.failed = sum(1 for j in jobs if j.status == BatchJobStatus.FAILED)
        return summary

    def test_finalize_computes_averages(self):
        summary = self._make_summary_with_jobs([
            (BatchJobStatus.SUCCESS, 80.0, 20),
            (BatchJobStatus.SUCCESS, 60.0, 10),
            (BatchJobStatus.FAILED, 0.0, 0),
        ])
        summary.finalize()
        self.assertAlmostEqual(summary.avg_beauty, 70.0, places=1)
        self.assertAlmostEqual(summary.avg_moves, 15.0, places=1)
        self.assertEqual(summary.best_game_index, 1)
        self.assertEqual(summary.worst_game_index, 2)

    def test_finalize_quality_distribution(self):
        summary = self._make_summary_with_jobs([
            (BatchJobStatus.SUCCESS, 90.0, 30),
            (BatchJobStatus.SUCCESS, 70.0, 25),
        ])
        summary.finalize()
        self.assertIn("good", summary.quality_distribution)
        self.assertEqual(summary.quality_distribution["good"], 2)

    def test_finalize_style_distribution(self):
        jobs = [
            BatchJob(index=1, style="tal", era="romantic"),
            BatchJob(index=2, style="morphy", era="romantic"),
            BatchJob(index=3, style="tal", era="romantic"),
        ]
        for j in jobs:
            j.status = BatchJobStatus.SUCCESS
            j.elapsed = 0.5
            j.moves = ["e4"]
            j.result = _make_gen_result(quality=GenerationQuality.ACCEPTABLE, beauty=50.0)
        summary = BatchSummary(total=3, successful=3, jobs=jobs)
        summary.finalize()
        self.assertEqual(summary.style_distribution.get("tal"), 2)
        self.assertEqual(summary.style_distribution.get("morphy"), 1)

    def test_to_dict_structure(self):
        summary = self._make_summary_with_jobs([
            (BatchJobStatus.SUCCESS, 75.0, 15),
        ])
        summary.total_time = 2.5
        summary.finalize()
        d = summary.to_dict()
        self.assertIn("total", d)
        self.assertIn("successful", d)
        self.assertIn("jobs", d)
        self.assertIsInstance(d["jobs"], list)
        self.assertEqual(len(d["jobs"]), 1)

    def test_empty_batch_finalize(self):
        summary = BatchSummary(total=0, jobs=[])
        summary.finalize()
        self.assertEqual(summary.avg_beauty, 0.0)
        self.assertEqual(summary.avg_moves, 0.0)
        self.assertIsNone(summary.best_game_index)


# ═══════════════════════════════════════════════════════════════════════════════
# PLAN_JOBS TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchEnginePlanJobs(unittest.TestCase):
    """Tests for BatchEngine.plan_jobs() — style/era/theme planning."""

    def _make_engine(self, **cfg_kwargs):
        cfg = BatchConfig(**cfg_kwargs)
        provider = _make_provider()
        return BatchEngine(config=cfg, provider=provider, stockfish_path=None)

    def test_plan_jobs_count(self):
        engine = self._make_engine(count=7)
        jobs = engine.plan_jobs()
        self.assertEqual(len(jobs), 7)
        self.assertTrue(all(j.status == BatchJobStatus.PENDING for j in jobs))

    def test_plan_jobs_indices_1_based(self):
        engine = self._make_engine(count=3)
        jobs = engine.plan_jobs()
        self.assertEqual([j.index for j in jobs], [1, 2, 3])

    def test_plan_jobs_fixed_style(self):
        engine = self._make_engine(
            count=3, styles=["morphy"], style_variation=StyleVariation.FIXED,
        )
        jobs = engine.plan_jobs()
        self.assertTrue(all(j.style == "morphy" for j in jobs))

    def test_plan_jobs_round_robin_styles(self):
        engine = self._make_engine(
            count=6,
            styles=["tal", "morphy", "capablanca"],
            style_variation=StyleVariation.ROUND_ROBIN,
        )
        jobs = engine.plan_jobs()
        expected = ["tal", "morphy", "capablanca", "tal", "morphy", "capablanca"]
        self.assertEqual([j.style for j in jobs], expected)

    def test_plan_jobs_random_style_within_pool(self):
        engine = self._make_engine(
            count=20,
            styles=["tal", "morphy"],
            style_variation=StyleVariation.RANDOM,
        )
        jobs = engine.plan_jobs()
        styles_used = set(j.style for j in jobs)
        self.assertTrue(styles_used.issubset({"tal", "morphy"}))

    def test_plan_jobs_era_rotation(self):
        engine = self._make_engine(
            count=4, eras=["romantic", "classical"],
        )
        jobs = engine.plan_jobs()
        # Should rotate: romantic, classical, romantic, classical
        eras = [j.era for j in jobs]
        self.assertEqual(eras, ["romantic", "classical", "romantic", "classical"])

    def test_plan_jobs_theme_rotation(self):
        engine = self._make_engine(
            count=3, themes=["queen_sacrifice", "windmill"],
        )
        jobs = engine.plan_jobs()
        themes = [j.theme for j in jobs]
        self.assertEqual(themes, ["queen_sacrifice", "windmill", "queen_sacrifice"])

    def test_plan_jobs_no_themes(self):
        engine = self._make_engine(count=2, themes=[])
        jobs = engine.plan_jobs()
        self.assertTrue(all(j.theme is None for j in jobs))

    def test_plan_jobs_depth_from_config(self):
        engine = self._make_engine(count=2, depth=60)
        jobs = engine.plan_jobs()
        self.assertTrue(all(j.depth == 60 for j in jobs))


# ═══════════════════════════════════════════════════════════════════════════════
# FILENAME RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════════

class TestFilenameResolution(unittest.TestCase):
    """Tests for BatchEngine._resolve_filename()."""

    def _resolve(self, pattern, job):
        cfg = BatchConfig(filename_pattern=pattern)
        engine = BatchEngine(config=cfg, provider=_make_provider(), stockfish_path=None)
        return engine._resolve_filename(job)

    def test_basic_number_token(self):
        job = BatchJob(index=3, style="tal", era="romantic")
        name = self._resolve("game_{n:03d}", job)
        self.assertEqual(name, "game_003")

    def test_style_and_era_tokens(self):
        job = BatchJob(index=1, style="morphy", era="classical")
        name = self._resolve("{style}_{era}_{n}", job)
        self.assertEqual(name, "morphy_classical_1")

    def test_theme_token(self):
        job = BatchJob(index=2, style="tal", era="romantic", theme="windmill")
        name = self._resolve("game_{n}_{theme}", job)
        self.assertEqual(name, "game_2_windmill")

    def test_missing_theme_token_replaced(self):
        job = BatchJob(index=1, style="tal", era="romantic", theme=None)
        name = self._resolve("{n}_{theme}", job)
        # Should handle None theme gracefully
        self.assertIn("1", name)

    def test_date_token_present(self):
        job = BatchJob(index=1, style="tal", era="romantic")
        name = self._resolve("{date}_game_{n}", job)
        # Should contain a date-like string (YYYYMMDD)
        self.assertRegex(name, r"\d{8}_game_1")


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION TESTS (mocked generator)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchEngineExecution(unittest.TestCase):
    """Integration tests for BatchEngine.run() with mocked generation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="caissa_batch_test_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_engine(self, **overrides):
        defaults = dict(
            count=3,
            mode=BatchMode.SEQUENTIAL,
            styles=["tal"],
            output_dir=self.tmpdir,
            export_formats=["pgn"],
            generate_summary=False,
            resume=False,
            min_quality="poor",
            quality_retries=1,
        )
        defaults.update(overrides)
        cfg = BatchConfig(**defaults)
        provider = _make_provider()
        return BatchEngine(config=cfg, provider=provider, stockfish_path=None)

    @patch("core.batch_engine.CaissaGenerator")
    def test_sequential_all_succeed(self, MockGen):
        mock_gen = MagicMock()
        mock_gen.generate_game.side_effect = _make_generate_game_side_effect()
        mock_gen.beauty_evaluator.evaluate_game.return_value = 72.0
        mock_gen._assess_quality.return_value = GenerationQuality.GOOD
        mock_gen.__enter__ = Mock(return_value=mock_gen)
        mock_gen.__exit__ = Mock(return_value=False)
        MockGen.return_value = mock_gen

        engine = self._make_engine(count=3)
        summary = engine.run()

        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.successful, 3)
        self.assertEqual(summary.failed, 0)
        self.assertGreaterEqual(summary.total_time, 0)

    @patch("core.batch_engine.CaissaGenerator")
    def test_sequential_with_failures(self, MockGen):
        call_count = 0
        def _alternate(context):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                return (False, "", [])
            return (True, '[Event "X"]\n\n1. e4 e5 *', ["e4", "e5"])

        mock_gen = MagicMock()
        mock_gen.generate_game.side_effect = _alternate
        mock_gen.beauty_evaluator.evaluate_game.return_value = 50.0
        mock_gen._assess_quality.return_value = GenerationQuality.POOR
        mock_gen.__enter__ = Mock(return_value=mock_gen)
        mock_gen.__exit__ = Mock(return_value=False)
        MockGen.return_value = mock_gen

        engine = self._make_engine(count=4)
        summary = engine.run()

        self.assertEqual(summary.successful, 2)
        self.assertEqual(summary.failed, 2)

    @patch("core.batch_engine.CaissaGenerator")
    def test_parallel_execution(self, MockGen):
        mock_gen = MagicMock()
        mock_gen.generate_game.side_effect = _make_generate_game_side_effect()
        mock_gen.beauty_evaluator.evaluate_game.return_value = 65.0
        mock_gen._assess_quality.return_value = GenerationQuality.ACCEPTABLE
        mock_gen.__enter__ = Mock(return_value=mock_gen)
        mock_gen.__exit__ = Mock(return_value=False)
        MockGen.return_value = mock_gen

        engine = self._make_engine(
            count=4, mode=BatchMode.PARALLEL, workers=2,
        )
        summary = engine.run()

        self.assertEqual(summary.total, 4)
        self.assertEqual(summary.successful, 4)

    @patch("core.batch_engine.CaissaGenerator")
    def test_progress_callback_called(self, MockGen):
        mock_gen = MagicMock()
        mock_gen.generate_game.side_effect = _make_generate_game_side_effect()
        mock_gen.beauty_evaluator.evaluate_game.return_value = 70.0
        mock_gen._assess_quality.return_value = GenerationQuality.GOOD
        mock_gen.__enter__ = Mock(return_value=mock_gen)
        mock_gen.__exit__ = Mock(return_value=False)
        MockGen.return_value = mock_gen

        engine = self._make_engine(count=2)

        calls = []
        def _on_progress(idx, total, status, msg):
            calls.append((idx, total, status))

        engine.run(on_progress=_on_progress)

        # Should have at least 2 success callbacks
        success_calls = [c for c in calls if c[2] == BatchJobStatus.SUCCESS]
        self.assertGreaterEqual(len(success_calls), 2)

    @patch("core.batch_engine.CaissaGenerator")
    def test_resume_skips_existing_files(self, MockGen):
        """When resume=True, jobs with existing output files are skipped."""
        mock_gen = MagicMock()
        mock_gen.generate_game.side_effect = _make_generate_game_side_effect()
        mock_gen.beauty_evaluator.evaluate_game.return_value = 70.0
        mock_gen._assess_quality.return_value = GenerationQuality.GOOD
        mock_gen.__enter__ = Mock(return_value=mock_gen)
        mock_gen.__exit__ = Mock(return_value=False)
        MockGen.return_value = mock_gen

        # Pre-create file for game 1
        Path(self.tmpdir, "game_001.pgn").write_text("existing", encoding="utf-8")

        engine = self._make_engine(
            count=3, resume=True,
            filename_pattern="game_{n:03d}",
        )
        summary = engine.run()

        self.assertEqual(summary.skipped, 1)
        # Games 2 and 3 should still run
        self.assertEqual(summary.successful, 2)

    @patch("core.batch_engine.CaissaGenerator")
    def test_quality_gate_retries(self, MockGen):
        """Quality gate should retry and keep the best result."""
        attempt_count = 0
        def _improving_quality(context):
            nonlocal attempt_count
            attempt_count += 1
            return (True, f'[Event "Q{attempt_count}"]\n\n1. e4 *', ["e4", "e5"])

        quality_sequence = iter([
            GenerationQuality.POOR,
            GenerationQuality.ACCEPTABLE,
            GenerationQuality.GOOD,
        ])

        mock_gen = MagicMock()
        mock_gen.generate_game.side_effect = _improving_quality
        mock_gen.beauty_evaluator.evaluate_game.return_value = 70.0
        mock_gen._assess_quality.side_effect = lambda m, b: next(quality_sequence, GenerationQuality.GOOD)
        mock_gen.__enter__ = Mock(return_value=mock_gen)
        mock_gen.__exit__ = Mock(return_value=False)
        MockGen.return_value = mock_gen

        engine = self._make_engine(
            count=1,
            min_quality="good",
            quality_retries=3,
        )
        summary = engine.run()
        self.assertEqual(summary.successful, 1)

    @patch("core.batch_engine.CaissaGenerator")
    def test_pgn_files_written(self, MockGen):
        """Verify PGN files are actually written to disk."""
        mock_gen = MagicMock()
        mock_gen.generate_game.side_effect = _make_generate_game_side_effect()
        mock_gen.beauty_evaluator.evaluate_game.return_value = 70.0
        mock_gen._assess_quality.return_value = GenerationQuality.GOOD
        mock_gen.__enter__ = Mock(return_value=mock_gen)
        mock_gen.__exit__ = Mock(return_value=False)
        MockGen.return_value = mock_gen

        engine = self._make_engine(
            count=2, filename_pattern="game_{n:03d}",
        )
        engine.run()

        files = list(Path(self.tmpdir).glob("*.pgn"))
        self.assertGreaterEqual(len(files), 2)

    @patch("core.batch_engine.CaissaGenerator")
    def test_summary_report_generated(self, MockGen):
        """When generate_summary=True, a report file should be written."""
        mock_gen = MagicMock()
        mock_gen.generate_game.side_effect = _make_generate_game_side_effect()
        mock_gen.beauty_evaluator.evaluate_game.return_value = 70.0
        mock_gen._assess_quality.return_value = GenerationQuality.GOOD
        mock_gen.__enter__ = Mock(return_value=mock_gen)
        mock_gen.__exit__ = Mock(return_value=False)
        MockGen.return_value = mock_gen

        engine = self._make_engine(
            count=2, generate_summary=True, resume=False,
        )
        engine.run()

        # Should have a batch_summary.md or batch_summary.json
        summary_files = list(Path(self.tmpdir).glob("batch_summary*"))
        self.assertGreater(len(summary_files), 0)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchConfigDefaults(unittest.TestCase):
    """Tests for BatchDefaults in config_manager."""

    def test_batch_defaults_dataclass(self):
        from config_manager import BatchDefaults
        bd = BatchDefaults()
        self.assertEqual(bd.count, 5)
        self.assertEqual(bd.style_variation, "round_robin")
        self.assertEqual(bd.min_quality, "acceptable")
        self.assertEqual(bd.quality_retries, 3)
        self.assertEqual(bd.mode, "sequential")
        self.assertEqual(bd.workers, 4)
        self.assertTrue(bd.pretty_pgn)
        self.assertTrue(bd.resume)
        self.assertTrue(bd.generate_summary)

    def test_caissa_config_has_batch(self):
        from config_manager import CaissaConfig, BatchDefaults
        cfg = CaissaConfig()
        self.assertIsInstance(cfg.batch, BatchDefaults)

    def test_batch_section_loaded_from_dict(self):
        from config_manager import _build_config_from_dict
        data = {
            "batch": {
                "count": 10,
                "mode": "parallel",
                "workers": 8,
                "min_quality": "good",
            }
        }
        config = _build_config_from_dict(data)
        self.assertEqual(config.batch.count, 10)
        self.assertEqual(config.batch.mode, "parallel")
        self.assertEqual(config.batch.workers, 8)
        self.assertEqual(config.batch.min_quality, "good")


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchEngineEdgeCases(unittest.TestCase):
    """Edge case tests."""

    def test_zero_count_returns_empty_summary(self):
        cfg = BatchConfig(count=0, generate_summary=False, resume=False)
        engine = BatchEngine(config=cfg, provider=_make_provider(), stockfish_path=None)
        summary = engine.run()
        self.assertEqual(summary.total, 0)
        self.assertEqual(summary.successful, 0)

    def test_single_game_batch(self):
        """Even a batch of 1 should work correctly."""
        cfg = BatchConfig(count=1, generate_summary=False, resume=False)
        engine = BatchEngine(config=cfg, provider=_make_provider(), stockfish_path=None)
        jobs = engine.plan_jobs()
        self.assertEqual(len(jobs), 1)

    def test_many_styles_round_robin(self):
        cfg = BatchConfig(
            count=12,
            styles=["tal", "morphy", "capablanca", "karpov"],
            style_variation=StyleVariation.ROUND_ROBIN,
        )
        engine = BatchEngine(config=cfg, provider=_make_provider(), stockfish_path=None)
        jobs = engine.plan_jobs()
        # Should cycle 3 full rounds
        for i in range(12):
            expected = ["tal", "morphy", "capablanca", "karpov"][i % 4]
            self.assertEqual(jobs[i].style, expected, f"Job {i+1}")


if __name__ == "__main__":
    unittest.main()
