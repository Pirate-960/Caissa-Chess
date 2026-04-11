"""
benchmarks/report_generator.py

Generate comprehensive comparison reports in HTML and Markdown.

PHASE 3.2+: Provider Comparison Reports
- HTML reports with interactive charts
- Markdown reports for GitHub/documentation
- Statistical analysis and recommendations
- Export to multiple formats

Usage:
    from benchmarks.report_generator import ReportGenerator
    
    generator = ReportGenerator(benchmark_suite)
    html = generator.to_html()
    markdown = generator.to_markdown()
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import statistics

logger = logging.getLogger(__name__)

# =============================================================================
# REPORT DATA CLASSES
# =============================================================================

@dataclass
class ReportConfig:
    """Configuration for report generation."""
    title: str = "CAISSA Benchmark Report"
    include_raw_data: bool = False
    include_charts: bool = True
    include_recommendations: bool = True
    include_statistical_analysis: bool = True
    chart_width: int = 600
    chart_height: int = 300


# =============================================================================
# STATISTICAL ANALYSIS
# =============================================================================

class StatisticalAnalyzer:
    """Perform statistical analysis on benchmark results."""
    
    @staticmethod
    def calculate_confidence_interval(values: List[float], confidence: float = 0.95) -> tuple:
        """Calculate confidence interval for a list of values."""
        if len(values) < 2:
            mean = values[0] if values else 0
            return mean, mean, mean
        
        n = len(values)
        mean = statistics.mean(values)
        std_err = statistics.stdev(values) / (n ** 0.5)
        
        # Z-score for 95% confidence
        z = 1.96 if confidence == 0.95 else 2.58  # 99%
        
        margin = z * std_err
        return mean - margin, mean, mean + margin
    
    @staticmethod
    def cohens_d(group1: List[float], group2: List[float]) -> float:
        """Calculate Cohen's d effect size between two groups."""
        if len(group1) < 2 or len(group2) < 2:
            return 0.0
        
        n1, n2 = len(group1), len(group2)
        mean1, mean2 = statistics.mean(group1), statistics.mean(group2)
        var1, var2 = statistics.variance(group1), statistics.variance(group2)
        
        # Pooled standard deviation
        pooled_std = ((var1 * (n1 - 1) + var2 * (n2 - 1)) / (n1 + n2 - 2)) ** 0.5
        
        if pooled_std == 0:
            return 0.0
        
        return (mean1 - mean2) / pooled_std
    
    @staticmethod
    def interpret_effect_size(d: float) -> str:
        """Interpret Cohen's d effect size."""
        d = abs(d)
        if d < 0.2:
            return "negligible"
        elif d < 0.5:
            return "small"
        elif d < 0.8:
            return "medium"
        else:
            return "large"
    
    @staticmethod
    def rank_providers(results: List[Dict[str, Any]], metric: str = "latency") -> List[Dict[str, Any]]:
        """Rank providers by a specific metric."""
        if metric == "latency":
            key = lambda r: r.get("latency", {}).get("mean_ms", float("inf"))
            reverse = False
        elif metric == "cost":
            key = lambda r: r.get("estimated_cost_usd", float("inf"))
            reverse = False
        elif metric == "success":
            key = lambda r: r.get("success_rate", 0)
            reverse = True
        else:
            return results
        
        sorted_results = sorted(results, key=key, reverse=reverse)
        
        for i, result in enumerate(sorted_results):
            result[f"{metric}_rank"] = i + 1
        
        return sorted_results


# =============================================================================
# RECOMMENDATION ENGINE
# =============================================================================

class RecommendationEngine:
    """Generate recommendations based on benchmark results."""
    
    def __init__(self, results: List[Dict[str, Any]]):
        self.results = results
    
    def generate_recommendations(self) -> List[Dict[str, Any]]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        if not self.results:
            return recommendations
        
        # Find best performers
        fastest = min(self.results, key=lambda r: r.get("latency", {}).get("mean_ms", float("inf")))
        cheapest = min(self.results, key=lambda r: r.get("estimated_cost_usd", float("inf")))
        most_reliable = max(self.results, key=lambda r: r.get("success_rate", 0))
        
        # Best overall (balanced)
        def score(r):
            latency = r.get("latency", {}).get("mean_ms", 1000)
            cost = r.get("estimated_cost_usd", 0.1) * 10000  # Normalize
            success = r.get("success_rate", 0)
            # Lower is better (latency and cost), higher success is better
            return latency + cost - (success * 500)
        
        best_overall = min(self.results, key=score)
        
        # Add recommendations
        recommendations.append({
            "category": "Performance",
            "recommendation": f"Use **{fastest.get('provider_name')}** ({fastest.get('model')}) for lowest latency",
            "details": f"Mean latency: {fastest.get('latency', {}).get('mean_ms', 0):.0f}ms",
            "priority": "high" if fastest.get("latency", {}).get("mean_ms", 1000) < 500 else "medium",
        })
        
        recommendations.append({
            "category": "Cost",
            "recommendation": f"Use **{cheapest.get('provider_name')}** ({cheapest.get('model')}) for lowest cost",
            "details": f"Estimated cost: ${cheapest.get('estimated_cost_usd', 0):.4f}",
            "priority": "high" if cheapest.get("estimated_cost_usd", 1) < 0.01 else "medium",
        })
        
        recommendations.append({
            "category": "Reliability",
            "recommendation": f"Use **{most_reliable.get('provider_name')}** ({most_reliable.get('model')}) for highest reliability",
            "details": f"Success rate: {most_reliable.get('success_rate', 0)*100:.0f}%",
            "priority": "high" if most_reliable.get("success_rate", 0) >= 0.99 else "medium",
        })
        
        recommendations.append({
            "category": "Overall",
            "recommendation": f"**{best_overall.get('provider_name')}** offers the best balance of performance, cost, and reliability",
            "details": f"Latency: {best_overall.get('latency', {}).get('mean_ms', 0):.0f}ms, Cost: ${best_overall.get('estimated_cost_usd', 0):.4f}, Success: {best_overall.get('success_rate', 0)*100:.0f}%",
            "priority": "high",
        })
        
        # Add warnings
        for result in self.results:
            if result.get("success_rate", 1) < 0.9:
                recommendations.append({
                    "category": "Warning",
                    "recommendation": f"**{result.get('provider_name')}** has low success rate ({result.get('success_rate', 0)*100:.0f}%)",
                    "details": "Consider investigating API issues or rate limiting",
                    "priority": "high",
                })
        
        return recommendations


# =============================================================================
# HTML REPORT GENERATOR
# =============================================================================

class HTMLReportGenerator:
    """Generate HTML benchmark reports."""
    
    def __init__(self, suite_data: Dict[str, Any], config: Optional[ReportConfig] = None):
        self.suite_data = suite_data
        self.config = config or ReportConfig()
        self.results = suite_data.get("results", [])
    
    def generate(self) -> str:
        """Generate complete HTML report."""
        sections = [
            self._html_header(),
            self._html_summary(),
            self._html_comparison_table(),
        ]
        
        if self.config.include_charts:
            sections.append(self._html_charts())
        
        if self.config.include_statistical_analysis:
            sections.append(self._html_statistical_analysis())
        
        if self.config.include_recommendations:
            sections.append(self._html_recommendations())
        
        if self.config.include_raw_data:
            sections.append(self._html_raw_data())
        
        sections.append(self._html_footer())
        
        return "\n".join(sections)
    
    def _html_header(self) -> str:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.config.title}</title>
    <style>
        :root {{
            --primary-color: #2563eb;
            --success-color: #10b981;
            --warning-color: #f59e0b;
            --danger-color: #ef4444;
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-color: #1e293b;
            --border-color: #e2e8f0;
        }}
        
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            padding: 2rem;
        }}
        
        .container {{ max-width: 1200px; margin: 0 auto; }}
        
        h1, h2, h3 {{ margin-bottom: 1rem; }}
        h1 {{ color: var(--primary-color); font-size: 2rem; }}
        h2 {{ color: var(--text-color); font-size: 1.5rem; border-bottom: 2px solid var(--primary-color); padding-bottom: 0.5rem; margin-top: 2rem; }}
        
        .card {{
            background: var(--card-bg);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }}
        
        .stat-card {{
            text-align: center;
            padding: 1rem;
            border-radius: 8px;
            background: linear-gradient(135deg, var(--primary-color), #3b82f6);
            color: white;
        }}
        
        .stat-card .value {{ font-size: 2rem; font-weight: bold; }}
        .stat-card .label {{ font-size: 0.875rem; opacity: 0.9; }}
        
        table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
        th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid var(--border-color); }}
        th {{ background: var(--bg-color); font-weight: 600; }}
        tr:hover {{ background: var(--bg-color); }}
        
        .badge {{
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .badge-success {{ background: var(--success-color); color: white; }}
        .badge-warning {{ background: var(--warning-color); color: white; }}
        .badge-danger {{ background: var(--danger-color); color: white; }}
        
        .chart-container {{ position: relative; height: 300px; margin: 1rem 0; }}
        
        .bar-chart {{
            display: flex;
            align-items: flex-end;
            gap: 1rem;
            height: 200px;
            padding: 1rem;
            background: var(--bg-color);
            border-radius: 8px;
        }}
        
        .bar {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        
        .bar-fill {{
            width: 100%;
            background: linear-gradient(180deg, var(--primary-color), #3b82f6);
            border-radius: 4px 4px 0 0;
            min-height: 4px;
            transition: height 0.3s ease;
        }}
        
        .bar-label {{ font-size: 0.75rem; margin-top: 0.5rem; text-align: center; }}
        .bar-value {{ font-size: 0.875rem; font-weight: 600; margin-bottom: 0.25rem; }}
        
        .recommendation {{
            padding: 1rem;
            border-left: 4px solid var(--primary-color);
            margin: 0.5rem 0;
            background: var(--bg-color);
            border-radius: 0 8px 8px 0;
        }}
        
        .recommendation.high {{ border-color: var(--success-color); }}
        .recommendation.warning {{ border-color: var(--warning-color); }}
        
        .footer {{ text-align: center; margin-top: 2rem; color: #64748b; font-size: 0.875rem; }}
        
        @media (max-width: 768px) {{
            body {{ padding: 1rem; }}
            .summary-grid {{ grid-template-columns: 1fr 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 {self.config.title}</h1>
        <p style="color: #64748b; margin-bottom: 2rem;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
"""
    
    def _html_summary(self) -> str:
        total_time = self.suite_data.get("total_time_seconds", 0)
        providers_count = len(self.results)
        total_runs = sum(r.get("runs", 0) for r in self.results)
        total_cost = sum(r.get("estimated_cost_usd", 0) for r in self.results)
        
        # Find fastest
        if self.results:
            fastest = min(self.results, key=lambda r: r.get("latency", {}).get("mean_ms", float("inf")))
            fastest_name = fastest.get("provider_name", "N/A")
            fastest_ms = fastest.get("latency", {}).get("mean_ms", 0)
        else:
            fastest_name = "N/A"
            fastest_ms = 0
        
        return f"""
        <div class="card">
            <h2>Summary</h2>
            <div class="summary-grid">
                <div class="stat-card">
                    <div class="value">{providers_count}</div>
                    <div class="label">Providers Tested</div>
                </div>
                <div class="stat-card">
                    <div class="value">{total_runs}</div>
                    <div class="label">Total Runs</div>
                </div>
                <div class="stat-card">
                    <div class="value">{total_time:.1f}s</div>
                    <div class="label">Total Time</div>
                </div>
                <div class="stat-card">
                    <div class="value">${total_cost:.4f}</div>
                    <div class="label">Total Cost</div>
                </div>
            </div>
            <p style="margin-top: 1rem; text-align: center; font-size: 1.1rem;">
                🏆 <strong>Fastest Provider:</strong> {fastest_name} ({fastest_ms:.0f}ms)
            </p>
        </div>
"""
    
    def _html_comparison_table(self) -> str:
        rows = []
        sorted_results = sorted(self.results, key=lambda r: r.get("latency", {}).get("mean_ms", float("inf")))
        
        for i, result in enumerate(sorted_results):
            name = result.get("provider_name", "Unknown")
            model = result.get("model", "N/A")
            runs = result.get("runs", 0)
            success = result.get("successful_runs", 0)
            success_rate = result.get("success_rate", 0)
            latency = result.get("latency", {})
            cost = result.get("estimated_cost_usd", 0)
            
            # Badge for ranking
            if i == 0:
                rank_badge = '<span class="badge badge-success">🥇 Fastest</span>'
            elif i == 1:
                rank_badge = '<span class="badge badge-warning">🥈</span>'
            elif i == 2:
                rank_badge = '<span class="badge badge-warning">🥉</span>'
            else:
                rank_badge = f'<span class="badge">#{i+1}</span>'
            
            # Success rate badge
            if success_rate >= 0.95:
                success_badge = "badge-success"
            elif success_rate >= 0.8:
                success_badge = "badge-warning"
            else:
                success_badge = "badge-danger"
            
            rows.append(f"""
                <tr>
                    <td>{rank_badge} <strong>{name}</strong></td>
                    <td>{model}</td>
                    <td>{latency.get('mean_ms', 0):.0f}ms</td>
                    <td>{latency.get('median_ms', 0):.0f}ms</td>
                    <td>{latency.get('p95_ms', 0):.0f}ms</td>
                    <td>${cost:.4f}</td>
                    <td><span class="badge {success_badge}">{success_rate*100:.0f}%</span></td>
                    <td>{success}/{runs}</td>
                </tr>
            """)
        
        return f"""
        <div class="card">
            <h2>Provider Comparison</h2>
            <table>
                <thead>
                    <tr>
                        <th>Provider</th>
                        <th>Model</th>
                        <th>Mean Latency</th>
                        <th>Median</th>
                        <th>P95</th>
                        <th>Cost</th>
                        <th>Success Rate</th>
                        <th>Runs</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(rows)}
                </tbody>
            </table>
        </div>
"""
    
    def _html_charts(self) -> str:
        # Latency bar chart
        bars = []
        max_latency = max((r.get("latency", {}).get("mean_ms", 0) for r in self.results), default=1)
        # Avoid division by zero when all providers failed
        if max_latency == 0:
            max_latency = 1
        
        for result in sorted(self.results, key=lambda r: r.get("latency", {}).get("mean_ms", 0)):
            name = result.get("provider_name", "?")
            latency = result.get("latency", {}).get("mean_ms", 0)
            height = (latency / max_latency) * 150  # Scale to 150px max
            
            bars.append(f"""
                <div class="bar">
                    <div class="bar-value">{latency:.0f}ms</div>
                    <div class="bar-fill" style="height: {height}px;"></div>
                    <div class="bar-label">{name}</div>
                </div>
            """)
        
        return f"""
        <div class="card">
            <h2>Latency Comparison</h2>
            <div class="bar-chart">
                {"".join(bars)}
            </div>
        </div>
"""
    
    def _html_statistical_analysis(self) -> str:
        if len(self.results) < 2:
            return ""
        
        analyzer = StatisticalAnalyzer()
        
        analyses = []
        for result in self.results:
            latencies = result.get("raw_latencies", [])
            if len(latencies) >= 2:
                lower, mean, upper = analyzer.calculate_confidence_interval(latencies)
                analyses.append(f"""
                    <tr>
                        <td><strong>{result.get('provider_name')}</strong></td>
                        <td>{mean:.0f}ms</td>
                        <td>{lower:.0f} - {upper:.0f}ms</td>
                        <td>{statistics.stdev(latencies):.1f}ms</td>
                    </tr>
                """)
        
        return f"""
        <div class="card">
            <h2>Statistical Analysis</h2>
            <h3>95% Confidence Intervals</h3>
            <table>
                <thead>
                    <tr>
                        <th>Provider</th>
                        <th>Mean</th>
                        <th>95% CI</th>
                        <th>Std Dev</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(analyses)}
                </tbody>
            </table>
        </div>
"""
    
    def _html_recommendations(self) -> str:
        engine = RecommendationEngine(self.results)
        recommendations = engine.generate_recommendations()
        
        rec_html = []
        for rec in recommendations:
            priority_class = "high" if rec["priority"] == "high" else ""
            if rec["category"] == "Warning":
                priority_class = "warning"
            
            rec_html.append(f"""
                <div class="recommendation {priority_class}">
                    <strong>{rec['category']}:</strong> {rec['recommendation']}<br>
                    <small style="color: #64748b;">{rec['details']}</small>
                </div>
            """)
        
        return f"""
        <div class="card">
            <h2>💡 Recommendations</h2>
            {"".join(rec_html)}
        </div>
"""
    
    def _html_raw_data(self) -> str:
        return f"""
        <div class="card">
            <h2>Raw Data</h2>
            <pre style="background: var(--bg-color); padding: 1rem; overflow-x: auto; border-radius: 4px; font-size: 0.875rem;">
{json.dumps(self.suite_data, indent=2)}
            </pre>
        </div>
"""
    
    def _html_footer(self) -> str:
        return """
        <div class="footer">
            <p>Generated by CAISSA Benchmark Suite • Phase 3.2+</p>
        </div>
    </div>
</body>
</html>
"""


# =============================================================================
# MARKDOWN REPORT GENERATOR
# =============================================================================

class MarkdownReportGenerator:
    """Generate Markdown benchmark reports."""
    
    def __init__(self, suite_data: Dict[str, Any], config: Optional[ReportConfig] = None):
        self.suite_data = suite_data
        self.config = config or ReportConfig()
        self.results = suite_data.get("results", [])
    
    def generate(self) -> str:
        """Generate complete Markdown report."""
        sections = [
            self._md_header(),
            self._md_summary(),
            self._md_comparison_table(),
        ]
        
        if self.config.include_statistical_analysis:
            sections.append(self._md_statistical_analysis())
        
        if self.config.include_recommendations:
            sections.append(self._md_recommendations())
        
        sections.append(self._md_footer())
        
        return "\n".join(sections)
    
    def _md_header(self) -> str:
        return f"""# 📊 {self.config.title}

> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---
"""
    
    def _md_summary(self) -> str:
        total_time = self.suite_data.get("total_time_seconds", 0)
        providers_count = len(self.results)
        total_runs = sum(r.get("runs", 0) for r in self.results)
        total_cost = sum(r.get("estimated_cost_usd", 0) for r in self.results)
        
        if self.results:
            fastest = min(self.results, key=lambda r: r.get("latency", {}).get("mean_ms", float("inf")))
            fastest_name = fastest.get("provider_name", "N/A")
            fastest_ms = fastest.get("latency", {}).get("mean_ms", 0)
        else:
            fastest_name = "N/A"
            fastest_ms = 0
        
        return f"""
## Summary

| Metric | Value |
|--------|-------|
| Providers Tested | {providers_count} |
| Total Runs | {total_runs} |
| Total Time | {total_time:.1f}s |
| Total Cost | ${total_cost:.4f} |

🏆 **Fastest Provider:** {fastest_name} ({fastest_ms:.0f}ms)

---
"""
    
    def _md_comparison_table(self) -> str:
        sorted_results = sorted(self.results, key=lambda r: r.get("latency", {}).get("mean_ms", float("inf")))
        
        rows = []
        for i, result in enumerate(sorted_results):
            rank = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{i+1}"
            name = result.get("provider_name", "Unknown")
            model = result.get("model", "N/A")
            latency = result.get("latency", {})
            cost = result.get("estimated_cost_usd", 0)
            success_rate = result.get("success_rate", 0)
            
            rows.append(f"| {rank} {name} | {model} | {latency.get('mean_ms', 0):.0f}ms | {latency.get('median_ms', 0):.0f}ms | ${cost:.4f} | {success_rate*100:.0f}% |")
        
        return f"""
## Provider Comparison

| Provider | Model | Mean Latency | Median | Cost | Success |
|----------|-------|-------------|--------|------|---------|
{chr(10).join(rows)}

---
"""
    
    def _md_statistical_analysis(self) -> str:
        if len(self.results) < 2:
            return ""
        
        analyzer = StatisticalAnalyzer()
        
        rows = []
        for result in self.results:
            latencies = result.get("raw_latencies", [])
            if len(latencies) >= 2:
                lower, mean, upper = analyzer.calculate_confidence_interval(latencies)
                std = statistics.stdev(latencies)
                rows.append(f"| {result.get('provider_name')} | {mean:.0f}ms | {lower:.0f} - {upper:.0f}ms | ±{std:.1f}ms |")
        
        return f"""
## Statistical Analysis

### 95% Confidence Intervals

| Provider | Mean | 95% CI | Std Dev |
|----------|------|--------|---------|
{chr(10).join(rows)}

---
"""
    
    def _md_recommendations(self) -> str:
        engine = RecommendationEngine(self.results)
        recommendations = engine.generate_recommendations()
        
        rec_md = []
        for rec in recommendations:
            icon = "✅" if rec["priority"] == "high" else "💡"
            if rec["category"] == "Warning":
                icon = "⚠️"
            
            rec_md.append(f"- {icon} **{rec['category']}**: {rec['recommendation']}")
            rec_md.append(f"  - _{rec['details']}_")
        
        return f"""
## 💡 Recommendations

{chr(10).join(rec_md)}

---
"""
    
    def _md_footer(self) -> str:
        return """
---

*Generated by CAISSA Benchmark Suite • Phase 3.2+*
"""


# =============================================================================
# MAIN REPORT GENERATOR
# =============================================================================

class ReportGenerator:
    """
    Main report generator supporting multiple output formats.
    
    Usage:
        generator = ReportGenerator(benchmark_suite_data)
        html = generator.to_html()
        markdown = generator.to_markdown()
        generator.save("report.html", format="html")
    """
    
    def __init__(self, suite_data: Dict[str, Any], config: Optional[ReportConfig] = None):
        self.suite_data = suite_data
        self.config = config or ReportConfig()
    
    def to_html(self) -> str:
        """Generate HTML report."""
        logger.info("Generating HTML benchmark report")
        generator = HTMLReportGenerator(self.suite_data, self.config)
        return generator.generate()
    
    def to_markdown(self) -> str:
        """Generate Markdown report."""
        logger.info("Generating Markdown benchmark report")
        generator = MarkdownReportGenerator(self.suite_data, self.config)
        return generator.generate()
    
    def to_json(self, pretty: bool = True) -> str:
        """Export raw data as JSON."""
        if pretty:
            return json.dumps(self.suite_data, indent=2)
        return json.dumps(self.suite_data)
    
    def save(self, path: str, format: Optional[str] = None) -> None:
        """
        Save report to file.
        
        Args:
            path: Output file path
            format: Output format (html, md, json). Auto-detected from extension if not provided.
        """
        # Auto-detect format from extension
        if format is None:
            ext = os.path.splitext(path)[1].lower()
            format = {".html": "html", ".htm": "html", ".md": "markdown", ".json": "json"}.get(ext, "html")
        
        # Generate content
        if format == "html":
            content = self.to_html()
        elif format in ("markdown", "md"):
            content = self.to_markdown()
        elif format == "json":
            content = self.to_json()
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        # Write to file
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"Report saved to: {path}")


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate benchmark reports")
    parser.add_argument("input", help="Input JSON file with benchmark data")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--format", "-f", choices=["html", "markdown", "json"], default="html")
    parser.add_argument("--title", "-t", default="CAISSA Benchmark Report")
    
    args = parser.parse_args()
    
    # Load input data
    with open(args.input) as f:
        suite_data = json.load(f)
    
    # Generate report
    config = ReportConfig(title=args.title)
    generator = ReportGenerator(suite_data, config)
    
    if args.output:
        generator.save(args.output, format=args.format)
    else:
        # Print to stdout
        if args.format == "html":
            print(generator.to_html())
        elif args.format == "markdown":
            print(generator.to_markdown())
        else:
            print(generator.to_json())


if __name__ == "__main__":
    main()
