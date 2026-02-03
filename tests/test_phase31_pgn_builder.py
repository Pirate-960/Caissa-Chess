"""
tests/test_phase31_pgn_builder.py

Tests for Phase 3.1 PGN builder enhancements:
- NAG (Numeric Annotation Glyphs)
- Multi-format export (PGN, HTML, Markdown, JSON)
- Variations and advanced annotations
"""

import unittest
import json

from export.pgn_builder import (
    PGNBuilder,
    NAG,
    ExportFormat,
    CommentaryStyle,
    MoveAnnotation,
    Variation,
    GameMetadata,
    AdvancedMoveEntry,
)


class TestNAG(unittest.TestCase):
    """Tests for NAG enum."""

    def test_traditional_nags(self):
        """Traditional NAG codes should be correct."""
        self.assertEqual(NAG.GOOD_MOVE, 1)
        self.assertEqual(NAG.POOR_MOVE, 2)
        self.assertEqual(NAG.BRILLIANT_MOVE, 3)
        self.assertEqual(NAG.BLUNDER, 4)
        self.assertEqual(NAG.INTERESTING_MOVE, 5)
        self.assertEqual(NAG.DUBIOUS_MOVE, 6)

    def test_evaluation_nags(self):
        """Evaluation NAG codes should be correct."""
        self.assertEqual(NAG.DRAWISH, 10)
        self.assertEqual(NAG.WHITE_ADVANTAGE, 16)
        self.assertEqual(NAG.BLACK_ADVANTAGE, 17)
        self.assertEqual(NAG.WHITE_DECISIVE, 18)
        self.assertEqual(NAG.BLACK_DECISIVE, 19)


class TestExportFormat(unittest.TestCase):
    """Tests for ExportFormat enum."""

    def test_all_formats_defined(self):
        """All export formats should be defined."""
        formats = [
            ExportFormat.PGN,
            ExportFormat.MARKDOWN,
            ExportFormat.HTML,
            ExportFormat.JSON,
        ]
        self.assertEqual(len(formats), 4)


class TestMoveAnnotation(unittest.TestCase):
    """Tests for MoveAnnotation dataclass."""

    def test_empty_annotation(self):
        """Empty annotation should produce empty string."""
        ann = MoveAnnotation()
        result = ann.to_pgn_string()
        self.assertEqual(result, "")

    def test_nag_annotation(self):
        """NAG codes should be converted to $n format."""
        ann = MoveAnnotation(nag_codes=[NAG.BRILLIANT_MOVE])
        result = ann.to_pgn_string()
        self.assertEqual(result, "$3")

    def test_multiple_nags(self):
        """Multiple NAG codes should be included."""
        ann = MoveAnnotation(nag_codes=[NAG.GOOD_MOVE, NAG.WHITE_ADVANTAGE])
        result = ann.to_pgn_string()
        self.assertIn("$1", result)
        self.assertIn("$16", result)

    def test_comment_annotation(self):
        """Comments should be wrapped in braces."""
        ann = MoveAnnotation(comment="A strong move")
        result = ann.to_pgn_string()
        self.assertIn("{A strong move}", result)

    def test_evaluation_annotation(self):
        """Evaluation should be included in comment."""
        ann = MoveAnnotation(evaluation=150)  # +1.50
        result = ann.to_pgn_string()
        self.assertIn("eval", result)
        self.assertIn("+1.50", result)

    def test_clock_time_annotation(self):
        """Clock time should be included."""
        ann = MoveAnnotation(clock_time="0:45:30")
        result = ann.to_pgn_string()
        self.assertIn("%clk", result)
        self.assertIn("0:45:30", result)


class TestVariation(unittest.TestCase):
    """Tests for Variation dataclass."""

    def test_empty_variation(self):
        """Empty variation should produce empty string."""
        var = Variation(
            moves=[],
            starting_move_number=1,
            is_white_move=True,
        )
        result = var.to_pgn_string()
        self.assertEqual(result, "")

    def test_white_variation(self):
        """White's variation should start with move number."""
        var = Variation(
            moves=["d4", "d5", "c4"],
            starting_move_number=1,
            is_white_move=True,
        )
        result = var.to_pgn_string()
        self.assertIn("1.d4", result)
        self.assertTrue(result.startswith("("))
        self.assertTrue(result.endswith(")"))

    def test_black_variation(self):
        """Black's variation should start with continuation dots."""
        var = Variation(
            moves=["e6", "d4", "d5"],
            starting_move_number=1,
            is_white_move=False,
        )
        result = var.to_pgn_string()
        self.assertIn("1...", result)

    def test_variation_with_comment(self):
        """Variation should include comment."""
        var = Variation(
            moves=["d4"],
            starting_move_number=1,
            is_white_move=True,
            comment="Alternative line",
        )
        result = var.to_pgn_string()
        self.assertIn("Alternative line", result)


class TestGameMetadata(unittest.TestCase):
    """Tests for GameMetadata dataclass."""

    def test_default_values(self):
        """Default values should be set."""
        meta = GameMetadata()
        self.assertEqual(meta.event, "Caissa AI Generation")
        self.assertIsNotNone(meta.date)

    def test_to_pgn_headers(self):
        """to_pgn_headers should produce valid PGN headers."""
        meta = GameMetadata(
            event="Test Event",
            white="Player A",
            black="Player B",
            result="1-0",
        )
        headers = meta.to_pgn_headers()
        self.assertIn('[Event "Test Event"]', headers)
        self.assertIn('[White "Player A"]', headers)
        self.assertIn('[Result "1-0"]', headers)

    def test_optional_headers(self):
        """Optional headers should be included when set."""
        meta = GameMetadata(
            eco="B90",
            opening="Sicilian Defense",
            white_elo=2700,
        )
        headers = meta.to_pgn_headers()
        self.assertIn('[ECO "B90"]', headers)
        self.assertIn('[Opening "Sicilian Defense"]', headers)
        self.assertIn('[WhiteElo "2700"]', headers)


class TestPGNBuilderAdvanced(unittest.TestCase):
    """Tests for PGNBuilder advanced methods."""

    def setUp(self):
        """Set up PGNBuilder."""
        self.builder = PGNBuilder(
            event="Test Game",
            white="White",
            black="Black",
        )

    def test_add_move_advanced(self):
        """add_move_advanced should add annotated moves."""
        self.builder.add_move_advanced(
            "e4",
            nags=[NAG.GOOD_MOVE],
            comment="Strong opening",
            evaluation=30,
        )
        self.assertEqual(len(self.builder.moves), 1)
        self.assertEqual(self.builder.moves[0], "e4")
        self.assertIn(0, self.builder._global_annotations)

    def test_annotate_move(self):
        """annotate_move should add annotations to existing moves."""
        self.builder.add_move("e4")
        self.builder.add_move("e5")
        self.builder.annotate_move(0, nags=[NAG.BRILLIANT_MOVE])
        self.assertIn(0, self.builder._global_annotations)
        self.assertIn(
            NAG.BRILLIANT_MOVE,
            self.builder._global_annotations[0].nag_codes
        )

    def test_add_variation(self):
        """add_variation should add alternative lines."""
        self.builder.add_move("e4")
        self.builder.add_variation(0, ["d4", "d5"], "Queen's Gambit")
        self.assertIn(0, self.builder._variations)
        self.assertEqual(len(self.builder._variations[0]), 1)

    def test_brilliant_move_marker(self):
        """add_brilliant_move_marker should add !! annotation."""
        self.builder.add_move("Rxh7")
        self.builder.add_brilliant_move_marker(0)
        self.assertIn(
            NAG.BRILLIANT_MOVE,
            self.builder._global_annotations[0].nag_codes
        )

    def test_blunder_marker(self):
        """add_blunder_marker should add ?? annotation."""
        self.builder.add_move("Ke2")
        self.builder.add_blunder_marker(0, comment="Loses the queen!")
        ann = self.builder._global_annotations[0]
        self.assertIn(NAG.BLUNDER, ann.nag_codes)
        self.assertEqual(ann.comment, "Loses the queen!")


class TestPGNBuilderExport(unittest.TestCase):
    """Tests for PGNBuilder export methods."""

    def setUp(self):
        """Set up PGNBuilder with sample game."""
        self.builder = PGNBuilder(
            event="Export Test",
            white="Tal",
            black="Petrosian",
        )
        self.builder.add_move_advanced("e4", nags=[NAG.GOOD_MOVE])
        self.builder.add_move_advanced("c5")
        self.builder.add_move_advanced("Nf3")
        self.builder.add_move_advanced("d6", comment="Sicilian Defense")
        self.builder.set_opening_info("B90", "Sicilian Defense", "Najdorf")

    def test_build_pgn_advanced(self):
        """build_pgn_advanced should produce valid PGN."""
        pgn = self.builder.build_pgn_advanced(result="1-0")
        self.assertIn('[Event "Export Test"]', pgn)
        self.assertIn('[White "Tal"]', pgn)
        self.assertIn('[ECO "B90"]', pgn)
        self.assertIn("1-0", pgn)

    def test_export_markdown(self):
        """export_markdown should produce valid Markdown."""
        md = self.builder.export_markdown()
        self.assertIn("# Export Test", md)
        self.assertIn("| White | **Tal** |", md)
        self.assertIn("Sicilian Defense", md)

    def test_export_html(self):
        """export_html should produce valid HTML."""
        html = self.builder.export_html()
        self.assertIn("<html>", html)
        self.assertIn("Export Test", html)
        self.assertIn("Tal", html)

    def test_export_json(self):
        """export_json should produce valid JSON."""
        json_str = self.builder.export_json()
        data = json.loads(json_str)
        self.assertEqual(data["metadata"]["white"], "Tal")
        self.assertEqual(len(data["moves"]), 4)
        self.assertEqual(data["moves"][0]["san"], "e4")

    def test_export_method(self):
        """export should route to correct format."""
        pgn = self.builder.export(ExportFormat.PGN)
        self.assertIn('[Event', pgn)
        
        md = self.builder.export(ExportFormat.MARKDOWN)
        self.assertIn("#", md)
        
        html = self.builder.export(ExportFormat.HTML)
        self.assertIn("<html>", html)
        
        json_out = self.builder.export(ExportFormat.JSON)
        self.assertTrue(json_out.startswith("{"))


class TestPGNBuilderUtility(unittest.TestCase):
    """Tests for PGNBuilder utility methods."""

    def test_reset(self):
        """reset should clear all state."""
        builder = PGNBuilder(white="Test", black="Test")
        builder.add_move("e4")
        builder.add_move("e5")
        builder.reset()
        self.assertEqual(len(builder.moves), 0)
        self.assertEqual(len(builder._global_annotations), 0)

    def test_clone(self):
        """clone should create independent copy."""
        builder = PGNBuilder(white="Original", black="Copy")
        builder.add_move("e4")
        
        clone = builder.clone()
        clone.add_move("e5")
        
        self.assertEqual(len(builder.moves), 1)
        self.assertEqual(len(clone.moves), 2)

    def test_set_metadata(self):
        """set_metadata should update metadata fields."""
        builder = PGNBuilder()
        builder.set_metadata(
            event="Custom Event",
            site="Custom Site",
            round="3",
        )
        self.assertEqual(builder._metadata.event, "Custom Event")
        self.assertEqual(builder._metadata.round, "3")

    def test_set_player_elos(self):
        """set_player_elos should update Elo ratings."""
        builder = PGNBuilder()
        builder.set_player_elos(white_elo=2700, black_elo=2650)
        self.assertEqual(builder._metadata.white_elo, 2700)
        self.assertEqual(builder._metadata.black_elo, 2650)


class TestNAGSymbols(unittest.TestCase):
    """Tests for NAG to symbol mapping."""

    def test_nag_symbols_mapping(self):
        """NAG_SYMBOLS should have correct mappings."""
        builder = PGNBuilder()
        self.assertEqual(builder.NAG_SYMBOLS[NAG.GOOD_MOVE], "!")
        self.assertEqual(builder.NAG_SYMBOLS[NAG.BRILLIANT_MOVE], "!!")
        self.assertEqual(builder.NAG_SYMBOLS[NAG.BLUNDER], "??")
        self.assertEqual(builder.NAG_SYMBOLS[NAG.WHITE_DECISIVE], "+-")


if __name__ == "__main__":
    unittest.main()
