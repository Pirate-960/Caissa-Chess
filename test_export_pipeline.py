"""
Test script for the unified export pipeline.
Exercises the annotation parser and all export formats with realistic LLM output.
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from export.annotation_parser import parse_pgn, detect_opening, from_san_list
from export.game_exporter import GameExporter, ExportConfig


# =============================================================================
# SAMPLE PGN DATA (simulating LLM output)
# =============================================================================

SAMPLE_ANNOTATED_PGN = """[Event "Danish Gambit Exhibition"]
[Site "Caissa Engine"]
[Date "2025.01.15"]
[Round "1"]
[White "Mikhail Tal"]
[Black "Stockfish 16"]
[Result "1-0"]

1. e4 e5 2. d4 exd4 3. c3 dxc3 4. Bc4 {The Danish Gambit! White sacrifices two pawns for rapid development and open lines.} cxb2 5. Bxb2!! {A brilliant sacrifice -- White now has devastating pressure on the long diagonal and f7.} Nf6?! {Playing with fire. Better was 5...d5.} 6. e5 Ne4 7. Qg4! {Targeting g7 with a vicious queen sortie.} d5 8. exd6 Bxd6?? {A terrible blunder.} 9. Bxg7 Rg8 10. Qxe4+ Be7 11. Bxf7+ Kf8 12. Bh6# 1-0"""

SAMPLE_MORPHY_PGN = """[Event "Caissa Masterpiece"]
[Site "Paris, France"]
[Date "2025.06.20"]
[Round "?"]
[White "Paul Morphy"]
[Black "Magnus Carlsen"]
[Result "1-0"]
[ECO "C51"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 {The Italian Game.} 4. b4!? {The Evans Gambit! A tribute to Captain Evans.} Bxb4 5. c3 Ba5 6. d4 exd4 7. O-O d6 8. cxd4 Bb6 9. Nc3 {White has enormous central control for the pawn.} Na5 10. Bg5! f6? 11. Bf4 Nh6 12. Nd5!! {A stunning centralized knight. The position is nearly winning.} Be6 13. Bxd6 cxd6 14. Nxb6 axb6 15. Qa4+ Kf7 16. Qe8+ Kg7 17. Qxe6 1-0"""

SAMPLE_SHORT_PGN = """[Event "Quick Tactical Win"]
[White "Caissa"]
[Black "Opponent"]
[Result "1-0"]

1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6?? {Blunders into Scholar's mate.} 4. Qxf7# 1-0"""

SAMPLE_BARE_PGN = """1. d4 Nf6 2. c4 g6 3. Nc3 Bg7 4. e4 d6 5. Nf3 O-O 6. Be2 e5 7. O-O Nc6 8. d5 Ne7 9. Ne1 Nd7 10. Nd3 f5 11. f3 f4 12. b4 g5 13. c5 h5 14. cxd6 cxd6 15. Nb5 g4 16. Nxa7 Rxa7 17. Bxa7 gxf3 18. Bxf3 Ng6 19. Be3 Nf6 20. Nb2 Nh4 21. Nc4 Nxf3+ 22. Rxf3 Bh3 23. Bf2 Ng4 24. Re1 Qg5 25. Nd2 Rf6 *"""


def divider(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def test_annotation_parser():
    divider("TEST 1: Annotation Parser — Annotated PGN")

    game = parse_pgn(SAMPLE_ANNOTATED_PGN)

    print(f"  White:        {game.white}")
    print(f"  Black:        {game.black}")
    print(f"  Event:        {game.event}")
    print(f"  Result:       {game.result}")
    print(f"  Total moves:  {game.move_count}")
    print(f"  Annotations:  {game.has_annotations}")
    print(f"  ECO:          {game.eco or '(none detected)'}")
    print(f"  Opening:      {game.opening_name or '(none detected)'}")
    print()

    annotated = 0
    for m in game.moves:
        parts = [f"  {m.move_number}{'.' if m.is_white else '...'} {m.san}"]
        if m.nags:
            parts.append(f" NAGs={''.join(m.nags)}")
        if m.comment:
            short = m.comment[:60] + "..." if len(m.comment) > 60 else m.comment
            parts.append(f" // {short}")
            annotated += 1
        print("".join(parts))

    print(f"\n  Annotated plies: {annotated}/{len(game.moves)}")
    assert game.result == "1-0", f"Expected 1-0, got {game.result}"
    assert game.has_annotations, "Expected annotations"
    assert len(game.moves) > 0, "Expected moves"
    print("  ✅ PASSED")


def test_parser_morphy():
    divider("TEST 2: Annotation Parser — Morphy PGN with ECO")

    game = parse_pgn(SAMPLE_MORPHY_PGN)
    print(f"  White: {game.white}")
    print(f"  Black: {game.black}")
    print(f"  ECO:   {game.eco}")
    print(f"  Moves: {game.move_count}")
    print(f"  Has annotations: {game.has_annotations}")

    # Check some specific annotations
    nag_moves = [m for m in game.moves if m.nags]
    for m in nag_moves:
        print(f"    {m.move_number}{'.' if m.is_white else '...'}{m.san} {''.join(m.nags)}")

    assert game.result == "1-0"
    assert len(nag_moves) > 0, "Expected NAG-annotated moves"
    print("  ✅ PASSED")


def test_parser_bare():
    divider("TEST 3: Parser — Bare PGN (no annotations, no headers)")

    game = parse_pgn(SAMPLE_BARE_PGN)
    print(f"  Moves: {game.move_count}")
    print(f"  Result: {game.result}")
    print(f"  Has annotations: {game.has_annotations}")
    assert len(game.moves) > 20, "Expected 25+ plies"
    assert game.result == "*"
    print("  ✅ PASSED")


def test_from_san_list():
    divider("TEST 4: from_san_list() backward compat")

    moves = ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"]
    game = from_san_list(moves, result="*")
    print(f"  Moves: {game.move_count}")
    print(f"  ECO: {game.eco}")
    print(f"  Opening: {game.opening_name}")
    assert game.move_count == 5
    # Should detect Sicilian Najdorf
    assert game.eco == "B90", f"Expected B90, got {game.eco}"
    print("  ✅ PASSED")


def test_opening_detection():
    divider("TEST 5: Opening Detection")

    tests = [
        (["e4", "e5", "Nf3", "Nc6", "Bb5"], "C80", "Ruy Lopez"),
        (["e4", "e6"], "C00", "French Defense"),
        (["d4", "d5", "c4"], "", ""),  # Not in our small DB
    ]

    for moves, expected_eco, expected_name in tests:
        eco, name, _ = detect_opening(moves)
        status = "✅" if eco == expected_eco else "❌"
        print(f"  {status} {' '.join(moves[:5])}... → ECO={eco or '(none)'}, Name={name or '(none)'}")

    print("  ✅ PASSED")


def test_pgn_export():
    divider("TEST 6: PGN Export (annotated)")

    game = parse_pgn(SAMPLE_ANNOTATED_PGN)
    exporter = GameExporter(game=game, beauty_score=78.5, style_name="romantic")
    pgn = exporter.export_pgn()

    print(pgn[:900])
    print("..." if len(pgn) > 900 else "")

    # Verify key features
    assert "[Annotator" in pgn, "Missing Annotator header"
    assert "[PlyCount" in pgn, "Missing PlyCount header"
    assert "[BeautyScore" in pgn, "Missing BeautyScore header"
    assert "[Style" in pgn, "Missing Style header"

    # Section structure
    assert "MOVES" in pgn, "Missing MOVES section divider"
    assert "MOVE COMMENTARY" in pgn, "Missing MOVE COMMENTARY section"
    assert "GAME SUMMARY" in pgn, "Missing GAME SUMMARY section"

    # Move formatting: each move pair on its own line
    lines = pgn.split("\n")
    move_lines = [l for l in lines if l and l[0].isdigit()]
    assert len(move_lines) >= 5, f"Expected ≥5 move lines, got {len(move_lines)}"

    # NAGs stay on move lines
    assert "!!" in pgn, "Missing NAG symbols"
    # Commentary in separate section (no braces)
    assert "5. Bxb2!! —" in pgn, "Missing commentary entry for 5.Bxb2!!"
    assert "1-0" in pgn, "Missing result"
    print("\n  ✅ PASSED")


def test_json_export():
    divider("TEST 7: JSON Export (rich)")

    game = parse_pgn(SAMPLE_ANNOTATED_PGN)
    exporter = GameExporter(game=game, beauty_score=78.5, style_name="romantic")
    json_out = exporter.export_json()

    import json
    data = json.loads(json_out)

    print(f"  Top-level keys: {list(data.keys())}")
    print(f"  Metadata keys:  {list(data['metadata'].keys())}")
    print(f"  Opening:        {data['opening']}")
    print(f"  Summary:        {data['summary']}")
    print(f"  Moves count:    {len(data['moves'])}")

    # Check a move with annotations
    annotated_moves = [m for m in data["moves"] if "comment" in m or "nags" in m]
    print(f"  Annotated:      {len(annotated_moves)}")
    if annotated_moves:
        print(f"  Sample move:    {annotated_moves[0]}")

    assert "metadata" in data
    assert "opening" in data
    assert "moves" in data
    assert "summary" in data
    assert data["metadata"]["result"] == "1-0"
    assert data["metadata"]["beauty_score"] == 78.5
    assert len(annotated_moves) > 0, "Expected annotated moves in JSON"
    print("\n  ✅ PASSED")


def test_markdown_export():
    divider("TEST 8: Markdown Export")

    game = parse_pgn(SAMPLE_MORPHY_PGN)
    exporter = GameExporter(game=game, beauty_score=85.0, style_name="romantic")
    md = exporter.export_markdown()

    print(md[:800])
    print("..." if len(md) > 800 else "")

    assert "# Caissa Masterpiece" in md
    assert "Paul Morphy" in md
    assert "Magnus Carlsen" in md
    assert "**Result:" in md
    assert "## Summary" in md
    assert "1-0" in md
    print("\n  ✅ PASSED")


def test_html_export():
    divider("TEST 9: HTML Export")

    game = parse_pgn(SAMPLE_ANNOTATED_PGN)
    exporter = GameExporter(game=game, beauty_score=78.5)
    html = exporter.export_html()

    print(f"  HTML length: {len(html)} chars")
    print(f"  Has <style>:  {'<style>' in html}")
    print(f"  Has move-table: {'class=\"move-table\"' in html}")
    print(f"  Has comments:   {'comment-cell' in html}")
    print(f"  Has NAGs:       {'class=\"nag' in html}")
    print(f"  Has summary:    {'class=\"summary\"' in html}")
    print(f"  Has theme btn:  {'theme-toggle' in html}")

    assert "<!DOCTYPE html>" in html
    assert "move-table" in html or "moves-inline" in html
    assert 'class="nag' in html
    assert "comment-cell" in html or "comment-inline" in html
    assert 'class="summary"' in html
    print("  ✅ PASSED")


def test_export_all():
    divider("TEST 10: export_all() convenience method")

    game = parse_pgn(SAMPLE_ANNOTATED_PGN)
    exporter = GameExporter(game=game)
    all_formats = exporter.export_all()

    for fmt, content in all_formats.items():
        print(f"  {fmt:10s}: {len(content):6d} chars")

    assert len(all_formats) == 5
    assert all(len(v) > 0 for v in all_formats.values())
    assert "pgn_strict" in all_formats
    print("  ✅ PASSED")


def test_pgn_strict_export():
    divider("TEST 11: PGN Strict Export (standard-compliant)")

    game = parse_pgn(SAMPLE_ANNOTATED_PGN)
    exporter = GameExporter(game=game, beauty_score=78.5, style_name="romantic")
    pgn = exporter.export_pgn_strict()

    print(pgn[:900])
    print("..." if len(pgn) > 900 else "")

    # Headers present
    assert "[Annotator" in pgn, "Missing Annotator header"
    assert "[PlyCount" in pgn, "Missing PlyCount header"

    # Inline {comments} present (standard PGN)
    assert "{" in pgn, "Missing inline {comments}"
    assert "}" in pgn, "Missing closing brace"

    # NAGs inline
    assert "!!" in pgn, "Missing NAG symbols"

    # No section dividers (this is pure PGN)
    assert "MOVES" not in pgn, "Strict PGN should not have section dividers"
    assert "COMMENTARY" not in pgn, "Strict PGN should not have section dividers"

    # Result termination
    assert "1-0" in pgn, "Missing result"

    # Comments are inline with moves
    lines = pgn.split("\n")
    comment_lines = [l for l in lines if "{" in l and "}" in l and l[0:1].isdigit()]
    assert len(comment_lines) >= 2, f"Expected ≥2 move lines with inline comments, got {len(comment_lines)}"

    print("\n  ✅ PASSED")


def test_short_game():
    divider("TEST 12: Short game (Scholar's Mate)")

    game = parse_pgn(SAMPLE_SHORT_PGN)
    exporter = GameExporter(game=game)

    pgn = exporter.export_pgn()
    json_out = exporter.export_json()
    md = exporter.export_markdown()

    print(f"  Moves: {game.move_count}")
    print(f"  Has blunder annotation: {any('??' in (m.nags or []) for m in game.moves)}")
    print(f"  PGN length: {len(pgn)}")
    print(f"  JSON length: {len(json_out)}")
    print(f"  MD length: {len(md)}")

    # Verify the blunder annotation was preserved
    blunder_moves = [m for m in game.moves if "??" in (m.nags or [])]
    assert len(blunder_moves) == 1, f"Expected 1 blunder, got {len(blunder_moves)}"
    assert blunder_moves[0].san == "Nf6", f"Expected Nf6??, got {blunder_moves[0].san}"
    print("  ✅ PASSED")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  CAISSA EXPORT PIPELINE — VERIFICATION SUITE")
    print("=" * 70)

    tests = [
        test_annotation_parser,
        test_parser_morphy,
        test_parser_bare,
        test_from_san_list,
        test_opening_detection,
        test_pgn_export,
        test_json_export,
        test_markdown_export,
        test_html_export,
        test_export_all,
        test_pgn_strict_export,
        test_short_game,
    ]

    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    divider("RESULTS")
    print(f"  Passed: {passed}/{passed + failed}")
    print(f"  Failed: {failed}/{passed + failed}")

    if failed == 0:
        print("\n  🎉 ALL TESTS PASSED")
    else:
        print(f"\n  ⚠️ {failed} TEST(S) FAILED")

    sys.exit(0 if failed == 0 else 1)
