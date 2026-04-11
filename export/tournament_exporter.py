"""
Tournament Exporter for CAISSA Chess v0.5.0

This module extends the export system to handle tournament-specific outputs:
- Tournament standings (Markdown, HTML, JSON)
- Match collections (multi-game PGN)
- Analytics reports
- Player cards

Integrates seamlessly with the existing GameExporter for individual games.

NOTE (v0.5.0): This module is ADDITIVE. It does not modify or replace
any existing export functionality. All GameExporter features remain intact.

Author: CAISSA Team
Version: 0.5.0
"""

import json
import logging
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any

from export.game_exporter import GameExporter, ExportConfig
from export.annotation_parser import parse_pgn

logger = logging.getLogger(__name__)


@dataclass
class TournamentExportConfig(ExportConfig):
    """
    Extended export configuration for tournaments.
    
    Inherits all GameExporter config options and adds tournament-specific settings.
    """
    # Standings
    standings_show_tiebreaks: bool = True
    standings_show_elo_change: bool = True
    standings_max_players: int = 0  # 0 = show all
    
    # Crosstable
    crosstable_show_colors: bool = True
    crosstable_compact: bool = False
    
    # Analytics
    analytics_include_style: bool = True
    analytics_include_openings: bool = True
    analytics_charts_enabled: bool = True
    
    # Collection
    collection_separate_files: bool = False  # True = one PGN per game
    collection_include_index: bool = True
    
    # HTML Report
    html_tournament_template: str = "default"
    html_include_crosstable: bool = True
    html_include_round_navigator: bool = True


class TournamentExporter:
    """
    Exports tournament data in multiple formats.
    
    Works alongside GameExporter for individual games while providing
    tournament-level aggregation and formatting.
    
    Example:
        ```python
        from core.tournament import TournamentResult
        
        result: TournamentResult = await tournament.run()
        exporter = TournamentExporter(result)
        
        # Export various formats
        exporter.export_standings_markdown("standings.md")
        exporter.export_crosstable_markdown("crosstable.md")
        exporter.export_all_games_pgn("games.pgn")
        exporter.export_json("tournament.json")
        exporter.export_html_report("report.html")
        ```
    """
    
    def __init__(
        self,
        tournament_result: Any,  # TournamentResult - avoid circular import
        config: Optional[TournamentExportConfig] = None,
    ):
        """
        Initialize the tournament exporter.
        
        Args:
            tournament_result: Complete tournament result from Tournament.run()
            config: Export configuration (uses defaults if None)
        """
        self.result = tournament_result
        self.config = config or TournamentExportConfig()

    def _export_match_pgn(self, match: Any, pretty: bool = False) -> str:
        """Export a single match as PGN, optionally using pretty formatting."""
        if not pretty:
            if match.pgn:
                return match.pgn
            return self._generate_minimal_pgn(match)

        try:
            # Use MatchExporter for pretty mode so move-level comments (think times,
            # analysis commentary when present) are carried into the PGN output.
            match_exporter = MatchExporter(match_result=match, include_elo=True)
            return match_exporter.export_pgn()
        except Exception:
            logger.debug("Falling back to raw PGN for match %s", getattr(match, "match_id", "?"))

        if match.pgn:
            return match.pgn
        return self._generate_minimal_pgn(match)

    @staticmethod
    def _safe_player_name(name: str) -> str:
        """Create filesystem-safe player name component for export file names."""
        return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name).strip("_")
    
    # =========================================================================
    # MARKDOWN EXPORTS
    # =========================================================================
    
    def export_standings_markdown(self, filepath: Optional[str] = None) -> str:
        """
        Export tournament standings as Markdown table.
        
        Args:
            filepath: Optional path to save file
        
        Returns:
            str: Markdown content
        """
        lines = [
            f"# {self.result.config.name}",
            "",
            f"**Format**: {self.result.config.format.value}",
            f"**Date**: {self.result.start_time.strftime('%Y-%m-%d')}",
            f"**Players**: {len(self.result.standings)}",
            f"**Rounds**: {len(self.result.rounds)}",
            f"**Games**: {self.result.total_games}",
            "",
            "## Final Standings",
            "",
        ]
        
        # Build table header
        headers = ["#", "Player", "Points", "W", "D", "L"]
        if self.config.standings_show_elo_change:
            headers.extend(["Rating", "Δ"])
        if self.config.standings_show_tiebreaks:
            headers.append("TB1")
        
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "|".join(["---"] * len(headers)) + "|")
        
        # Build rows
        for standing in self.result.standings:
            row = [
                str(standing.rank),
                standing.player.name,
                f"{standing.points:.1f}",
                str(standing.wins),
                str(standing.draws),
                str(standing.losses),
            ]
            
            if self.config.standings_show_elo_change:
                row.append(str(standing.player.elo_rating))
                # Calculate ELO change from matches
                elo_change = self._calculate_player_elo_change(standing.player.id)
                sign = "+" if elo_change >= 0 else ""
                row.append(f"{sign}{elo_change}")
            
            if self.config.standings_show_tiebreaks:
                # Use first tiebreak
                tb_value = list(standing.tiebreaks.values())[0] if standing.tiebreaks else 0
                row.append(f"{tb_value:.1f}")
            
            lines.append("| " + " | ".join(row) + " |")
        
        # Add statistics
        lines.extend([
            "",
            "## Statistics",
            "",
            f"- Total moves: {self.result.total_moves}",
            f"- Decisive games: {self.result.decisive_games} ({self.result.decisive_games/max(1,self.result.total_games)*100:.1f}%)",
            f"- Draws: {self.result.draws}",
            f"- Average game length: {self.result.avg_game_length:.1f} moves",
        ])
        
        if self.result.winner:
            lines.extend([
                "",
                f"**🏆 Winner: {self.result.winner.name}**",
            ])
        
        content = "\n".join(lines)
        
        if filepath:
            Path(filepath).write_text(content, encoding="utf-8")
            logger.info(f"Standings exported to {filepath}")
        
        return content
    
    def export_crosstable_markdown(self, filepath: Optional[str] = None) -> str:
        """
        Export tournament crosstable as Markdown.
        
        Args:
            filepath: Optional path to save file
        
        Returns:
            str: Markdown content
        """
        players = [s.player for s in self.result.standings]
        n = len(players)
        
        lines = [
            f"# {self.result.config.name} - Crosstable",
            "",
        ]
        
        # Build header
        header = ["#", "Player"]
        for i in range(n):
            header.append(str(i + 1))
        header.append("Pts")
        
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "|".join(["---"] * len(header)) + "|")
        
        # Build rows
        for i, player in enumerate(players):
            row = [str(i + 1), player.name]
            
            for j, opponent in enumerate(players):
                if i == j:
                    row.append("×")
                else:
                    result = self._get_head_to_head(player.id, opponent.id)
                    row.append(result)
            
            # Points
            standing = self.result.standings[i]
            row.append(f"{standing.points:.1f}")
            
            lines.append("| " + " | ".join(row) + " |")
        
        content = "\n".join(lines)
        
        if filepath:
            Path(filepath).write_text(content, encoding="utf-8")
            logger.info(f"Crosstable exported to {filepath}")
        
        return content
    
    def export_round_summary_markdown(self, round_num: int, filepath: Optional[str] = None) -> str:
        """
        Export a single round's summary as Markdown.
        
        Args:
            round_num: Round number (1-indexed)
            filepath: Optional path to save file
        
        Returns:
            str: Markdown content
        """
        if round_num < 1 or round_num > len(self.result.rounds):
            raise ValueError(f"Invalid round number: {round_num}")
        
        round_obj = self.result.rounds[round_num - 1]
        
        lines = [
            f"# Round {round_num}",
            "",
            f"**Games**: {len(round_obj.pairings)}",
            "",
            "## Results",
            "",
            "| White | Result | Black |",
            "|-------|--------|-------|",
        ]
        
        for i, (white, black) in enumerate(round_obj.pairings):
            result = round_obj.results[i] if i < len(round_obj.results) else None
            result_str = result.result.value if result else "*"
            lines.append(f"| {white.name} | {result_str} | {black.name} |")
        
        if round_obj.byes:
            lines.extend([
                "",
                "**Byes**: " + ", ".join(p.name for p in round_obj.byes),
            ])
        
        content = "\n".join(lines)
        
        if filepath:
            Path(filepath).write_text(content, encoding="utf-8")
        
        return content
    
    # =========================================================================
    # PGN EXPORTS
    # =========================================================================
    
    def export_all_games_pgn(self, filepath: Optional[str] = None, pretty: bool = False) -> str:
        """
        Export all tournament games as a single PGN collection.
        
        Uses the existing GameExporter for each individual game.
        
        Args:
            filepath: Optional path to save file
        
        Returns:
            str: Complete PGN collection
        """
        pgn_parts = []
        
        for i, match in enumerate(self.result.matches, 1):
            # Add game header comment
            pgn_parts.append(f"; === Game {i}: {match.white.name} vs {match.black.name} ===")
            pgn_parts.append("")
            
            pgn_parts.append(self._export_match_pgn(match, pretty=pretty))
            
            pgn_parts.append("")
            pgn_parts.append("")
        
        content = "\n".join(pgn_parts)
        
        if filepath:
            Path(filepath).write_text(content, encoding="utf-8")
            logger.info(f"All games exported to {filepath}")
        
        return content

    def export_games_pgn_per_game(self, output_dir: str, pretty: bool = True) -> Dict[str, str]:
        """Export each tournament game into its own PGN file."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        exported: Dict[str, str] = {}

        for idx, match in enumerate(self.result.matches, 1):
            safe_white = self._safe_player_name(match.white.name)
            safe_black = self._safe_player_name(match.black.name)
            filename = f"game_{idx:03d}_{safe_white}_vs_{safe_black}.pgn"
            path = out / filename
            path.write_text(self._export_match_pgn(match, pretty=pretty), encoding="utf-8")
            exported[f"pgn_game_{idx:03d}"] = str(path)

        return exported

    def export_games_reports_per_game(self, output_dir: str) -> Dict[str, str]:
        """
        Export each tournament game as per-game Markdown, JSON, and HTML.

        This is additive to tournament-level exports and is intended for
        "all formats" mode where every game gets its own report bundle.
        """
        base = Path(output_dir)
        md_dir = base / "games_md"
        json_dir = base / "games_json"
        html_dir = base / "games_html"
        md_dir.mkdir(parents=True, exist_ok=True)
        json_dir.mkdir(parents=True, exist_ok=True)
        html_dir.mkdir(parents=True, exist_ok=True)

        exported: Dict[str, str] = {}
        exported["games_md_dir"] = str(md_dir)
        exported["games_json_dir"] = str(json_dir)
        exported["games_html_dir"] = str(html_dir)

        for idx, match in enumerate(self.result.matches, 1):
            safe_white = self._safe_player_name(match.white.name)
            safe_black = self._safe_player_name(match.black.name)
            stem = f"game_{idx:03d}_{safe_white}_vs_{safe_black}"

            try:
                match_exporter = MatchExporter(match_result=match, include_elo=True)

                md_path = md_dir / f"{stem}.md"
                md_path.write_text(match_exporter.export_markdown(), encoding="utf-8")
                exported[f"md_game_{idx:03d}"] = str(md_path)

                json_path = json_dir / f"{stem}.json"
                json_path.write_text(match_exporter.export_json(), encoding="utf-8")
                exported[f"json_game_{idx:03d}"] = str(json_path)

                html_path = html_dir / f"{stem}.html"
                html_path.write_text(match_exporter.export_html(), encoding="utf-8")
                exported[f"html_game_{idx:03d}"] = str(html_path)
            except ValueError as e:
                # Non-exportable edge case (e.g. empty/forfeit game); keep tournament export running.
                logger.warning("Skipping per-game rich export for match %s: %s", getattr(match, "match_id", "?"), e)

        return exported
    
    def export_player_games_pgn(
        self,
        player_id: str,
        filepath: Optional[str] = None,
    ) -> str:
        """
        Export all games for a specific player.
        
        Args:
            player_id: Player ID
            filepath: Optional path to save file
        
        Returns:
            str: PGN collection for the player
        """
        player_matches = [
            m for m in self.result.matches
            if m.white.id == player_id or m.black.id == player_id
        ]
        
        pgn_parts = []
        for match in player_matches:
            if match.pgn:
                pgn_parts.append(match.pgn)
                pgn_parts.append("")
        
        content = "\n".join(pgn_parts)
        
        if filepath:
            Path(filepath).write_text(content, encoding="utf-8")
        
        return content
    
    # =========================================================================
    # JSON EXPORTS
    # =========================================================================
    
    def export_json(self, filepath: Optional[str] = None) -> str:
        """
        Export complete tournament data as JSON.
        
        Args:
            filepath: Optional path to save file
        
        Returns:
            str: JSON content
        """
        data = self.result.to_dict()
        
        # Add computed statistics
        data["statistics"] = {
            "total_moves": self.result.total_moves,
            "decisive_games": self.result.decisive_games,
            "draw_rate": self.result.draws / max(1, self.result.total_games) * 100,
            "avg_game_length": self.result.avg_game_length,
            "duration_seconds": self.result.duration,
        }
        
        content = json.dumps(data, indent=2, default=str)
        
        if filepath:
            Path(filepath).write_text(content, encoding="utf-8")
            logger.info(f"Tournament JSON exported to {filepath}")
        
        return content
    
    def export_standings_json(self, filepath: Optional[str] = None) -> str:
        """
        Export just the standings as JSON.
        
        Args:
            filepath: Optional path to save file
        
        Returns:
            str: JSON content
        """
        standings_data = [s.to_dict() for s in self.result.standings]
        content = json.dumps(standings_data, indent=2)
        
        if filepath:
            Path(filepath).write_text(content, encoding="utf-8")
        
        return content
    
    # =========================================================================
    # HTML EXPORTS
    # =========================================================================
    
    def export_html_report(self, filepath: Optional[str] = None) -> str:
        """
        Export complete tournament report as HTML.
        
        Args:
            filepath: Optional path to save file
        
        Returns:
            str: HTML content
        """
        html_parts = [
            "<!DOCTYPE html>",
            "<html lang='en'>",
            "<head>",
            "  <meta charset='UTF-8'>",
            "  <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
            f"  <title>{self.result.config.name} - Tournament Report</title>",
            self._get_html_styles(),
            "</head>",
            "<body>",
            f"  <h1>🏆 {self.result.config.name}</h1>",
            "  <div class='meta'>",
            f"    <p><strong>Format:</strong> {self.result.config.format.value}</p>",
            f"    <p><strong>Date:</strong> {self.result.start_time.strftime('%B %d, %Y')}</p>",
            f"    <p><strong>Players:</strong> {len(self.result.standings)}</p>",
            f"    <p><strong>Games:</strong> {self.result.total_games}</p>",
            "  </div>",
        ]
        
        # Winner
        if self.result.winner:
            html_parts.extend([
                "  <div class='winner'>",
                f"    <h2>🥇 Winner: {self.result.winner.name}</h2>",
                f"    <p>Rating: {self.result.winner.elo_rating}</p>",
                "  </div>",
            ])
        
        # Standings table
        html_parts.extend([
            "  <h2>Standings</h2>",
            "  <table class='standings'>",
            "    <thead>",
            "      <tr>",
            "        <th>#</th>",
            "        <th>Player</th>",
            "        <th>Points</th>",
            "        <th>W</th>",
            "        <th>D</th>",
            "        <th>L</th>",
            "        <th>Rating</th>",
            "      </tr>",
            "    </thead>",
            "    <tbody>",
        ])
        
        for standing in self.result.standings:
            row_class = "winner" if standing.rank == 1 else ""
            html_parts.extend([
                f"      <tr class='{row_class}'>",
                f"        <td>{standing.rank}</td>",
                f"        <td>{standing.player.name}</td>",
                f"        <td>{standing.points:.1f}</td>",
                f"        <td>{standing.wins}</td>",
                f"        <td>{standing.draws}</td>",
                f"        <td>{standing.losses}</td>",
                f"        <td>{standing.player.elo_rating}</td>",
                "      </tr>",
            ])
        
        html_parts.extend([
            "    </tbody>",
            "  </table>",
        ])
        
        # Round results
        html_parts.append("  <h2>Round Results</h2>")
        for round_obj in self.result.rounds:
            html_parts.extend([
                f"  <h3>Round {round_obj.round_number}</h3>",
                "  <table class='round'>",
                "    <tr><th>White</th><th>Result</th><th>Black</th></tr>",
            ])
            
            for i, (white, black) in enumerate(round_obj.pairings):
                result = round_obj.results[i] if i < len(round_obj.results) else None
                result_str = result.result.value if result else "*"
                html_parts.append(
                    f"    <tr><td>{white.name}</td><td>{result_str}</td><td>{black.name}</td></tr>"
                )
            
            html_parts.append("  </table>")
        
        # Statistics
        html_parts.extend([
            "  <h2>Statistics</h2>",
            "  <ul>",
            f"    <li>Total moves: {self.result.total_moves}</li>",
            f"    <li>Decisive games: {self.result.decisive_games}</li>",
            f"    <li>Draws: {self.result.draws}</li>",
            f"    <li>Average game length: {self.result.avg_game_length:.1f} moves</li>",
            "  </ul>",
        ])
        
        html_parts.extend([
            "  <footer>",
            "    <p>Generated by CAISSA Chess Engine v0.5.0</p>",
            "  </footer>",
            "</body>",
            "</html>",
        ])
        
        content = "\n".join(html_parts)
        
        if filepath:
            Path(filepath).write_text(content, encoding="utf-8")
            logger.info(f"HTML report exported to {filepath}")
        
        return content
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _calculate_player_elo_change(self, player_id: str) -> int:
        """Calculate total ELO change for a player across all matches."""
        total_change = 0
        for match in self.result.matches:
            if match.elo_change:
                if match.white.id == player_id:
                    total_change += match.elo_change.white_delta
                elif match.black.id == player_id:
                    total_change += match.elo_change.black_delta
        return total_change
    
    def _get_head_to_head(self, player1_id: str, player2_id: str) -> str:
        """Get head-to-head result symbol between two players."""
        results = []
        for match in self.result.matches:
            if match.white.id == player1_id and match.black.id == player2_id:
                if match.result.value == "1-0":
                    results.append("1")
                elif match.result.value == "0-1":
                    results.append("0")
                else:
                    results.append("½")
            elif match.white.id == player2_id and match.black.id == player1_id:
                if match.result.value == "0-1":
                    results.append("1")
                elif match.result.value == "1-0":
                    results.append("0")
                else:
                    results.append("½")
        
        return " ".join(results) if results else "-"
    
    def _generate_minimal_pgn(self, match: Any) -> str:
        """Generate minimal PGN from match data."""
        lines = [
            f'[Event "{self.result.config.name}"]',
            f'[Site "CAISSA Engine"]',
            f'[Date "{match.start_time.strftime("%Y.%m.%d")}"]',
            f'[Round "{self._get_round_for_match(match)}"]',
            f'[White "{match.white.name}"]',
            f'[Black "{match.black.name}"]',
            f'[Result "{match.result.value}"]',
            "",
        ]
        
        # Add moves
        move_strs = []
        move_num = 1
        for i, record in enumerate(match.moves):
            if record.color == "white":
                move_strs.append(f"{move_num}. {record.san}")
            else:
                move_strs.append(record.san)
                move_num += 1
        
        lines.append(" ".join(move_strs) + " " + match.result.value)
        
        return "\n".join(lines)
    
    def _get_round_for_match(self, match: Any) -> str:
        """Get the round number for a match."""
        for round_obj in self.result.rounds:
            for result in round_obj.results:
                if result and result.match_id == match.match_id:
                    return str(round_obj.round_number)
        return "?"
    
    def _get_html_styles(self) -> str:
        """Get CSS styles for HTML report."""
        return """
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      max-width: 1000px;
      margin: 0 auto;
      padding: 20px;
      background: #f5f5f5;
      color: #333;
    }
    h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
    h2 { color: #34495e; margin-top: 30px; }
    h3 { color: #7f8c8d; }
    .meta { background: #fff; padding: 15px; border-radius: 8px; margin: 20px 0; }
    .meta p { margin: 5px 0; }
    .winner { background: linear-gradient(135deg, #f39c12, #f1c40f); 
              padding: 20px; border-radius: 8px; text-align: center; }
    .winner h2 { margin: 0; color: #fff; }
    .winner p { margin: 5px 0; color: rgba(255,255,255,0.9); }
    table { width: 100%; border-collapse: collapse; margin: 15px 0; 
            background: #fff; border-radius: 8px; overflow: hidden; }
    th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
    th { background: #3498db; color: #fff; }
    tr:hover { background: #f8f9fa; }
    tr.winner { background: #fffde7; }
    .standings td:nth-child(3) { font-weight: bold; color: #2980b9; }
    footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd;
             text-align: center; color: #95a5a6; font-size: 0.9em; }
  </style>
"""


def export_tournament(
    tournament_result: Any,
    output_dir: str,
    formats: Optional[List[str]] = None,
    pretty_pgn: bool = False,
    per_game_pgn: bool = False,
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
    formats = formats or ["markdown", "json", "html", "pgn"]
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
    
    if "pgn" in formats:
        if per_game_pgn:
            games_dir = output_path / "games_pgn"
            exported.update(exporter.export_games_pgn_per_game(str(games_dir), pretty=pretty_pgn))
            exported["pgn_games_dir"] = str(games_dir)
            if any(fmt in formats for fmt in ("markdown", "json", "html")):
                exported.update(exporter.export_games_reports_per_game(str(output_path)))
        else:
            filename = "all_games_pretty.pgn" if pretty_pgn else "all_games.pgn"
            path = output_path / filename
            exporter.export_all_games_pgn(str(path), pretty=pretty_pgn)
            exported["pgn_pretty" if pretty_pgn else "pgn"] = str(path)
    
    logger.info(f"Tournament exported to {output_dir}: {list(exported.keys())}")
    return exported


class MatchExporter(GameExporter):
    """
    Extended exporter for LLM vs LLM tournament matches.
    
    Inherits from GameExporter and adds tournament-specific sections:
    - LLM provider information and model details
    - Think time breakdowns per move
    - ELO rating changes with K-factor details
    - Timeout and retry statistics
    - Match metadata (match ID, time control, termination reason)
    
    This provides full compatibility with existing GameExporter formats while
    enriching output with competitive match data.
    
    Usage:
        match_result = await match_engine.play_match(white, black)
        exporter = MatchExporter(match_result)
        html = exporter.export_html()
        json = exporter.export_json()
    """
    
    def __init__(
        self,
        match_result: Any,  # MatchResult from match_engine
        config: Optional[Any] = None,  # ExportConfig
        include_elo: bool = True,
        match_analysis: Optional[Any] = None,  # MatchAnalysis from match_analyzer (NEW)
    ):
        """
        Args:
            match_result: MatchResult from MatchEngine.play_match()
            config: ExportConfig (uses defaults if None)
            include_elo: Include ELO change information in output
            match_analysis: MatchAnalysis from MatchAnalyzer (optional, adds beauty scores, commentary, annotations)
        
        Raises:
            ValueError: If match result is empty/invalid (forfeit, timeout with 0 moves)
        """
        from export.annotation_parser import ParsedGame, ParsedMove
        from export.game_exporter import ExportConfig
        from core.match_engine import TerminationReason
        
        self.match_result = match_result
        self.include_elo = include_elo
        self.match_analysis = match_analysis  # Store analysis for enhanced export
        
        # CRITICAL FIX: Validate match is exportable
        if not match_result.moves or len(match_result.moves) == 0:
            termination = match_result.termination.value if hasattr(match_result.termination, 'value') else str(match_result.termination)
            raise ValueError(
                f"Cannot export empty match {match_result.match_id} "
                f"(termination: {termination}, moves: {len(match_result.moves)}). "
                f"Match likely forfeited or timed out before any moves were played."
            )
        
        # Convert MatchResult to ParsedGame for base class
        parsed_moves = []
        for i, move in enumerate(match_result.moves):
            # Check if we have analysis data for this move
            if match_analysis and i < len(match_analysis.move_annotations):
                annotation = match_analysis.move_annotations[i]
                comment_parts = []
                
                # Add think time
                if move.think_time:
                    comment_parts.append(f"{move.think_time:.1f}s")
                
                # Add commentary from analysis
                if annotation.comment:
                    comment_parts.append(annotation.comment)
                
                combined_comment = " - ".join(comment_parts) if comment_parts else ""
                
                parsed_move = ParsedMove(
                    san=move.san,
                    move_number=move.move_number,
                    is_white=(move.color == "white"),
                    comment=combined_comment,
                    nags=annotation.nags,  # Use NAGs from analysis
                    evaluation=annotation.evaluation,  # Use Stockfish eval from analysis
                    clock_time=f"{move.think_time:.1f}" if move.think_time else None,
                )
            else:
                # Fallback: no analysis data
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
        
        # Build headers for ParsedGame
        headers = {
            "Event": "LLM vs LLM Match",
            "Site": "CAISSA Chess Engine",
            "Date": match_result.start_time.strftime("%Y.%m.%d") if match_result.start_time else "????.??.??",
            "Round": "1",
            "White": match_result.white.name,
            "Black": match_result.black.name,
            "Result": match_result.result.value,
            "WhiteElo": str(match_result.white.elo_rating),
            "BlackElo": str(match_result.black.elo_rating),
            "TimeControl": match_result.time_control.name if match_result.time_control else "?",
            "Termination": match_result.termination.value if match_result.termination else "?",
            "MatchID": match_result.match_id,
            "Annotator": "CAISSA v0.5.0 LLM Tournament System",
        }
        
        # Add ELO change info
        if include_elo and match_result.elo_change:
            headers["WhiteEloChange"] = f"{match_result.elo_change.white_delta:+d}"
            headers["BlackEloChange"] = f"{match_result.elo_change.black_delta:+d}"
            headers["WhiteEloNew"] = str(match_result.white.elo_rating + match_result.elo_change.white_delta)
            headers["BlackEloNew"] = str(match_result.black.elo_rating + match_result.elo_change.black_delta)
        
        # Create ParsedGame
        parsed_game = ParsedGame(
            headers=headers,
            moves=parsed_moves,
            result=match_result.result.value,
            raw_pgn=match_result.pgn,
        )
        
        # Configure export with tournament-specific settings
        if config is None:
            config = ExportConfig(
                pgn_include_clock=True,
                pgn_include_evaluations=True,
                md_include_game_summary=True,
                md_include_eval_bars=True,
                html_dark_mode=True,  # Tournament matches look great in dark mode
                html_include_styles=True,
            )
        
        # Initialize parent with ParsedGame
        # Use beauty score from analysis if available, fallback to match_result
        beauty_score = None
        if match_analysis:
            beauty_score = match_analysis.beauty_score
        elif hasattr(match_result, 'beauty_score'):
            beauty_score = match_result.beauty_score
        
        super().__init__(
            game=parsed_game,
            config=config,
            beauty_score=beauty_score,
            style_name="LLM Tournament",
        )
    
    # =========================================================================
    # EXTENDED HTML EXPORT - Add LLM Match Details
    # =========================================================================
    
    def export_html(self) -> str:
        """
        Export HTML with additional LLM match sections.
        
        Extends base GameExporter HTML with:
        - Match metadata banner
        - Provider and model information
        - Think time statistics
        - ELO rating changes with visualization
        - Timeout and retry details
        
        Returns:
            Complete HTML document with LLM match enhancements
        """
        # Get base HTML from parent
        base_html = super().export_html()
        
        # Insert match-specific sections before the closing tags
        # Find the summary div and insert our match details after it
        match_sections = self._html_match_details()
        
        # Insert before page footer
        if '<div class="page-footer">' in base_html:
            base_html = base_html.replace(
                '<div class="page-footer">',
                f'{match_sections}\n<div class="page-footer">'
            )
        else:
            # Fallback: insert before closing body tag
            base_html = base_html.replace('</body>', f'{match_sections}\n</body>')
        
        return base_html
    
    def _html_match_details(self) -> str:
        """Generate HTML sections for LLM match-specific details."""
        import html as html_lib
        
        mr = self.match_result
        parts = []
        
        # Match metadata banner
        parts.append('<div class="match-metadata" style="background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius); padding:20px; margin:32px 0;">')
        parts.append('  <h3 style="margin:0 0 16px 0; color:var(--accent); font-size:1.3em;">⚔️ LLM Match Details</h3>')
        parts.append('  <div class="meta-grid" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:12px;">')
        
        # Match ID and time control
        parts.append(f'    <div><strong>Match ID:</strong> <code style="background:var(--bg); padding:2px 6px; border-radius:4px;">{html_lib.escape(mr.match_id[:8])}</code></div>')
        parts.append(f'    <div><strong>Time Control:</strong> {html_lib.escape(mr.time_control.name)} ({mr.time_control.value}s)</div>')
        parts.append(f'    <div><strong>Duration:</strong> {mr.duration:.1f}s</div>')
        parts.append(f'    <div><strong>Total Moves:</strong> {mr.total_moves}</div>')
        
        parts.append('  </div>')
        parts.append('</div>')
        
        # LLM Provider details
        parts.append('<div class="llm-providers" style="background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius); padding:20px; margin:24px 0;">')
        parts.append('  <h3 style="margin:0 0 16px 0; color:var(--accent); font-size:1.3em;">🤖 LLM Players</h3>')
        parts.append('  <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">')
        
        # White player
        white_provider = mr.white.provider.__class__.__name__ if mr.white.provider else "Unknown"
        white_model = getattr(mr.white.provider, 'model', 'Unknown') if mr.white.provider else "Unknown"
        parts.append('    <div>')
        parts.append(f'      <h4 style="margin:0 0 8px 0;">⚪ White: {html_lib.escape(mr.white.name)}</h4>')
        parts.append('      <ul style="margin:0; padding-left:20px; line-height:1.8;">')
        parts.append(f'        <li><strong>Provider:</strong> {html_lib.escape(white_provider)}</li>')
        parts.append(f'        <li><strong>Model:</strong> {html_lib.escape(str(white_model))}</li>')
        parts.append(f'        <li><strong>Temperature:</strong> {mr.white.temperature}</li>')
        
        # Build ELO line
        elo_line = f'        <li><strong>ELO:</strong> {mr.white.elo_rating}'
        if self.include_elo and mr.elo_change:
            change = mr.elo_change.white_delta
            color = '#4ade80' if change > 0 else ('#f87171' if change < 0 else '#94a3b8')
            elo_line += f' → <span style="color:{color}; font-weight:bold;">{mr.white.elo_rating + change} ({change:+d})</span>'
        elo_line += '</li>'
        parts.append(elo_line)
        
        parts.append(f'        <li><strong>Think Time:</strong> {mr.white_think_time:.1f}s</li>')
        parts.append(f'        <li><strong>Illegal Attempts:</strong> {mr.white_illegal_attempts}</li>')
        parts.append('      </ul>')
        parts.append('    </div>')
        
        # Black player
        black_provider = mr.black.provider.__class__.__name__ if mr.black.provider else "Unknown"
        black_model = getattr(mr.black.provider, 'model', 'Unknown') if mr.black.provider else "Unknown"
        parts.append('    <div>')
        parts.append(f'      <h4 style="margin:0 0 8px 0;">⚫ Black: {html_lib.escape(mr.black.name)}</h4>')
        parts.append('      <ul style="margin:0; padding-left:20px; line-height:1.8;">')
        parts.append(f'        <li><strong>Provider:</strong> {html_lib.escape(black_provider)}</li>')
        parts.append(f'        <li><strong>Model:</strong> {html_lib.escape(str(black_model))}</li>')
        parts.append(f'        <li><strong>Temperature:</strong> {mr.black.temperature}</li>')
        
        # Build ELO line
        elo_line = f'        <li><strong>ELO:</strong> {mr.black.elo_rating}'
        if self.include_elo and mr.elo_change:
            change = mr.elo_change.black_delta
            color = '#4ade80' if change > 0 else ('#f87171' if change < 0 else '#94a3b8')
            elo_line += f' → <span style="color:{color}; font-weight:bold;">{mr.black.elo_rating + change} ({change:+d})</span>'
        elo_line += '</li>'
        parts.append(elo_line)
        
        parts.append(f'        <li><strong>Think Time:</strong> {mr.black_think_time:.1f}s</li>')
        parts.append(f'        <li><strong>Illegal Attempts:</strong> {mr.black_illegal_attempts}</li>')
        parts.append('      </ul>')
        parts.append('    </div>')
        
        parts.append('  </div>')
        parts.append('</div>')
        
        # Think time visualization
        if mr.moves:
            parts.append('<div class="think-times" style="background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius); padding:20px; margin:24px 0;">')
            parts.append('  <h3 style="margin:0 0 16px 0; color:var(--accent); font-size:1.3em;">⏱️ Think Time Analysis</h3>')
            
            # Calculate statistics
            white_times = [m.think_time for m in mr.moves if m.color == "white"]
            black_times = [m.think_time for m in mr.moves if m.color == "black"]
            
            if white_times:
                white_avg = sum(white_times) / len(white_times)
                white_max = max(white_times)
                white_min = min(white_times)
            else:
                white_avg = white_max = white_min = 0
            
            if black_times:
                black_avg = sum(black_times) / len(black_times)
                black_max = max(black_times)
                black_min = min(black_times)
            else:
                black_avg = black_max = black_min = 0
            
            parts.append('  <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">')
            parts.append('    <div>')
            parts.append('      <h4 style="margin:0 0 8px 0;">⚪ White Times</h4>')
            parts.append('      <ul style="margin:0; padding-left:20px; line-height:1.8;">')
            parts.append(f'        <li><strong>Average:</strong> {white_avg:.2f}s</li>')
            parts.append(f'        <li><strong>Min:</strong> {white_min:.2f}s</li>')
            parts.append(f'        <li><strong>Max:</strong> {white_max:.2f}s</li>')
            parts.append(f'        <li><strong>Total:</strong> {mr.white_think_time:.1f}s</li>')
            parts.append('      </ul>')
            parts.append('    </div>')
            parts.append('    <div>')
            parts.append('      <h4 style="margin:0 0 8px 0;">⚫ Black Times</h4>')
            parts.append('      <ul style="margin:0; padding-left:20px; line-height:1.8;">')
            parts.append(f'        <li><strong>Average:</strong> {black_avg:.2f}s</li>')
            parts.append(f'        <li><strong>Min:</strong> {black_min:.2f}s</li>')
            parts.append(f'        <li><strong>Max:</strong> {black_max:.2f}s</li>')
            parts.append(f'        <li><strong>Total:</strong> {mr.black_think_time:.1f}s</li>')
            parts.append('      </ul>')
            parts.append('    </div>')
            parts.append('  </div>')
            parts.append('</div>')
        
        # Termination details
        parts.append('<div class="termination" style="background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius); padding:20px; margin:24px 0;">')
        parts.append('  <h3 style="margin:0 0 12px 0; color:var(--accent); font-size:1.3em;">🏁 Game Termination</h3>')
        parts.append(f'  <p style="margin:0; font-size:1.1em;"><strong>Reason:</strong> {html_lib.escape(mr.termination.value.replace("_", " ").title())}</p>')
        if mr.termination.value in ["timeout", "forfeit"]:
            parts.append('  <p style="margin:8px 0 0 0; color:var(--fg-muted); font-style:italic;">')
            if mr.termination.value == "timeout":
                parts.append('    ⚠️ Game ended due to time control violation. Consider using longer time controls for LLM matches.')
            else:
                parts.append('    ⚠️ Player exceeded maximum illegal move attempts.')
            parts.append('  </p>')
        parts.append('</div>')
        
        # ═════════════════════════════════════════════════════════════════════
        # POST-MATCH ANALYSIS SECTION (if available)
        # ═════════════════════════════════════════════════════════════════════
        if self.match_analysis:
            ma = self.match_analysis
            
            # Beauty Score & Metrics
            parts.append('<div class="analysis-beauty" style="background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius); padding:20px; margin:24px 0;">')
            parts.append('  <h3 style="margin:0 0 16px 0; color:var(--accent); font-size:1.3em;">✨ Beauty & Quality Analysis</h3>')
            parts.append('  <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:16px;">')
            
            # Beauty score bar
            beauty_pct = min(100, ma.beauty_score)
            beauty_color = '#4ade80' if beauty_pct >= 70 else ('#fbbf24' if beauty_pct >= 40 else '#f87171')
            parts.append('    <div>')
            parts.append('      <strong>Beauty Score</strong>')
            parts.append(f'      <div style="background:var(--bg); border-radius:8px; height:32px; margin-top:8px; position:relative; overflow:hidden;">')
            parts.append(f'        <div style="background:{beauty_color}; width:{beauty_pct}%; height:100%; display:flex; align-items:center; justify-content:center; font-weight:bold; color:white;">')
            parts.append(f'          {ma.beauty_score:.1f}/100')
            parts.append('        </div>')
            parts.append('      </div>')
            parts.append('    </div>')
            
            # Complexity score
            complexity_pct = min(100, ma.complexity_score)
            parts.append('    <div>')
            parts.append('      <strong>Complexity</strong>')
            parts.append(f'      <div style="background:var(--bg); border-radius:8px; height:32px; margin-top:8px; position:relative; overflow:hidden;">')
            parts.append(f'        <div style="background:#3b82f6; width:{complexity_pct}%; height:100%; display:flex; align-items:center; justify-content:center; font-weight:bold; color:white;">')
            parts.append(f'          {ma.complexity_score:.1f}/100')
            parts.append('        </div>')
            parts.append('      </div>')
            parts.append('    </div>')
            
            # Drama score
            drama_pct = min(100, ma.drama_score)
            parts.append('    <div>')
            parts.append('      <strong>Drama</strong>')
            parts.append(f'      <div style="background:var(--bg); border-radius:8px; height:32px; margin-top:8px; position:relative; overflow:hidden;">')
            parts.append(f'        <div style="background:#ec4899; width:{drama_pct}%; height:100%; display:flex; align-items:center; justify-content:center; font-weight:bold; color:white;">')
            parts.append(f'          {ma.drama_score:.1f}/100')
            parts.append('        </div>')
            parts.append('      </div>')
            parts.append('    </div>')
            
            parts.append('  </div>')
            parts.append('</div>')
            
            # Accuracy Metrics
            parts.append('<div class="analysis-accuracy" style="background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius); padding:20px; margin:24px 0;">')
            parts.append('  <h3 style="margin:0 0 16px 0; color:var(--accent); font-size:1.3em;">🎯 Accuracy Analysis</h3>')
            parts.append('  <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">')
            
            # White accuracy
            white_acc = min(100, ma.white_accuracy)
            white_acc_color = '#4ade80' if white_acc >= 80 else ('#fbbf24' if white_acc >= 60 else '#f87171')
            parts.append('    <div>')
            parts.append('      <h4 style="margin:0 0 8px 0;">⚪ White Accuracy</h4>')
            parts.append('      <ul style="margin:0; padding-left:20px; line-height:1.8;">')
            parts.append(f'        <li><strong>Accuracy:</strong> <span style="color:{white_acc_color}; font-weight:bold;">{ma.white_accuracy:.1f}%</span></li>')
            parts.append(f'        <li><strong>Avg CPL:</strong> {ma.white_avg_centipawn_loss:.1f}</li>')
            parts.append('      </ul>')
            parts.append('    </div>')
            
            # Black accuracy
            black_acc = min(100, ma.black_accuracy)
            black_acc_color = '#4ade80' if black_acc >= 80 else ('#fbbf24' if black_acc >= 60 else '#f87171')
            parts.append('    <div>')
            parts.append('      <h4 style="margin:0 0 8px 0;">⚫ Black Accuracy</h4>')
            parts.append('      <ul style="margin:0; padding-left:20px; line-height:1.8;">')
            parts.append(f'        <li><strong>Accuracy:</strong> <span style="color:{black_acc_color}; font-weight:bold;">{ma.black_accuracy:.1f}%</span></li>')
            parts.append(f'        <li><strong>Avg CPL:</strong> {ma.black_avg_centipawn_loss:.1f}</li>')
            parts.append('      </ul>')
            parts.append('    </div>')
            
            parts.append('  </div>')
            parts.append('</div>')
            
            # Critical Moments
            if ma.critical_moments:
                parts.append('<div class="critical-moments" style="background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius); padding:20px; margin:24px 0;">')
                parts.append('  <h3 style="margin:0 0 16px 0; color:var(--accent); font-size:1.3em;">🔥 Critical Moments</h3>')
                
                for moment in ma.critical_moments[:10]:  # Show top 10 critical moments
                    moment_icon = {
                        "blunder": "💥",
                        "brilliancy": "✨",
                        "turning_point": "🔄",
                        "missed_win": "⚠️"
                    }.get(moment.moment_type, "📌")
                    
                    moment_color = {
                        "blunder": "#f87171",
                        "brilliancy": "#4ade80",
                        "turning_point": "#fbbf24",
                        "missed_win": "#fb923c"
                    }.get(moment.moment_type, "#94a3b8")
                    
                    parts.append(f'  <div style="border-left:4px solid {moment_color}; padding:12px; margin-bottom:12px; background:var(--bg);">')
                    parts.append(f'    <div style="font-weight:bold; color:{moment_color};">{moment_icon} Move {moment.move_number}: {html_lib.escape(moment.san)} - {moment.moment_type.replace("_", " ").title()}</div>')
                    parts.append(f'    <div style="margin-top:4px; color:var(--fg-muted); font-size:0.95em;">{html_lib.escape(moment.commentary)}</div>')
                    
                    if moment.eval_swing > 0:
                        parts.append(f'    <div style="margin-top:4px; font-size:0.9em; color:var(--fg-muted);">Evaluation: {moment.eval_before:.1f} → {moment.eval_after:.1f} (swing: {moment.eval_swing:.0f} cp)</div>')
                    
                    parts.append('  </div>')
                
                parts.append('</div>')
            
            # Game Narrative
            if ma.narrative:
                parts.append('<div class="game-narrative" style="background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius); padding:20px; margin:24px 0;">')
                parts.append('  <h3 style="margin:0 0 16px 0; color:var(--accent); font-size:1.3em;">📖 Game Story</h3>')
                parts.append(f'  <p style="margin:0 0 12px 0; line-height:1.6;">{html_lib.escape(ma.narrative.summary)}</p>')
                
                if ma.narrative.winner_reason:
                    parts.append(f'  <p style="margin:0; font-style:italic; color:var(--fg-muted);">{html_lib.escape(ma.narrative.winner_reason)}</p>')
                
                parts.append('</div>')
            
            # Analysis metadata
            parts.append('<div class="analysis-meta" style="padding:12px; margin:24px 0; color:var(--fg-muted); font-size:0.9em; text-align:center; border-top:1px solid var(--border);">')
            parts.append(f'  ℹ️ Analysis performed in {ma.analysis_time:.2f}s using Stockfish depth {ma.stockfish_depth}')
            if ma.commentary_enabled:
                parts.append(' with LLM commentary')
            parts.append('</div>')
        
        return '\n'.join(parts)
    
    # =========================================================================
    # EXTENDED MARKDOWN EXPORT
    # =========================================================================
    
    def export_markdown(self) -> str:
        """Extend base markdown with LLM match details."""
        base_md = super().export_markdown()
        match_md = self._markdown_match_details()
        return base_md + "\n\n" + match_md
    
    def _markdown_match_details(self) -> str:
        """Generate markdown sections for LLM match details."""
        mr = self.match_result
        lines = [
            "",
            "---",
            "",
            "## ⚔️ LLM Match Details",
            "",
            "### Match Information",
            "",
            f"- **Match ID:** `{mr.match_id[:8]}`",
            f"- **Time Control:** {mr.time_control.name} ({mr.time_control.value}s per move)",
            f"- **Duration:** {mr.duration:.1f}s",
            f"- **Total Moves:** {mr.total_moves}",
            f"- **Termination:** {mr.termination.value.replace('_', ' ').title()}",
            "",
            "### 🤖 LLM Players",
            "",
            "| Metric | White | Black |",
            "|--------|-------|-------|",
            f"| **Player** | {mr.white.name} | {mr.black.name} |",
        ]
        
        # Provider info
        white_provider = mr.white.provider.__class__.__name__ if mr.white.provider else "Unknown"
        black_provider = mr.black.provider.__class__.__name__ if mr.black.provider else "Unknown"
        lines.append(f"| **Provider** | {white_provider} | {black_provider} |")
        
        # Model info
        white_model = getattr(mr.white.provider, 'model', 'Unknown') if mr.white.provider else "Unknown"
        black_model = getattr(mr.black.provider, 'model', 'Unknown') if mr.black.provider else "Unknown"
        lines.append(f"| **Model** | {white_model} | {black_model} |")
        
        # Temperature
        lines.append(f"| **Temperature** | {mr.white.temperature} | {mr.black.temperature} |")
        
        # ELO ratings
        if self.include_elo and mr.elo_change:
            white_new = mr.white.elo_rating + mr.elo_change.white_delta
            black_new = mr.black.elo_rating + mr.elo_change.black_delta
            lines.append(f"| **ELO (Old)** | {mr.white.elo_rating} | {mr.black.elo_rating} |")
            lines.append(f"| **ELO (New)** | {white_new} ({mr.elo_change.white_delta:+d}) | {black_new} ({mr.elo_change.black_delta:+d}) |")
        else:
            lines.append(f"| **ELO** | {mr.white.elo_rating} | {mr.black.elo_rating} |")
        
        # Think times
        lines.append(f"| **Total Think Time** | {mr.white_think_time:.1f}s | {mr.black_think_time:.1f}s |")
        lines.append(f"| **Illegal Attempts** | {mr.white_illegal_attempts} | {mr.black_illegal_attempts} |")
        
        # Think time statistics
        white_times = [m.think_time for m in mr.moves if m.color == "white"]
        black_times = [m.think_time for m in mr.moves if m.color == "black"]
        
        if white_times and black_times:
            lines.extend([
                "",
                "### ⏱️ Think Time Analysis",
                "",
                "| Statistic | White | Black |",
                "|-----------|-------|-------|",
                f"| **Average** | {sum(white_times)/len(white_times):.2f}s | {sum(black_times)/len(black_times):.2f}s |",
                f"| **Min** | {min(white_times):.2f}s | {min(black_times):.2f}s |",
                f"| **Max** | {max(white_times):.2f}s | {max(black_times):.2f}s |",
            ])
        
        return "\n".join(lines)
    
    # =========================================================================
    # EXTENDED JSON EXPORT
    # =========================================================================
    
    def export_json(self) -> str:
        """Extend base JSON with LLM match metadata."""
        import json as json_lib
        
        # Get base JSON
        base_json = super().export_json()
        data = json_lib.loads(base_json)
        
        # Add match-specific metadata
        mr = self.match_result
        data["match_metadata"] = {
            "match_id": mr.match_id,
            "time_control": {
                "name": mr.time_control.name,
                "seconds_per_move": mr.time_control.value,
            },
            "duration_seconds": mr.duration,
            "termination": mr.termination.value,
            "white_player": {
                "name": mr.white.name,
                "provider": mr.white.provider.__class__.__name__ if mr.white.provider else None,
                "model": getattr(mr.white.provider, 'model', None) if mr.white.provider else None,
                "temperature": mr.white.temperature,
                "elo_rating": mr.white.elo_rating,
                "elo_change": mr.elo_change.white_delta if mr.elo_change else 0,
                "total_think_time": mr.white_think_time,
                "illegal_attempts": mr.white_illegal_attempts,
            },
            "black_player": {
                "name": mr.black.name,
                "provider": mr.black.provider.__class__.__name__ if mr.black.provider else None,
                "model": getattr(mr.black.provider, 'model', None) if mr.black.provider else None,
                "temperature": mr.black.temperature,
                "elo_rating": mr.black.elo_rating,
                "elo_change": mr.elo_change.black_delta if mr.elo_change else 0,
                "total_think_time": mr.black_think_time,
                "illegal_attempts": mr.black_illegal_attempts,
            },
        }
        
        # Add per-move think times
        data["think_times"] = [
            {
                "move_number": m.move_number,
                "color": m.color,
                "san": m.san,
                "think_time": m.think_time,
                "attempt": m.attempt,
            }
            for m in mr.moves
        ]
        
        return json_lib.dumps(data, indent=2, ensure_ascii=False)


def export_match(
    match_result: Any,
    output_dir: str,
    formats: Optional[List[str]] = None,
    include_elo: bool = True,
    match_analysis: Optional[Any] = None,
) -> Dict[str, str]:
    """
    Export a single LLM vs LLM match using MatchExporter (extends GameExporter).
    
    This is a convenience function that creates a MatchExporter and exports
    to the specified formats.
    
    Args:
        match_result: MatchResult from MatchEngine.play_match()
        output_dir: Directory to save files
        formats: List of formats to export (default: ["pgn"])
                 Supported: "pgn", "markdown", "html", "json"
        include_elo: Include ELO change information in output
        match_analysis: Optional MatchAnalysis from MatchAnalyzer (adds beauty scores, commentary)
    
    Returns:
        Dict mapping format name to file path
    
    Raises:
        ValueError: If match result is empty/invalid (forfeit, timeout with 0 moves)
    """
    from export.game_exporter import ExportConfig
    from core.match_engine import TerminationReason
    
    # CRITICAL FIX: Validate match before attempting export
    if not match_result.moves or len(match_result.moves) == 0:
        termination = match_result.termination.value if hasattr(match_result.termination, 'value') else str(match_result.termination)
        logger.warning(
            f"Skipping export of empty match {match_result.match_id} "
            f"(termination: {termination}, winner: {match_result.result.value})"
        )
        # Return empty dict instead of crashing
        return {}
    
    formats = formats or ["pgn"]
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create MatchExporter with tournament-specific config
    config = ExportConfig(
        pgn_include_clock=True,
        pgn_include_evaluations=True,
        md_include_game_summary=True,
        md_include_eval_bars=True,
        html_dark_mode=True,
        html_include_styles=True,
    )
    
    try:
        exporter = MatchExporter(
            match_result=match_result,
            config=config,
            include_elo=include_elo,
            match_analysis=match_analysis,  # CRITICAL FIX: Pass analysis through
        )
    except ValueError as e:
        logger.error(f"Failed to create MatchExporter: {e}")
        return {}
    
    exported = {}
    base_name = f"match_{match_result.white.name}_vs_{match_result.black.name}"
    
    if "pgn" in formats:
        path = output_path / f"{base_name}.pgn"
        content = exporter.export_pgn()
        path.write_text(content, encoding="utf-8")
        exported["pgn"] = str(path)
        logger.info(f"PGN exported to {path}")
    
    if "markdown" in formats:
        path = output_path / f"{base_name}.md"
        content = exporter.export_markdown()
        path.write_text(content, encoding="utf-8")
        exported["markdown"] = str(path)
        logger.info(f"Markdown exported to {path}")
    
    if "html" in formats:
        path = output_path / f"{base_name}.html"
        content = exporter.export_html()
        path.write_text(content, encoding="utf-8")
        exported["html"] = str(path)
        logger.info(f"HTML exported to {path}")
    
    if "json" in formats:
        path = output_path / f"{base_name}.json"
        content = exporter.export_json()
        path.write_text(content, encoding="utf-8")
        exported["json"] = str(path)
        logger.info(f"JSON exported to {path}")
    
    return exported
