"""Prompt management for CAISSA chess generation."""

from __future__ import annotations

from core.board_state import BoardState


STYLE_SYSTEM_PROMPTS: dict[str, str] = {
    "aggressive": (
        "You are a highly aggressive chess engine that favours attacks, sacrifices, and tactical"
        " complications. Always seek the most dynamic continuation."
    ),
    "positional": (
        "You are a positional chess engine that values pawn structure, piece activity, and"
        " long-term strategic advantages. Prefer solid, principled play."
    ),
    "romantic": (
        "You are a romantic-era chess engine inspired by Morphy and Anderssen. Seek brilliant"
        " combinations, king attacks, and beautiful sacrifices."
    ),
    "defensive": (
        "You are a defensive chess engine that prioritises safety and consolidation. Avoid"
        " complications and prefer solid positions."
    ),
    "balanced": (
        "You are a balanced chess engine that weighs both tactical and strategic factors."
        " Play the objectively best move."
    ),
}


class PromptManager:
    """Manages prompt templates for chess move generation."""

    def get_system_prompt(self, style: str = "balanced") -> str:
        """Return a system prompt for the given playing style."""
        base = STYLE_SYSTEM_PROMPTS.get(style, STYLE_SYSTEM_PROMPTS["balanced"])
        return (
            f"{base}\n\n"
            "When asked for a move, respond with ONLY the move in Standard Algebraic Notation"
            " (e.g., e4, Nf3, O-O). Do not include explanations unless specifically asked."
        )

    def build_move_prompt(self, board_state: BoardState, style: str = "balanced") -> str:
        """Build a move-generation prompt from the current board state."""
        turn = "White" if board_state.turn_is_white else "Black"
        legal_count = board_state.legal_move_count
        fen = board_state.fen

        prompt = (
            f"Current position (FEN): {fen}\n"
            f"It is {turn}'s turn.\n"
            f"There are {legal_count} legal moves available.\n"
        )
        if board_state.is_check:
            prompt += "The king is in CHECK.\n"

        prompt += f"\nPlay a {style} move. Respond with only the move in SAN notation."
        return prompt

    def build_analysis_prompt(self, board_state: BoardState) -> str:
        """Build a position analysis prompt."""
        return (
            f"Analyse this chess position:\nFEN: {board_state.fen}\n\n"
            "Provide a brief assessment of the position, key strategic themes, and the best plan."
        )

    @staticmethod
    def available_styles() -> list[str]:
        return list(STYLE_SYSTEM_PROMPTS.keys())
