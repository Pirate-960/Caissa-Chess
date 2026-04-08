"""
core/match_workflow.py

Complete workflow for running and analyzing LLM vs LLM matches.

This module provides a high-level API that combines:
1. MatchEngine - Playing the match
2. MatchAnalyzer - Post-match analysis
3. MatchExporter - Rich export with annotations

Example:
    from core.match_workflow import run_analyzed_match
    
    result = await run_analyzed_match(
        white_player=gpt4_player,
        black_player=claude_player,
        stockfish_path="path/to/stockfish",
        output_dir="matches/",
        enable_analysis=True
    )

Author: CAISSA Team
Version: 0.5.0
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from core.match_engine import MatchEngine, MatchResult
from core.match_analyzer import MatchAnalyzer, MatchAnalysis
from core.tournament_player import TournamentPlayer, TimeControl
from core.llm_provider import LLMProvider
from export.tournament_exporter import MatchExporter
from export.game_exporter import ExportConfig

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# HIGH-LEVEL WORKFLOW FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

async def run_analyzed_match(
    white_player: TournamentPlayer,
    black_player: TournamentPlayer,
    stockfish_path: Optional[str] = None,
    commentary_provider: Optional[LLMProvider] = None,
    time_control: TimeControl = TimeControl.RAPID,
    output_dir: Optional[Path] = None,
    enable_analysis: bool = True,
    enable_commentary: bool = True,
    analysis_depth: int = 15,
    export_formats: list = None,
    match_id: Optional[str] = None,
) -> Tuple[MatchResult, Optional[MatchAnalysis]]:
    """
    Complete LLM vs LLM match workflow with analysis and export.
    
    Pipeline:
    1. Play the match (MatchEngine)
    2. Analyze the match (MatchAnalyzer) - optional
    3. Export results (MatchExporter) - HTML, PGN, JSON, Markdown
    
    Args:
        white_player: White's tournament player
        black_player: Black's tournament player
        stockfish_path: Path to Stockfish binary (required for analysis)
        commentary_provider: LLM for strategic commentary (optional)
        time_control: Time control (BULLET, BLITZ, RAPID, etc.)
        output_dir: Directory for output files (None = no export)
        enable_analysis: Run post-match analysis
        enable_commentary: Generate LLM commentary (requires commentary_provider)
        analysis_depth: Stockfish depth for analysis
        export_formats: List of formats ["html", "pgn", "json", "md"] (None = all)
        match_id: Custom match ID (generated if None)
    
    Returns:
        Tuple of (MatchResult, MatchAnalysis)
        MatchAnalysis is None if enable_analysis=False
    
    Example:
        result, analysis = await run_analyzed_match(
            white_player=gpt4,
            black_player=claude,
            stockfish_path="/usr/bin/stockfish",
            output_dir=Path("matches/"),
            enable_analysis=True,
            enable_commentary=True,
        )
        
        print(f"Winner: {result.result.value}")
        print(f"Beauty: {analysis.beauty_score:.1f}")
        print(f"Critical Moments: {len(analysis.critical_moments)}")
    """
    if export_formats is None:
        export_formats = ["html", "pgn", "json", "md"]
    
    logger.info(
        f"Starting analyzed match: {white_player.name} (White) vs {black_player.name} (Black) "
        f"[Time Control: {time_control.name}, Analysis: {enable_analysis}]"
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 1: PLAY THE MATCH
    # ═══════════════════════════════════════════════════════════════════════════
    
    logger.info("▶️  Step 1: Playing match...")
    
    match_engine = MatchEngine(
        white=white_player,
        black=black_player,
        time_control=time_control,
        match_id=match_id,
    )
    
    match_result = await match_engine.play_match()
    
    logger.info(
        f"✅ Match complete: {match_result.result.value} "
        f"({match_result.total_moves} moves, {match_result.duration:.1f}s)"
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 2: ANALYZE THE MATCH (if enabled)
    # ═══════════════════════════════════════════════════════════════════════════
    
    match_analysis = None
    
    if enable_analysis:
        if not stockfish_path:
            logger.warning("⚠️  Analysis requested but no Stockfish path provided. Skipping analysis.")
        else:
            logger.info("▶️  Step 2: Analyzing match...")
            
            with MatchAnalyzer(
                stockfish_path=stockfish_path,
                commentary_provider=commentary_provider if enable_commentary else None,
                depth=analysis_depth,
                enable_commentary=enable_commentary,
            ) as analyzer:
                match_analysis = await analyzer.analyze_match(match_result)
            
            logger.info(
                f"✅ Analysis complete: Beauty={match_analysis.beauty_score:.1f}, "
                f"Drama={match_analysis.drama_score:.1f}, "
                f"Critical Moments={len(match_analysis.critical_moments)}"
            )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 3: EXPORT RESULTS (if output_dir provided)
    # ═══════════════════════════════════════════════════════════════════════════
    
    if output_dir:
        logger.info("▶️  Step 3: Exporting results...")
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create filename base
        filename_base = (
            f"{match_result.match_id[:8]}_"
            f"{white_player.name.replace(' ', '_')}_vs_{black_player.name.replace(' ', '_')}"
        )
        
        # Create exporter with analysis (if available)
        exporter = MatchExporter(
            match_result=match_result,
            match_analysis=match_analysis,
            include_elo=True,
        )
        
        # Export to requested formats
        exports_completed = []
        
        if "html" in export_formats:
            html_path = output_dir / f"{filename_base}.html"
            html_content = exporter.export_html()
            html_path.write_text(html_content, encoding="utf-8")
            exports_completed.append(f"HTML → {html_path}")
        
        if "pgn" in export_formats:
            pgn_path = output_dir / f"{filename_base}.pgn"
            pgn_content = exporter.export_pgn()
            pgn_path.write_text(pgn_content, encoding="utf-8")
            exports_completed.append(f"PGN → {pgn_path}")
        
        if "json" in export_formats:
            json_path = output_dir / f"{filename_base}.json"
            json_content = exporter.export_json()
            json_path.write_text(json_content, encoding="utf-8")
            exports_completed.append(f"JSON → {json_path}")
        
        if "md" in export_formats:
            md_path = output_dir / f"{filename_base}.md"
            md_content = exporter.export_markdown()
            md_path.write_text(md_content, encoding="utf-8")
            exports_completed.append(f"Markdown → {md_path}")
        
        for export_msg in exports_completed:
            logger.info(f"✅ {export_msg}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DONE
    # ═══════════════════════════════════════════════════════════════════════════
    
    logger.info("🎉 Match workflow complete!")
    
    return match_result, match_analysis


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH MATCH WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════════

async def run_match_series(
    white_player: TournamentPlayer,
    black_player: TournamentPlayer,
    num_games: int = 5,
    **kwargs
) -> list:
    """
    Run a series of matches between two players.
    
    Useful for:
    - Best-of-N series
    - Statistical significance testing
    - Head-to-head records
    
    Args:
        white_player: White's tournament player
        black_player: Black's tournament player
        num_games: Number of games to play
        **kwargs: Passed to run_analyzed_match()
    
    Returns:
        List of (MatchResult, MatchAnalysis) tuples
    """
    logger.info(
        f"Starting {num_games}-game series: "
        f"{white_player.name} vs {black_player.name}"
    )
    
    results = []
    
    for game_num in range(1, num_games + 1):
        logger.info(f"═══ Game {game_num}/{num_games} ═══")
        
        # Alternate colors for fairness
        if game_num % 2 == 1:
            w, b = white_player, black_player
        else:
            w, b = black_player, white_player
        
        result, analysis = await run_analyzed_match(
            white_player=w,
            black_player=b,
            **kwargs
        )
        
        results.append((result, analysis))
    
    # Print series summary
    white_wins = sum(1 for r, _ in results if r.result.value == "1-0")
    black_wins = sum(1 for r, _ in results if r.result.value == "0-1")
    draws = sum(1 for r, _ in results if r.result.value == "1/2-1/2")
    
    logger.info(
        f"📊 Series complete: "
        f"{white_player.name} {white_wins}-{black_wins}-{draws} {black_player.name}"
    )
    
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def load_workflow_config(config_path: Path) -> Dict[str, Any]:
    """
    Load workflow configuration from YAML file.
    
    Example config:
        match:
          time_control: "rapid"
          enable_analysis: true
          enable_commentary: true
          analysis_depth: 15
          
        export:
          output_dir: "matches/"
          formats: ["html", "pgn", "json"]
          
        stockfish:
          path: "/usr/bin/stockfish"
    """
    import yaml
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    return config


def create_workflow_from_config(config: Dict[str, Any]) -> dict:
    """
    Create workflow parameters from config dictionary.
    
    Returns kwargs for run_analyzed_match()
    """
    workflow_kwargs = {}
    
    # Match settings
    if "match" in config:
        match_config = config["match"]
        
        if "time_control" in match_config:
            from core.tournament_player import TimeControl
            workflow_kwargs["time_control"] = TimeControl[match_config["time_control"].upper()]
        
        workflow_kwargs["enable_analysis"] = match_config.get("enable_analysis", True)
        workflow_kwargs["enable_commentary"] = match_config.get("enable_commentary", True)
        workflow_kwargs["analysis_depth"] = match_config.get("analysis_depth", 15)
    
    # Export settings
    if "export" in config:
        export_config = config["export"]
        
        if "output_dir" in export_config:
            workflow_kwargs["output_dir"] = Path(export_config["output_dir"])
        
        workflow_kwargs["export_formats"] = export_config.get("formats", ["html", "pgn", "json", "md"])
    
    # Stockfish
    if "stockfish" in config and "path" in config["stockfish"]:
        workflow_kwargs["stockfish_path"] = config["stockfish"]["path"]
    
    return workflow_kwargs


# ═══════════════════════════════════════════════════════════════════════════════
# CLI HELPER
# ═══════════════════════════════════════════════════════════════════════════════

async def main_cli():
    """
    Simple CLI for testing match workflow.
    
    Usage:
        python -m core.match_workflow
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Run an analyzed LLM vs LLM chess match")
    parser.add_argument("--white", required=True, help="White player provider:model")
    parser.add_argument("--black", required=True, help="Black player provider:model")
    parser.add_argument("--stockfish", help="Path to Stockfish binary")
    parser.add_argument("--output", default="matches/", help="Output directory")
    parser.add_argument("--time-control", default="rapid", choices=["bullet", "blitz", "rapid", "classical"])
    parser.add_argument("--no-analysis", action="store_true", help="Disable post-match analysis")
    parser.add_argument("--no-commentary", action="store_true", help="Disable LLM commentary")
    parser.add_argument("--depth", type=int, default=15, help="Stockfish analysis depth")
    
    args = parser.parse_args()
    
    # TODO: Parse white/black player specs and create TournamentPlayer instances
    # This would require integration with LLM provider factory
    
    print("Match workflow CLI - TODO: Implement player creation from CLI args")


if __name__ == "__main__":
    asyncio.run(main_cli())
