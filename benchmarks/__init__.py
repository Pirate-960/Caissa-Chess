"""
benchmarks/__init__.py

CAISSA Benchmark Suite - Phase 3.2+

Provides performance and quality benchmarking for LLM providers.

PHASE 3.2+: Enhanced Features
- Rich console output (rich_console.py)
- Quality analysis (quality_analyzer.py)
- Benchmark history (benchmark_history.py)
- Report generation (report_generator.py)
"""

from benchmarks.provider_benchmark import (
    BenchmarkEngine,
    BenchmarkResult,
    BenchmarkSuite,
    LatencyMetrics,
    QualityMetrics,
    TokenUsage,
    ProviderPricing,
)

# Phase 3.2+ imports
try:
    from benchmarks.rich_console import (
        render_benchmark_summary,
        render_comparison_table,
        ProgressBar,
        LiveProgress,
        Table,
        sparkline,
    )
except ImportError:
    pass

try:
    from benchmarks.quality_analyzer import (
        QualityAnalyzer,
        QualityReport,
        BatchQualityAnalyzer,
        QualityDimension,
    )
except ImportError:
    pass

try:
    from benchmarks.benchmark_history import (
        BenchmarkHistory,
        BenchmarkRecord,
        TrendData,
        RegressionAlert,
    )
except ImportError:
    pass

try:
    from benchmarks.report_generator import (
        ReportGenerator,
        ReportConfig,
        HTMLReportGenerator,
        MarkdownReportGenerator,
    )
except ImportError:
    pass

__all__ = [
    # Core benchmark classes
    "BenchmarkEngine",
    "BenchmarkResult",
    "BenchmarkSuite",
    "LatencyMetrics",
    "QualityMetrics",
    "TokenUsage",
    "ProviderPricing",
    # Phase 3.2+ Rich Console
    "render_benchmark_summary",
    "render_comparison_table",
    "ProgressBar",
    "LiveProgress",
    "Table",
    "sparkline",
    # Phase 3.2+ Quality Analysis
    "QualityAnalyzer",
    "QualityReport",
    "BatchQualityAnalyzer",
    "QualityDimension",
    # Phase 3.2+ History
    "BenchmarkHistory",
    "BenchmarkRecord",
    "TrendData",
    "RegressionAlert",
    # Phase 3.2+ Reports
    "ReportGenerator",
    "ReportConfig",
    "HTMLReportGenerator",
    "MarkdownReportGenerator",
]
