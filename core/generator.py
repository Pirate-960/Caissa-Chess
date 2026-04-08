"""CAISSA game generator - orchestrates LLM-based chess game generation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import chess

from core.board_state import BoardState
from core.llm_provider import LLMProvider, LLMResponse
from core.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """Configuration for game generation."""

    max_moves: int = 80
    style: str = "aggressive"
    temperature_override: float | None = None
    enforce_legality: bool = True
    aesthetic_weight: float = 0.5


@dataclass
class GeneratedGame:
    """Result of a generated chess game."""

    moves: list[str] = field(default_factory=list)
    pgn: str = ""
    aesthetic_score: float = 0.0
    provider_responses: list[LLMResponse] = field(default_factory=list)
    termination_reason: str = "normal"
    metadata: dict = field(default_factory=dict)


class CaissaGenerator:
    """Generates aesthetic chess games using LLM providers."""

    def __init__(
        self,
        white_provider: LLMProvider,
        black_provider: LLMProvider | None = None,
        config: GenerationConfig | None = None,
    ) -> None:
        self.white_provider = white_provider
        self.black_provider = black_provider or white_provider
        self.config = config or GenerationConfig()
        self.prompt_manager = PromptManager()

    def generate_game(self) -> GeneratedGame:
        """Generate a complete chess game."""
        board = chess.Board()
        board_state = BoardState(board)
        game = GeneratedGame()
        move_count = 0

        while not board.is_game_over() and move_count < self.config.max_moves:
            provider = self.white_provider if board.turn == chess.WHITE else self.black_provider
            prompt = self.prompt_manager.build_move_prompt(board_state, self.config.style)
            system_prompt = self.prompt_manager.get_system_prompt(self.config.style)

            try:
                response = provider.generate(prompt, system_prompt)
                game.provider_responses.append(response)
                move_san = self._extract_move(response.content, board)
                if move_san:
                    board.push_san(move_san)
                    game.moves.append(move_san)
                    board_state = BoardState(board)
                    move_count += 1
                else:
                    logger.warning("No legal move extracted from response: %s", response.content)
                    game.termination_reason = "illegal_move"
                    break
            except Exception as exc:
                logger.error("Generation error: %s", exc)
                game.termination_reason = f"error: {exc}"
                break

        game.pgn = self._build_pgn(game.moves)
        return game

    def _extract_move(self, text: str, board: chess.Board) -> str | None:
        """Extract a legal move from LLM text output."""
        text = text.strip()
        # Try direct SAN
        for token in text.split():
            token = token.strip(".,!?;:")
            try:
                move = board.parse_san(token)
                return board.san(move)
            except Exception:
                pass
        # Try first word
        first = text.split()[0].strip(".,!?;:") if text.split() else ""
        try:
            move = board.parse_san(first)
            return board.san(move)
        except Exception:
            pass
        return None

    def _build_pgn(self, moves: list[str]) -> str:
        """Build a simple PGN string from moves."""
        board = chess.Board()
        parts: list[str] = []
        for i, san in enumerate(moves):
            if i % 2 == 0:
                parts.append(f"{i // 2 + 1}.")
            parts.append(san)
            try:
                board.push_san(san)
            except Exception:
                break
        return " ".join(parts)
