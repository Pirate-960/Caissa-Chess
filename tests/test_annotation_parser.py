"""
Comprehensive tests for export/annotation_parser.py

Covers:
- ParsedMove and ParsedGame dataclasses
- NAG_SYMBOL_MAP, NAG_PATTERN, EVAL_PATTERNS, CLOCK_PATTERN
- parse_pgn (main entry point)
- _extract_headers, _extract_movetext, _detect_result, _parse_movetext
- _fix_move_numbers, _extract_evaluation, _extract_clock_time
- detect_opening, from_san_list
"""

from export.annotation_parser import (
    ParsedMove,
    ParsedGame,
    NAG_SYMBOL_MAP,
    NAG_PATTERN,
    CLOCK_PATTERN,
    parse_pgn,
    detect_opening,
    from_san_list,
    _extract_headers,
    _extract_movetext,
    _detect_result,
    _parse_movetext,
    _fix_move_numbers,
    _extract_evaluation,
    _extract_clock_time,
)


# =============================================================================
# DATACLASSES
# =============================================================================

class TestParsedMove:
    def test_defaults(self):
        m = ParsedMove(san="e4", move_number=1, is_white=True)
        assert m.san == "e4"
        assert m.move_number == 1
        assert m.is_white is True
        assert m.comment == ""
        assert m.nags == []
        assert m.evaluation is None
        assert m.clock_time is None

    def test_with_annotations(self):
        m = ParsedMove(
            san="Nf3", move_number=2, is_white=True,
            comment="developing", nags=["!"], evaluation=0.3
        )
        assert m.nags == ["!"]
        assert m.evaluation == 0.3


class TestParsedGame:
    def test_defaults(self):
        g = ParsedGame()
        assert g.headers == {}
        assert g.moves == []
        assert g.result == "*"
        assert g.eco == ""
        assert g.opening_name == ""
        assert g.raw_pgn == ""

    def test_properties(self):
        g = ParsedGame(headers={"White": "Tal", "Black": "Petrosian", "Event": "WCh"})
        assert g.white == "Tal"
        assert g.black == "Petrosian"
        assert g.event == "WCh"

    def test_properties_defaults(self):
        g = ParsedGame()
        assert g.white == "?"
        assert g.black == "?"
        assert g.event == "Caissa Generated Game"
        assert g.date == "????.??.??"
        assert g.site == "Caissa Chess Engine"

    def test_move_count_empty(self):
        g = ParsedGame()
        assert g.move_count == 0

    def test_move_count(self):
        g = ParsedGame(moves=[
            ParsedMove("e4", 1, True),
            ParsedMove("e5", 1, False),
            ParsedMove("Nf3", 2, True),
        ])
        assert g.move_count == 2

    def test_has_annotations_false(self):
        g = ParsedGame(moves=[
            ParsedMove("e4", 1, True),
        ])
        assert g.has_annotations is False

    def test_has_annotations_true(self):
        g = ParsedGame(moves=[
            ParsedMove("e4", 1, True, comment="Good opening"),
        ])
        assert g.has_annotations is True

    def test_san_list(self):
        g = ParsedGame(moves=[
            ParsedMove("e4", 1, True),
            ParsedMove("e5", 1, False),
        ])
        assert g.san_list == ["e4", "e5"]


# =============================================================================
# CONSTANTS
# =============================================================================

class TestConstants:
    def test_nag_symbol_map(self):
        assert NAG_SYMBOL_MAP["!!"] == "Brilliant move"
        assert NAG_SYMBOL_MAP["??"] == "Blunder"
        assert "!" in NAG_SYMBOL_MAP
        assert "?" in NAG_SYMBOL_MAP

    def test_nag_pattern(self):
        assert NAG_PATTERN.search("Nf3!!") is not None
        assert NAG_PATTERN.search("e4?") is not None
        assert NAG_PATTERN.search("e4!?") is not None

    def test_clock_pattern(self):
        match = CLOCK_PATTERN.search("[%clk 1:23:45]")
        assert match is not None
        assert match.group(1) == "1:23:45"


# =============================================================================
# EXTRACT HELPERS
# =============================================================================

class TestExtractHeaders:
    def test_basic_headers(self):
        pgn = '[Event "Test"]\n[White "Alice"]\n[Black "Bob"]\n\n1. e4 e5'
        h = _extract_headers(pgn)
        assert h["Event"] == "Test"
        assert h["White"] == "Alice"
        assert h["Black"] == "Bob"

    def test_no_headers(self):
        h = _extract_headers("1. e4 e5")
        assert h == {}


class TestExtractMovetext:
    def test_strips_headers(self):
        pgn = '[Event "Test"]\n\n1. e4 e5 2. Nf3'
        mt = _extract_movetext(pgn)
        assert "e4" in mt
        assert "[Event" not in mt

    def test_movetext_only(self):
        mt = _extract_movetext("1. e4 e5")
        assert mt == "1. e4 e5"


class TestDetectResult:
    def test_from_movetext(self):
        assert _detect_result("1. e4 e5 1-0", {}) == "1-0"
        assert _detect_result("1. e4 e5 0-1", {}) == "0-1"
        assert _detect_result("1. e4 e5 1/2-1/2", {}) == "1/2-1/2"

    def test_from_headers(self):
        assert _detect_result("1. e4 e5", {"Result": "1-0"}) == "1-0"

    def test_unknown(self):
        assert _detect_result("1. e4 e5", {}) == "*"


# =============================================================================
# EXTRACT EVALUATION / CLOCK
# =============================================================================

class TestExtractEvaluation:
    def test_bracket_format(self):
        assert _extract_evaluation("[+1.23]") == 1.23
        assert _extract_evaluation("[-0.5]") == -0.5

    def test_eval_keyword(self):
        assert _extract_evaluation("eval: +2.0") == 2.0

    def test_none_for_empty(self):
        assert _extract_evaluation("") is None
        assert _extract_evaluation("No eval here") is None


class TestExtractClockTime:
    def test_clock_format(self):
        assert _extract_clock_time("[%clk 0:45:00]") == "0:45:00"

    def test_none_for_empty(self):
        assert _extract_clock_time("") is None
        assert _extract_clock_time("No clock") is None


# =============================================================================
# PARSE MOVETEXT
# =============================================================================

class TestParseMovetext:
    def test_basic_moves(self):
        moves = _parse_movetext("1. e4 e5 2. Nf3 Nc6")
        assert len(moves) == 4
        assert moves[0].san == "e4"
        assert moves[0].is_white is True
        assert moves[1].san == "e5"
        assert moves[1].is_white is False
        assert moves[2].san == "Nf3"
        assert moves[3].san == "Nc6"

    def test_with_comments(self):
        moves = _parse_movetext("1. e4 {Good start} e5")
        assert moves[0].comment == "Good start"

    def test_with_nags(self):
        moves = _parse_movetext("1. e4!! e5?")
        assert "!!" in moves[0].nags
        assert "?" in moves[1].nags

    def test_empty(self):
        assert _parse_movetext("") == []

    def test_result_stripped(self):
        moves = _parse_movetext("1. e4 e5 1-0")
        assert len(moves) == 2


# =============================================================================
# FIX MOVE NUMBERS
# =============================================================================

class TestFixMoveNumbers:
    def test_corrects_numbering(self):
        moves = [
            ParsedMove("e4", 99, True),
            ParsedMove("e5", 99, True),
            ParsedMove("Nf3", 99, True),
        ]
        _fix_move_numbers(moves)
        assert moves[0].move_number == 1
        assert moves[0].is_white is True
        assert moves[1].move_number == 1
        assert moves[1].is_white is False
        assert moves[2].move_number == 2
        assert moves[2].is_white is True


# =============================================================================
# PARSE PGN (main entry point)
# =============================================================================

class TestParsePgn:
    def test_empty_input(self):
        g = parse_pgn("")
        assert g.moves == []
        assert g.result == "*"

    def test_none_input(self):
        g = parse_pgn(None)
        assert g.moves == []

    def test_full_pgn(self):
        pgn = (
            '[Event "Test"]\n'
            '[White "Alice"]\n'
            '[Black "Bob"]\n'
            '[Result "1-0"]\n'
            "\n"
            "1. e4 e5 2. Nf3 Nc6 1-0"
        )
        g = parse_pgn(pgn)
        assert g.white == "Alice"
        assert g.black == "Bob"
        assert g.result == "1-0"
        assert len(g.moves) == 4

    def test_preserves_raw_pgn(self):
        pgn = "1. e4 e5"
        g = parse_pgn(pgn)
        assert g.raw_pgn == pgn

    def test_comments_preserved(self):
        pgn = "1. e4 {Opening} e5"
        g = parse_pgn(pgn)
        assert g.moves[0].comment == "Opening"


# =============================================================================
# DETECT OPENING
# =============================================================================

class TestDetectOpening:
    def test_empty_moves(self):
        eco, name, var = detect_opening([])
        assert eco == ""
        assert name == ""

    def test_returns_tuple(self):
        result = detect_opening(["e4", "e5", "Nf3"])
        assert isinstance(result, tuple)
        assert len(result) == 3


# =============================================================================
# FROM SAN LIST
# =============================================================================

class TestFromSanList:
    def test_basic(self):
        g = from_san_list(["e4", "e5", "Nf3"])
        assert len(g.moves) == 3
        assert g.moves[0].san == "e4"
        assert g.moves[0].is_white is True
        assert g.moves[1].san == "e5"
        assert g.moves[1].is_white is False
        assert g.moves[2].san == "Nf3"
        assert g.moves[2].is_white is True
        assert g.moves[2].move_number == 2

    def test_with_headers(self):
        g = from_san_list(["e4"], headers={"White": "Kasparov"}, result="1-0")
        assert g.white == "Kasparov"
        assert g.result == "1-0"

    def test_empty(self):
        g = from_san_list([])
        assert g.moves == []
        assert g.result == "*"
