"""
benchmarks/benchmark_history.py

Benchmark result persistence and trend analysis.

PHASE 3.2+: Benchmark History
- JSON database for storing benchmark results
- Trend analysis over time
- Regression detection
- Historical comparisons

Usage:
    from benchmarks.benchmark_history import BenchmarkHistory
    
    history = BenchmarkHistory("benchmarks/history.json")
    history.save(benchmark_result)
    trends = history.get_trends(provider="openai", days=30)
"""

import os
import json
import hashlib
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
import statistics


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class TrendData:
    """Trend analysis data."""
    provider: str
    model: str
    period_days: int
    data_points: int
    
    # Latency trends
    latency_mean_first: float = 0.0
    latency_mean_last: float = 0.0
    latency_change_percent: float = 0.0
    latency_trend: str = "stable"  # improving, degrading, stable
    
    # Cost trends
    cost_first: float = 0.0
    cost_last: float = 0.0
    cost_change_percent: float = 0.0
    cost_trend: str = "stable"
    
    # Success rate trends
    success_first: float = 0.0
    success_last: float = 0.0
    success_change_percent: float = 0.0
    success_trend: str = "stable"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Trend Analysis: {self.provider} ({self.model})",
            f"  Period: {self.period_days} days ({self.data_points} data points)",
            "",
            f"  Latency: {self.latency_mean_first:.0f}ms → {self.latency_mean_last:.0f}ms ({self.latency_change_percent:+.1f}%) [{self.latency_trend}]",
            f"  Cost:    ${self.cost_first:.4f} → ${self.cost_last:.4f} ({self.cost_change_percent:+.1f}%) [{self.cost_trend}]",
            f"  Success: {self.success_first*100:.0f}% → {self.success_last*100:.0f}% ({self.success_change_percent:+.1f}%) [{self.success_trend}]",
        ]
        return "\n".join(lines)


@dataclass
class RegressionAlert:
    """Alert for detected regression."""
    provider: str
    model: str
    metric: str
    previous_value: float
    current_value: float
    change_percent: float
    severity: str  # low, medium, high
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def __str__(self) -> str:
        icon = {"low": "ℹ️", "medium": "⚠️", "high": "🚨"}.get(self.severity, "")
        return f"{icon} {self.provider}: {self.metric} {self.change_percent:+.1f}% ({self.previous_value:.2f} → {self.current_value:.2f})"


@dataclass
class BenchmarkRecord:
    """Single benchmark record for persistence."""
    id: str
    timestamp: str
    provider: str
    model: str
    runs: int
    successful_runs: int
    latency_mean: float
    latency_median: float
    latency_p95: float
    estimated_cost: float
    quality_score: float = 0.0
    prompt_type: str = "chess_short"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkRecord":
        return cls(**data)
    
    @classmethod
    def from_benchmark_result(cls, result: Dict[str, Any], prompt_type: str = "chess_short") -> "BenchmarkRecord":
        """Create record from BenchmarkResult dict."""
        latency = result.get("latency", {})
        
        # Generate unique ID
        id_string = f"{result.get('provider_name', '')}{result.get('timestamp', '')}"
        record_id = hashlib.sha256(id_string.encode()).hexdigest()[:12]
        
        return cls(
            id=record_id,
            timestamp=result.get("timestamp", datetime.now().isoformat()),
            provider=result.get("provider_name", "unknown"),
            model=result.get("model", "unknown"),
            runs=result.get("runs", 0),
            successful_runs=result.get("successful_runs", 0),
            latency_mean=latency.get("mean_ms", 0),
            latency_median=latency.get("median_ms", 0),
            latency_p95=latency.get("p95_ms", 0),
            estimated_cost=result.get("estimated_cost_usd", 0),
            prompt_type=prompt_type,
        )


# =============================================================================
# BENCHMARK HISTORY
# =============================================================================

class BenchmarkHistory:
    """
    Persistent storage and analysis for benchmark results.
    
    Stores results in a JSON file with trend analysis and
    regression detection capabilities.
    """
    
    def __init__(self, db_path: str = "benchmarks/history.json"):
        """
        Initialize benchmark history.
        
        Args:
            db_path: Path to JSON database file
        """
        self.db_path = Path(db_path)
        self._records: List[BenchmarkRecord] = []
        self._load()
    
    def _load(self) -> None:
        """Load records from disk."""
        if self.db_path.exists():
            try:
                with open(self.db_path) as f:
                    data = json.load(f)
                self._records = [BenchmarkRecord.from_dict(r) for r in data.get("records", [])]
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load history: {e}")
                self._records = []
        else:
            self._records = []
    
    def _save(self) -> None:
        """Save records to disk."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "record_count": len(self._records),
            "records": [r.to_dict() for r in self._records],
        }
        
        with open(self.db_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def save(self, result: Dict[str, Any], prompt_type: str = "chess_short") -> BenchmarkRecord:
        """
        Save a benchmark result to history.
        
        Args:
            result: BenchmarkResult dict (from provider_benchmark)
            prompt_type: Type of prompt used
            
        Returns:
            Created BenchmarkRecord
        """
        record = BenchmarkRecord.from_benchmark_result(result, prompt_type)
        self._records.append(record)
        self._save()
        return record
    
    def save_suite(self, suite: Dict[str, Any], prompt_type: str = "chess_short") -> List[BenchmarkRecord]:
        """Save all results from a benchmark suite."""
        records = []
        for result in suite.get("results", []):
            record = self.save(result, prompt_type)
            records.append(record)
        return records
    
    def get_records(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        days: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[BenchmarkRecord]:
        """
        Get filtered records from history.
        
        Args:
            provider: Filter by provider name
            model: Filter by model name
            days: Filter to last N days
            limit: Maximum number of records
            
        Returns:
            List of matching records
        """
        records = self._records.copy()
        
        # Filter by provider
        if provider:
            records = [r for r in records if r.provider.lower() == provider.lower()]
        
        # Filter by model
        if model:
            records = [r for r in records if model.lower() in r.model.lower()]
        
        # Filter by date
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff.isoformat()
            records = [r for r in records if r.timestamp >= cutoff_str]
        
        # Sort by timestamp (newest first)
        records.sort(key=lambda r: r.timestamp, reverse=True)
        
        # Apply limit
        if limit:
            records = records[:limit]
        
        return records
    
    def get_trends(
        self,
        provider: str,
        model: Optional[str] = None,
        days: int = 30,
    ) -> Optional[TrendData]:
        """
        Analyze trends for a provider over time.
        
        Args:
            provider: Provider name
            model: Optional model filter
            days: Number of days to analyze
            
        Returns:
            TrendData with analysis, or None if insufficient data
        """
        records = self.get_records(provider=provider, model=model, days=days)
        
        if len(records) < 2:
            return None
        
        # Sort chronologically (oldest first)
        records.sort(key=lambda r: r.timestamp)
        
        # Split into first half and second half
        mid = len(records) // 2
        first_half = records[:mid]
        second_half = records[mid:]
        
        # Calculate averages for each half
        def avg(records, attr):
            values = [getattr(r, attr) for r in records]
            return statistics.mean(values) if values else 0
        
        latency_first = avg(first_half, "latency_mean")
        latency_last = avg(second_half, "latency_mean")
        
        cost_first = avg(first_half, "estimated_cost")
        cost_last = avg(second_half, "estimated_cost")
        
        success_first = sum(r.successful_runs for r in first_half) / max(sum(r.runs for r in first_half), 1)
        success_last = sum(r.successful_runs for r in second_half) / max(sum(r.runs for r in second_half), 1)
        
        # Calculate changes
        def change_percent(old, new):
            if old == 0:
                return 0
            return ((new - old) / old) * 100
        
        def trend_direction(change, metric_type="lower_better"):
            threshold = 10  # 10% change threshold
            if abs(change) < threshold:
                return "stable"
            if metric_type == "lower_better":
                return "improving" if change < 0 else "degrading"
            else:  # higher_better
                return "improving" if change > 0 else "degrading"
        
        return TrendData(
            provider=provider,
            model=model or records[0].model,
            period_days=days,
            data_points=len(records),
            latency_mean_first=latency_first,
            latency_mean_last=latency_last,
            latency_change_percent=change_percent(latency_first, latency_last),
            latency_trend=trend_direction(change_percent(latency_first, latency_last), "lower_better"),
            cost_first=cost_first,
            cost_last=cost_last,
            cost_change_percent=change_percent(cost_first, cost_last),
            cost_trend=trend_direction(change_percent(cost_first, cost_last), "lower_better"),
            success_first=success_first,
            success_last=success_last,
            success_change_percent=change_percent(success_first, success_last),
            success_trend=trend_direction(change_percent(success_first, success_last), "higher_better"),
        )
    
    def detect_regressions(
        self,
        threshold_percent: float = 20.0,
    ) -> List[RegressionAlert]:
        """
        Detect performance regressions across all providers.
        
        Args:
            threshold_percent: Minimum change to trigger alert
            
        Returns:
            List of regression alerts
        """
        alerts = []
        providers = set(r.provider for r in self._records)
        
        for provider in providers:
            records = self.get_records(provider=provider, limit=10)
            
            if len(records) < 2:
                continue
            
            # Compare latest to previous average
            latest = records[0]
            previous = records[1:6]  # Last 5 (excluding latest)
            
            if not previous:
                continue
            
            # Calculate previous averages
            prev_latency = statistics.mean([r.latency_mean for r in previous])
            prev_cost = statistics.mean([r.estimated_cost for r in previous])
            prev_success = sum(r.successful_runs for r in previous) / sum(r.runs for r in previous)
            
            # Check latency regression
            latency_change = ((latest.latency_mean - prev_latency) / prev_latency * 100) if prev_latency else 0
            if latency_change > threshold_percent:
                severity = "high" if latency_change > 50 else "medium" if latency_change > 30 else "low"
                alerts.append(RegressionAlert(
                    provider=provider,
                    model=latest.model,
                    metric="latency",
                    previous_value=prev_latency,
                    current_value=latest.latency_mean,
                    change_percent=latency_change,
                    severity=severity,
                    timestamp=latest.timestamp,
                ))
            
            # Check cost regression
            if prev_cost > 0:
                cost_change = ((latest.estimated_cost - prev_cost) / prev_cost * 100)
                if cost_change > threshold_percent:
                    severity = "high" if cost_change > 50 else "medium" if cost_change > 30 else "low"
                    alerts.append(RegressionAlert(
                        provider=provider,
                        model=latest.model,
                        metric="cost",
                        previous_value=prev_cost,
                        current_value=latest.estimated_cost,
                        change_percent=cost_change,
                        severity=severity,
                        timestamp=latest.timestamp,
                    ))
            
            # Check success rate regression
            current_success = latest.successful_runs / latest.runs if latest.runs else 0
            if prev_success > 0:
                success_change = ((current_success - prev_success) / prev_success * 100)
                if success_change < -threshold_percent:  # Negative is bad for success
                    severity = "high" if success_change < -30 else "medium" if success_change < -20 else "low"
                    alerts.append(RegressionAlert(
                        provider=provider,
                        model=latest.model,
                        metric="success_rate",
                        previous_value=prev_success,
                        current_value=current_success,
                        change_percent=success_change,
                        severity=severity,
                        timestamp=latest.timestamp,
                    ))
        
        # Sort by severity
        severity_order = {"high": 0, "medium": 1, "low": 2}
        alerts.sort(key=lambda a: severity_order.get(a.severity, 3))
        
        return alerts
    
    def get_provider_comparison(self) -> Dict[str, Any]:
        """
        Generate provider comparison based on historical data.
        
        Returns:
            Comparison dict with rankings and statistics
        """
        providers = set(r.provider for r in self._records)
        comparison = {}
        
        for provider in providers:
            records = self.get_records(provider=provider, days=30)
            
            if not records:
                continue
            
            latencies = [r.latency_mean for r in records]
            costs = [r.estimated_cost for r in records]
            success_rates = [r.successful_runs / r.runs if r.runs else 0 for r in records]
            
            comparison[provider] = {
                "sample_size": len(records),
                "latency": {
                    "mean": statistics.mean(latencies),
                    "median": statistics.median(latencies),
                    "std": statistics.stdev(latencies) if len(latencies) > 1 else 0,
                },
                "cost": {
                    "mean": statistics.mean(costs),
                    "total": sum(costs),
                },
                "success_rate": {
                    "mean": statistics.mean(success_rates),
                },
                "models_used": list(set(r.model for r in records)),
            }
        
        # Add rankings
        if comparison:
            sorted_by_latency = sorted(comparison.keys(), key=lambda p: comparison[p]["latency"]["mean"])
            sorted_by_cost = sorted(comparison.keys(), key=lambda p: comparison[p]["cost"]["mean"])
            sorted_by_success = sorted(comparison.keys(), key=lambda p: comparison[p]["success_rate"]["mean"], reverse=True)
            
            for i, provider in enumerate(sorted_by_latency):
                comparison[provider]["latency_rank"] = i + 1
            for i, provider in enumerate(sorted_by_cost):
                comparison[provider]["cost_rank"] = i + 1
            for i, provider in enumerate(sorted_by_success):
                comparison[provider]["success_rank"] = i + 1
        
        return {
            "providers": comparison,
            "analysis_date": datetime.now().isoformat(),
            "total_records": len(self._records),
        }
    
    def clear(self) -> None:
        """Clear all history."""
        self._records = []
        self._save()
    
    def export(self, format: str = "json") -> str:
        """Export history to string."""
        if format == "json":
            return json.dumps({
                "records": [r.to_dict() for r in self._records]
            }, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Benchmark History Analysis")
    parser.add_argument("--db", default="benchmarks/history.json", help="Database path")
    parser.add_argument("--provider", "-p", help="Filter by provider")
    parser.add_argument("--days", "-d", type=int, default=30, help="Days to analyze")
    parser.add_argument("--trends", action="store_true", help="Show trends")
    parser.add_argument("--regressions", action="store_true", help="Detect regressions")
    parser.add_argument("--compare", action="store_true", help="Compare providers")
    parser.add_argument("--list", action="store_true", help="List records")
    
    args = parser.parse_args()
    
    history = BenchmarkHistory(args.db)
    
    if args.list:
        records = history.get_records(provider=args.provider, days=args.days, limit=20)
        print(f"\nRecords ({len(records)} found):")
        for r in records:
            print(f"  {r.timestamp[:19]} | {r.provider:12} | {r.model:20} | {r.latency_mean:.0f}ms | ${r.estimated_cost:.4f}")
    
    if args.trends and args.provider:
        trend = history.get_trends(args.provider, days=args.days)
        if trend:
            print(trend.summary())
        else:
            print(f"Insufficient data for trend analysis (need at least 2 records)")
    
    if args.regressions:
        alerts = history.detect_regressions()
        if alerts:
            print(f"\nRegression Alerts ({len(alerts)} found):")
            for alert in alerts:
                print(f"  {alert}")
        else:
            print("\nNo regressions detected ✓")
    
    if args.compare:
        comparison = history.get_provider_comparison()
        print(f"\nProvider Comparison (last {args.days} days):")
        for provider, data in comparison.get("providers", {}).items():
            print(f"\n  {provider}:")
            print(f"    Latency: {data['latency']['mean']:.0f}ms (rank #{data.get('latency_rank', '?')})")
            print(f"    Cost:    ${data['cost']['mean']:.4f} (rank #{data.get('cost_rank', '?')})")
            print(f"    Success: {data['success_rate']['mean']*100:.0f}% (rank #{data.get('success_rank', '?')})")


if __name__ == "__main__":
    main()
