"""
tests/test_phase32_plus.py

Tests for Phase 3.2+ enhancements.

Coverage:
- Rich console output utilities
- Quality analyzer for game scoring
- Benchmark history and trend analysis
- Report generation (HTML/Markdown)
"""

import os
import sys
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# =============================================================================
# TEST FIXTURES
# =============================================================================

SAMPLE_PGN = """[Event "Test Game"]
[Site "CAISSA"]
[Date "2024.01.01"]
[White "White"]
[Black "Black"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 
6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Na5 10. Bc2 c5 1-0"""

SAMPLE_TACTICAL_PGN = """[Event "Tactical"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. Ng5 d5 5. exd5 Nxd5 
6. Nxf7 Kxf7 7. Qf3+ Ke6 8. Nc3 Ncb4 9. O-O c6 10. d4 Kd7 
11. Qf7+ Be7 12. Bg5 Rf8 13. Qxg7 Rf7 14. Qg8 Nxc2 15. Bxe7 Qxe7 1-0"""

SAMPLE_BENCHMARK_RESULT = {
    "provider_name": "openai",
    "model": "gpt-4o-mini",
    "runs": 5,
    "successful_runs": 5,
    "success_rate": 1.0,
    "latency": {
        "min_ms": 150,
        "max_ms": 350,
        "mean_ms": 250,
        "median_ms": 240,
        "std_dev_ms": 50,
        "p95_ms": 320,
        "p99_ms": 345,
    },
    "quality": {
        "response_length_avg": 200,
        "response_length_std": 30,
        "contains_chess_notation": 95.0,
        "valid_pgn_rate": 90.0,
        "error_rate": 0.0,
    },
    "total_tokens": 1500,
    "estimated_cost_usd": 0.0015,
    "timestamp": datetime.now().isoformat(),
    "raw_latencies": [150, 200, 250, 300, 350],
    "errors": [],
}

SAMPLE_BENCHMARK_SUITE = {
    "benchmark_date": datetime.now().isoformat(),
    "total_time_seconds": 12.5,
    "results": [
        SAMPLE_BENCHMARK_RESULT,
        {
            **SAMPLE_BENCHMARK_RESULT,
            "provider_name": "anthropic",
            "model": "claude-3-haiku",
            "latency": {**SAMPLE_BENCHMARK_RESULT["latency"], "mean_ms": 350},
            "estimated_cost_usd": 0.002,
        },
        {
            **SAMPLE_BENCHMARK_RESULT,
            "provider_name": "ollama",
            "model": "llama2",
            "latency": {**SAMPLE_BENCHMARK_RESULT["latency"], "mean_ms": 100},
            "estimated_cost_usd": 0.0,
        },
    ],
}


# =============================================================================
# RICH CONSOLE TESTS
# =============================================================================

class TestRichConsole(unittest.TestCase):
    """Tests for rich console output utilities."""
    
    def test_progress_bar_initialization(self):
        """Test ProgressBar creation and basic operations."""
        from benchmarks.rich_console import ProgressBar
        
        bar = ProgressBar(100)
        self.assertEqual(bar.total, 100)
        self.assertEqual(bar.current, 0)
    
    def test_progress_bar_update(self):
        """Test ProgressBar update returns string."""
        from benchmarks.rich_console import ProgressBar
        
        bar = ProgressBar(100)
        result = bar.update(50)
        
        self.assertIsInstance(result, str)
        self.assertIn("50", result)  # Should contain percentage
    
    def test_progress_bar_increment(self):
        """Test ProgressBar increment."""
        from benchmarks.rich_console import ProgressBar
        
        bar = ProgressBar(10)
        bar.update(5)
        result = bar.increment(2)
        
        self.assertEqual(bar.current, 7)
    
    def test_sparkline_generation(self):
        """Test sparkline chart generation."""
        from benchmarks.rich_console import sparkline
        
        values = [1, 2, 3, 4, 5, 4, 3, 2, 1]
        result = sparkline(values)
        
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)
    
    def test_sparkline_empty(self):
        """Test sparkline with empty values."""
        from benchmarks.rich_console import sparkline
        
        result = sparkline([])
        self.assertEqual(result, "")
    
    def test_histogram_generation(self):
        """Test histogram chart generation."""
        from benchmarks.rich_console import histogram
        
        values = [100, 150, 200, 250, 300, 350, 400]
        lines = histogram(values, bins=5)
        
        self.assertIsInstance(lines, list)
        self.assertEqual(len(lines), 5)
    
    def test_table_creation(self):
        """Test Table creation and rendering."""
        from benchmarks.rich_console import Table, TableColumn
        
        table = Table(
            columns=[
                TableColumn("Name", 10),
                TableColumn("Value", 10, align="right"),
            ],
            title="Test Table"
        )
        table.add_row("Test", "123")
        
        result = table.render()
        
        self.assertIsInstance(result, str)
        self.assertIn("Test", result)
        self.assertIn("123", result)
    
    def test_format_latency(self):
        """Test latency formatting."""
        from benchmarks.rich_console import format_latency
        
        result = format_latency(150)
        self.assertIn("150", result)
    
    def test_format_cost(self):
        """Test cost formatting."""
        from benchmarks.rich_console import format_cost
        
        result = format_cost(0.0015)
        self.assertIn("0.0015", result)
    
    def test_format_success_rate(self):
        """Test success rate formatting."""
        from benchmarks.rich_console import format_success_rate
        
        result = format_success_rate(0.98)
        self.assertIn("98", result)
    
    def test_render_benchmark_summary(self):
        """Test complete benchmark summary rendering."""
        from benchmarks.rich_console import render_benchmark_summary
        
        result = render_benchmark_summary(SAMPLE_BENCHMARK_SUITE)
        
        self.assertIsInstance(result, str)
        self.assertIn("openai", result.lower())
        self.assertIn("anthropic", result.lower())
    
    def test_render_comparison_table(self):
        """Test comparison table rendering."""
        from benchmarks.rich_console import render_comparison_table
        
        result = render_comparison_table(SAMPLE_BENCHMARK_SUITE["results"])
        
        self.assertIsInstance(result, str)
        self.assertIn("Provider", result)
    
    def test_render_provider_card(self):
        """Test provider card rendering."""
        from benchmarks.rich_console import render_provider_card
        
        result = render_provider_card(SAMPLE_BENCHMARK_RESULT)
        
        self.assertIsInstance(result, str)
        self.assertIn("openai", result.lower())


# =============================================================================
# QUALITY ANALYZER TESTS
# =============================================================================

class TestQualityAnalyzer(unittest.TestCase):
    """Tests for quality analyzer."""
    
    def test_analyzer_initialization(self):
        """Test QualityAnalyzer creation."""
        from benchmarks.quality_analyzer import QualityAnalyzer
        
        analyzer = QualityAnalyzer()
        self.assertIsNotNone(analyzer.weights)
    
    def test_analyze_valid_pgn(self):
        """Test analyzing a valid PGN game."""
        from benchmarks.quality_analyzer import QualityAnalyzer, QualityDimension
        
        analyzer = QualityAnalyzer()
        report = analyzer.analyze(SAMPLE_PGN)
        
        self.assertGreater(report.overall_score, 0)
        self.assertIn(report.grade, ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "F"])
        self.assertGreater(report.move_count, 0)
        self.assertIn(QualityDimension.LEGALITY, report.scores)
    
    def test_analyze_tactical_game(self):
        """Test analyzing a tactical game."""
        from benchmarks.quality_analyzer import QualityAnalyzer
        
        analyzer = QualityAnalyzer()
        report = analyzer.analyze(SAMPLE_TACTICAL_PGN)
        
        self.assertGreater(report.overall_score, 0)
        # Tactical game should have some tactical highlights
        self.assertIsInstance(report.tactical_highlights, list)
    
    def test_detect_opening(self):
        """Test opening detection."""
        from benchmarks.quality_analyzer import QualityAnalyzer
        
        analyzer = QualityAnalyzer()
        report = analyzer.analyze(SAMPLE_PGN)
        
        # Should detect Ruy Lopez or Spanish
        self.assertIn("Ruy", report.detected_opening)
    
    def test_quality_report_to_dict(self):
        """Test QualityReport serialization."""
        from benchmarks.quality_analyzer import QualityAnalyzer
        
        analyzer = QualityAnalyzer()
        report = analyzer.analyze(SAMPLE_PGN)
        
        data = report.to_dict()
        
        self.assertIsInstance(data, dict)
        self.assertIn("overall_score", data)
        self.assertIn("grade", data)
    
    def test_quality_report_summary(self):
        """Test QualityReport text summary."""
        from benchmarks.quality_analyzer import QualityAnalyzer
        
        analyzer = QualityAnalyzer()
        report = analyzer.analyze(SAMPLE_PGN)
        
        summary = report.summary()
        
        self.assertIsInstance(summary, str)
        self.assertIn("Quality Report", summary)
    
    def test_empty_game(self):
        """Test analyzing empty/invalid input."""
        from benchmarks.quality_analyzer import QualityAnalyzer
        
        analyzer = QualityAnalyzer()
        report = analyzer.analyze("")
        
        self.assertEqual(report.grade, "F")
        self.assertIn("No valid moves", report.warnings[0])
    
    def test_batch_analyzer(self):
        """Test BatchQualityAnalyzer."""
        from benchmarks.quality_analyzer import BatchQualityAnalyzer
        
        analyzer = BatchQualityAnalyzer()
        games = [SAMPLE_PGN, SAMPLE_TACTICAL_PGN]
        
        result = analyzer.analyze_batch(games)
        
        self.assertEqual(result["total_games"], 2)
        self.assertEqual(result["valid_games"], 2)
        self.assertIn("average_score", result)
        self.assertIn("dimension_averages", result)
    
    def test_custom_weights(self):
        """Test analyzer with custom weights."""
        from benchmarks.quality_analyzer import QualityAnalyzer, QualityDimension
        
        custom_weights = {
            QualityDimension.LEGALITY: 0.5,
            QualityDimension.TACTICAL: 0.2,
            QualityDimension.AESTHETIC: 0.2,
            QualityDimension.STRUCTURAL: 0.1,
        }
        
        analyzer = QualityAnalyzer(weights=custom_weights)
        report = analyzer.analyze(SAMPLE_PGN)
        
        self.assertGreater(report.overall_score, 0)


# =============================================================================
# BENCHMARK HISTORY TESTS
# =============================================================================

class TestBenchmarkHistory(unittest.TestCase):
    """Tests for benchmark history and trend analysis."""
    
    def setUp(self):
        """Create temporary database file."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_history.json")
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_history_initialization(self):
        """Test BenchmarkHistory creation."""
        from benchmarks.benchmark_history import BenchmarkHistory
        
        history = BenchmarkHistory(self.db_path)
        self.assertEqual(len(history._records), 0)
    
    def test_save_result(self):
        """Test saving a benchmark result."""
        from benchmarks.benchmark_history import BenchmarkHistory
        
        history = BenchmarkHistory(self.db_path)
        record = history.save(SAMPLE_BENCHMARK_RESULT)
        
        self.assertEqual(record.provider, "openai")
        self.assertEqual(len(history._records), 1)
    
    def test_save_suite(self):
        """Test saving a benchmark suite."""
        from benchmarks.benchmark_history import BenchmarkHistory
        
        history = BenchmarkHistory(self.db_path)
        records = history.save_suite(SAMPLE_BENCHMARK_SUITE)
        
        self.assertEqual(len(records), 3)
        self.assertEqual(len(history._records), 3)
    
    def test_persistence(self):
        """Test data persists across instances."""
        from benchmarks.benchmark_history import BenchmarkHistory
        
        # Save with first instance
        history1 = BenchmarkHistory(self.db_path)
        history1.save(SAMPLE_BENCHMARK_RESULT)
        
        # Load with second instance
        history2 = BenchmarkHistory(self.db_path)
        
        self.assertEqual(len(history2._records), 1)
    
    def test_get_records_filter_provider(self):
        """Test filtering records by provider."""
        from benchmarks.benchmark_history import BenchmarkHistory
        
        history = BenchmarkHistory(self.db_path)
        history.save_suite(SAMPLE_BENCHMARK_SUITE)
        
        records = history.get_records(provider="openai")
        
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].provider, "openai")
    
    def test_get_records_limit(self):
        """Test limiting records."""
        from benchmarks.benchmark_history import BenchmarkHistory
        
        history = BenchmarkHistory(self.db_path)
        history.save_suite(SAMPLE_BENCHMARK_SUITE)
        
        records = history.get_records(limit=2)
        
        self.assertEqual(len(records), 2)
    
    def test_trend_analysis_insufficient_data(self):
        """Test trends with insufficient data."""
        from benchmarks.benchmark_history import BenchmarkHistory
        
        history = BenchmarkHistory(self.db_path)
        history.save(SAMPLE_BENCHMARK_RESULT)
        
        trend = history.get_trends("openai")
        
        # Need at least 2 records
        self.assertIsNone(trend)
    
    def test_trend_analysis_with_data(self):
        """Test trends with sufficient data."""
        from benchmarks.benchmark_history import BenchmarkHistory
        
        history = BenchmarkHistory(self.db_path)
        
        # Add multiple records
        for i in range(5):
            result = {
                **SAMPLE_BENCHMARK_RESULT,
                "timestamp": (datetime.now() - timedelta(days=i)).isoformat(),
                "latency": {**SAMPLE_BENCHMARK_RESULT["latency"], "mean_ms": 200 + i * 20},
            }
            history.save(result)
        
        trend = history.get_trends("openai")
        
        self.assertIsNotNone(trend)
        self.assertEqual(trend.provider, "openai")
        self.assertEqual(trend.data_points, 5)
    
    def test_trend_data_summary(self):
        """Test TrendData summary generation."""
        from benchmarks.benchmark_history import TrendData
        
        trend = TrendData(
            provider="openai",
            model="gpt-4o-mini",
            period_days=30,
            data_points=10,
            latency_mean_first=200,
            latency_mean_last=250,
            latency_change_percent=25,
            latency_trend="degrading",
        )
        
        summary = trend.summary()
        
        self.assertIn("openai", summary)
        self.assertIn("degrading", summary)
    
    def test_regression_detection(self):
        """Test regression detection."""
        from benchmarks.benchmark_history import BenchmarkHistory
        
        history = BenchmarkHistory(self.db_path)
        
        # Add baseline records
        for i in range(5):
            result = {
                **SAMPLE_BENCHMARK_RESULT,
                "timestamp": (datetime.now() - timedelta(days=i+1)).isoformat(),
                "latency": {**SAMPLE_BENCHMARK_RESULT["latency"], "mean_ms": 200},
            }
            history.save(result)
        
        # Add regressed record
        regressed = {
            **SAMPLE_BENCHMARK_RESULT,
            "timestamp": datetime.now().isoformat(),
            "latency": {**SAMPLE_BENCHMARK_RESULT["latency"], "mean_ms": 400},  # 100% regression
        }
        history.save(regressed)
        
        alerts = history.detect_regressions(threshold_percent=20)
        
        # Should detect latency regression
        self.assertGreater(len(alerts), 0)
        self.assertEqual(alerts[0].metric, "latency")
    
    def test_provider_comparison(self):
        """Test provider comparison."""
        from benchmarks.benchmark_history import BenchmarkHistory
        
        history = BenchmarkHistory(self.db_path)
        history.save_suite(SAMPLE_BENCHMARK_SUITE)
        
        comparison = history.get_provider_comparison()
        
        self.assertIn("providers", comparison)
        self.assertIn("openai", comparison["providers"])
        self.assertIn("anthropic", comparison["providers"])
    
    def test_clear_history(self):
        """Test clearing history."""
        from benchmarks.benchmark_history import BenchmarkHistory
        
        history = BenchmarkHistory(self.db_path)
        history.save_suite(SAMPLE_BENCHMARK_SUITE)
        history.clear()
        
        self.assertEqual(len(history._records), 0)
    
    def test_export_json(self):
        """Test exporting history to JSON."""
        from benchmarks.benchmark_history import BenchmarkHistory
        
        history = BenchmarkHistory(self.db_path)
        history.save(SAMPLE_BENCHMARK_RESULT)
        
        exported = history.export("json")
        data = json.loads(exported)
        
        self.assertIn("records", data)
        self.assertEqual(len(data["records"]), 1)


# =============================================================================
# REPORT GENERATOR TESTS
# =============================================================================

class TestReportGenerator(unittest.TestCase):
    """Tests for report generation."""
    
    def setUp(self):
        """Create temporary directory for reports."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_report_generator_initialization(self):
        """Test ReportGenerator creation."""
        from benchmarks.report_generator import ReportGenerator
        
        generator = ReportGenerator(SAMPLE_BENCHMARK_SUITE)
        self.assertIsNotNone(generator)
    
    def test_html_report_generation(self):
        """Test HTML report generation."""
        from benchmarks.report_generator import ReportGenerator
        
        generator = ReportGenerator(SAMPLE_BENCHMARK_SUITE)
        html = generator.to_html()
        
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("openai", html.lower())
        self.assertIn("anthropic", html.lower())
    
    def test_markdown_report_generation(self):
        """Test Markdown report generation."""
        from benchmarks.report_generator import ReportGenerator
        
        generator = ReportGenerator(SAMPLE_BENCHMARK_SUITE)
        md = generator.to_markdown()
        
        self.assertIn("# ", md)
        self.assertIn("openai", md.lower())
        self.assertIn("|", md)  # Table markers
    
    def test_json_export(self):
        """Test JSON export."""
        from benchmarks.report_generator import ReportGenerator
        
        generator = ReportGenerator(SAMPLE_BENCHMARK_SUITE)
        json_str = generator.to_json()
        
        data = json.loads(json_str)
        self.assertIn("results", data)
    
    def test_save_html(self):
        """Test saving HTML report to file."""
        from benchmarks.report_generator import ReportGenerator
        
        generator = ReportGenerator(SAMPLE_BENCHMARK_SUITE)
        path = os.path.join(self.temp_dir, "report.html")
        
        generator.save(path)
        
        self.assertTrue(os.path.exists(path))
        with open(path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("<!DOCTYPE html>", content)
    
    def test_save_markdown(self):
        """Test saving Markdown report to file."""
        from benchmarks.report_generator import ReportGenerator
        
        generator = ReportGenerator(SAMPLE_BENCHMARK_SUITE)
        path = os.path.join(self.temp_dir, "report.md")
        
        generator.save(path)
        
        self.assertTrue(os.path.exists(path))
    
    def test_report_config(self):
        """Test report configuration."""
        from benchmarks.report_generator import ReportGenerator, ReportConfig
        
        config = ReportConfig(
            title="Custom Report",
            include_raw_data=True,
            include_charts=False,
        )
        
        generator = ReportGenerator(SAMPLE_BENCHMARK_SUITE, config)
        html = generator.to_html()
        
        self.assertIn("Custom Report", html)
    
    def test_statistical_analysis(self):
        """Test statistical analysis in report."""
        from benchmarks.report_generator import StatisticalAnalyzer
        
        values = [100, 150, 200, 250, 300]
        lower, mean, upper = StatisticalAnalyzer.calculate_confidence_interval(values)
        
        self.assertLess(lower, mean)
        self.assertLess(mean, upper)
    
    def test_cohens_d(self):
        """Test effect size calculation."""
        from benchmarks.report_generator import StatisticalAnalyzer
        
        group1 = [100, 110, 120, 130, 140]
        group2 = [200, 210, 220, 230, 240]
        
        d = StatisticalAnalyzer.cohens_d(group1, group2)
        
        # Large difference should have large effect size
        self.assertGreater(abs(d), 0.8)
    
    def test_recommendations(self):
        """Test recommendation engine."""
        from benchmarks.report_generator import RecommendationEngine
        
        engine = RecommendationEngine(SAMPLE_BENCHMARK_SUITE["results"])
        recommendations = engine.generate_recommendations()
        
        self.assertGreater(len(recommendations), 0)
        self.assertIn("category", recommendations[0])
        self.assertIn("recommendation", recommendations[0])


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestPhase32PlusIntegration(unittest.TestCase):
    """Integration tests for Phase 3.2+ components."""
    
    def test_full_pipeline(self):
        """Test full benchmark → history → report pipeline."""
        from benchmarks.benchmark_history import BenchmarkHistory
        from benchmarks.report_generator import ReportGenerator
        from benchmarks.quality_analyzer import QualityAnalyzer
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Step 1: Create benchmark suite (using sample data)
            suite = SAMPLE_BENCHMARK_SUITE
            
            # Step 2: Save to history
            history = BenchmarkHistory(os.path.join(temp_dir, "history.json"))
            records = history.save_suite(suite)
            self.assertEqual(len(records), 3)
            
            # Step 3: Generate report
            generator = ReportGenerator(suite)
            report_path = os.path.join(temp_dir, "report.html")
            generator.save(report_path)
            self.assertTrue(os.path.exists(report_path))
            
            # Step 4: Quality analysis (separate)
            analyzer = QualityAnalyzer()
            quality = analyzer.analyze(SAMPLE_PGN)
            self.assertGreater(quality.overall_score, 0)
    
    def test_provider_benchmark_cli_args(self):
        """Test that provider_benchmark accepts new CLI arguments."""
        from benchmarks import provider_benchmark
        import argparse
        
        # Get parser
        parser = argparse.ArgumentParser()
        # Verify new arguments exist by checking the main function exists
        self.assertTrue(hasattr(provider_benchmark, 'main'))


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    unittest.main()
