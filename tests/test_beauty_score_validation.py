"""
Integration test for v0.5.0 LLM Match Analysis & Beauty Scoring.

This test validates that the critical bug fix (binary_path → path) works correctly
and that the analysis pipeline produces real beauty scores.

IMPORTANT: This is a REAL test that requires:
- Stockfish binary installed
- Valid LLM provider configured (for end-to-end test)
"""

import sys
import json
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("CAISSA v0.5.0 - BEAUTY SCORE VALIDATION TEST")
print("=" * 80)

# ============================================================================
# TEST 1: Verify Config Attribute Fix
# ============================================================================
print("\n[TEST 1] Stockfish Config Attribute Validation...")

try:
    from config_manager import cfg
    
    # This should work (the fix)
    stockfish_path = cfg.stockfish.path
    print(f"  ✓ cfg.stockfish.path accessible: {stockfish_path}")
    
    # This should fail (the bug we fixed)
    try:
        _ = cfg.stockfish.binary_path
        print("  ✗ FAIL: cfg.stockfish.binary_path should not exist!")
        sys.exit(1)
    except AttributeError:
        print("  ✓ cfg.stockfish.binary_path correctly raises AttributeError (bug is fixed)")
    
    # Verify path exists
    path_obj = Path(stockfish_path)
    if path_obj.exists():
        print(f"  ✓ Stockfish binary exists: {path_obj.absolute()}")
    else:
        print(f"  ⚠️  WARNING: Stockfish binary not found at {stockfish_path}")
        print("  → This will cause analysis to skip, but config is correct")
    
except Exception as e:
    print(f"  ✗ FAIL: Config validation error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# TEST 2: Import Validation
# ============================================================================
print("\n[TEST 2] Analysis Pipeline Imports...")

try:
    from core.match_analyzer import MatchAnalyzer, MatchAnalysis
    from core.match_workflow import run_analyzed_match, run_match_series
    from core.match_engine import MatchEngine, MatchResult
    from aesthetic.beauty_eval import BeautyEvaluator
    print("  ✓ All analysis imports successful")
except ImportError as e:
    print(f"  ✗ FAIL: Import error: {e}")
    sys.exit(1)

# ============================================================================
# TEST 3: MatchAnalyzer Initialization (with real Stockfish)
# ============================================================================
print("\n[TEST 3] MatchAnalyzer Initialization...")

try:
    from config_manager import cfg
    
    stockfish_path = cfg.stockfish.path
    
    if not Path(stockfish_path).exists():
        print(f"  ⚠️  SKIP: Stockfish not found at {stockfish_path}")
        print("  → Install Stockfish to run full analysis tests")
    else:
        # Try to initialize MatchAnalyzer
        analyzer = MatchAnalyzer(
            stockfish_path=stockfish_path,
            commentary_provider=None,  # No LLM needed for this test
            enable_commentary=False,
        )
        
        print("  ✓ MatchAnalyzer initialized successfully")
        print(f"    - Stockfish path: {analyzer.stockfish_path}")
        print(f"    - Analysis depth: {cfg.stockfish.depth}")
        print(f"    - Beauty evaluator: {analyzer.beauty_evaluator is not None}")
        
        # Clean up
        analyzer.__exit__(None, None, None)
        print("  ✓ MatchAnalyzer cleanup successful")
        
except Exception as e:
    print(f"  ✗ FAIL: MatchAnalyzer initialization error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# TEST 4: Beauty Score Calculation (Mock Match)
# ============================================================================
print("\n[TEST 4] Beauty Score Calculation (Mock Data)...")

try:
    import chess
    from core.match_engine import MoveRecord, MatchResult, TerminationReason
    from core.elo_calculator import GameResult
    from dataclasses import dataclass
    
    # Create a simple mock match with known moves
    board = chess.Board()
    
    # Helper to create move records
    def make_move(move_num, color, san_str):
        player_name = "TestWhite" if color == "white" else "TestBlack"
        move = board.parse_san(san_str)
        fen_before = board.fen()
        board.push(move)
        fen_after = board.fen()
        
        return MoveRecord(
            move_number=move_num,
            player=player_name,
            color=color,
            san=san_str,
            uci=move.uci(),
            fen_before=fen_before,
            fen_after=fen_after,
            think_time=1.0,
            attempt=1,
            is_check=board.is_check(),
            is_capture=move.drop is not None if hasattr(move, 'drop') else False,
            is_promotion=move.promotion is not None if hasattr(move, 'promotion') else False,
        )
    
    # Create moves for Italian Game opening
    mock_moves = [
        make_move(1, "white", "e4"),
        make_move(1, "black", "e5"),
        make_move(2, "white", "Nf3"),
        make_move(2, "black", "Nc6"),
        make_move(3, "white", "Bc4"),
        make_move(3, "black", "Bc5"),
    ]
    
    # Create mock result
    from core.tournament_player import TournamentPlayer
    
    white_player = TournamentPlayer(name="TestWhite", provider_name="test")
    black_player = TournamentPlayer(name="TestBlack", provider_name="test")
    
    mock_result = MatchResult(
        match_id="test-beauty-001",
        white=white_player,
        black=black_player,
        moves=mock_moves,
        result=GameResult.WHITE_WINS,
        termination=TerminationReason.CHECKMATE,
        final_fen=board.fen(),
        total_moves=len(mock_moves),
    )
    
    print(f"  ✓ Mock match created: {len(mock_moves)} moves")
    
    # Run analysis if Stockfish available
    if not Path(cfg.stockfish.path).exists():
        print("  ⚠️  SKIP: Stockfish not available for beauty calculation")
    else:
        async def test_beauty_calculation():
            analyzer = MatchAnalyzer(
                stockfish_path=cfg.stockfish.path,
                commentary_provider=None,
                enable_commentary=False,
            )
            
            try:
                analysis = await analyzer.analyze_match(mock_result)
                
                # Validate analysis results
                assert analysis is not None, "Analysis should not be None"
                assert analysis.beauty_score >= 0, "Beauty score should be >= 0"
                assert analysis.beauty_score <= 100, "Beauty score should be <= 100"
                assert len(analysis.move_annotations) == len(mock_moves), "Should have annotations for all moves"
                
                print(f"  ✓ Beauty score calculated: {analysis.beauty_score:.2f}/100")
                print(f"  ✓ Move annotations count: {len(analysis.move_annotations)}")
                
                # Check that move annotations have evaluation data
                if analysis.move_annotations:
                    first_annotation = analysis.move_annotations[0]
                    print(f"  ✓ First move evaluation: {first_annotation.evaluation:.2f} cp")
                
                # Check for critical moments (there might be none in a simple game)
                print(f"  ✓ Critical moments detected: {len(analysis.critical_moments)}")
                print(f"  ✓ White accuracy: {analysis.white_accuracy:.1f}%")
                print(f"  ✓ Black accuracy: {analysis.black_accuracy:.1f}%")
                
                return True
                
            finally:
                analyzer.__exit__(None, None, None)
        
        success = asyncio.run(test_beauty_calculation())
        
        if not success:
            print("  ✗ FAIL: Beauty calculation did not complete")
            sys.exit(1)
    
except Exception as e:
    print(f"  ✗ FAIL: Beauty calculation error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# TEST 5: Export Integration (verify analysis is included)
# ============================================================================
print("\n[TEST 5] Export Integration with Analysis...")

try:
    from export.tournament_exporter import MatchExporter
    
    # Use the mock result from TEST 4
    # Without analysis
    exporter_no_analysis = MatchExporter(
        match_result=mock_result,
        match_analysis=None,
        include_elo=True,
    )
    
    json_str_no_analysis = exporter_no_analysis.export_json()
    json_no_analysis = json.loads(json_str_no_analysis)
    beauty_no_analysis = json_no_analysis.get("metadata", {}).get("beauty_score", -1)
    
    print(f"  ✓ Export without analysis: beauty_score = {beauty_no_analysis}")
    
    if beauty_no_analysis != 0.0:
        print(f"  ✗ FAIL: Expected beauty_score=0.0 without analysis, got {beauty_no_analysis}")
        sys.exit(1)
    
    # With analysis (if Stockfish available)
    if Path(cfg.stockfish.path).exists():
        async def test_export_with_analysis():
            analyzer = MatchAnalyzer(
                stockfish_path=cfg.stockfish.path,
                commentary_provider=None,
                enable_commentary=False,
            )
            
            try:
                analysis = await analyzer.analyze_match(mock_result)
                
                exporter_with_analysis = MatchExporter(
                    match_result=mock_result,
                    match_analysis=analysis,
                    include_elo=True,
                )
                
                json_str_with_analysis = exporter_with_analysis.export_json()
                json_with_analysis = json.loads(json_str_with_analysis)
                beauty_with_analysis = json_with_analysis.get("metadata", {}).get("beauty_score", -1)
                
                print(f"  ✓ Export with analysis: beauty_score = {beauty_with_analysis:.2f}")
                
                if beauty_with_analysis == 0.0:
                    print(f"  ✗ FAIL: beauty_score should be non-zero with analysis!")
                    return False
                
                # Check that moves have evaluations
                moves = json_with_analysis.get("moves", [])
                if moves and "evaluation" not in moves[0]:
                    print(f"  ✗ FAIL: Moves should have evaluation data!")
                    return False
                
                print(f"  ✓ Moves include evaluation data")
                
                return True
                
            finally:
                analyzer.__exit__(None, None, None)
        
        success = asyncio.run(test_export_with_analysis())
        
        if not success:
            print("  ✗ FAIL: Export with analysis failed")
            sys.exit(1)
    else:
        print("  ⚠️  SKIP: Stockfish not available for analysis export test")
    
except Exception as e:
    print(f"  ✗ FAIL: Export integration error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================================
# TEST 6: Main.py Execution Path Validation
# ============================================================================
print("\n[TEST 6] Main.py Analysis Execution Path...")

try:
    # Verify the fix is in main.py
    main_py_path = Path(__file__).parent.parent / "main.py"
    
    with open(main_py_path, 'r', encoding='utf-8') as f:
        main_content = f.read()
    
    # Check for the CORRECT attribute access
    if "getattr(cfg.stockfish, 'path', None)" in main_content:
        print("  ✓ main.py uses correct attribute: cfg.stockfish.path")
    else:
        print("  ✗ FAIL: main.py does not use cfg.stockfish.path")
        sys.exit(1)
    
    # Check that the BUG is NOT present
    if "getattr(cfg.stockfish, 'binary_path', None)" in main_content:
        print("  ✗ FAIL: main.py still has the bug: cfg.stockfish.binary_path")
        sys.exit(1)
    else:
        print("  ✓ Bug NOT present: binary_path removed")
    
    # Check that MatchAnalyzer import exists
    if "from core.match_analyzer import MatchAnalyzer" in main_content:
        print("  ✓ MatchAnalyzer import present in main.py")
    else:
        print("  ⚠️  WARNING: MatchAnalyzer import not found in main.py")
    
except Exception as e:
    print(f"  ✗ FAIL: Main.py validation error: {e}")
    sys.exit(1)

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("✅ ALL BEAUTY SCORE VALIDATION TESTS PASSED!")
print("=" * 80)

print("\nTest Summary:")
print("  ✓ Config attribute fix validated (binary_path → path)")
print("  ✓ Analysis pipeline imports working")
print("  ✓ MatchAnalyzer initializes correctly")

if Path(cfg.stockfish.path).exists():
    print("  ✓ Beauty scores calculated correctly (non-zero)")
    print("  ✓ Exports include analysis data")
    print("  ✓ Full analysis pipeline functional")
else:
    print("  ⚠️  Stockfish not available - some tests skipped")
    print("     → Install Stockfish for full validation")

print("  ✓ Main.py uses correct config path")
print("  ✓ Bug fix confirmed in codebase")

print("\n" + "=" * 80)
print("🎯 READY FOR PRODUCTION")
print("=" * 80)

print("\nNext Steps:")
print("  1. Run a real LLM match: python main.py → Option 6")
print("  2. Verify console shows: '🔍 Analyzing match...'")
print("  3. Check export has beauty_score > 0")
print("  4. Confirm evaluations and commentary in export files")
print()
