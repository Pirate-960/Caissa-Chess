"""
export/game_exporter.py

Unified export system for chess games across all formats.

This module bridges the gap between the LLM generation pipeline and the export
formats (PGN, JSON, Markdown, HTML). It takes a ParsedGame (from annotation_parser)
and produces high-quality, consistent, richly-annotated output in any format.

Architecture:
    LLM → raw PGN → annotation_parser.parse_pgn() → ParsedGame → GameExporter → formatted output

Previously, the pipeline had two disconnected formatting systems (PGNWriter in caissa.py
and PGNBuilder in export/pgn_builder.py) and lost all LLM-generated annotations during
move extraction. This module unifies everything.
"""

import json
import logging
import html as html_lib
import textwrap
from datetime import datetime
from dataclasses import dataclass

import chess
from typing import Any, Dict, List, Optional, Tuple

from export.annotation_parser import ParsedGame, NAG_SYMBOL_MAP

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class ExportConfig:
    """Export formatting configuration."""
    # PGN
    pgn_line_width: int = 80
    pgn_include_annotations: bool = True
    pgn_include_comments: bool = True
    pgn_include_evaluations: bool = True
    pgn_include_clock: bool = True

    # Markdown
    md_include_diagram_markers: bool = True
    md_include_eval_bars: bool = True
    md_include_game_summary: bool = True
    md_moves_per_row: int = 1  # 1 = one move pair per line, 0 = flowing text

    # HTML
    html_include_styles: bool = True
    html_dark_mode: bool = False
    html_interactive: bool = False  # Future: board integration
    html_comment_mode: str = "full"  # "full" | "truncate" | "tooltip"
    html_move_layout: str = "table"  # "table" | "inline"
    html_show_phase_markers: bool = True

    # JSON
    json_pretty: bool = True
    json_include_raw_pgn: bool = False  # Include original PGN in JSON


# =============================================================================
# MAIN EXPORTER CLASS
# =============================================================================

class GameExporter:
    """
    Unified game exporter producing consistent, annotated output across all formats.

    Usage:
        from export.annotation_parser import parse_pgn
        from export.game_exporter import GameExporter

        parsed = parse_pgn(raw_pgn_string)
        exporter = GameExporter(parsed)
        pgn_out = exporter.export_pgn()
        json_out = exporter.export_json()
        md_out = exporter.export_markdown()
        html_out = exporter.export_html()
    """

    def __init__(
        self,
        game: ParsedGame,
        config: Optional[ExportConfig] = None,
        beauty_score: Optional[float] = None,
        style_name: Optional[str] = None,
    ):
        """
        Args:
            game: ParsedGame from annotation_parser
            config: Export configuration (uses defaults if None)
            beauty_score: Overall beauty score if available
            style_name: Style/era used for generation
        """
        self.game = game
        self.config = config or ExportConfig()
        self.beauty_score = beauty_score
        self.style_name = style_name

    # =========================================================================
    # PGN EXPORT
    # =========================================================================

    def export_pgn(self) -> str:
        """
        Export as a pretty-formatted PGN with three distinct sections:

        1. **Moves** — Clean movetext, one move pair per line, NAGs inline.
        2. **Move Commentary** — Per-move annotations separated from the move list.
        3. **Game Summary** — High-level game narrative.

        Returns:
            Complete PGN string with headers, sectioned content, and result.
        """
        parts = []

        # ── Headers ──
        parts.append(self._format_pgn_headers())
        parts.append("")

        # ── Section 1: Moves ──
        parts.append(self._pgn_section_divider("MOVES"))
        parts.append("")
        parts.append(self._format_pgn_movetext())
        parts.append("")
        parts.append(self.game.result)

        # ── Section 2: Move Commentary (only if annotations exist) ──
        commentary = self._format_pgn_commentary()
        if commentary:
            parts.append("")
            parts.append(self._pgn_section_divider("MOVE COMMENTARY"))
            parts.append("")
            parts.append(commentary)

        # ── Section 3: Game Summary ──
        summary = self._format_pgn_game_summary()
        if summary:
            parts.append("")
            parts.append(self._pgn_section_divider("GAME SUMMARY"))
            parts.append("")
            parts.append(summary)

        parts.append("")  # Trailing newline
        return "\n".join(parts)

    @staticmethod
    def _pgn_section_divider(title: str) -> str:
        """Return a clean section divider."""
        bar = "═" * 55
        return f"{bar}\n  {title}\n{bar}"

    def _format_pgn_headers(self) -> str:
        """Format PGN Seven Tag Roster + extra headers in standard order."""
        headers = dict(self.game.headers)

        # Ensure required STR headers exist
        defaults = {
            "Event": self.game.event,
            "Site": self.game.site,
            "Date": self.game.date,
            "Round": headers.get("Round", "?"),
            "White": self.game.white,
            "Black": self.game.black,
            "Result": self.game.result,
        }
        for key, default in defaults.items():
            if key not in headers:
                headers[key] = default

        # Add opening info if detected
        if self.game.eco and "ECO" not in headers:
            headers["ECO"] = self.game.eco
        if self.game.opening_name and "Opening" not in headers:
            headers["Opening"] = self.game.opening_name

        # Add annotator
        if "Annotator" not in headers:
            headers["Annotator"] = "Caissa Chess Engine"

        # Add ply count
        headers["PlyCount"] = str(len(self.game.moves))

        # Add beauty score as custom header
        if self.beauty_score is not None:
            headers["BeautyScore"] = f"{self.beauty_score:.1f}"

        # Add style
        if self.style_name:
            headers["Style"] = self.style_name

        # Add FEN headers (starting position + final position)
        start_fen, final_fen = self._compute_fen()
        headers["FEN"] = start_fen
        if final_fen and final_fen != start_fen:
            headers["FinalFEN"] = final_fen

        # Standard order: STR first, then extras alphabetically
        str_order = ["Event", "Site", "Date", "Round", "White", "Black", "Result"]
        extra_order = ["ECO", "Opening", "Annotator", "PlyCount", "FEN", "FinalFEN", "BeautyScore", "Style"]

        lines = []
        added = set()

        # STR headers
        for key in str_order:
            if key in headers:
                lines.append(f'[{key} "{headers[key]}"]')
                added.add(key)

        # Known extra headers in a nice order
        for key in extra_order:
            if key in headers and key not in added:
                lines.append(f'[{key} "{headers[key]}"]')
                added.add(key)

        # Any remaining custom headers
        for key, value in sorted(headers.items()):
            if key not in added:
                lines.append(f'[{key} "{value}"]')

        return "\n".join(lines)

    # ── FEN computation ──────────────────────────────────────────────────

    def _compute_fen(self) -> Tuple[str, str]:
        """Replay all moves and return (start_fen, final_fen).

        If the game's headers already contain a ``[FEN]`` tag (non-standard
        start), that is used as the starting position; otherwise the
        standard starting position is assumed.

        Returns:
            Tuple of (starting_FEN, final_position_FEN).  If moves cannot
            be replayed (e.g. illegal SAN), final_fen falls back to
            start_fen.
        """
        start_fen = self.game.headers.get(
            "FEN", chess.STARTING_FEN
        )
        board = chess.Board(start_fen)
        try:
            for move_entry in self.game.moves:
                board.push_san(move_entry.san)
        except (chess.IllegalMoveError, chess.InvalidMoveError, ValueError) as exc:
            logger.warning("FEN computation stopped early: %s", exc)
        return start_fen, board.fen()

    def _format_pgn_movetext(self) -> str:
        """
        Format clean movetext — one move pair per line, NAGs inline, no comments.

        Example output:
            1. e4 e5
            2. f4! exf4
            3. Nf3 g5
        """
        cfg = self.config
        lines: List[str] = []
        pending_white = ""

        for move in self.game.moves:
            # Build token: move number (if white) + SAN + NAGs
            token = ""
            if move.is_white:
                token = f"{move.move_number}. "

            token += move.san

            # Attach NAGs directly to the move (they are part of notation)
            if cfg.pgn_include_annotations and move.nags:
                for nag in move.nags:
                    token += nag

            if move.is_white:
                pending_white = token
            else:
                # Pair white + black on one line
                if pending_white:
                    lines.append(f"{pending_white} {token}")
                    pending_white = ""
                else:
                    # Black move without a preceding white (shouldn't happen, but safe)
                    lines.append(f"{move.move_number}... {token}")

        # Flush any trailing white move without a reply
        if pending_white:
            lines.append(pending_white)

        return "\n".join(lines)

    def _format_pgn_commentary(self) -> str:
        """
        Build the per-move commentary section.

        Only moves that have comments, evaluations, or clock data are listed.
        Each entry is the move reference followed by its annotation text.

        Example:
            2. f4! — The King's Gambit, heart and soul of the Romantic era.

            3... g5 — Black boldly challenges White's knight.
        """
        cfg = self.config
        entries: List[str] = []

        for move in self.game.moves:
            # Collect comment parts for this move
            parts: List[str] = []
            if cfg.pgn_include_comments and move.comment:
                parts.append(move.comment)
            if cfg.pgn_include_evaluations and move.evaluation is not None:
                eval_str = f"+{move.evaluation:.2f}" if move.evaluation >= 0 else f"{move.evaluation:.2f}"
                if "eval" not in (move.comment or "").lower() and str(move.evaluation) not in (move.comment or ""):
                    parts.append(f"eval: {eval_str}")
            if cfg.pgn_include_clock and move.clock_time:
                parts.append(f"clk {move.clock_time}")

            if not parts:
                continue

            # Move reference (e.g. "5. Bxb2!!" or "3... g5")
            nag_str = "".join(move.nags) if move.nags else ""
            if move.is_white:
                ref = f"{move.move_number}. {move.san}{nag_str}"
            else:
                ref = f"{move.move_number}... {move.san}{nag_str}"

            comment_body = " | ".join(parts) if len(parts) > 1 else parts[0]

            # Wrap long commentary with indentation for continuation lines
            max_width = cfg.pgn_line_width
            header = f"{ref} —"
            if len(header) + 1 + len(comment_body) > max_width:
                wrapped = textwrap.fill(
                    comment_body,
                    width=max_width,
                    initial_indent="  ",
                    subsequent_indent="  ",
                )
                entries.append(f"{header}\n{wrapped}")
            else:
                entries.append(f"{header} {comment_body}")

        return "\n\n".join(entries)

    def _format_pgn_game_summary(self) -> str:
        """
        Build a short game summary comment.

        Includes opening info, annotation count, beauty score, and key moments.
        """
        lines: List[str] = []

        # Opening
        if self.game.opening_name:
            eco_prefix = f"{self.game.eco}: " if self.game.eco else ""
            lines.append(f"Opening: {eco_prefix}{self.game.opening_name}")

        # Result description
        result_desc = self._describe_result()
        if result_desc:
            lines.append(f"Result: {self.game.result} — {result_desc}")

        # Key moments: brilliant moves and blunders
        brilliancies = []
        blunders = []
        for m in self.game.moves:
            ref = f"{m.move_number}{'.' if m.is_white else '...'}{m.san}"
            if "!!" in (m.nags or []):
                brilliancies.append(ref)
            if "??" in (m.nags or []):
                blunders.append(ref)

        if brilliancies:
            lines.append(f"Brilliancies: {', '.join(brilliancies)}")
        if blunders:
            lines.append(f"Blunders: {', '.join(blunders)}")

        # Stats
        annotation_count = sum(1 for m in self.game.moves if m.comment or m.nags)
        lines.append(f"Annotated moves: {annotation_count}/{len(self.game.moves)}")

        if self.beauty_score is not None:
            lines.append(f"Beauty score: {self.beauty_score:.1f}")
        if self.style_name:
            lines.append(f"Style: {self.style_name.title()}")

        if not lines:
            return ""

        return "\n".join(lines)

    # =========================================================================
    # PGN STRICT EXPORT (standard-compliant)
    # =========================================================================

    def export_pgn_strict(self) -> str:
        """
        Export as standard-compliant PGN with inline {comments} next to moves.

        This format is machine-parseable by Lichess, ChessBase, SCID, and all
        PGN-compliant software. Comments are embedded directly in the movetext
        using the PGN standard { } annotation syntax.

        Returns:
            Complete PGN string conforming to the PGN specification.
        """
        parts = []

        # Headers
        parts.append(self._format_pgn_headers())
        parts.append("")  # Blank line between headers and movetext

        # Movetext with inline annotations
        parts.append(self._format_pgn_strict_movetext())

        parts.append("")  # Trailing newline
        return "\n".join(parts)

    def _format_pgn_strict_movetext(self) -> str:
        """
        Format movetext with inline {comments} per the PGN specification.

        Each move is on its own line. Comments follow the move on the same line
        (or wrapped below). The result termination marker ends the movetext.

        Example:
            1. e4 e5
            2. f4 {The King's Gambit!} exf4
            3. Nf3 g5 {Black holds onto the pawn boldly.}
        """
        cfg = self.config
        lines: List[str] = []
        pending_white = ""
        pending_white_comment = ""

        for move in self.game.moves:
            # Build the SAN token with NAGs
            token = move.san
            if cfg.pgn_include_annotations and move.nags:
                for nag in move.nags:
                    token += nag

            # Build inline comment
            comment = self._build_strict_comment(move)

            if move.is_white:
                # Flush any previous pending pair
                # (shouldn't happen since we flush on black, but safety)
                pending_white = f"{move.move_number}. {token}"
                pending_white_comment = comment
            else:
                # Build the full line: white + white_comment + black + black_comment
                line_parts: List[str] = []

                if pending_white:
                    line_parts.append(pending_white)
                    if pending_white_comment:
                        line_parts.append(pending_white_comment)
                    line_parts.append(token)
                else:
                    line_parts.append(f"{move.move_number}... {token}")

                if comment:
                    line_parts.append(comment)

                full_line = " ".join(line_parts)

                # Wrap if line is too long
                if len(full_line) > cfg.pgn_line_width:
                    lines.append(self._wrap_strict_line(full_line, cfg.pgn_line_width))
                else:
                    lines.append(full_line)

                pending_white = ""
                pending_white_comment = ""

        # Flush trailing white move
        if pending_white:
            full_line = pending_white
            if pending_white_comment:
                full_line += " " + pending_white_comment
            lines.append(full_line)

        # Result termination
        lines.append(self.game.result)

        return "\n".join(lines)

    def _build_strict_comment(self, move) -> str:
        """Build a PGN-standard {comment} string for a single move."""
        cfg = self.config
        parts: List[str] = []

        if cfg.pgn_include_comments and move.comment:
            parts.append(move.comment)
        if cfg.pgn_include_evaluations and move.evaluation is not None:
            eval_str = f"+{move.evaluation:.2f}" if move.evaluation >= 0 else f"{move.evaluation:.2f}"
            if "eval" not in (move.comment or "").lower() and str(move.evaluation) not in (move.comment or ""):
                parts.append(f"eval: {eval_str}")
        if cfg.pgn_include_clock and move.clock_time:
            parts.append(f"[%clk {move.clock_time}]")

        if not parts:
            return ""

        body = " | ".join(parts) if len(parts) > 1 else parts[0]
        return "{" + body + "}"

    @staticmethod
    def _wrap_strict_line(line: str, width: int) -> str:
        """Wrap a long PGN strict line, keeping {comments} intact."""
        if len(line) <= width:
            return line
        return textwrap.fill(
            line,
            width=width,
            subsequent_indent="  ",
            break_on_hyphens=False,
        )

    # =========================================================================
    # JSON EXPORT
    # =========================================================================

    def export_json(self) -> str:
        """
        Export as richly structured JSON with all available metadata.

        Returns:
            JSON string with metadata, moves, annotations, and game analysis.
        """
        game_data = {
            "metadata": self._build_json_metadata(),
            "opening": self._build_json_opening(),
            "moves": self._build_json_moves(),
            "summary": self._build_json_summary(),
        }

        if self.config.json_include_raw_pgn:
            game_data["raw_pgn"] = self.game.raw_pgn

        indent = 2 if self.config.json_pretty else None
        return json.dumps(game_data, indent=indent, ensure_ascii=False)

    def _build_json_metadata(self) -> Dict[str, Any]:
        """Build metadata section for JSON export."""
        meta = {
            "event": self.game.event,
            "site": self.game.site,
            "date": self.game.date,
            "round": self.game.headers.get("Round", "?"),
            "white": self.game.white,
            "black": self.game.black,
            "result": self.game.result,
            "result_description": self._describe_result(),
            "ply_count": len(self.game.moves),
            "move_count": self.game.move_count,
            "annotator": "Caissa Chess Engine",
            "generated_at": datetime.now().isoformat(),
        }

        if self.beauty_score is not None:
            meta["beauty_score"] = round(self.beauty_score, 2)
        if self.style_name:
            meta["style"] = self.style_name

        # Include any extra headers
        extra_headers = {}
        for key, value in self.game.headers.items():
            if key not in ("Event", "Site", "Date", "Round", "White", "Black", "Result"):
                extra_headers[key.lower()] = value
        if extra_headers:
            meta["extra_headers"] = extra_headers

        return meta

    def _build_json_opening(self) -> Dict[str, Any]:
        """Build opening section for JSON export."""
        return {
            "eco": self.game.eco or None,
            "name": self.game.opening_name or None,
            "variation": self.game.opening_variation or None,
            "detected": bool(self.game.eco),
        }

    def _build_json_moves(self) -> List[Dict[str, Any]]:
        """Build structured move list for JSON export."""
        moves_data = []

        for move in self.game.moves:
            move_entry: Dict[str, Any] = {
                "ply": (move.move_number - 1) * 2 + (0 if move.is_white else 1) + 1,
                "move_number": move.move_number,
                "color": "white" if move.is_white else "black",
                "san": move.san,
            }

            # Annotations
            if move.nags:
                move_entry["nags"] = move.nags
                # Add human-readable annotation
                nag_descriptions = []
                for nag in move.nags:
                    if nag in NAG_SYMBOL_MAP:
                        nag_descriptions.append(NAG_SYMBOL_MAP[nag])
                if nag_descriptions:
                    move_entry["annotation_text"] = ", ".join(nag_descriptions)

            # Comment
            if move.comment:
                move_entry["comment"] = move.comment

            # Evaluation
            if move.evaluation is not None:
                move_entry["evaluation"] = round(move.evaluation, 2)

            # Clock
            if move.clock_time:
                move_entry["clock"] = move.clock_time

            moves_data.append(move_entry)

        return moves_data

    def _build_json_summary(self) -> Dict[str, Any]:
        """Build game summary section for JSON export."""
        annotated_count = sum(1 for m in self.game.moves if m.comment or m.nags)
        brilliant_moves = [m for m in self.game.moves if "!!" in (m.nags or [])]
        blunders = [m for m in self.game.moves if "??" in (m.nags or [])]

        summary: Dict[str, Any] = {
            "total_moves": self.game.move_count,
            "total_plies": len(self.game.moves),
            "annotations_count": annotated_count,
            "has_annotations": self.game.has_annotations,
        }

        if brilliant_moves:
            summary["brilliant_moves"] = [
                f"{m.move_number}{'.' if m.is_white else '...'}{m.san}"
                for m in brilliant_moves
            ]
        if blunders:
            summary["blunders"] = [
                f"{m.move_number}{'.' if m.is_white else '...'}{m.san}"
                for m in blunders
            ]

        # Evaluation trend (if evaluations available)
        evals = [m.evaluation for m in self.game.moves if m.evaluation is not None]
        if evals:
            summary["evaluation_range"] = {
                "min": round(min(evals), 2),
                "max": round(max(evals), 2),
                "final": round(evals[-1], 2),
            }

        if self.beauty_score is not None:
            summary["beauty_score"] = round(self.beauty_score, 2)

        return summary

    # =========================================================================
    # MARKDOWN EXPORT
    # =========================================================================

    def export_markdown(self) -> str:
        """
        Export as richly formatted Markdown with annotations inline.

        Returns:
            Markdown string with game info, annotated moves, and summary.
        """
        md = []

        # Title
        md.append(f"# {self.game.event}")
        md.append("")

        # Game info
        md.append(self._md_game_info_table())
        md.append("")

        # Opening info
        if self.game.eco or self.game.opening_name:
            md.append("## Opening")
            md.append("")
            opening_str = ""
            if self.game.eco:
                opening_str += f"**{self.game.eco}**"
            if self.game.opening_name:
                opening_str += f" — {self.game.opening_name}"
            if self.game.opening_variation:
                opening_str += f" ({self.game.opening_variation})"
            md.append(opening_str)
            md.append("")

        # Moves
        md.append("## Game")
        md.append("")
        md.append(self._md_annotated_moves())
        md.append("")

        # Result
        md.append(f"**Result: {self.game.result}** {self._describe_result()}")
        md.append("")

        # Summary
        if self.config.md_include_game_summary:
            md.append(self._md_game_summary())

        return "\n".join(md)

    def _md_game_info_table(self) -> str:
        """Build Markdown game info table."""
        rows = [
            "| Field | Value |",
            "|:------|:------|",
            f"| **White** | {self.game.white} |",
            f"| **Black** | {self.game.black} |",
            f"| **Date** | {self.game.date} |",
            f"| **Result** | {self.game.result} |",
        ]
        if self.game.eco:
            rows.append(f"| **Opening** | {self.game.eco}: {self.game.opening_name} |")
        if self.beauty_score is not None:
            rows.append(f"| **Beauty Score** | {self.beauty_score:.1f} |")
        if self.style_name:
            rows.append(f"| **Style** | {self.style_name.title()} |")
        rows.append(f"| **Moves** | {self.game.move_count} |")
        return "\n".join(rows)

    def _md_annotated_moves(self) -> str:
        """Format moves with inline annotations for Markdown."""
        lines = []

        for move in self.game.moves:
            if move.is_white:
                # Start a new move pair
                nag_str = "".join(move.nags) if move.nags else ""
                line = f"**{move.move_number}.** {move.san}{nag_str}"
            else:
                nag_str = "".join(move.nags) if move.nags else ""
                # Append black's move to the current line
                if lines:
                    lines[-1] += f" {move.san}{nag_str}"
                else:
                    line = f"**{move.move_number}...** {move.san}{nag_str}"
                    lines.append(line)
                    line = ""

                # Add combined comment after the move pair
                white_comment = ""
                if move.move_number <= len(self.game.moves):
                    # Find white's move for this number
                    for wm in self.game.moves:
                        if wm.move_number == move.move_number and wm.is_white and wm.comment:
                            white_comment = wm.comment
                            break
                if white_comment:
                    lines.append(f"> {white_comment}")
                if move.comment:
                    lines.append(f"> {move.comment}")
                if move.evaluation is not None:
                    eval_str = f"+{move.evaluation:.2f}" if move.evaluation >= 0 else f"{move.evaluation:.2f}"
                    lines.append(f"> *Eval: {eval_str}*")
                lines.append("")  # Blank line between move pairs
                continue

            if move.is_white:
                lines.append(line)
                # If white has a comment and there's no black move following, show it
                if move.comment and (move == self.game.moves[-1]):
                    lines.append(f"> {move.comment}")

        return "\n".join(lines)

    def _md_game_summary(self) -> str:
        """Build game summary section for Markdown."""
        lines = ["## Summary", ""]

        annotated = sum(1 for m in self.game.moves if m.comment or m.nags)
        brilliant = [m for m in self.game.moves if "!!" in (m.nags or [])]
        blunders = [m for m in self.game.moves if "??" in (m.nags or [])]

        lines.append(f"- **Total moves:** {self.game.move_count}")
        lines.append(f"- **Annotated moves:** {annotated}")

        if brilliant:
            moves_str = ", ".join(
                f"{m.move_number}{'.' if m.is_white else '...'}{m.san}"
                for m in brilliant
            )
            lines.append(f"- **Brilliant moves (!!): ** {moves_str}")

        if blunders:
            moves_str = ", ".join(
                f"{m.move_number}{'.' if m.is_white else '...'}{m.san}"
                for m in blunders
            )
            lines.append(f"- **Blunders (??): ** {moves_str}")

        if self.beauty_score is not None:
            lines.append(f"- **Beauty score:** {self.beauty_score:.1f}")

        lines.append("")
        return "\n".join(lines)

    # =========================================================================
    # HTML EXPORT
    # =========================================================================

    def export_html(self) -> str:
        """
        Export as a polished, modern HTML page with annotations.

        Features:
            - Two-column move table (White | Black) with inline annotations
            - Full comments (not truncated) displayed below each move pair
            - Dark/light theme with automatic OS-preference detection + toggle
            - Phase markers (Opening / Middlegame / Endgame)
            - Rich summary with tactical statistics
            - Print-friendly stylesheet
            - Responsive layout

        Returns:
            Complete HTML document string.
        """
        parts = []

        if self.config.html_include_styles:
            parts.append(self._html_head())

        parts.append(self._html_body())

        if self.config.html_include_styles:
            parts.append(self._html_footer_script())
            parts.append("</body></html>")

        return "\n".join(parts)

    # -- CSS ------------------------------------------------------------------

    def _html_head(self) -> str:
        """Generate HTML head with modern CSS (supports light + dark via class toggle)."""
        title = html_lib.escape(self.game.event)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="description" content="Chess game: {title}">
<title>{title}</title>
<style>
/* ── Reset & Base ──────────────────────────────────── */
*, *::before, *::after {{ margin:0; padding:0; box-sizing:border-box; }}

:root {{
  --bg:        #faf9f6;
  --fg:        #23272f;
  --fg-muted:  #6b7280;
  --accent:    #b58863;
  --accent2:   #f0d9b5;
  --card-bg:   #f3efe8;
  --border:    #d5cec3;
  --nag:       #c0392b;
  --eval:      #2d7a4f;
  --brilliant: #f59e0b;
  --blunder:   #dc2626;
  --good:      #16a34a;
  --interesting:#6366f1;
  --shadow:    0 1px 3px rgba(0,0,0,.08);
  --radius:    8px;
}}

html.dark {{
  --bg:        #1a1a2e;
  --fg:        #e2e8f0;
  --fg-muted:  #94a3b8;
  --accent:    #e07b39;
  --accent2:   #3b2f20;
  --card-bg:   #16213e;
  --border:    #334155;
  --nag:       #f87171;
  --eval:      #4ade80;
  --brilliant: #fbbf24;
  --blunder:   #f87171;
  --good:      #4ade80;
  --interesting:#818cf8;
  --shadow:    0 1px 4px rgba(0,0,0,.35);
}}

body {{
  font-family: 'Georgia', 'Times New Roman', serif;
  max-width: 880px; margin: 0 auto; padding: 32px 20px 60px;
  background: var(--bg); color: var(--fg);
  line-height: 1.65; transition: background .25s, color .25s;
}}

a {{ color: var(--accent); }}

/* ── Header ────────────────────────────────────────── */
.header {{
  display: flex; justify-content: space-between; align-items: flex-start;
  border-bottom: 3px solid var(--accent); padding-bottom: 12px; margin-bottom: 6px;
}}
.header h1 {{ font-size: 1.75em; line-height: 1.25; }}
.theme-toggle {{
  background: var(--card-bg); border: 1px solid var(--border);
  border-radius: 20px; padding: 5px 14px; cursor: pointer;
  font-size: .85em; color: var(--fg); transition: all .2s;
  white-space: nowrap;
}}
.theme-toggle:hover {{ background: var(--accent); color: #fff; }}
.subtitle {{ color: var(--fg-muted); font-style: italic; margin-bottom: 22px; font-size: .95em; }}

/* ── Game Info Card ────────────────────────────────── */
.game-info {{
  background: var(--card-bg); padding: 18px 24px; border-radius: var(--radius);
  margin: 0 0 28px; border-left: 4px solid var(--accent); box-shadow: var(--shadow);
  display: grid; grid-template-columns: 1fr 1fr; gap: 4px 24px;
}}
.game-info p {{ margin: 3px 0; font-size: .95em; }}
.game-info strong {{ color: var(--fg-muted); font-weight: 600; }}
.game-info .span-full {{ grid-column: 1 / -1; }}
.opening-badge {{
  display: inline-block; background: var(--accent); color: #fff;
  padding: 2px 12px; border-radius: 14px; font-size: .82em;
  font-weight: 600; letter-spacing: .3px;
}}
.beauty-badge {{
  display: inline-block; background: var(--brilliant); color: #1a1a1a;
  padding: 2px 12px; border-radius: 14px; font-size: .82em; font-weight: 700;
}}

/* ── Phase Marker ──────────────────────────────────── */
.phase-marker {{
  display: flex; align-items: center; gap: 10px;
  margin: 18px 0 8px; font-size: .8em; text-transform: uppercase;
  letter-spacing: 1.2px; font-weight: 700; color: var(--fg-muted);
}}
.phase-marker::after {{
  content: ''; flex: 1; height: 1px; background: var(--border);
}}

/* ── Move Table ────────────────────────────────────── */
.move-table {{
  width: 100%; border-collapse: separate; border-spacing: 0;
  margin: 12px 0 28px; font-size: 1.02em;
}}
.move-table th {{
  text-align: left; font-size: .72em; text-transform: uppercase;
  letter-spacing: 1px; color: var(--fg-muted); padding: 6px 10px;
  border-bottom: 2px solid var(--border);
}}
.move-table th:first-child {{ width: 48px; text-align: center; }}
.move-table td {{
  padding: 5px 10px; vertical-align: top;
  border-bottom: 1px solid color-mix(in srgb, var(--border) 50%, transparent);
}}
.move-table td:first-child {{
  text-align: center; color: var(--fg-muted); font-weight: 700; font-size: .92em;
}}
.move-table tr:hover td {{ background: var(--card-bg); }}

.san {{ font-weight: 600; letter-spacing: .2px; }}
.nag {{ font-weight: 700; margin-left: 2px; }}
.nag-brilliant {{ color: var(--brilliant); }}
.nag-blunder  {{ color: var(--blunder); }}
.nag-good     {{ color: var(--good); }}
.nag-dubious  {{ color: var(--nag); }}
.nag-interest {{ color: var(--interesting); }}

.eval {{
  display: inline-block; font-size: .78em; font-weight: 700;
  color: var(--eval); margin-left: 5px; opacity: .85;
}}

/* ── Comments ──────────────────────────────────────── */
.comment-row td {{
  padding: 2px 10px 10px; border-bottom: 1px solid var(--border);
}}
.comment-cell {{
  font-style: italic; font-size: .88em; color: var(--fg-muted);
  line-height: 1.55; padding: 6px 14px;
  background: var(--card-bg); border-radius: var(--radius);
  border-left: 3px solid var(--accent2);
}}
.comment-cell .comment-badge {{
  font-style: normal; font-weight: 700; font-size: .75em;
  text-transform: uppercase; letter-spacing: .5px;
  color: var(--accent); margin-right: 6px;
}}

/* ── Inline moves (fallback mode) ──────────────────── */
.moves-inline {{
  line-height: 2.1; margin: 16px 0 28px; font-size: 1.02em;
}}
.moves-inline .move-num {{ color: var(--fg-muted); font-weight: 700; margin-right: 2px; }}
.moves-inline .san:hover {{ background: var(--card-bg); border-radius: 3px; }}
.moves-inline .comment-inline {{
  color: var(--fg-muted); font-style: italic; font-size: .88em;
  padding: 1px 6px; background: var(--card-bg); border-radius: 3px;
}}

/* ── Result Banner ─────────────────────────────────── */
.result-banner {{
  text-align: center; font-size: 1.5em; font-weight: 700;
  padding: 14px 0 6px; margin: 8px 0;
  border-top: 2px solid var(--border); border-bottom: 2px solid var(--border);
  letter-spacing: 1px;
}}

/* ── Summary Card ──────────────────────────────────── */
.summary {{
  background: var(--card-bg); padding: 20px 24px; border-radius: var(--radius);
  margin-top: 24px; box-shadow: var(--shadow);
}}
.summary h3 {{
  font-size: 1.05em; margin-bottom: 12px;
  border-bottom: 1px solid var(--border); padding-bottom: 6px;
}}
.stat-grid {{
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px 20px;
}}
.stat-grid li {{
  list-style: none; font-size: .92em; padding: 4px 0;
}}
.stat-grid li strong {{ display: inline-block; min-width: 110px; }}
.highlight-list {{
  margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--border);
}}
.highlight-list li {{
  list-style: none; padding: 3px 0; font-size: .92em;
}}
.badge {{
  display: inline-block; padding: 1px 8px; border-radius: 10px;
  font-size: .78em; font-weight: 700; margin-right: 4px;
}}
.badge-brilliant {{ background: var(--brilliant); color: #1a1a1a; }}
.badge-blunder   {{ background: var(--blunder);   color: #fff; }}
.badge-good      {{ background: var(--good);      color: #fff; }}

/* ── Footer ────────────────────────────────────────── */
.page-footer {{
  margin-top: 36px; padding-top: 14px; border-top: 1px solid var(--border);
  font-size: .78em; color: var(--fg-muted); text-align: center;
}}

/* ── Print ─────────────────────────────────────────── */
@media print {{
  body {{ max-width: 100%; padding: 10px; }}
  .theme-toggle {{ display: none; }}
  .move-table tr:hover td {{ background: transparent; }}
}}

/* ── Responsive ────────────────────────────────────── */
@media (max-width: 600px) {{
  .game-info {{ grid-template-columns: 1fr; }}
  .stat-grid {{ grid-template-columns: 1fr; }}
  .header {{ flex-direction: column; gap: 10px; }}
}}
</style>
</head>
<body>"""

    # -- Body -----------------------------------------------------------------

    def _html_body(self) -> str:
        """Generate the full HTML body content."""
        parts = []
        e = html_lib.escape

        # Header + theme toggle
        parts.append('<div class="header">')
        parts.append(f'  <h1>{e(self.game.event)}</h1>')
        parts.append('  <button class="theme-toggle" onclick="toggleTheme()" '
                      'aria-label="Toggle dark mode">🌓 Theme</button>')
        parts.append('</div>')
        parts.append(f'<p class="subtitle">Generated by Caissa Chess Engine</p>')

        # Game info card
        parts.append(self._html_game_info())

        # Moves (table or inline)
        if self.config.html_move_layout == "table":
            parts.append(self._html_move_table())
        else:
            parts.append(self._html_moves_inline())

        # Result banner
        parts.append(f'<div class="result-banner">{e(self.game.result)}</div>')

        # Summary
        parts.append(self._html_summary())

        # Footer
        parts.append('<div class="page-footer">')
        parts.append(f'  Caissa Chess Engine &middot; {e(self.game.date)}')
        parts.append('</div>')

        return "\n".join(parts)

    def _html_game_info(self) -> str:
        """Render the game-info metadata card."""
        e = html_lib.escape
        parts = ['<div class="game-info">']
        parts.append(f"<p><strong>White</strong> {e(self.game.white)}</p>")
        parts.append(f"<p><strong>Black</strong> {e(self.game.black)}</p>")
        parts.append(f"<p><strong>Date</strong> {e(self.game.date)}</p>")
        parts.append(f"<p><strong>Result</strong> {e(self.game.result)} &mdash; {e(self._describe_result())}</p>")
        if self.game.eco:
            parts.append(
                f'<p class="span-full"><span class="opening-badge">{e(self.game.eco)}</span> '
                f'{e(self.game.opening_name)}</p>'
            )
        if self.beauty_score is not None:
            parts.append(
                f'<p class="span-full"><span class="beauty-badge">'
                f'&#9733; {self.beauty_score:.1f}</span> Beauty Score</p>'
            )
        if self.style_name:
            parts.append(f'<p><strong>Style</strong> {e(self.style_name.title())}</p>')
        parts.append("</div>")
        return "\n".join(parts)

    # -- Move table -----------------------------------------------------------

    def _estimate_phase(self, ply_index: int) -> str:
        """Rough game-phase estimate based on ply index and total plies."""
        total = len(self.game.moves)
        if total == 0:
            return "opening"
        ratio = ply_index / total
        if ratio < 0.25:
            return "opening"
        elif ratio < 0.70:
            return "middlegame"
        else:
            return "endgame"

    def _nag_css_class(self, nags: List[str]) -> str:
        """Return the most significant NAG CSS class."""
        nag_str = "".join(nags)
        if "!!" in nag_str:
            return "nag-brilliant"
        if "??" in nag_str:
            return "nag-blunder"
        if "!" in nag_str:
            return "nag-good"
        if "?!" in nag_str:
            return "nag-interest"
        if "?" in nag_str:
            return "nag-dubious"
        return ""

    def _render_move_cell(self, move, e) -> str:
        """Render a single move's SAN + NAG + eval as an HTML fragment."""
        if move is None:
            return ""
        frag = f'<span class="san">{e(move.san)}</span>'
        if move.nags:
            cls = self._nag_css_class(move.nags)
            frag += f'<span class="nag {cls}">{"".join(move.nags)}</span>'
        if move.evaluation is not None:
            ev = f"+{move.evaluation:.1f}" if move.evaluation >= 0 else f"{move.evaluation:.1f}"
            frag += f'<span class="eval">[{ev}]</span>'
        return frag

    def _render_comment_block(self, move, label: str, e) -> str:
        """Render a comment block for a move (if it has a comment)."""
        if not move or not move.comment:
            return ""
        text = move.comment
        if self.config.html_comment_mode == "truncate" and len(text) > 200:
            text = text[:197] + "..."
        return (
            f'<span class="comment-badge">{e(label)}</span>'
            f'{e(text)}'
        )

    def _html_move_table(self) -> str:
        """Render moves as a two-column table (White | Black) with comment rows."""
        e = html_lib.escape
        parts = []

        # Group moves into pairs (white, black)
        pairs = []
        i = 0
        moves = self.game.moves
        while i < len(moves):
            white_move = moves[i] if i < len(moves) and moves[i].is_white else None
            if white_move is None:
                # Black move without a preceding white move (rare)
                pairs.append((None, moves[i]))
                i += 1
                continue
            black_move = moves[i + 1] if (i + 1) < len(moves) and not moves[i + 1].is_white else None
            pairs.append((white_move, black_move))
            i += 2 if black_move else 1

        # Track phase for markers
        last_phase = None

        parts.append('<table class="move-table">')
        parts.append('<thead><tr><th>#</th><th>White</th><th>Black</th></tr></thead>')
        parts.append('<tbody>')

        for pair_idx, (w, b) in enumerate(pairs):
            ply_idx = pair_idx * 2
            move_num = w.move_number if w else (b.move_number if b else pair_idx + 1)

            # Phase marker
            if self.config.html_show_phase_markers:
                phase = self._estimate_phase(ply_idx)
                if phase != last_phase:
                    label = {"opening": "♟ Opening", "middlegame": "⚔ Middlegame", "endgame": "♚ Endgame"}.get(phase, phase)
                    parts.append(
                        f'<tr><td colspan="3">'
                        f'<div class="phase-marker">{label}</div>'
                        f'</td></tr>'
                    )
                    last_phase = phase

            # Move row
            parts.append(f'<tr>')
            parts.append(f'<td>{move_num}.</td>')
            parts.append(f'<td>{self._render_move_cell(w, e)}</td>')
            parts.append(f'<td>{self._render_move_cell(b, e)}</td>')
            parts.append(f'</tr>')

            # Comment row (only if at least one side has a comment)
            w_comment = self._render_comment_block(w, f"{move_num}. {w.san}" if w else "", e)
            b_comment = self._render_comment_block(b, f"{move_num}...{b.san}" if b else "", e)
            if w_comment or b_comment:
                parts.append('<tr class="comment-row">')
                parts.append(f'<td></td>')
                parts.append(f'<td colspan="2"><div class="comment-cell">')
                if w_comment:
                    parts.append(w_comment)
                if w_comment and b_comment:
                    parts.append('<br>')
                if b_comment:
                    parts.append(b_comment)
                parts.append('</div></td></tr>')

        parts.append('</tbody></table>')
        return "\n".join(parts)

    # -- Inline moves (legacy / fallback) -------------------------------------

    def _html_moves_inline(self) -> str:
        """Render moves in the flowing inline format (like the old exporter)."""
        e = html_lib.escape
        parts = ['<div class="moves-inline">']
        for move in self.game.moves:
            if move.is_white:
                parts.append(f'<span class="move-num">{move.move_number}.</span>')
            parts.append(f'<span class="san">{e(move.san)}</span>')
            if move.nags:
                cls = self._nag_css_class(move.nags)
                parts.append(f'<span class="nag {cls}">{"".join(move.nags)}</span>')
            if move.comment:
                text = move.comment
                if self.config.html_comment_mode == "truncate" and len(text) > 120:
                    text = text[:117] + "..."
                parts.append(f'<span class="comment-inline">{e(text)}</span>')
            if move.evaluation is not None:
                ev = f"+{move.evaluation:.1f}" if move.evaluation >= 0 else f"{move.evaluation:.1f}"
                parts.append(f'<span class="eval">[{ev}]</span>')
            parts.append(" ")
        parts.append("</div>")
        return "\n".join(parts)

    # -- Summary --------------------------------------------------------------

    def _html_summary(self) -> str:
        """Generate a rich HTML summary card with tactical stats."""
        e = html_lib.escape
        moves = self.game.moves
        annotated = sum(1 for m in moves if m.comment or m.nags)
        brilliant = [m for m in moves if "!!" in (m.nags or [])]
        good_moves = [m for m in moves if "!" in (m.nags or []) and "!!" not in (m.nags or [])]
        interesting = [m for m in moves if "!?" in (m.nags or [])]
        dubious = [m for m in moves if "?!" in (m.nags or [])]
        mistakes = [m for m in moves if "?" in (m.nags or []) and "??" not in (m.nags or []) and "!?" not in (m.nags or []) and "?!" not in (m.nags or [])]
        blunders = [m for m in moves if "??" in (m.nags or [])]
        checks = [m for m in moves if m.san.endswith("+") or m.san.endswith("#")]
        captures = [m for m in moves if "x" in m.san]

        parts = ['<div class="summary">', '<h3>Game Summary</h3>']

        # Stats grid
        parts.append('<ul class="stat-grid">')
        parts.append(f'<li><strong>Total moves</strong> {self.game.move_count}</li>')
        parts.append(f'<li><strong>Annotated</strong> {annotated} / {len(moves)} plies</li>')
        parts.append(f'<li><strong>Checks</strong> {len(checks)}</li>')
        parts.append(f'<li><strong>Captures</strong> {len(captures)}</li>')
        if self.beauty_score is not None:
            parts.append(f'<li><strong>Beauty score</strong> {self.beauty_score:.1f} / 100</li>')
        if self.style_name:
            parts.append(f'<li><strong>Style</strong> {e(self.style_name.title())}</li>')
        parts.append('</ul>')

        # Highlight list
        highlight_items = []

        def _move_label(m):
            return f"{m.move_number}{'.' if m.is_white else '...'}{m.san}"

        if brilliant:
            for m in brilliant:
                highlight_items.append(
                    f'<li><span class="badge badge-brilliant">!!</span> '
                    f'{e(_move_label(m))}'
                    + (f' &mdash; <em>{e(m.comment)}</em>' if m.comment else '')
                    + '</li>'
                )
        if good_moves:
            for m in good_moves:
                highlight_items.append(
                    f'<li><span class="badge badge-good">!</span> '
                    f'{e(_move_label(m))}'
                    + (f' &mdash; <em>{e(m.comment)}</em>' if m.comment else '')
                    + '</li>'
                )
        if blunders:
            for m in blunders:
                highlight_items.append(
                    f'<li><span class="badge badge-blunder">??</span> '
                    f'{e(_move_label(m))}'
                    + (f' &mdash; <em>{e(m.comment)}</em>' if m.comment else '')
                    + '</li>'
                )
        if mistakes:
            for m in mistakes:
                highlight_items.append(
                    f'<li><span class="badge badge-blunder">?</span> '
                    f'{e(_move_label(m))}'
                    + (f' &mdash; <em>{e(m.comment)}</em>' if m.comment else '')
                    + '</li>'
                )

        if highlight_items:
            parts.append('<ul class="highlight-list">')
            parts.extend(highlight_items)
            parts.append('</ul>')

        parts.append('</div>')
        return "\n".join(parts)

    # -- Theme toggle JS ------------------------------------------------------

    def _html_footer_script(self) -> str:
        """Minimal JS for dark/light toggle with localStorage persistence."""
        # Determine initial theme from config
        initial = "dark" if self.config.html_dark_mode else ""
        return f"""
<script>
(function() {{
  var saved = localStorage.getItem('caissa-theme');
  if (saved === 'dark' || (!saved && {'true' if self.config.html_dark_mode else 'false'})) {{
    document.documentElement.classList.add('dark');
  }}
  if (!saved && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {{
    document.documentElement.classList.add('dark');
  }}
}})();
function toggleTheme() {{
  var isDark = document.documentElement.classList.toggle('dark');
  localStorage.setItem('caissa-theme', isDark ? 'dark' : 'light');
}}
</script>"""

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _describe_result(self) -> str:
        """Human-readable result description."""
        descriptions = {
            "1-0": "White wins",
            "0-1": "Black wins",
            "1/2-1/2": "Draw",
            "*": "Game in progress",
        }
        return descriptions.get(self.game.result, "Unknown result")

    # =========================================================================
    # CONVENIENCE: EXPORT BY FORMAT NAME
    # =========================================================================

    def export(self, format_name: str) -> str:
        """
        Export in the specified format.

        Args:
            format_name: One of "pgn", "json", "markdown", "html"

        Returns:
            Formatted game string

        Raises:
            ValueError: If format_name is not recognized
        """
        format_name = format_name.lower().strip()
        logger.info("Exporting game: format=%s", format_name)

        exporters = {
            "pgn": self.export_pgn,
            "pgn_strict": self.export_pgn_strict,
            "json": self.export_json,
            "markdown": self.export_markdown,
            "md": self.export_markdown,
            "html": self.export_html,
        }

        exporter = exporters.get(format_name)
        if not exporter:
            raise ValueError(
                f"Unknown format '{format_name}'. "
                f"Supported: {', '.join(exporters.keys())}"
            )

        result = exporter()
        logger.info("Export complete: format=%s, %d chars", format_name, len(result))
        return result

    def export_all(self) -> Dict[str, str]:
        """
        Export in all formats at once.

        Returns:
            Dictionary mapping format name to exported content.
        """
        return {
            "pgn": self.export_pgn(),
            "pgn_strict": self.export_pgn_strict(),
            "json": self.export_json(),
            "markdown": self.export_markdown(),
            "html": self.export_html(),
        }
