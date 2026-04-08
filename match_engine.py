"""Match engine for LLM vs LLM chess matches and tournaments."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import chess

from core.board_state import BoardState
from core.generator import CaissaGenerator, GenerationConfig, GeneratedGame
from core.llm_provider import LLMProvider, MockProvider
from core.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class TimeControl(Enum):
    """Standard time controls."""

    BULLET = 5
    BLITZ = 30
    RAPID = 300
    CLASSICAL = 1800


class GameResult(Enum):
    WHITE_WINS = "1-0"
    BLACK_WINS = "0-1"
    DRAW = "1/2-1/2"
    FORFEIT_WHITE = "forfeit_white"
    FORFEIT_BLACK = "forfeit_black"


@dataclass
class PlayerProfile:
    """Represents an LLM player with ELO tracking."""

    name: str
    provider: LLMProvider
    elo: int = 1500
    wins: int = 0
    losses: int = 0
    draws: int = 0
    forfeits: int = 0

    @property
    def games_played(self) -> int:
        return self.wins + self.losses + self.draws

    @property
    def points(self) -> float:
        return float(self.wins) + 0.5 * self.draws


@dataclass
class MatchResult:
    """Result of a single match between two players."""

    white_player: str
    black_player: str
    result: GameResult
    moves: list[str] = field(default_factory=list)
    move_times: list[float] = field(default_factory=list)
    termination: str = "normal"
    white_elo_before: int = 1500
    black_elo_before: int = 1500
    white_elo_after: int = 1500
    black_elo_after: int = 1500
    aesthetic_score: float = 0.0
    pgn: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class MatchEngine:
    """Runs LLM vs LLM chess matches with time control and ELO tracking."""

    ELO_K_FACTOR = 20

    def __init__(
        self,
        time_control: TimeControl = TimeControl.BLITZ,
        max_moves: int = 100,
        style: str = "balanced",
    ) -> None:
        self._time_control = time_control
        self._max_moves = max_moves
        self._style = style
        self._prompt_manager = PromptManager()

    @property
    def time_limit_seconds(self) -> float:
        return float(self._time_control.value)

    def play_match(
        self, white: PlayerProfile, black: PlayerProfile
    ) -> MatchResult:
        """Play a single match between two LLM players."""
        board = chess.Board()
        result = MatchResult(
            white_player=white.name,
            black_player=black.name,
            result=GameResult.DRAW,
            white_elo_before=white.elo,
            black_elo_before=black.elo,
        )
        logger.info("Match: %s (White) vs %s (Black)", white.name, black.name)

        move_count = 0
        while not board.is_game_over() and move_count < self._max_moves:
            current_player = white if board.turn == chess.WHITE else black
            board_state = BoardState(board)
            prompt = self._prompt_manager.build_move_prompt(board_state, self._style)
            system_prompt = self._prompt_manager.get_system_prompt(self._style)

            t_start = time.monotonic()
            move_san = self._get_move_with_timeout(
                current_player.provider, prompt, system_prompt, board
            )
            elapsed = time.monotonic() - t_start
            result.move_times.append(elapsed)

            if move_san is None:
                logger.warning("%s timed out or failed on move %d", current_player.name, move_count + 1)
                if board.turn == chess.WHITE:
                    result.result = GameResult.FORFEIT_WHITE
                    result.termination = f"forfeit: {white.name} failed to produce a legal move"
                else:
                    result.result = GameResult.FORFEIT_BLACK
                    result.termination = f"forfeit: {black.name} failed to produce a legal move"
                break

            if elapsed > self.time_limit_seconds:
                logger.warning(
                    "%s exceeded time limit (%.2fs > %.2fs)",
                    current_player.name, elapsed, self.time_limit_seconds,
                )
                if board.turn == chess.WHITE:
                    result.result = GameResult.FORFEIT_WHITE
                    result.termination = f"timeout: {white.name}"
                else:
                    result.result = GameResult.FORFEIT_BLACK
                    result.termination = f"timeout: {black.name}"
                break

            try:
                board.push_san(move_san)
                result.moves.append(move_san)
                move_count += 1
            except Exception as exc:
                logger.error("Invalid move %r from %s: %s", move_san, current_player.name, exc)
                if board.turn == chess.WHITE:
                    result.result = GameResult.FORFEIT_WHITE
                else:
                    result.result = GameResult.FORFEIT_BLACK
                result.termination = f"illegal_move: {move_san}"
                break
        else:
            result.result = self._determine_result(board)
            result.termination = board.result() if board.is_game_over() else "max_moves"

        result.pgn = self._build_pgn(result.moves, white.name, black.name, result.result)
        self._update_elo(white, black, result)
        result.white_elo_after = white.elo
        result.black_elo_after = black.elo
        logger.info(
            "Result: %s | ELO: %s %d->%d, %s %d->%d",
            result.result.value,
            white.name, result.white_elo_before, white.elo,
            black.name, result.black_elo_before, black.elo,
        )
        return result

    def _get_move_with_timeout(
        self,
        provider: LLMProvider,
        prompt: str,
        system_prompt: str,
        board: chess.Board,
    ) -> str | None:
        """Get a move from a provider, returning None on failure."""
        try:
            response = provider.generate(prompt, system_prompt)
            return self._extract_move(response.content, board)
        except Exception as exc:
            logger.error("Provider error: %s", exc)
            return None

    def _extract_move(self, text: str, board: chess.Board) -> str | None:
        for token in text.split():
            token = token.strip(".,!?;:()")
            try:
                move = board.parse_san(token)
                if move in board.legal_moves:
                    return board.san(move)
            except Exception:
                pass
        return None

    def _determine_result(self, board: chess.Board) -> GameResult:
        if board.is_checkmate():
            return GameResult.WHITE_WINS if board.turn == chess.BLACK else GameResult.BLACK_WINS
        return GameResult.DRAW

    def _build_pgn(
        self, moves: list[str], white: str, black: str, result: GameResult
    ) -> str:
        board = chess.Board()
        parts: list[str] = [
            f'[White "{white}"]',
            f'[Black "{black}"]',
            f'[Result "{result.value}"]',
            "",
        ]
        move_tokens: list[str] = []
        for i, san in enumerate(moves):
            if i % 2 == 0:
                move_tokens.append(f"{i // 2 + 1}.")
            move_tokens.append(san)
            try:
                board.push_san(san)
            except Exception:
                break
        move_tokens.append(result.value)
        parts.append(" ".join(move_tokens))
        return "\n".join(parts)

    def _update_elo(
        self, white: PlayerProfile, black: PlayerProfile, result: MatchResult
    ) -> None:
        expected_white = 1 / (1 + 10 ** ((black.elo - white.elo) / 400))
        expected_black = 1 - expected_white

        if result.result in (GameResult.WHITE_WINS, GameResult.FORFEIT_BLACK):
            score_white, score_black = 1.0, 0.0
            white.wins += 1
            black.losses += 1
        elif result.result in (GameResult.BLACK_WINS, GameResult.FORFEIT_WHITE):
            score_white, score_black = 0.0, 1.0
            white.losses += 1
            black.wins += 1
        else:
            score_white, score_black = 0.5, 0.5
            white.draws += 1
            black.draws += 1

        white.elo += round(self.ELO_K_FACTOR * (score_white - expected_white))
        black.elo += round(self.ELO_K_FACTOR * (score_black - expected_black))


class Tournament:
    """Manages a tournament between multiple LLM players."""

    def __init__(
        self,
        name: str = "CAISSA Tournament",
        time_control: TimeControl = TimeControl.BLITZ,
        rounds: int = 1,
        style: str = "balanced",
    ) -> None:
        self._name = name
        self._time_control = time_control
        self._rounds = rounds
        self._style = style
        self._players: list[PlayerProfile] = []
        self._results: list[MatchResult] = []
        self._engine = MatchEngine(time_control=time_control, style=style)

    def add_player(self, name: str, provider: LLMProvider, elo: int = 1500) -> PlayerProfile:
        """Register a player in the tournament."""
        player = PlayerProfile(name=name, provider=provider, elo=elo)
        self._players.append(player)
        logger.info("Player registered: %s (ELO %d)", name, elo)
        return player

    def run_round_robin(self) -> list[MatchResult]:
        """Run a round-robin tournament."""
        if len(self._players) < 2:
            raise ValueError("At least 2 players required for a tournament")

        logger.info("Starting %s: %d players, %d rounds", self._name, len(self._players), self._rounds)
        for _round in range(self._rounds):
            for i, white in enumerate(self._players):
                for j, black in enumerate(self._players):
                    if i == j:
                        continue
                    result = self._engine.play_match(white, black)
                    self._results.append(result)

        logger.info("Tournament complete. %d games played.", len(self._results))
        return self._results

    def get_standings(self) -> list[PlayerProfile]:
        """Return players sorted by points (descending)."""
        return sorted(self._players, key=lambda p: (p.points, p.wins, p.elo), reverse=True)

    def print_standings(self) -> None:
        """Print tournament standings to stdout."""
        standings = self.get_standings()
        print(f"\n{'='*50}")
        print(f"  {self._name} - Final Standings")
        print(f"{'='*50}")
        print(f"{'Rank':<5} {'Player':<20} {'ELO':<6} {'Pts':<6} {'W':<4} {'L':<4} {'D':<4}")
        print("-" * 50)
        for i, p in enumerate(standings, 1):
            print(
                f"{i:<5} {p.name:<20} {p.elo:<6} "
                f"{p.points:<6.1f} {p.wins:<4} {p.losses:<4} {p.draws:<4}"
            )

    @property
    def results(self) -> list[MatchResult]:
        return list(self._results)

    @property
    def players(self) -> list[PlayerProfile]:
        return list(self._players)
