"""Stockfish engine client for position evaluation."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class StockfishEvaluation:
    """Result of a Stockfish position evaluation."""

    score_cp: int | None = None
    score_mate: int | None = None
    best_move: str | None = None
    depth: int = 0
    pv: list[str] | None = None

    @property
    def is_mate(self) -> bool:
        return self.score_mate is not None

    @property
    def score_str(self) -> str:
        if self.score_mate is not None:
            return f"M{self.score_mate}"
        return f"{self.score_cp / 100:.2f}" if self.score_cp is not None else "?"


class StockfishClient:
    """Client for communicating with the Stockfish chess engine via UCI."""

    def __init__(self, path: str | None = None, depth: int = 15) -> None:
        self._path = path or self._find_stockfish()
        self._depth = depth
        self._process: subprocess.Popen | None = None
        self._available = False
        if self._path:
            self._available = self._test_connection()

    @staticmethod
    def _find_stockfish() -> str | None:
        """Try to locate Stockfish on the system PATH."""
        import shutil
        return shutil.which("stockfish")

    @property
    def is_available(self) -> bool:
        return self._available

    def _test_connection(self) -> bool:
        try:
            proc = subprocess.Popen(
                [self._path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            proc.stdin.write("uci\n")
            proc.stdin.flush()
            for _ in range(50):
                line = proc.stdout.readline()
                if "uciok" in line:
                    proc.stdin.write("quit\n")
                    proc.stdin.flush()
                    proc.wait(timeout=5)
                    return True
            proc.terminate()
        except Exception as exc:
            logger.debug("Stockfish test failed: %s", exc)
        return False

    def evaluate(self, fen: str) -> StockfishEvaluation:
        """Evaluate a position and return the best move + score."""
        if not self._available or not self._path:
            logger.warning("Stockfish not available")
            return StockfishEvaluation()
        try:
            proc = subprocess.Popen(
                [self._path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            commands = f"uci\nposition fen {fen}\ngo depth {self._depth}\n"
            stdout, _ = proc.communicate(input=commands, timeout=30)
            return self._parse_output(stdout)
        except Exception as exc:
            logger.error("Stockfish evaluation failed: %s", exc)
            return StockfishEvaluation()

    def _parse_output(self, output: str) -> StockfishEvaluation:
        eval_result = StockfishEvaluation()
        for line in output.splitlines():
            if line.startswith("info") and "score" in line:
                parts = line.split()
                try:
                    score_idx = parts.index("score")
                    score_type = parts[score_idx + 1]
                    score_val = int(parts[score_idx + 2])
                    if score_type == "cp":
                        eval_result.score_cp = score_val
                    elif score_type == "mate":
                        eval_result.score_mate = score_val
                    if "depth" in parts:
                        eval_result.depth = int(parts[parts.index("depth") + 1])
                    if "pv" in parts:
                        pv_idx = parts.index("pv")
                        eval_result.pv = parts[pv_idx + 1:]
                except (ValueError, IndexError):
                    pass
            elif line.startswith("bestmove"):
                parts = line.split()
                if len(parts) >= 2:
                    eval_result.best_move = parts[1]
        return eval_result
