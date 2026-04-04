"""GIF animation generator for chess games."""

from __future__ import annotations

import logging
from pathlib import Path

import chess

logger = logging.getLogger(__name__)


class GIFGenerator:
    """Generates animated GIFs of chess games."""

    def __init__(self, square_size: int = 60, fps: float = 1.0) -> None:
        self._square_size = square_size
        self._fps = fps

    def generate(self, moves: list[str], output_path: str | Path) -> Path | None:
        """Generate an animated GIF for the given moves."""
        output_path = Path(output_path)
        try:
            from PIL import Image, ImageDraw, ImageFont  # type: ignore
        except ImportError:
            logger.warning("Pillow not installed. Cannot generate GIF.")
            return None

        frames = self._render_frames(moves)
        if not frames:
            return None

        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration_ms = int(1000 / self._fps)
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0,
        )
        logger.info("GIF saved to %s", output_path)
        return output_path

    def _render_frames(self, moves: list[str]):
        """Render board frames. Returns list of PIL Images."""
        try:
            from PIL import Image, ImageDraw  # type: ignore
        except ImportError:
            return []

        board = chess.Board()
        frames = [self._board_to_image(board)]
        for san in moves:
            try:
                board.push_san(san)
                frames.append(self._board_to_image(board))
            except Exception:
                break
        return frames

    def _board_to_image(self, board: chess.Board):
        """Render a board position as a PIL Image."""
        from PIL import Image, ImageDraw  # type: ignore

        size = self._square_size * 8
        img = Image.new("RGB", (size, size), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        light = (240, 217, 181)
        dark = (181, 136, 99)
        piece_chars = {
            (chess.PAWN, chess.WHITE): "P",
            (chess.KNIGHT, chess.WHITE): "N",
            (chess.BISHOP, chess.WHITE): "B",
            (chess.ROOK, chess.WHITE): "R",
            (chess.QUEEN, chess.WHITE): "Q",
            (chess.KING, chess.WHITE): "K",
            (chess.PAWN, chess.BLACK): "p",
            (chess.KNIGHT, chess.BLACK): "n",
            (chess.BISHOP, chess.BLACK): "b",
            (chess.ROOK, chess.BLACK): "r",
            (chess.QUEEN, chess.BLACK): "q",
            (chess.KING, chess.BLACK): "k",
        }

        s = self._square_size
        for rank in range(7, -1, -1):
            for file in range(8):
                sq = chess.square(file, rank)
                x = file * s
                y = (7 - rank) * s
                color = light if (rank + file) % 2 == 0 else dark
                draw.rectangle([x, y, x + s, y + s], fill=color)
                piece = board.piece_at(sq)
                if piece:
                    char = piece_chars.get((piece.piece_type, piece.color), "?")
                    draw.text((x + s // 4, y + s // 4), char, fill=(0, 0, 0))
        return img
