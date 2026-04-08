"""Tournament data exporter with multiple format support."""

from __future__ import annotations

import csv
import datetime
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TournamentResult:
    """Result record for a single tournament game."""

    round_number: int
    white: str
    black: str
    result: str
    white_elo: int
    black_elo: int
    move_count: int = 0
    aesthetic_score: float = 0.0
    pgn: str = ""
    time_control: str = "-"


@dataclass
class TournamentStanding:
    """Standing record for a tournament participant."""

    rank: int
    player: str
    elo: int
    wins: int
    losses: int
    draws: int
    points: float
    games_played: int


class TournamentExporter:
    """Exports tournament data in multiple formats."""

    def __init__(self, tournament_name: str = "CAISSA Tournament") -> None:
        self._name = tournament_name
        self._results: list[TournamentResult] = []
        self._standings: list[TournamentStanding] = []

    def add_result(self, result: TournamentResult) -> None:
        """Add a game result to the tournament records."""
        self._results.append(result)

    def add_standing(self, standing: TournamentStanding) -> None:
        """Add or update a player standing."""
        self._standings.append(standing)

    def add_results_batch(self, results: list[TournamentResult]) -> None:
        """Add multiple results at once."""
        for result in results:
            self._results.append(result)

    def export_json(self, path: str | Path) -> Path:
        """Export tournament data as JSON."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "tournament": self._name,
            "generated_at": datetime.datetime.now().isoformat(),
            "results": [asdict(r) for r in self._results],
            "standings": [asdict(s) for s in self._standings],
        }
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Tournament JSON exported to %s", p)
        return p

    def export_csv(self, path: str | Path) -> Path:
        """Export tournament results as CSV."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not self._results:
            p.write_text("", encoding="utf-8")
            return p
        fieldnames = list(asdict(self._results[0]).keys())
        with p.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for result in self._results:
                writer.writerow(asdict(result))
        logger.info("Tournament CSV exported to %s", p)
        return p

    def export_pgn_bundle(self, path: str | Path) -> Path:
        """Export all games as a single PGN bundle."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        games: list[str] = []
        for r in self._results:
            if r.pgn:
                games.append(r.pgn)
        p.write_text("\n\n".join(games), encoding="utf-8")
        logger.info("Tournament PGN bundle exported to %s", p)
        return p

    def export_per_game_pgn(self, directory: str | Path) -> list[Path]:
        """Export each game as an individual PGN file."""
        base_dir = Path(directory)
        base_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for i, r in enumerate(self._results, 1):
            if r.pgn:
                filename = f"game_{i:03d}_{r.white}_vs_{r.black}.pgn".replace(" ", "_")
                p = base_dir / filename
                p.write_text(r.pgn, encoding="utf-8")
                paths.append(p)
        logger.info("Exported %d individual PGN files to %s", len(paths), base_dir)
        return paths

    def export_markdown(self, path: str | Path) -> Path:
        """Export tournament report as Markdown."""
        from export.markdown_report import MarkdownReport
        p = Path(path)
        reporter = MarkdownReport()
        content = reporter.generate_tournament_report(
            self._name,
            [asdict(r) for r in self._results],
            [asdict(s) for s in self._standings]
        )
        p.write_text(content, encoding="utf-8")
        logger.info("Tournament Markdown exported to %s", p)
        return p

    def export_html(self, path: str | Path) -> Path:
        """Export tournament report as HTML."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        
        results_rows = ""
        for i, r in enumerate(self._results, 1):
            results_rows += f"""
            <tr>
                <td>{i}</td>
                <td>{r.white}</td>
                <td>{r.black}</td>
                <td>{r.result}</td>
                <td>{r.aesthetic_score:.2f}</td>
                <td>{r.move_count}</td>
            </tr>"""

        standings_rows = ""
        for s in self._standings:
            standings_rows += f"""
            <tr>
                <td>{s.rank}</td>
                <td>{s.player}</td>
                <td>{s.elo}</td>
                <td>{s.points}</td>
                <td>{s.wins}</td>
                <td>{s.losses}</td>
                <td>{s.draws}</td>
            </tr>"""

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{self._name}</title>
    <style>
        body {{ font-family: sans-serif; margin: 20px; line-height: 1.6; }}
        h1, h2 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        tr:nth-child(even) {{ background-color: #f9f9f9; }}
        .meta {{ color: #666; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <h1>{self._name}</h1>
    <div class="meta">
        <p>Generated: {datetime.date.today().isoformat()}</p>
        <p>Games played: {len(self._results)}</p>
    </div>

    <h2>Standings</h2>
    <table>
        <thead>
            <tr>
                <th>Rank</th>
                <th>Player</th>
                <th>ELO</th>
                <th>Points</th>
                <th>Wins</th>
                <th>Losses</th>
                <th>Draws</th>
            </tr>
        </thead>
        <tbody>
            {standings_rows}
        </tbody>
    </table>

    <h2>Results</h2>
    <table>
        <thead>
            <tr>
                <th>#</th>
                <th>White</th>
                <th>Black</th>
                <th>Result</th>
                <th>Aesthetic Score</th>
                <th>Moves</th>
            </tr>
        </thead>
        <tbody>
            {results_rows}
        </tbody>
    </table>
</body>
</html>"""
        p.write_text(html_content, encoding="utf-8")
        logger.info("Tournament HTML exported to %s", p)
        return p

    def export_all(self, output_dir: str | Path) -> dict[str, Path | list[Path]]:
        """Export tournament data in all supported formats."""
        base = Path(output_dir)
        base.mkdir(parents=True, exist_ok=True)
        
        exports = {
            "json": self.export_json(base / "tournament.json"),
            "csv": self.export_csv(base / "tournament.csv"),
            "pgn_bundle": self.export_pgn_bundle(base / "tournament.pgn"),
            "per_game_pgn": self.export_per_game_pgn(base / "games"),
            "markdown": self.export_markdown(base / "report.md"),
            "html": self.export_html(base / "report.html"),
        }
        return exports

    @property
    def results(self) -> list[TournamentResult]:
        return list(self._results)

    @property
    def standings(self) -> list[TournamentStanding]:
        return list(self._standings)

    def clear(self) -> None:
        """Clear all tournament data."""
        self._results.clear()
        self._standings.clear()
