"""Markdown report generator for CAISSA games."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GameReport:
    """Data for a single game report."""

    white: str
    black: str
    moves: list[str]
    result: str = "*"
    aesthetic_score: float = 0.0
    pgn: str = ""
    notes: str = ""
    event: str = "CAISSA Game"


class MarkdownReport:
    """Generates Markdown reports for chess games and tournaments."""

    def __init__(self, title: str = "CAISSA Chess Report") -> None:
        self._title = title

    def generate_game_report(self, report: GameReport) -> str:
        """Generate a Markdown report for a single game."""
        move_pairs: list[str] = []
        for i in range(0, len(report.moves), 2):
            white_move = report.moves[i]
            black_move = report.moves[i + 1] if i + 1 < len(report.moves) else "..."
            move_pairs.append(f"| {i // 2 + 1} | {white_move} | {black_move} |")

        table = "\n".join(move_pairs)
        sections: list[str] = [
            f"# {report.event}",
            f"**Date**: {datetime.date.today().isoformat()}",
            f"**White**: {report.white}  |  **Black**: {report.black}",
            f"**Result**: {report.result}",
            f"**Aesthetic Score**: {report.aesthetic_score:.2f}/1.00",
            "",
            "## Moves",
            "",
            "| # | White | Black |",
            "|---|-------|-------|",
            table,
        ]
        if report.notes:
            sections += ["", "## Notes", "", report.notes]
        if report.pgn:
            sections += ["", "## PGN", "", "```pgn", report.pgn, "```"]
        return "\n".join(sections)

    def generate_tournament_report(
        self,
        tournament_name: str,
        results: list[dict],
        standings: list[dict] | None = None,
    ) -> str:
        """Generate a Markdown tournament report."""
        sections: list[str] = [
            f"# {tournament_name}",
            f"**Generated**: {datetime.date.today().isoformat()}",
            f"**Games played**: {len(results)}",
            "",
            "## Results",
            "",
            "| # | White | Black | Result | Score |",
            "|---|-------|-------|--------|-------|",
        ]
        for i, r in enumerate(results, 1):
            sections.append(
                f"| {i} | {r.get('white', '?')} | {r.get('black', '?')} "
                f"| {r.get('result', '*')} | {r.get('aesthetic_score', 0.0):.2f} |"
            )
        if standings:
            sections += ["", "## Standings", "", "| Rank | Player | ELO | Wins | Losses | Draws |",
                         "|------|--------|-----|------|--------|-------|"]
            for i, s in enumerate(standings, 1):
                sections.append(
                    f"| {i} | {s.get('player', '?')} | {s.get('elo', 1500)} "
                    f"| {s.get('wins', 0)} | {s.get('losses', 0)} | {s.get('draws', 0)} |"
                )
        return "\n".join(sections)

    def save(self, content: str, path: str | Path) -> Path:
        """Save a Markdown report to a file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p
