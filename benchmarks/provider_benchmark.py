"""
benchmarks/provider_benchmark.py

Performance and quality benchmarking tool for LLM providers.

PHASE 3.2: Quality & Testing
- Response quality benchmarking
- Performance/latency metrics
- Cost analysis per provider
- Statistical comparisons

PHASE 3.2+: Enhanced Features
- Rich console output with colors and charts
- Quality scoring for generated games
- Benchmark history and trend analysis
- HTML/Markdown report generation
- Regression detection

Usage:
    python -m benchmarks.provider_benchmark --providers openai,anthropic --runs 5
    python -m benchmarks.provider_benchmark --all --output results.json
    python -m benchmarks.provider_benchmark --all --report benchmark_report.html
    python -m benchmarks.provider_benchmark --all --rich  # Rich console output
"""

import os
import sys
import json
import time
import argparse
import statistics
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import logging

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from log_manager import setup_logging

# Handlers are wired by log_manager.setup_logging()
logger = logging.getLogger(__name__)


# =============================================================================
# COST ESTIMATION (approximate pricing as of 2024)
# =============================================================================

class ProviderPricing:
    """Approximate pricing per 1M tokens (input/output)."""
    
    # Format: (input_per_1M, output_per_1M)
    PRICING = {
        "gpt-4-turbo": (10.0, 30.0),
        "gpt-4o": (5.0, 15.0),
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-3.5-turbo": (0.50, 1.50),
        "claude-3-opus": (15.0, 75.0),
        "claude-3-sonnet": (3.0, 15.0),
        "claude-3-haiku": (0.25, 1.25),
        "claude-3-5-sonnet": (3.0, 15.0),
        "gemini-pro": (0.50, 1.50),
        "gemini-1.5-pro": (3.50, 10.50),
        "ollama": (0.0, 0.0),  # Free (local)
    }
    
    @classmethod
    def estimate_cost(cls, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for given token counts."""
        # Find matching pricing
        for model_key, (input_price, output_price) in cls.PRICING.items():
            if model_key in model.lower():
                input_cost = (input_tokens / 1_000_000) * input_price
                output_cost = (output_tokens / 1_000_000) * output_price
                return input_cost + output_cost
        
        # Default to GPT-4o-mini pricing if unknown
        return (input_tokens / 1_000_000) * 0.15 + (output_tokens / 1_000_000) * 0.60


# =============================================================================
# BENCHMARK DATACLASSES
# =============================================================================

@dataclass
class TokenUsage:
    """Token usage for a single generation."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    @property
    def estimated_cost(self) -> float:
        return 0.0  # Will be calculated with model info


@dataclass
class LatencyMetrics:
    """Latency metrics for a benchmark run."""
    min_ms: float = 0.0
    max_ms: float = 0.0
    mean_ms: float = 0.0
    median_ms: float = 0.0
    std_dev_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0


@dataclass
class QualityMetrics:
    """Quality metrics for generated content."""
    response_length_avg: float = 0.0
    response_length_std: float = 0.0
    contains_chess_notation: float = 0.0  # Percentage
    valid_pgn_rate: float = 0.0           # Percentage
    error_rate: float = 0.0               # Percentage


@dataclass
class BenchmarkResult:
    """Complete benchmark result for a provider."""
    provider_name: str
    model: str
    runs: int
    successful_runs: int
    failed_runs: int
    latency: LatencyMetrics = field(default_factory=LatencyMetrics)
    quality: QualityMetrics = field(default_factory=QualityMetrics)
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    raw_latencies: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "model": self.model,
            "runs": self.runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "success_rate": self.successful_runs / self.runs if self.runs > 0 else 0,
            "latency": asdict(self.latency),
            "quality": asdict(self.quality),
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "timestamp": self.timestamp,
            "errors": self.errors,
        }


@dataclass 
class BenchmarkSuite:
    """Complete benchmark suite results."""
    results: List[BenchmarkResult] = field(default_factory=list)
    total_time_seconds: float = 0.0
    benchmark_date: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "benchmark_date": self.benchmark_date,
            "total_time_seconds": self.total_time_seconds,
            "results": [r.to_dict() for r in self.results],
        }
    
    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            "\n" + "=" * 70,
            "BENCHMARK SUMMARY",
            "=" * 70,
            f"Date: {self.benchmark_date}",
            f"Total Time: {self.total_time_seconds:.1f}s",
            "",
        ]
        
        # Sort by mean latency
        sorted_results = sorted(self.results, key=lambda r: r.latency.mean_ms)
        
        lines.append(f"{'Provider':<20} {'Model':<25} {'Runs':<6} {'Mean (ms)':<12} {'Cost ($)':<10}")
        lines.append("-" * 70)
        
        for r in sorted_results:
            lines.append(
                f"{r.provider_name:<20} {r.model[:24]:<25} "
                f"{r.successful_runs}/{r.runs:<4} {r.latency.mean_ms:<12.0f} "
                f"${r.estimated_cost_usd:<9.4f}"
            )
        
        lines.append("=" * 70)
        return "\n".join(lines)


# =============================================================================
# BENCHMARK PROMPTS
# =============================================================================

BENCHMARK_PROMPTS = {
    "simple": {
        "system": "You are a helpful assistant.",
        "user": "What is 2 + 2? Reply with just the number.",
        "expected_length": 10,
    },
    "chess_short": {
        "system": "You are a chess game generator. Generate moves in standard algebraic notation.",
        "user": "Generate 5 moves of a chess game starting with 1. e4. Return only the moves.",
        "expected_length": 50,
    },
    "chess_full": {
        "system": """You are CAISSA, an AI that generates beautiful chess games.
Generate games that are tactically sharp and aesthetically pleasing.""",
        "user": """Generate a 15-move chess game between two grandmasters.
The game should feature:
- An opening from the Italian Game
- At least one piece sacrifice
- Sharp tactical play

Return the game in PGN format with annotations.""",
        "expected_length": 500,
    },
}


# =============================================================================
# PROVIDER FACTORY
# =============================================================================

def create_provider(provider_name: str) -> tuple:
    """Create a provider instance. Returns (provider, model_name) or (None, error)."""
    try:
        from core.provider_factory import create_provider as factory_create
        provider = factory_create(provider_name)
        model = provider.model if hasattr(provider, 'model') else provider_name
        return provider, model
    except Exception as e:
        return None, str(e)


# =============================================================================
# BENCHMARK ENGINE
# =============================================================================

class BenchmarkEngine:
    """Engine for running benchmarks."""
    
    def __init__(self, prompt_type: str = "chess_short", temperature: float = 0.7):
        self.prompt_type = prompt_type
        self.temperature = temperature
        self.prompt_config = BENCHMARK_PROMPTS.get(prompt_type, BENCHMARK_PROMPTS["simple"])
    
    def run_single(self, provider, model: str) -> tuple:
        """Run a single benchmark. Returns (latency_ms, response, error)."""
        try:
            start = time.perf_counter()
            response = provider.generate(
                system_prompt=self.prompt_config["system"],
                user_prompt=self.prompt_config["user"],
                temperature=self.temperature
            )
            latency_ms = (time.perf_counter() - start) * 1000
            
            return latency_ms, response, None
            
        except Exception as e:
            return 0.0, "", str(e)
    
    def run_provider_benchmark(
        self, 
        provider_name: str, 
        runs: int = 5,
        warmup: int = 1
    ) -> BenchmarkResult:
        """Run full benchmark for a provider."""
        
        logger.info(f"Starting benchmark for {provider_name}...")
        
        # Create provider
        provider, model = create_provider(provider_name)
        if provider is None:
            return BenchmarkResult(
                provider_name=provider_name,
                model="N/A",
                runs=runs,
                successful_runs=0,
                failed_runs=runs,
                errors=[model]  # model contains error message
            )
        
        # Warmup runs (not counted)
        for i in range(warmup):
            logger.info(f"  Warmup {i+1}/{warmup}...")
            self.run_single(provider, model)
        
        # Actual benchmark runs
        latencies = []
        responses = []
        errors = []
        
        for i in range(runs):
            logger.info(f"  Run {i+1}/{runs}...")
            latency, response, error = self.run_single(provider, model)
            
            if error:
                errors.append(error)
            else:
                latencies.append(latency)
                responses.append(response)
        
        # Calculate metrics
        successful = len(latencies)
        failed = len(errors)
        
        result = BenchmarkResult(
            provider_name=provider_name,
            model=model,
            runs=runs,
            successful_runs=successful,
            failed_runs=failed,
            raw_latencies=latencies,
            errors=errors[:5],  # Keep first 5 errors
        )
        
        if latencies:
            sorted_latencies = sorted(latencies)
            result.latency = LatencyMetrics(
                min_ms=min(latencies),
                max_ms=max(latencies),
                mean_ms=statistics.mean(latencies),
                median_ms=statistics.median(latencies),
                std_dev_ms=statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
                p95_ms=sorted_latencies[int(len(sorted_latencies) * 0.95)] if len(sorted_latencies) >= 20 else max(latencies),
                p99_ms=sorted_latencies[int(len(sorted_latencies) * 0.99)] if len(sorted_latencies) >= 100 else max(latencies),
            )
        
        if responses:
            lengths = [len(r) for r in responses]
            chess_notation = sum(1 for r in responses if "e4" in r or "Nf3" in r) / len(responses)
            
            result.quality = QualityMetrics(
                response_length_avg=statistics.mean(lengths),
                response_length_std=statistics.stdev(lengths) if len(lengths) > 1 else 0.0,
                contains_chess_notation=chess_notation * 100,
                error_rate=(failed / runs) * 100 if runs > 0 else 0.0,
            )
            
            # Estimate tokens (rough: 4 chars per token)
            avg_input_tokens = len(self.prompt_config["system"] + self.prompt_config["user"]) // 4
            avg_output_tokens = int(result.quality.response_length_avg) // 4
            result.total_tokens = (avg_input_tokens + avg_output_tokens) * successful
            result.estimated_cost_usd = ProviderPricing.estimate_cost(
                model, 
                avg_input_tokens * successful, 
                avg_output_tokens * successful
            )
        
        logger.info(f"  Completed: {successful}/{runs} successful, mean={result.latency.mean_ms:.0f}ms")
        return result
    
    def run_suite(
        self, 
        providers: List[str], 
        runs: int = 5
    ) -> BenchmarkSuite:
        """Run benchmark suite for multiple providers."""
        start_time = time.time()
        suite = BenchmarkSuite()
        
        for provider_name in providers:
            result = self.run_provider_benchmark(provider_name, runs=runs)
            suite.results.append(result)
        
        suite.total_time_seconds = time.time() - start_time
        return suite


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark LLM providers for CAISSA chess generation"
    )
    parser.add_argument(
        "--providers", "-p",
        type=str,
        default="openai",
        help="Comma-separated list of providers (openai,anthropic,azure,gemini,ollama)"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Test all available providers"
    )
    parser.add_argument(
        "--runs", "-r",
        type=int,
        default=5,
        help="Number of benchmark runs per provider (default: 5)"
    )
    parser.add_argument(
        "--prompt", "-t",
        type=str,
        default="chess_short",
        choices=["simple", "chess_short", "chess_full"],
        help="Prompt type to use (default: chess_short)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output JSON file for results"
    )
    parser.add_argument(
        "--report",
        type=str,
        help="Generate HTML/Markdown report (auto-detect format from extension)"
    )
    parser.add_argument(
        "--rich",
        action="store_true",
        help="Use rich console output with colors and charts"
    )
    parser.add_argument(
        "--save-history",
        action="store_true",
        help="Save results to benchmark history database"
    )
    parser.add_argument(
        "--analyze-quality",
        action="store_true",
        help="Run quality analysis on generated responses"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Quiet mode (minimal output)"
    )
    
    args = parser.parse_args()

    # Single logging authority: configure once via log_manager.
    setup_logging(
        log_dir="logs",
        level="INFO",
        verbosity="quiet" if args.quiet else "normal",
        console_logs=True,
    )
    
    # Determine providers
    if args.all:
        providers = ["openai", "anthropic", "azure", "gemini", "ollama"]
    else:
        providers = [p.strip().lower() for p in args.providers.split(",")]
    
    # Run benchmarks
    engine = BenchmarkEngine(prompt_type=args.prompt)
    suite = engine.run_suite(providers, runs=args.runs)
    
    # Output results
    if args.rich:
        try:
            from benchmarks.rich_console import render_benchmark_summary
            print(render_benchmark_summary(suite.to_dict()))
        except ImportError:
            print(suite.summary())
    else:
        print(suite.summary())
    
    # Save to history
    if args.save_history:
        try:
            from benchmarks.benchmark_history import BenchmarkHistory
            history = BenchmarkHistory()
            records = history.save_suite(suite.to_dict(), args.prompt)
            print(f"\n✓ Saved {len(records)} records to benchmark history")
        except ImportError as e:
            print(f"\nWarning: Could not save to history: {e}")
    
    # Save JSON output
    if args.output:
        with open(args.output, "w") as f:
            json.dump(suite.to_dict(), f, indent=2)
        print(f"\nResults saved to: {args.output}")
    
    # Generate report
    if args.report:
        try:
            from benchmarks.report_generator import ReportGenerator
            generator = ReportGenerator(suite.to_dict())
            generator.save(args.report)
        except ImportError as e:
            print(f"\nWarning: Could not generate report: {e}")


if __name__ == "__main__":
    main()
