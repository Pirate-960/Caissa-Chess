"""Tournament data exporter with multiple format support."""

from __future__ import annotations

import csv
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
        """Export all games as a PGN bundle."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        games: list[str] = []
        for r in self._results:
            if r.pgn:
                games.append(r.pgn)
        p.write_text("\n\n".join(games), encoding="utf-8")
        return p

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
