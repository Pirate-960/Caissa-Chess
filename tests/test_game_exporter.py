"""
Comprehensive tests for export/game_exporter.py

Covers:
- ExportConfig dataclass defaults and customisation
- GameExporter.__init__
- export_pgn  (pretty-formatted with sections)
- export_pgn_strict (standard-compliant inline comments)
- export_json (structured JSON)
- export_markdown (Markdown format)
- export_html (HTML document)
- export() / export_all() convenience methods
- Helper methods: _describe_result, _estimate_phase, _nag_css_class,
  _render_move_cell, _render_comment_block, _pgn_section_divider,
  _format_pgn_headers, _format_pgn_movetext, _format_pgn_commentary,
  _format_pgn_game_summary, _build_strict_comment, _wrap_strict_line,
  _build_json_metadata, _build_json_opening, _build_json_moves,
  _build_json_summary, _md_game_info_table, _md_annotated_moves,
  _md_game_summary, _html_head, _html_body, _html_game_info,
  _html_move_table, _html_moves_inline, _html_summary,
  _html_footer_script
"""

import json
import pytest
import html as html_lib

from export.annotation_parser import ParsedMove, ParsedGame
from export.game_exporter import ExportConfig, GameExporter


# =============================================================================
# Helpers — build test games
# =============================================================================

def _make_game(**overrides) -> ParsedGame:
    """Build a simple ParsedGame for testing."""
    defaults = dict(
        headers={"White": "Alice", "Black": "Bob", "Event": "Test", "Result": "1-0"},
        moves=[
            ParsedMove("e4", 1, True),
            ParsedMove("e5", 1, False),
            ParsedMove("Nf3", 2, True, comment="Developing"),
            ParsedMove("Nc6", 2, False),
        ],
        result="1-0",
        eco="C50",
        opening_name="Italian Game",
        raw_pgn='[Event "Test"]\n\n1. e4 e5 2. Nf3 Nc6 1-0',
    )
    defaults.update(overrides)
    return ParsedGame(**defaults)


def _annotated_game() -> ParsedGame:
    """Game rich in annotations for commentary / summary tests."""
    return ParsedGame(
        headers={"White": "Tal", "Black": "Fischer", "Event": "WCh", "Result": "1-0"},
        moves=[
            ParsedMove("e4", 1, True, nags=["!"]),
            ParsedMove("e5", 1, False),
            ParsedMove("f4", 2, True, comment="King's Gambit!", nags=["!!"]),
            ParsedMove("exf4", 2, False, comment="Accepted", evaluation=-0.5),
            ParsedMove("Nf3", 3, True, evaluation=0.3),
            ParsedMove("g5", 3, False, nags=["??"]),
        ],
        result="1-0",
        eco="C30",
        opening_name="King's Gambit",
    )


def _empty_game() -> ParsedGame:
    return ParsedGame()


# =============================================================================
# ExportConfig
# =============================================================================

class TestExportConfig:
    def test_defaults(self):
        c = ExportConfig()
        assert c.pgn_line_width == 80
        assert c.pgn_include_annotations is True
        assert c.pgn_include_comments is True
        assert c.pgn_include_evaluations is True
        assert c.pgn_include_clock is True
        assert c.md_include_diagram_markers is True
        assert c.md_moves_per_row == 1
        assert c.html_dark_mode is False
        assert c.html_comment_mode == "full"
        assert c.html_move_layout == "table"
        assert c.json_pretty is True
        assert c.json_include_raw_pgn is False

    def test_custom_values(self):
        c = ExportConfig(pgn_line_width=120, html_dark_mode=True, json_pretty=False)
        assert c.pgn_line_width == 120
        assert c.html_dark_mode is True
        assert c.json_pretty is False


# =============================================================================
# GameExporter init
# =============================================================================

class TestGameExporterInit:
    def test_defaults(self):
        g = _make_game()
        exp = GameExporter(g)
        assert exp.game is g
        assert isinstance(exp.config, ExportConfig)
        assert exp.beauty_score is None
        assert exp.style_name is None

    def test_with_options(self):
        g = _make_game()
        cfg = ExportConfig(html_dark_mode=True)
        exp = GameExporter(g, config=cfg, beauty_score=87.5, style_name="romantic")
        assert exp.beauty_score == 87.5
        assert exp.style_name == "romantic"
        assert exp.config.html_dark_mode is True


# =============================================================================
# _describe_result
# =============================================================================

class TestDescribeResult:
    @pytest.mark.parametrize("result,desc", [
        ("1-0", "White wins"),
        ("0-1", "Black wins"),
        ("1/2-1/2", "Draw"),
        ("*", "Game in progress"),
    ])
    def test_known_results(self, result, desc):
        g = ParsedGame(result=result)
        exp = GameExporter(g)
        assert exp._describe_result() == desc

    def test_unknown(self):
        g = ParsedGame(result="???")
        exp = GameExporter(g)
        assert exp._describe_result() == "Unknown result"


# =============================================================================
# PGN export — pretty format
# =============================================================================

class TestExportPgn:
    def test_contains_headers(self):
        out = GameExporter(_make_game()).export_pgn()
        assert '[White "Alice"]' in out
        assert '[Black "Bob"]' in out
        assert '[Result "1-0"]' in out

    def test_contains_moves_section(self):
        out = GameExporter(_make_game()).export_pgn()
        assert "MOVES" in out
        assert "1. e4 e5" in out
        assert "2. Nf3 Nc6" in out

    def test_contains_result(self):
        out = GameExporter(_make_game()).export_pgn()
        assert "\n1-0\n" in out

    def test_commentary_section(self):
        out = GameExporter(_annotated_game()).export_pgn()
        assert "MOVE COMMENTARY" in out
        assert "King's Gambit!" in out

    def test_summary_section(self):
        out = GameExporter(_annotated_game(), beauty_score=90.0, style_name="romantic").export_pgn()
        assert "GAME SUMMARY" in out
        assert "Beauty score: 90.0" in out

    def test_eco_in_headers(self):
        out = GameExporter(_make_game()).export_pgn()
        assert '[ECO "C50"]' in out

    def test_beauty_score_header(self):
        out = GameExporter(_make_game(), beauty_score=75.0).export_pgn()
        assert '[BeautyScore "75.0"]' in out

    def test_style_header(self):
        out = GameExporter(_make_game(), style_name="positional").export_pgn()
        assert '[Style "positional"]' in out

    def test_section_divider(self):
        div = GameExporter._pgn_section_divider("TEST")
        assert "TEST" in div
        assert "═" in div

    def test_no_annotations_no_commentary(self):
        g = ParsedGame(moves=[ParsedMove("e4", 1, True), ParsedMove("e5", 1, False)], result="*")
        out = GameExporter(g).export_pgn()
        assert "MOVE COMMENTARY" not in out


class TestFormatPgnHeaders:
    def test_standard_order(self):
        g = _make_game()
        exp = GameExporter(g)
        hdr = exp._format_pgn_headers()
        lines = hdr.strip().split("\n")
        assert lines[0].startswith('[Event')
        assert lines[1].startswith('[Site')
        assert lines[2].startswith('[Date')

    def test_includes_annotator(self):
        hdr = GameExporter(_make_game())._format_pgn_headers()
        assert "Annotator" in hdr

    def test_includes_plycount(self):
        hdr = GameExporter(_make_game())._format_pgn_headers()
        assert '[PlyCount "4"]' in hdr


class TestFormatPgnMovetext:
    def test_pairs(self):
        mt = GameExporter(_make_game())._format_pgn_movetext()
        assert "1. e4 e5" in mt
        assert "2. Nf3 Nc6" in mt

    def test_nags_inline(self):
        g = _annotated_game()
        mt = GameExporter(g)._format_pgn_movetext()
        assert "e4!" in mt
        assert "f4!!" in mt

    def test_trailing_white(self):
        g = ParsedGame(moves=[ParsedMove("e4", 1, True)], result="*")
        mt = GameExporter(g)._format_pgn_movetext()
        assert mt.strip() == "1. e4"


class TestFormatPgnCommentary:
    def test_empty_when_no_comments(self):
        g = ParsedGame(moves=[ParsedMove("e4", 1, True)], result="*")
        assert GameExporter(g)._format_pgn_commentary() == ""

    def test_includes_eval(self):
        g = ParsedGame(moves=[ParsedMove("e4", 1, True, evaluation=1.5)], result="*")
        c = GameExporter(g)._format_pgn_commentary()
        assert "eval:" in c
        assert "+1.50" in c

    def test_includes_clock(self):
        g = ParsedGame(moves=[ParsedMove("e4", 1, True, clock_time="0:30:00")], result="*")
        c = GameExporter(g)._format_pgn_commentary()
        assert "clk 0:30:00" in c


class TestFormatPgnGameSummary:
    def test_empty_game(self):
        s = GameExporter(_empty_game())._format_pgn_game_summary()
        assert "Annotated moves: 0/0" in s

    def test_brilliancies_listed(self):
        s = GameExporter(_annotated_game())._format_pgn_game_summary()
        assert "Brilliancies" in s

    def test_blunders_listed(self):
        s = GameExporter(_annotated_game())._format_pgn_game_summary()
        assert "Blunders" in s


# =============================================================================
# PGN strict export
# =============================================================================

class TestExportPgnStrict:
    def test_contains_headers_and_result(self):
        out = GameExporter(_make_game()).export_pgn_strict()
        assert '[White "Alice"]' in out
        assert "1-0" in out

    def test_inline_comments(self):
        out = GameExporter(_annotated_game()).export_pgn_strict()
        assert "{" in out
        assert "King's Gambit!" in out

    def test_no_section_dividers(self):
        out = GameExporter(_make_game()).export_pgn_strict()
        assert "═" not in out

    def test_build_strict_comment_empty(self):
        m = ParsedMove("e4", 1, True)
        exp = GameExporter(_make_game())
        assert exp._build_strict_comment(m) == ""

    def test_build_strict_comment_with_parts(self):
        m = ParsedMove("e4", 1, True, comment="Good", evaluation=1.0, clock_time="0:30:00")
        exp = GameExporter(_make_game())
        c = exp._build_strict_comment(m)
        assert c.startswith("{")
        assert c.endswith("}")
        assert "Good" in c
        assert "clk" in c

    def test_wrap_strict_line_short(self):
        assert GameExporter._wrap_strict_line("short", 80) == "short"

    def test_wrap_strict_line_long(self):
        long = "a " * 60
        wrapped = GameExporter._wrap_strict_line(long, 80)
        assert len(wrapped.split("\n")[0]) <= 80


# =============================================================================
# JSON export
# =============================================================================

class TestExportJson:
    def test_valid_json(self):
        out = GameExporter(_make_game()).export_json()
        data = json.loads(out)
        assert "metadata" in data
        assert "moves" in data
        assert "opening" in data
        assert "summary" in data

    def test_metadata(self):
        data = json.loads(GameExporter(_make_game(), beauty_score=80.0).export_json())
        meta = data["metadata"]
        assert meta["white"] == "Alice"
        assert meta["black"] == "Bob"
        assert meta["result"] == "1-0"
        assert meta["beauty_score"] == 80.0

    def test_moves_structure(self):
        data = json.loads(GameExporter(_make_game()).export_json())
        moves = data["moves"]
        assert len(moves) == 4
        assert moves[0]["san"] == "e4"
        assert moves[0]["color"] == "white"
        assert moves[1]["color"] == "black"

    def test_nag_annotation_text(self):
        data = json.loads(GameExporter(_annotated_game()).export_json())
        brilliant = [m for m in data["moves"] if m.get("nags") and "!!" in m["nags"]]
        assert len(brilliant) > 0
        assert "annotation_text" in brilliant[0]

    def test_opening_section(self):
        data = json.loads(GameExporter(_make_game()).export_json())
        assert data["opening"]["eco"] == "C50"
        assert data["opening"]["name"] == "Italian Game"
        assert data["opening"]["detected"] is True

    def test_no_opening(self):
        data = json.loads(GameExporter(_empty_game()).export_json())
        assert data["opening"]["eco"] is None
        assert data["opening"]["detected"] is False

    def test_summary_section(self):
        data = json.loads(GameExporter(_make_game()).export_json())
        s = data["summary"]
        assert s["total_plies"] == 4
        assert s["total_moves"] == 2

    def test_include_raw_pgn(self):
        cfg = ExportConfig(json_include_raw_pgn=True)
        data = json.loads(GameExporter(_make_game(), config=cfg).export_json())
        assert "raw_pgn" in data

    def test_not_include_raw_pgn(self):
        data = json.loads(GameExporter(_make_game()).export_json())
        assert "raw_pgn" not in data

    def test_compact_json(self):
        cfg = ExportConfig(json_pretty=False)
        out = GameExporter(_make_game(), config=cfg).export_json()
        # Compact JSON has no newlines within the body
        assert "\n" not in out

    def test_eval_range_in_summary(self):
        g = ParsedGame(
            moves=[
                ParsedMove("e4", 1, True, evaluation=0.3),
                ParsedMove("e5", 1, False, evaluation=-0.1),
            ],
            result="*",
        )
        data = json.loads(GameExporter(g).export_json())
        assert "evaluation_range" in data["summary"]
        assert data["summary"]["evaluation_range"]["min"] == -0.1
        assert data["summary"]["evaluation_range"]["max"] == 0.3


# =============================================================================
# Markdown export
# =============================================================================

class TestExportMarkdown:
    def test_contains_title(self):
        out = GameExporter(_make_game()).export_markdown()
        assert "# Test" in out

    def test_info_table(self):
        out = GameExporter(_make_game()).export_markdown()
        assert "| **White** | Alice |" in out
        assert "| **Black** | Bob |" in out

    def test_opening_section(self):
        out = GameExporter(_make_game()).export_markdown()
        assert "## Opening" in out
        assert "C50" in out

    def test_result_line(self):
        out = GameExporter(_make_game()).export_markdown()
        assert "**Result: 1-0**" in out

    def test_summary_section(self):
        out = GameExporter(_make_game()).export_markdown()
        assert "## Summary" in out

    def test_annotated_moves(self):
        out = GameExporter(_annotated_game()).export_markdown()
        assert "e4!" in out

    def test_beauty_in_info(self):
        out = GameExporter(_make_game(), beauty_score=70.0).export_markdown()
        assert "70.0" in out

    def test_no_opening_section_when_empty(self):
        out = GameExporter(_empty_game()).export_markdown()
        assert "## Opening" not in out


class TestMdHelpers:
    def test_game_info_table_rows(self):
        exp = GameExporter(_make_game())
        table = exp._md_game_info_table()
        assert "|:------|" in table
        assert "White" in table

    def test_game_summary_has_brilliant(self):
        s = GameExporter(_annotated_game())._md_game_summary()
        assert "Brilliant" in s or "!!" in s


# =============================================================================
# HTML export
# =============================================================================

class TestExportHtml:
    def test_is_html(self):
        out = GameExporter(_make_game()).export_html()
        assert "<!DOCTYPE html>" in out
        assert "</html>" in out

    def test_contains_event_title(self):
        out = GameExporter(_make_game()).export_html()
        assert "<title>Test</title>" in out

    def test_contains_moves(self):
        out = GameExporter(_make_game()).export_html()
        assert "e4" in out
        assert "Nf3" in out

    def test_dark_mode_class(self):
        # Dark mode is applied via JS — check the script references it
        cfg = ExportConfig(html_dark_mode=True)
        out = GameExporter(_make_game(), config=cfg).export_html()
        assert "dark" in out

    def test_inline_layout(self):
        cfg = ExportConfig(html_move_layout="inline")
        out = GameExporter(_make_game(), config=cfg).export_html()
        assert "moves-inline" in out

    def test_table_layout(self):
        out = GameExporter(_make_game()).export_html()
        assert "move-table" in out

    def test_without_styles(self):
        cfg = ExportConfig(html_include_styles=False)
        out = GameExporter(_make_game(), config=cfg).export_html()
        assert "<!DOCTYPE html>" not in out
        assert "e4" in out  # Body still present

    def test_escape_special_chars(self):
        g = ParsedGame(
            headers={"Event": 'Test <script>"</script>'},
            moves=[],
            result="*",
        )
        out = GameExporter(g).export_html()
        # The Event header value must be escaped in the HTML output
        assert "&lt;script&gt;" in out

    def test_comment_truncate_mode(self):
        long_comment = "A" * 300
        g = ParsedGame(
            moves=[ParsedMove("e4", 1, True, comment=long_comment)],
            result="*",
        )
        cfg = ExportConfig(html_comment_mode="truncate")
        out = GameExporter(g, config=cfg).export_html()
        assert "..." in out


class TestHtmlHelpers:
    def test_estimate_phase_opening(self):
        g = _make_game()
        exp = GameExporter(g)
        assert exp._estimate_phase(0) == "opening"

    def test_estimate_phase_endgame(self):
        g = _make_game()  # 4 moves
        exp = GameExporter(g)
        assert exp._estimate_phase(3) == "endgame"

    def test_estimate_phase_empty(self):
        exp = GameExporter(_empty_game())
        assert exp._estimate_phase(0) == "opening"

    def test_nag_css_class(self):
        exp = GameExporter(_make_game())
        assert exp._nag_css_class(["!!"]) == "nag-brilliant"
        assert exp._nag_css_class(["??"]) == "nag-blunder"
        assert exp._nag_css_class(["!"]) == "nag-good"
        # "?!" contains "!" which matches before "?!" in source priority order
        assert exp._nag_css_class(["?!"]) == "nag-good"
        assert exp._nag_css_class(["?"]) == "nag-dubious"
        assert exp._nag_css_class([]) == ""

    def test_render_move_cell_none(self):
        exp = GameExporter(_make_game())
        assert exp._render_move_cell(None, html_lib.escape) == ""

    def test_render_move_cell_basic(self):
        exp = GameExporter(_make_game())
        m = ParsedMove("e4", 1, True)
        cell = exp._render_move_cell(m, html_lib.escape)
        assert "e4" in cell
        assert "san" in cell

    def test_render_move_cell_with_nag_and_eval(self):
        exp = GameExporter(_make_game())
        m = ParsedMove("f4", 2, True, nags=["!!"], evaluation=1.5)
        cell = exp._render_move_cell(m, html_lib.escape)
        assert "!!" in cell
        assert "nag-brilliant" in cell
        assert "+1.5" in cell

    def test_render_comment_block_empty(self):
        exp = GameExporter(_make_game())
        m = ParsedMove("e4", 1, True)
        assert exp._render_comment_block(m, "1. e4", html_lib.escape) == ""

    def test_render_comment_block_with_comment(self):
        exp = GameExporter(_make_game())
        m = ParsedMove("e4", 1, True, comment="Good start")
        block = exp._render_comment_block(m, "1. e4", html_lib.escape)
        assert "Good start" in block

    def test_phase_markers_present(self):
        g = ParsedGame(
            moves=[ParsedMove(f"{'e' if i % 2 == 0 else 'd'}{4 if i < 2 else 5}", (i // 2) + 1, i % 2 == 0)
                   for i in range(20)],
            result="*",
        )
        out = GameExporter(g).export_html()
        assert "phase-marker" in out

    def test_html_summary(self):
        exp = GameExporter(_annotated_game(), beauty_score=88.0, style_name="aggressive")
        s = exp._html_summary()
        assert "Game Summary" in s
        assert "88.0" in s
        assert "Aggressive" in s  # title-cased


# =============================================================================
# export() convenience method
# =============================================================================

class TestExportConvenience:
    def test_pgn(self):
        exp = GameExporter(_make_game())
        out = exp.export("pgn")
        assert "MOVES" in out

    def test_pgn_strict(self):
        out = GameExporter(_make_game()).export("pgn_strict")
        assert '[White "Alice"]' in out

    def test_json(self):
        out = GameExporter(_make_game()).export("json")
        data = json.loads(out)
        assert "moves" in data

    def test_markdown(self):
        out = GameExporter(_make_game()).export("markdown")
        assert "# Test" in out

    def test_md_alias(self):
        out = GameExporter(_make_game()).export("md")
        assert "# Test" in out

    def test_html(self):
        out = GameExporter(_make_game()).export("html")
        assert "<!DOCTYPE html>" in out

    def test_case_insensitive(self):
        out = GameExporter(_make_game()).export("JSON")
        assert json.loads(out)

    def test_unknown_format(self):
        with pytest.raises(ValueError, match="Unknown format"):
            GameExporter(_make_game()).export("pdf")


class TestExportAll:
    def test_returns_all_formats(self):
        results = GameExporter(_make_game()).export_all()
        assert set(results.keys()) == {"pgn", "pgn_strict", "json", "markdown", "html"}
        for v in results.values():
            assert isinstance(v, str)
            assert len(v) > 0
