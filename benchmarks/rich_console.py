"""
benchmarks/rich_console.py

Rich console output utilities for benchmark visualization.

PHASE 3.2+: Enhanced Visualization
- Color-coded tables and progress bars
- ASCII charts for latency distribution
- Live progress indicators
- Statistical summaries

Works with or without 'rich' library installed.
"""

import sys
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# =============================================================================
# COLOR CODES (ANSI)
# =============================================================================

class Color:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    
    # Foreground
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    # Bright foreground
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    
    # Background
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def supports_color() -> bool:
    """Check if terminal supports color output."""
    if os.getenv("NO_COLOR"):
        return False
    if os.getenv("FORCE_COLOR"):
        return True
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


def colorize(text: str, *colors: str) -> str:
    """Apply color codes to text if terminal supports it."""
    if not supports_color():
        return text
    return "".join(colors) + text + Color.RESET


# =============================================================================
# SYMBOLS
# =============================================================================

class Symbol:
    """Unicode symbols for visual elements."""
    CHECK = "✓"
    CROSS = "✗"
    ARROW = "→"
    BULLET = "•"
    STAR = "★"
    CROWN = "👑"
    TROPHY = "🏆"
    ROCKET = "🚀"
    CHART = "📊"
    CLOCK = "⏱"
    MONEY = "💰"
    WARNING = "⚠"
    INFO = "ℹ"
    
    # Progress bar elements
    BAR_FULL = "█"
    BAR_HALF = "▌"
    BAR_EMPTY = "░"
    
    # Spark lines
    SPARK = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


# =============================================================================
# PROGRESS BAR
# =============================================================================

class ProgressBar:
    """ASCII progress bar for terminal output."""
    
    def __init__(
        self, 
        total: int, 
        width: int = 40,
        prefix: str = "",
        suffix: str = "",
        fill: str = Symbol.BAR_FULL,
        empty: str = Symbol.BAR_EMPTY,
    ):
        self.total = total
        self.width = width
        self.prefix = prefix
        self.suffix = suffix
        self.fill = fill
        self.empty = empty
        self.current = 0
    
    def update(self, current: int) -> str:
        """Update progress and return the bar string."""
        self.current = min(current, self.total)
        percent = self.current / self.total if self.total > 0 else 0
        filled = int(self.width * percent)
        
        bar = self.fill * filled + self.empty * (self.width - filled)
        percent_str = f"{percent*100:5.1f}%"
        
        return f"{self.prefix}|{bar}| {percent_str} {self.suffix}"
    
    def increment(self, amount: int = 1) -> str:
        """Increment progress and return the bar string."""
        return self.update(self.current + amount)
    
    def render(self) -> str:
        """Render current progress bar."""
        return self.update(self.current)


class LiveProgress:
    """Live updating progress display."""
    
    def __init__(self, total: int, description: str = "Processing"):
        self.bar = ProgressBar(total, prefix=description)
        self.start_time = None
        self._last_line_length = 0
    
    def start(self):
        """Start timing."""
        import time
        self.start_time = time.time()
    
    def update(self, current: int, status: str = ""):
        """Update and display progress."""
        import time
        elapsed = time.time() - self.start_time if self.start_time else 0
        
        bar_str = self.bar.update(current)
        time_str = f"[{elapsed:.1f}s]"
        
        line = f"\r{bar_str} {time_str} {status}"
        
        # Clear previous line if longer
        if len(line) < self._last_line_length:
            line += " " * (self._last_line_length - len(line))
        
        self._last_line_length = len(line)
        sys.stdout.write(line)
        sys.stdout.flush()
    
    def finish(self, message: str = "Complete!"):
        """Finish with a final message."""
        self.update(self.bar.total, colorize(message, Color.GREEN))
        print()  # New line


# =============================================================================
# SPARKLINE CHARTS
# =============================================================================

def sparkline(values: List[float], width: int = 20) -> str:
    """Generate a sparkline chart from values."""
    if not values:
        return ""
    
    min_val = min(values)
    max_val = max(values)
    range_val = max_val - min_val or 1
    
    # Normalize values to 0-7 range for sparkline characters
    normalized = [int((v - min_val) / range_val * 7) for v in values]
    
    # Sample if too many values
    if len(normalized) > width:
        step = len(normalized) / width
        normalized = [normalized[int(i * step)] for i in range(width)]
    
    return "".join(Symbol.SPARK[n] for n in normalized)


def histogram(values: List[float], bins: int = 10, width: int = 40) -> List[str]:
    """Generate ASCII histogram."""
    if not values:
        return ["No data"]
    
    min_val = min(values)
    max_val = max(values)
    range_val = max_val - min_val or 1
    bin_width = range_val / bins
    
    # Count values in each bin
    counts = [0] * bins
    for v in values:
        bin_idx = min(int((v - min_val) / bin_width), bins - 1)
        counts[bin_idx] += 1
    
    # Generate histogram lines
    max_count = max(counts) or 1
    lines = []
    
    for i, count in enumerate(counts):
        bin_start = min_val + i * bin_width
        bin_end = bin_start + bin_width
        bar_len = int((count / max_count) * width)
        bar = Symbol.BAR_FULL * bar_len
        
        lines.append(f"{bin_start:8.1f}-{bin_end:8.1f} |{bar} ({count})")
    
    return lines


# =============================================================================
# TABLES
# =============================================================================

@dataclass
class TableColumn:
    """Table column definition."""
    header: str
    width: int = 15
    align: str = "left"  # left, right, center
    color: Optional[str] = None


class Table:
    """ASCII table generator with color support."""
    
    def __init__(self, columns: List[TableColumn], title: str = ""):
        self.columns = columns
        self.title = title
        self.rows: List[List[Any]] = []
    
    def add_row(self, *values: Any):
        """Add a row of values."""
        self.rows.append(list(values))
    
    def _format_cell(self, value: Any, column: TableColumn) -> str:
        """Format a cell value."""
        text = str(value)[:column.width]
        
        if column.align == "right":
            text = text.rjust(column.width)
        elif column.align == "center":
            text = text.center(column.width)
        else:
            text = text.ljust(column.width)
        
        if column.color:
            text = colorize(text, column.color)
        
        return text
    
    def render(self) -> str:
        """Render the table as a string."""
        lines = []
        
        # Calculate total width
        total_width = sum(c.width for c in self.columns) + len(self.columns) * 3 + 1
        
        # Title
        if self.title:
            lines.append(colorize(f"\n{self.title.center(total_width)}", Color.BOLD))
        
        # Top border
        lines.append("╔" + "═" * (total_width - 2) + "╗")
        
        # Header row
        header_cells = [self._format_cell(c.header, c) for c in self.columns]
        lines.append("║ " + " │ ".join(header_cells) + " ║")
        
        # Header separator
        lines.append("╠" + "═" * (total_width - 2) + "╣")
        
        # Data rows
        for row in self.rows:
            cells = []
            for i, value in enumerate(row):
                col = self.columns[i] if i < len(self.columns) else self.columns[-1]
                cells.append(self._format_cell(value, col))
            lines.append("║ " + " │ ".join(cells) + " ║")
        
        # Bottom border
        lines.append("╚" + "═" * (total_width - 2) + "╝")
        
        return "\n".join(lines)


# =============================================================================
# BENCHMARK RESULT FORMATTERS
# =============================================================================

def format_latency(ms: float) -> str:
    """Format latency with color based on value."""
    if ms < 500:
        return colorize(f"{ms:,.0f}ms", Color.GREEN)
    elif ms < 2000:
        return colorize(f"{ms:,.0f}ms", Color.YELLOW)
    else:
        return colorize(f"{ms:,.0f}ms", Color.RED)


def format_cost(usd: float) -> str:
    """Format cost with color based on value."""
    if usd < 0.01:
        return colorize(f"${usd:.4f}", Color.GREEN)
    elif usd < 0.10:
        return colorize(f"${usd:.4f}", Color.YELLOW)
    else:
        return colorize(f"${usd:.4f}", Color.RED)


def format_success_rate(rate: float) -> str:
    """Format success rate with color."""
    percentage = rate * 100
    if rate >= 0.95:
        return colorize(f"{percentage:.0f}%", Color.GREEN)
    elif rate >= 0.80:
        return colorize(f"{percentage:.0f}%", Color.YELLOW)
    else:
        return colorize(f"{percentage:.0f}%", Color.RED)


def format_quality_score(score: float) -> str:
    """Format quality score (0-100) with color and icon."""
    if score >= 80:
        return colorize(f"{Symbol.STAR} {score:.0f}", Color.GREEN)
    elif score >= 60:
        return colorize(f"{score:.0f}", Color.YELLOW)
    else:
        return colorize(f"{score:.0f}", Color.RED)


# =============================================================================
# BENCHMARK SUMMARY RENDERERS
# =============================================================================

def render_benchmark_header(title: str = "CAISSA Benchmark Suite") -> str:
    """Render benchmark header banner."""
    width = 70
    lines = [
        "",
        colorize("╔" + "═" * (width - 2) + "╗", Color.CYAN),
        colorize("║" + f" {Symbol.CHART} {title} {Symbol.CHART} ".center(width - 2) + "║", Color.CYAN, Color.BOLD),
        colorize("╚" + "═" * (width - 2) + "╝", Color.CYAN),
        "",
    ]
    return "\n".join(lines)


def render_provider_card(result: Dict[str, Any]) -> str:
    """Render a provider result as a card."""
    name = result.get("provider_name", "Unknown")
    model = result.get("model", "N/A")
    success_rate = result.get("success_rate", 0)
    latency = result.get("latency", {}).get("mean_ms", 0)
    cost = result.get("estimated_cost_usd", 0)
    
    # Status icon
    if success_rate >= 0.95:
        status = colorize(f"{Symbol.CHECK} ", Color.GREEN)
    elif success_rate >= 0.5:
        status = colorize(f"{Symbol.WARNING} ", Color.YELLOW)
    else:
        status = colorize(f"{Symbol.CROSS} ", Color.RED)
    
    lines = [
        colorize(f"┌─ {status}{name} ", Color.BOLD) + colorize(f"({model})", Color.DIM),
        f"│  Latency: {format_latency(latency)}",
        f"│  Cost:    {format_cost(cost)}",
        f"│  Success: {format_success_rate(success_rate)}",
        "└" + "─" * 40,
    ]
    return "\n".join(lines)


def render_comparison_table(results: List[Dict[str, Any]]) -> str:
    """Render a comparison table for multiple providers."""
    table = Table(
        columns=[
            TableColumn("Provider", width=15),
            TableColumn("Model", width=20),
            TableColumn("Latency", width=12, align="right"),
            TableColumn("Cost", width=12, align="right"),
            TableColumn("Success", width=10, align="right"),
        ],
        title=f"{Symbol.TROPHY} Provider Comparison"
    )
    
    # Sort by latency (fastest first)
    sorted_results = sorted(results, key=lambda r: r.get("latency", {}).get("mean_ms", float("inf")))
    
    for i, result in enumerate(sorted_results):
        # Winner icon
        name = result.get("provider_name", "Unknown")
        if i == 0:
            name = f"{Symbol.CROWN} {name}"
        
        table.add_row(
            name,
            result.get("model", "N/A")[:20],
            format_latency(result.get("latency", {}).get("mean_ms", 0)),
            format_cost(result.get("estimated_cost_usd", 0)),
            format_success_rate(result.get("success_rate", 0)),
        )
    
    return table.render()


def render_latency_distribution(latencies: List[float], provider: str) -> str:
    """Render latency distribution visualization."""
    if not latencies:
        return "No latency data"
    
    import statistics
    
    lines = [
        colorize(f"\n{Symbol.CLOCK} Latency Distribution: {provider}", Color.BOLD),
        "",
        f"  Sparkline: {sparkline(latencies)}",
        "",
        f"  Min:    {min(latencies):,.0f}ms",
        f"  Max:    {max(latencies):,.0f}ms",
        f"  Mean:   {statistics.mean(latencies):,.0f}ms",
        f"  Median: {statistics.median(latencies):,.0f}ms",
        "",
        "  Distribution:",
    ]
    
    for line in histogram(latencies, bins=5, width=30):
        lines.append(f"    {line}")
    
    return "\n".join(lines)


def render_cost_breakdown(results: List[Dict[str, Any]]) -> str:
    """Render cost breakdown visualization."""
    lines = [
        colorize(f"\n{Symbol.MONEY} Cost Analysis", Color.BOLD),
        "",
    ]
    
    # Sort by cost
    sorted_results = sorted(results, key=lambda r: r.get("estimated_cost_usd", 0))
    max_cost = max(r.get("estimated_cost_usd", 0) for r in results) or 1
    
    for result in sorted_results:
        name = result.get("provider_name", "Unknown")
        cost = result.get("estimated_cost_usd", 0)
        bar_len = int((cost / max_cost) * 30) if max_cost > 0 else 0
        bar = Symbol.BAR_FULL * bar_len
        
        if cost == 0:
            cost_str = colorize("FREE", Color.GREEN, Color.BOLD)
        else:
            cost_str = format_cost(cost)
        
        lines.append(f"  {name:15} │{bar:30} {cost_str}")
    
    return "\n".join(lines)


# =============================================================================
# SUMMARY GENERATORS
# =============================================================================

def render_benchmark_summary(suite_data: Dict[str, Any]) -> str:
    """Render complete benchmark summary."""
    results = suite_data.get("results", [])
    
    sections = [
        render_benchmark_header(),
        f"  {Symbol.CLOCK} Total Time: {suite_data.get('total_time_seconds', 0):.1f}s",
        f"  {Symbol.BULLET} Providers Tested: {len(results)}",
        f"  {Symbol.BULLET} Date: {suite_data.get('benchmark_date', 'N/A')}",
        "",
        render_comparison_table(results),
        "",
        render_cost_breakdown(results),
    ]
    
    # Add latency distribution for each provider
    for result in results:
        latencies = result.get("raw_latencies", [])
        if latencies:
            sections.append(render_latency_distribution(latencies, result.get("provider_name", "Unknown")))
    
    # Winner announcement
    if results:
        winner = min(results, key=lambda r: r.get("latency", {}).get("mean_ms", float("inf")))
        sections.append("")
        sections.append(colorize(
            f"  {Symbol.ROCKET} Fastest Provider: {winner.get('provider_name')} ({winner.get('model')})",
            Color.GREEN, Color.BOLD
        ))
    
    return "\n".join(sections)


# =============================================================================
# MAIN - DEMO
# =============================================================================

if __name__ == "__main__":
    # Demo output
    print(render_benchmark_header())
    
    # Demo progress bar
    print("\nProgress Bar Demo:")
    bar = ProgressBar(100)
    for i in range(0, 101, 20):
        print(f"  {bar.update(i)}")
    
    # Demo sparkline
    import random
    values = [random.uniform(100, 500) for _ in range(20)]
    print(f"\nSparkline Demo: {sparkline(values)}")
    
    # Demo histogram
    print("\nHistogram Demo:")
    for line in histogram(values, bins=5, width=20):
        print(f"  {line}")
    
    # Demo table
    table = Table(
        columns=[
            TableColumn("Name", 12),
            TableColumn("Value", 10, align="right"),
            TableColumn("Status", 10, align="center"),
        ],
        title="Demo Table"
    )
    table.add_row("OpenAI", "42ms", colorize(Symbol.CHECK, Color.GREEN))
    table.add_row("Anthropic", "128ms", colorize(Symbol.CHECK, Color.GREEN))
    table.add_row("Ollama", "15ms", colorize(Symbol.CHECK, Color.GREEN))
    print(table.render())
    
    # Demo formatters
    print("\nFormatter Demo:")
    print(f"  Latency: {format_latency(150)} | {format_latency(800)} | {format_latency(3000)}")
    print(f"  Cost:    {format_cost(0.001)} | {format_cost(0.05)} | {format_cost(0.50)}")
    print(f"  Success: {format_success_rate(0.98)} | {format_success_rate(0.85)} | {format_success_rate(0.60)}")
