"""
export/tournament_exporter.py

Tournament export implementation for CAISSA Chess v0.5.0.

Provides exporters for complete tournament results:
- Markdown (standings, crosstable, round results)
- HTML (full interactive report)
- JSON (structured data for external tools)
- PGN (all games in one file, pretty or strict)
- Per-game PGN (individual files)

Author: CAISSA Team
Version: 0.5.0
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from export.game_exporter import GameExporter, ExportConfig

logger = logging.getLogger(__name__)


@dataclass
class TournamentExportConfig:
    """Configuration for tournament exports."""
    # Markdown
    md_include_standings: bool = True
    md_include_crosstable: bool = True
    md_include_rounds: bool = True
    md_include_game_links: bool = True
    
    # Analytics
    analytics_include_elo: bool = True
    analytics_include_style: bool = True
    analytics_include_openings: bool = True
    analytics_charts_enabled: bool = True
    
    # Collection
    collection_separate_files: bool = False  # True = one PGN per game
    collection_include_index: bool = True
    collection_pretty_pgn: bool = True  # True = use GameExporter.export_pgn()
    
    # HTML Report
    html_tournament_template: str = "default"
    html_include_crosstable: bool = True
    html_include_player_stats: bool = True
    html_dark_mode: bool = True


class TournamentExporter:
    """
    Complete tournament result exporter.
    
    Handles multi-format exports of tournament standings, matches,
    and performance analytics.
    """
    
    def __init__(
        self,
        tournament_result: Any,  # TournamentResult from Tournament.run()
        config: Optional[TournamentExportConfig] = None,
    ):
        self.result = tournament_result
        self.config = config or TournamentExportConfig()
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    # =========================================================================
    # MARKDOWN EXPORTS
    # =========================================================================
    
    def export_standings_markdown(self, filepath: Optional[str] = None) -> str:
        """
        Export tournament standings as a Markdown table.
        """
        lines = []
        lines.append(f"# Tournament Standings: {self.result.config.name}")
        lines.append("")
        lines.append(f"**Format:** {self.result.config.format.value}")
        lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        
        # Table header
        lines.append("| Rank | Player | Points | Wins | Draws | Losses | Games |")
        lines.append("|------|--------|--------|------|-------|--------|-------|")
        
        for standing in self.result.standings:
            lines.append(
                f"| {standing.rank} | **{standing.player.name}** | {standing.points:.1f} | "
                f"{standing.wins} | {standing.draws} | {standing.losses} | {standing.games_played} |"
            )
            
        content = "\n".join(lines)
        
        if filepath:
            Path(filepath).write_text(content, encoding="utf-8")
            
        return content

    def export_crosstable_markdown(self, filepath: Optional[str] = None) -> str:
        """
        Export tournament crosstable as a Markdown table.
        """
        # Note: Implementation depends on Crosstable object in result
        if not hasattr(self.result, 'crosstable') or not self.result.crosstable:
            return "Crosstable not available."
            
        lines = []
        lines.append(f"# Tournament Crosstable: {self.result.config.name}")
        lines.append("")
        
        # Build table
        players = [s.player for s in self.result.standings]
        header = "| Player | " + " | ".join([f"{i+1}" for i in range(len(players))]) + " | Pts |"
        separator = "|:---| " + " | ".join([":---:" for _ in range(len(players))]) + " |:---:|"
        
        lines.append(header)
        lines.append(separator)
        
        for i, p1 in enumerate(players):
            row = [f"{i+1}. {p1.name}"]
            for j, p2 in enumerate(players):
                if i == j:
                    row.append("—")
                else:
                    score = self.result.crosstable.get_score(p1.id, p2.id)
                    row.append(str(score) if score is not None else ".")
            
            # Find points for this player
            points = next(s.points for s in self.result.standings if s.player.id == p1.id)
            row.append(f"**{points:.1f}**")
            lines.append("| " + " | ".join(row) + " |")
            
        content = "\n".join(lines)
        
        if filepath:
            Path(filepath).write_text(content, encoding="utf-8")
            
        return content

    # =========================================================================
    # PGN EXPORTS
    # =========================================================================
    
    def export_all_games_pgn(self, filepath: Optional[str] = None, pretty: bool = True) -> str:
        """
        Export all tournament games as a single PGN collection.
        
        Uses the existing GameExporter for each individual game.
        
        Args:
            filepath: Optional path to save file
            pretty: Whether to use pretty PGN format (default: True)
        
        Returns:
            str: Complete PGN collection
        """
        pgn_parts = []
        
        for i, match in enumerate(self.result.matches, 1):
            # Add game header comment
            pgn_parts.append(f"; === Game {i}: {match.white.name} vs {match.black.name} ===")
            pgn_parts.append("")
            
            # Use MatchExporter to get the PGN
            try:
                exporter = MatchExporter(match, include_elo=True)
                if pretty:
                    pgn_parts.append(exporter.export_pgn())
                else:
                    pgn_parts.append(exporter.export_pgn_strict())
            except Exception as e:
                logger.warning(f"Could not export match {match.match_id}: {e}")
                # Fallback to raw PGN if available
                if match.pgn:
                    pgn_parts.append(match.pgn)
                else:
                    pgn_parts.append(self._generate_minimal_pgn(match))
            
            pgn_parts.append("")
            pgn_parts.append("")
        
        content = "\n".join(pgn_parts)
        
        if filepath:
            Path(filepath).write_text(content, encoding="utf-8")
            logger.info(f"All games exported to {filepath} (pretty={pretty})")
        
        return content

    def export_per_game_pgn(self, output_dir: str, pretty: bool = True) -> List[str]:
        """
        Export each tournament game as an individual PGN file.
        
        Args:
            output_dir: Directory to save individual PGN files
            pretty: Whether to use pretty PGN format (default: True)
            
        Returns:
            List of paths to exported files
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        exported_files = []
        
        for i, match in enumerate(self.result.matches, 1):
            # Build filename
            white_name = match.white.name.replace(" ", "_")
            black_name = match.black.name.replace(" ", "_")
            filename = f"game_{i:03d}_{white_name}_vs_{black_name}.pgn"
            filepath = output_path / filename
            
            # Use MatchExporter to get the PGN
            try:
                exporter = MatchExporter(match, include_elo=True)
                if pretty:
                    content = exporter.export_pgn()
                else:
                    content = exporter.export_pgn_strict()
                
                filepath.write_text(content, encoding="utf-8")
                exported_files.append(str(filepath))
            except Exception as e:
                logger.warning(f"Could not export individual match {match.match_id}: {e}")
            
        logger.info(f"Exported {len(exported_files)} individual games to {output_dir}")
        return exported_files

    def _generate_minimal_pgn(self, match: Any) -> str:
        """Generate a minimal PGN for a match that failed full export."""
        lines = [
            f'[White "{match.white.name}"]',
            f'[Black "{match.black.name}"]',
            f'[Result "{match.result.value}"]',
            "",
            match.result.value
        ]
        return "\n".join(lines)

    # =========================================================================
    # JSON EXPORTS
    # =========================================================================
    
    def export_json(self, filepath: Optional[str] = None) -> str:
        """
        Export complete tournament data as JSON.
        """
        data = self.result.to_dict()
        content = json.dumps(data, indent=2)
        
        if filepath:
            Path(filepath).write_text(content, encoding="utf-8")
            
        return content

    # =========================================================================
    # HTML REPORT
    # =========================================================================
    
    def export_html_report(self, filepath: str) -> str:
        """
        Export a complete HTML tournament report.
        """
        # For v0.5.0, this is a simplified version of the planned interactive report
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Tournament Report: {self.result.config.name}</title>
    {self._get_html_styles()}
</head>
<body>
    <h1>Tournament Report</h1>
    <div class="meta">
        <p><strong>Name:</strong> {self.result.config.name}</p>
        <p><strong>Format:</strong> {self.result.config.format.value}</p>
        <p><strong>Games:</strong> {self.result.total_games}</p>
    </div>
    
    {self._get_winner_section()}
    
    <h2>Final Standings</h2>
    <table class="standings">
        <thead>
            <tr>
                <th>Rank</th>
                <th>Player</th>
                <th>Points</th>
                <th>Wins</th>
                <th>Draws</th>
                <th>Losses</th>
            </tr>
        </thead>
        <tbody>
            {self._get_standings_rows()}
        </tbody>
    </table>
    
    <footer>
        Generated by CAISSA Chess Engine v0.5.0 on {datetime.now().strftime('%Y-%m-%d %H:%M')}
    </footer>
</body>
</html>
"""
        Path(filepath).write_text(html, encoding="utf-8")
        return html

    def _get_winner_section(self) -> str:
        if not self.result.winner:
            return ""
        return f"""
    <div class="winner">
        <h2>🏆 Winner: {self.result.winner.name}</h2>
        <p>Points: {self.result.standings[0].points:.1f}</p>
    </div>
"""

    def _get_standings_rows(self) -> str:
        rows = []
        for s in self.result.standings:
            rows.append(f"""
            <tr>
                <td>{s.rank}</td>
                <td>{s.player.name}</td>
                <td>{s.points:.1f}</td>
                <td>{s.wins}</td>
                <td>{s.draws}</td>
                <td>{s.losses}</td>
            </tr>
""")
        return "".join(rows)

    def _get_html_styles(self) -> str:
        return """
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; color: #333; }
        h1 { border-bottom: 2px solid #333; padding-bottom: 10px; }
        .meta { background: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .winner { text-align: center; background: #fff3cd; border: 1px solid #ffeeba; padding: 20px; border-radius: 5px; margin: 20px 0; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #ddd; }
        th { background: #eee; }
        footer { margin-top: 40px; font-size: 0.8em; color: #777; border-top: 1px solid #eee; padding-top: 20px; }
    </style>
"""


def export_tournament(
    tournament_result: Any,
    output_dir: str,
    formats: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Convenience function to export tournament in multiple formats.
    
    Args:
        tournament_result: TournamentResult from Tournament.run()
        output_dir: Directory to save files
        formats: List of formats to export (default: all)
    
    Returns:
        Dict mapping format name to file path
    """
    formats = formats or ["markdown", "json", "html", "pgn_pretty"]
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    exporter = TournamentExporter(tournament_result)
    exported = {}
    
    if "markdown" in formats:
        path = output_path / "standings.md"
        exporter.export_standings_markdown(str(path))
        exported["standings_md"] = str(path)
        
        path = output_path / "crosstable.md"
        exporter.export_crosstable_markdown(str(path))
        exported["crosstable_md"] = str(path)
    
    if "json" in formats:
        path = output_path / "tournament.json"
        exporter.export_json(str(path))
        exported["json"] = str(path)
    
    if "html" in formats:
        path = output_path / "report.html"
        exporter.export_html_report(str(path))
        exported["html"] = str(path)
    
    if "pgn" in formats or "pgn_pretty" in formats:
        path = output_path / "all_games.pgn"
        exporter.export_all_games_pgn(str(path), pretty=True)
        exported["pgn_pretty"] = str(path)

    if "pgn_strict" in formats:
        path = output_path / "all_games_strict.pgn"
        exporter.export_all_games_pgn(str(path), pretty=False)
        exported["pgn_strict"] = str(path)

    if "per_game_pgn" in formats:
        games_dir = output_path / "games"
        exporter.export_per_game_pgn(str(games_dir), pretty=True)
        exported["per_game_pgn"] = str(games_dir)
    
    logger.info(f"Tournament exported to {output_dir}: {list(exported.keys())}")
    return exported


class MatchExporter(GameExporter):
    """
    Extended exporter for LLM vs LLM tournament matches.
    """
    
    def __init__(
        self,
        match_result: Any,
        config: Optional[Any] = None,
        include_elo: bool = True,
        match_analysis: Optional[Any] = None,
    ):
        from export.annotation_parser import ParsedGame, ParsedMove
        from export.game_exporter import ExportConfig
        
        self.match_result = match_result
        self.include_elo = include_elo
        self.match_analysis = match_analysis
        
        # Validate match is exportable
        if not match_result.moves or len(match_result.moves) == 0:
            raise ValueError(f"Cannot export empty match {match_result.match_id}")
        
        # Convert moves
        parsed_moves = []
        for i, move in enumerate(match_result.moves):
            if match_analysis and i < len(match_analysis.move_annotations):
                annotation = match_analysis.move_annotations[i]
                parsed_move = ParsedMove(
                    san=move.san,
                    move_number=move.move_number,
                    is_white=(move.color == "white"),
                    comment=annotation.comment or f"[{move.think_time:.1f}s]",
                    nags=annotation.nags,
                    evaluation=annotation.evaluation,
                    clock_time=f"{move.think_time:.1f}" if move.think_time else None,
                )
            else:
                parsed_move = ParsedMove(
                    san=move.san,
                    move_number=move.move_number,
                    is_white=(move.color == "white"),
                    comment=f"[{move.think_time:.1f}s]" if move.think_time else "",
                    nags=[],
                    evaluation=move.evaluation,
                    clock_time=f"{move.think_time:.1f}" if move.think_time else None,
                )
            parsed_moves.append(parsed_move)
        
        # Build headers
        headers = {
            "Event": "LLM vs LLM Match",
            "Site": "CAISSA Chess Engine",
            "Date": match_result.start_time.strftime("%Y.%m.%d") if match_result.start_time else "????.??.??",
            "Round": "1",
            "White": match_result.white.name,
            "Black": match_result.black.name,
            "Result": match_result.result.value,
            "Annotator": "CAISSA v0.5.0 LLM Tournament System",
        }
        
        if include_elo and match_result.elo_change:
            headers["WhiteElo"] = str(match_result.white.elo_rating)
            headers["BlackElo"] = str(match_result.black.elo_rating)
            headers["WhiteEloChange"] = f"{match_result.elo_change.white_delta:+d}"
            headers["BlackEloChange"] = f"{match_result.elo_change.black_delta:+d}"
            headers["WhiteEloNew"] = str(match_result.white.elo_rating + match_result.elo_change.white_delta)
            headers["BlackEloNew"] = str(match_result.black.elo_rating + match_result.elo_change.black_delta)
        
        parsed_game = ParsedGame(
            headers=headers,
            moves=parsed_moves,
            result=match_result.result.value,
            raw_pgn=match_result.pgn,
        )
        
        if config is None:
            config = ExportConfig(
                pgn_include_clock=True,
                pgn_include_evaluations=True,
                md_include_game_summary=True,
                html_dark_mode=True,
            )
        
        super().__init__(
            game=parsed_game,
            config=config,
            beauty_score=getattr(match_result, 'beauty_score', None),
            style_name="LLM Tournament",
        )
