"""PGN file builder for chess games."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PGNHeaders:
    """Standard PGN headers."""

    event: str = "CAISSA Generated Game"
    site: str = "CAISSA"
    date: str = field(default_factory=lambda: datetime.date.today().isoformat())
    round: str = "1"
    white: str = "CAISSA White"
    black: str = "CAISSA Black"
    result: str = "*"
    white_elo: str = "?"
    black_elo: str = "?"
    time_control: str = "-"
    annotator: str = "CAISSA"


class PGNBuilder:
    """Builds PGN files from chess games."""

    def __init__(self, headers: PGNHeaders | None = None) -> None:
        self._headers = headers or PGNHeaders()
        self._games: list[str] = []

    @property
    def headers(self) -> PGNHeaders:
        return self._headers

    def build_pgn(self, moves: list[str], headers: PGNHeaders | None = None) -> str:
        """Build a PGN string from a list of SAN moves."""
        h = headers or self._headers
        lines: list[str] = [
            f'[Event "{h.event}"]',
            f'[Site "{h.site}"]',
            f'[Date "{h.date}"]',
            f'[Round "{h.round}"]',
            f'[White "{h.white}"]',
            f'[Black "{h.black}"]',
            f'[Result "{h.result}"]',
            f'[WhiteElo "{h.white_elo}"]',
            f'[BlackElo "{h.black_elo}"]',
            f'[TimeControl "{h.time_control}"]',
            f'[Annotator "{h.annotator}"]',
            "",
        ]
        move_text_parts: list[str] = []
        for i, san in enumerate(moves):
            if i % 2 == 0:
                move_text_parts.append(f"{i // 2 + 1}.")
            move_text_parts.append(san)
        move_text_parts.append(h.result)
        lines.append(" ".join(move_text_parts))
        pgn = "\n".join(lines)
        self._games.append(pgn)
        return pgn

    def save(self, path: str | Path, pgn: str | None = None) -> Path:
        """Save PGN to a file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        content = pgn if pgn is not None else "\n\n".join(self._games)
        p.write_text(content, encoding="utf-8")
        return p

    def clear(self) -> None:
        """Clear accumulated games."""
        self._games.clear()
