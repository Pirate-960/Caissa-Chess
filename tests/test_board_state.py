"""
Comprehensive tests for core/board_state.py

Covers:
- All 4 enums (GamePhase, PositionType, CastlingStatus, PawnStructure)
- All 6 dataclasses (MoveMetadata, PieceActivity, KingSafety,
  PawnStructureAnalysis, AdvancedPositionAnalysis, OpeningInfo)
- BoardState class: __init__, push_move, undo_move, reset, get_legal_moves_san,
  get_full_move_count, is_game_over, get_game_result, analyze_position_advanced,
  get_fen, set_fen, get_pgn, load_pgn, get_piece_at, get_all_pieces,
  get_attacked_squares, clone, __repr__, __str__
- Constants: CENTRAL_SQUARES, EXTENDED_CENTER, PIECE_VALUES
- Private helpers: _detect_game_phase, _detect_position_type,
  _calculate_material_balance, _analyze_king_safety, _analyze_pawn_structure,
  _calculate_space, _calculate_mobility, _calculate_tension, _calculate_complexity
"""

import chess
import pytest
from core.board_state import (
    GamePhase,
    PositionType,
    CastlingStatus,
    PawnStructure,
    MoveMetadata,
    PieceActivity,
    KingSafety,
    PawnStructureAnalysis,
    AdvancedPositionAnalysis,
    OpeningInfo,
    BoardState,
)


# =============================================================================
# HELPERS
# =============================================================================

def _make_board(fen=None):
    """Create a BoardState, optionally from a FEN."""
    bs = BoardState()
    if fen is not None:
        bs.reset(fen=fen)
    return bs


def _push(bs, san):
    """Push a move given in SAN notation and return the MoveMetadata."""
    move = bs.board.parse_san(san)
    return bs.push_move(move)


# =============================================================================
# ENUM TESTS
# =============================================================================

class TestGamePhaseEnum:
    def test_values(self):
        assert GamePhase.OPENING == "opening"
        assert GamePhase.EARLY_MIDDLE == "early_middle"
        assert GamePhase.MIDDLE == "middle"
        assert GamePhase.LATE_MIDDLE == "late_middle"
        assert GamePhase.ENDGAME == "endgame"
        assert GamePhase.PURE_ENDGAME == "pure_endgame"

    def test_member_count(self):
        assert len(GamePhase) == 6

    def test_is_str_enum(self):
        assert isinstance(GamePhase.OPENING, str)


class TestPositionTypeEnum:
    def test_values(self):
        assert PositionType.OPEN == "open"
        assert PositionType.SEMI_OPEN == "semi_open"
        assert PositionType.CLOSED == "closed"
        assert PositionType.DYNAMIC == "dynamic"
        assert PositionType.QUIET == "quiet"
        assert PositionType.SHARP == "sharp"

    def test_member_count(self):
        assert len(PositionType) == 6


class TestCastlingStatusEnum:
    def test_values(self):
        assert CastlingStatus.NOT_CASTLED == "not_castled"
        assert CastlingStatus.KINGSIDE == "kingside"
        assert CastlingStatus.QUEENSIDE == "queenside"
        assert CastlingStatus.CASTLING_LOST == "castling_lost"

    def test_member_count(self):
        assert len(CastlingStatus) == 4


class TestPawnStructureEnum:
    def test_values(self):
        assert PawnStructure.HEALTHY == "healthy"
        assert PawnStructure.DOUBLED == "doubled"
        assert PawnStructure.ISOLATED == "isolated"
        assert PawnStructure.BACKWARD == "backward"
        assert PawnStructure.PASSED == "passed"
        assert PawnStructure.CONNECTED == "connected"
        assert PawnStructure.CHAIN == "chain"

    def test_member_count(self):
        assert len(PawnStructure) == 7


# =============================================================================
# DATACLASS TESTS
# =============================================================================

class TestMoveMetadata:
    def test_creation(self):
        move = chess.Move.from_uci("e2e4")
        md = MoveMetadata(
            move=move,
            san="e4",
            position_before_fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            position_after_fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
            is_capture=False,
            is_check=False,
            is_checkmate=False,
        )
        assert md.san == "e4"
        assert md.is_sacrifice is False
        assert md.evaluation_before is None
        assert md.evaluation_after is None

    def test_optional_fields(self):
        move = chess.Move.from_uci("e2e4")
        md = MoveMetadata(
            move=move, san="e4",
            position_before_fen="fen1", position_after_fen="fen2",
            is_capture=False, is_check=False, is_checkmate=False,
            is_sacrifice=True, evaluation_before=0.3, evaluation_after=0.5,
        )
        assert md.is_sacrifice is True
        assert md.evaluation_before == 0.3


class TestPieceActivity:
    def test_creation(self):
        pa = PieceActivity(
            piece_type=chess.KNIGHT,
            square=chess.E4,
            mobility=8,
            attacks_count=3,
            defends_count=2,
            is_centralized=True,
            is_on_open_file=False,
        )
        assert pa.piece_type == chess.KNIGHT
        assert pa.mobility == 8
        assert pa.defends_count == 2
        assert pa.is_centralized is True
        assert pa.is_on_open_file is False
        assert pa.is_fianchettoed is False  # default
        assert pa.controls_key_squares == []  # default


class TestKingSafety:
    def test_creation_and_defaults(self):
        ks = KingSafety(
            king_square=chess.G1,
            pawn_shield_count=3,
            attackers_count=1,
            defenders_count=4,
            is_castled=True,
        )
        assert ks.king_square == chess.G1
        assert ks.is_castled is True
        assert ks.castling_side is None  # default is None
        assert ks.open_files_near_king == 0
        assert ks.safety_score == 0.0

    def test_to_dict(self):
        ks = KingSafety(
            king_square=chess.E1,
            pawn_shield_count=2,
            attackers_count=3,
            defenders_count=1,
            is_castled=False,
            safety_score=45.0,
        )
        d = ks.to_dict()
        assert d["king_square"] == "e1"
        assert d["pawn_shield_count"] == 2
        assert d["safety_score"] == 45.0
        assert isinstance(d, dict)


class TestPawnStructureAnalysis:
    def test_creation(self):
        psa = PawnStructureAnalysis(
            doubled_pawns=[chess.A2, chess.A3],
            isolated_pawns=[],
            backward_pawns=[],
            passed_pawns=[chess.D5],
            pawn_islands=2,
            structure_types=[PawnStructure.DOUBLED, PawnStructure.PASSED],
            structure_score=65.0,
        )
        assert len(psa.doubled_pawns) == 2
        assert psa.pawn_islands == 2

    def test_to_dict(self):
        psa = PawnStructureAnalysis(
            doubled_pawns=[], isolated_pawns=[], backward_pawns=[],
            passed_pawns=[], pawn_islands=1,
            structure_types=[PawnStructure.HEALTHY],
            structure_score=70.0,
        )
        d = psa.to_dict()
        assert d["pawn_islands"] == 1
        assert d["structure_score"] == 70.0
        assert "structure_types" in d


class TestAdvancedPositionAnalysis:
    def _make_king_safety(self, square=chess.G1, castled=True):
        return KingSafety(
            king_square=square, pawn_shield_count=3,
            attackers_count=0, defenders_count=5, is_castled=castled,
        )

    def _make_pawn_structure(self):
        return PawnStructureAnalysis(
            doubled_pawns=[], isolated_pawns=[], backward_pawns=[],
            passed_pawns=[], pawn_islands=1,
            structure_types=[PawnStructure.HEALTHY], structure_score=70.0,
        )

    def test_creation(self):
        apa = AdvancedPositionAnalysis(
            game_phase=GamePhase.OPENING,
            position_type=PositionType.QUIET,
            material_balance=0,
            white_king_safety=self._make_king_safety(chess.G1, True),
            black_king_safety=self._make_king_safety(chess.G8, True),
            white_pawn_structure=self._make_pawn_structure(),
            black_pawn_structure=self._make_pawn_structure(),
            white_space=30,
            black_space=28,
            white_mobility=20,
            black_mobility=20,
            tension_score=10.0,
            complexity_score=15.0,
        )
        assert apa.game_phase == GamePhase.OPENING
        assert apa.material_balance == 0
        assert apa.white_space == 30
        assert apa.complexity_score == 15.0

    def test_to_dict(self):
        wks = KingSafety(king_square=chess.G1, pawn_shield_count=3,
                         attackers_count=0, defenders_count=5, is_castled=True)
        bks = KingSafety(king_square=chess.G8, pawn_shield_count=2,
                         attackers_count=1, defenders_count=4, is_castled=True)
        wps = PawnStructureAnalysis(
            doubled_pawns=[], isolated_pawns=[], backward_pawns=[],
            passed_pawns=[], pawn_islands=1,
            structure_types=[PawnStructure.HEALTHY], structure_score=70.0,
        )
        bps = PawnStructureAnalysis(
            doubled_pawns=[], isolated_pawns=[], backward_pawns=[],
            passed_pawns=[], pawn_islands=1,
            structure_types=[PawnStructure.HEALTHY], structure_score=70.0,
        )
        apa = AdvancedPositionAnalysis(
            game_phase=GamePhase.MIDDLE,
            position_type=PositionType.DYNAMIC,
            material_balance=100,
            white_king_safety=wks,
            black_king_safety=bks,
            white_pawn_structure=wps,
            black_pawn_structure=bps,
            white_space=32,
            black_space=28,
            white_mobility=35,
            black_mobility=30,
            tension_score=55.0,
            complexity_score=60.0,
        )
        d = apa.to_dict()
        assert d["game_phase"] == "middle"
        assert d["material_balance"] == 100
        assert "white_king_safety" in d
        assert "white_pawn_structure" in d


class TestOpeningInfo:
    def test_creation(self):
        oi = OpeningInfo(opening_name="Sicilian Defense", eco_code="B20")
        assert oi.opening_name == "Sicilian Defense"
        assert oi.eco_code == "B20"
        assert oi.variation is None

    def test_to_dict(self):
        oi = OpeningInfo(opening_name="Ruy Lopez", eco_code="C60", variation="Berlin")
        d = oi.to_dict()
        assert d["opening_name"] == "Ruy Lopez"
        assert d["eco_code"] == "C60"
        assert d["variation"] == "Berlin"


# =============================================================================
# BOARD STATE CONSTANTS
# =============================================================================

class TestBoardStateConstants:
    def test_central_squares(self):
        assert chess.D4 in BoardState.CENTRAL_SQUARES
        assert chess.D5 in BoardState.CENTRAL_SQUARES
        assert chess.E4 in BoardState.CENTRAL_SQUARES
        assert chess.E5 in BoardState.CENTRAL_SQUARES
        assert len(BoardState.CENTRAL_SQUARES) == 4

    def test_extended_center(self):
        assert len(BoardState.EXTENDED_CENTER) > 4
        for sq in BoardState.CENTRAL_SQUARES:
            assert sq in BoardState.EXTENDED_CENTER

    def test_piece_values(self):
        assert BoardState.PIECE_VALUES[chess.PAWN] == 100
        assert BoardState.PIECE_VALUES[chess.KNIGHT] == 320
        assert BoardState.PIECE_VALUES[chess.BISHOP] == 330
        assert BoardState.PIECE_VALUES[chess.ROOK] == 500
        assert BoardState.PIECE_VALUES[chess.QUEEN] == 900


# =============================================================================
# BOARD STATE CORE METHODS
# =============================================================================

class TestBoardStateInit:
    def test_default_init(self):
        bs = BoardState()
        assert bs.board.fen() == chess.STARTING_FEN
        assert bs.move_history == []
        assert len(bs._position_cache) == 0

    def test_custom_fen_via_reset(self):
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        bs = _make_board(fen=fen)
        assert bs.board.fen() == fen

    def test_invalid_fen_via_set_fen(self):
        bs = BoardState()
        result = bs.set_fen("not-a-valid-fen")
        assert result is False


class TestBoardStatePushMove:
    def test_push_legal_uci(self):
        bs = BoardState()
        move = chess.Move.from_uci("e2e4")
        md = bs.push_move(move)
        assert isinstance(md, MoveMetadata)
        assert md.san == "e4"
        assert md.is_capture is False
        assert md.is_check is False
        assert len(bs.move_history) == 1

    def test_push_legal_san_via_helper(self):
        bs = BoardState()
        md = _push(bs, "e4")
        assert md.san == "e4"

    def test_push_chess_move_object(self):
        bs = BoardState()
        move = chess.Move.from_uci("e2e4")
        md = bs.push_move(move)
        assert md.san == "e4"

    def test_push_multiple_moves(self):
        bs = BoardState()
        _push(bs, "e4")
        _push(bs, "e5")
        _push(bs, "Nf3")
        assert len(bs.move_history) == 3

    def test_push_illegal_move_raises(self):
        bs = BoardState()
        # Ke2 is illegal at start (pawn on e2)
        with pytest.raises(Exception):
            _push(bs, "Ke2")

    def test_push_capture_flag(self):
        bs = BoardState()
        _push(bs, "e4")
        _push(bs, "d5")
        md = _push(bs, "exd5")
        assert md.is_capture is True

    def test_push_check_flag(self):
        bs = BoardState()
        # Scholar's mate setup: get a check
        _push(bs, "e4")
        _push(bs, "e5")
        _push(bs, "Bc4")
        _push(bs, "Nc6")
        md = _push(bs, "Qh5")  # Not check yet
        assert md.is_check is False
        _push(bs, "Nf6")
        md2 = _push(bs, "Qxf7")  # This is checkmate
        assert md2.is_check is True
        assert md2.is_checkmate is True


class TestBoardStateUndoMove:
    def test_undo_returns_metadata(self):
        bs = BoardState()
        _push(bs, "e4")
        md = bs.undo_move()
        assert isinstance(md, MoveMetadata)
        assert md.san == "e4"
        assert len(bs.move_history) == 0

    def test_undo_restores_position(self):
        bs = BoardState()
        fen_before = bs.get_fen()
        _push(bs, "e4")
        bs.undo_move()
        assert bs.get_fen() == fen_before

    def test_undo_empty_returns_none(self):
        bs = BoardState()
        result = bs.undo_move()
        assert result is None

    def test_multiple_undo(self):
        bs = BoardState()
        _push(bs, "e4")
        _push(bs, "e5")
        _push(bs, "Nf3")
        bs.undo_move()
        bs.undo_move()
        assert len(bs.move_history) == 1


class TestBoardStateReset:
    def test_reset_to_starting(self):
        bs = BoardState()
        _push(bs, "e4")
        _push(bs, "e5")
        bs.reset()
        assert bs.board.fen() == chess.STARTING_FEN
        assert len(bs.move_history) == 0

    def test_reset_to_custom_fen(self):
        fen = "8/8/8/4k3/8/8/8/4K3 w - - 0 1"
        bs = BoardState()
        _push(bs, "e4")
        bs.reset(fen=fen)
        assert bs.board.fen() == fen
        assert len(bs.move_history) == 0


class TestBoardStateGetLegalMovesSan:
    def test_starting_position(self):
        bs = BoardState()
        moves = bs.get_legal_moves_san()
        assert "e4" in moves
        assert "d4" in moves
        assert "Nf3" in moves
        assert len(moves) == 20  # 20 legal moves at start

    def test_after_move(self):
        bs = BoardState()
        _push(bs, "e4")
        moves = bs.get_legal_moves_san()
        assert "e5" in moves
        assert "Nf6" in moves


class TestBoardStateGameState:
    def test_full_move_count_start(self):
        bs = BoardState()
        assert bs.get_full_move_count() == 1

    def test_full_move_count_after_moves(self):
        bs = BoardState()
        _push(bs, "e4")
        _push(bs, "e5")
        assert bs.get_full_move_count() == 2

    def test_is_game_over_false_at_start(self):
        bs = BoardState()
        assert bs.is_game_over() is False

    def test_game_result_ongoing(self):
        bs = BoardState()
        assert bs.get_game_result() == "ONGOING"

    def test_checkmate_detection(self):
        # Scholar's mate
        bs = BoardState()
        for san in ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7"]:
            _push(bs, san)
        assert bs.is_game_over() is True
        assert bs.get_game_result() == "CHECKMATE"

    def test_stalemate_detection(self):
        # Known stalemate position: Black king on f8, White pawn on f7, White king on f6
        # Black has no legal moves but is not in check => stalemate
        fen = "5k2/5P2/5K2/8/8/8/8/8 b - - 0 1"
        bs = _make_board(fen=fen)
        assert bs.is_game_over() is True
        assert bs.get_game_result() == "STALEMATE"

    def test_insufficient_material(self):
        # K vs K
        fen = "8/8/8/4k3/8/8/8/4K3 w - - 0 1"
        bs = _make_board(fen=fen)
        assert bs.get_game_result() == "INSUFFICIENT_MATERIAL"


# =============================================================================
# FEN/PGN UTILITIES
# =============================================================================

class TestBoardStateFenPgn:
    def test_get_fen(self):
        bs = BoardState()
        assert bs.get_fen() == chess.STARTING_FEN

    def test_set_fen_valid(self):
        bs = BoardState()
        fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        result = bs.set_fen(fen)
        assert result is True
        assert bs.get_fen() == fen
        assert len(bs.move_history) == 0

    def test_set_fen_invalid(self):
        bs = BoardState()
        result = bs.set_fen("invalid fen string")
        assert result is False

    def test_get_pgn(self):
        bs = BoardState()
        _push(bs, "e4")
        _push(bs, "e5")
        pgn = bs.get_pgn(event="Test", white="Alice", black="Bob")
        assert "Alice" in pgn
        assert "Bob" in pgn
        assert "Test" in pgn
        assert "e4" in pgn

    def test_load_pgn_valid(self):
        pgn_str = '[Event "Test"]\n[White "W"]\n[Black "B"]\n[Result "*"]\n\n1. e4 e5 2. Nf3 *'
        bs = BoardState()
        result = bs.load_pgn(pgn_str)
        assert result is True
        assert len(bs.move_history) == 3  # e4, e5, Nf3

    def test_load_pgn_invalid(self):
        bs = BoardState()
        result = bs.load_pgn("")
        assert result is False

    def test_get_pgn_result_ongoing(self):
        bs = BoardState()
        _push(bs, "e4")
        pgn = bs.get_pgn()
        assert "*" in pgn

    def test_get_pgn_result_checkmate(self):
        bs = BoardState()
        for san in ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7"]:
            _push(bs, san)
        pgn = bs.get_pgn()
        assert "1-0" in pgn


# =============================================================================
# PIECE QUERY METHODS
# =============================================================================

class TestBoardStatePieceQueries:
    def test_get_piece_at_starting(self):
        bs = BoardState()
        assert bs.get_piece_at("e1") == "K"
        assert bs.get_piece_at("e8") == "k"
        assert bs.get_piece_at("e4") is None
        assert bs.get_piece_at("a2") == "P"

    def test_get_piece_at_invalid_square(self):
        bs = BoardState()
        assert bs.get_piece_at("z9") is None

    def test_get_all_pieces(self):
        bs = BoardState()
        pieces = bs.get_all_pieces()
        assert len(pieces) == 32
        assert pieces["e1"] == "K"
        assert pieces["e8"] == "k"
        assert pieces["a1"] == "R"
        assert pieces["h8"] == "r"

    def test_get_attacked_squares_white(self):
        bs = BoardState()
        attacked = bs.get_attacked_squares(chess.WHITE)
        # White pawns attack rank 3, knights attack some squares
        assert "d3" in attacked  # c2 pawn attacks d3
        assert len(attacked) > 0

    def test_get_attacked_squares_black(self):
        bs = BoardState()
        attacked = bs.get_attacked_squares(chess.BLACK)
        assert "d6" in attacked
        assert len(attacked) > 0


# =============================================================================
# CLONE AND REPR
# =============================================================================

class TestBoardStateCloneRepr:
    def test_clone_creates_independent_copy(self):
        bs = BoardState()
        _push(bs, "e4")
        clone = bs.clone()
        _push(clone, "e5")
        assert len(bs.move_history) == 1
        assert len(clone.move_history) == 2

    def test_clone_preserves_position(self):
        bs = BoardState()
        _push(bs, "e4")
        clone = bs.clone()
        assert clone.get_fen() == bs.get_fen()

    def test_repr(self):
        bs = BoardState()
        r = repr(bs)
        assert "BoardState" in r
        assert "moves=0" in r

    def test_str(self):
        bs = BoardState()
        s = str(bs)
        # Unicode board representation
        assert len(s) > 0


# =============================================================================
# ADVANCED ANALYSIS
# =============================================================================

class TestBoardStateAnalyzePositionAdvanced:
    def test_starting_position_analysis(self):
        bs = BoardState()
        analysis = bs.analyze_position_advanced()
        assert isinstance(analysis, AdvancedPositionAnalysis)
        assert analysis.material_balance == 0
        assert analysis.game_phase == GamePhase.OPENING

    def test_analysis_caching(self):
        bs = BoardState()
        a1 = bs.analyze_position_advanced(use_cache=True)
        a2 = bs.analyze_position_advanced(use_cache=True)
        assert a1 is a2  # Same object from cache

    def test_analysis_no_cache(self):
        bs = BoardState()
        a1 = bs.analyze_position_advanced(use_cache=False)
        a2 = bs.analyze_position_advanced(use_cache=False)
        # Different objects, same values
        assert a1.material_balance == a2.material_balance

    def test_material_imbalance(self):
        # White up a queen (black has no queen)
        fen = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        bs = _make_board(fen=fen)
        analysis = bs.analyze_position_advanced()
        assert analysis.material_balance > 0  # White ahead

    def test_endgame_detection(self):
        # K + R vs K endgame
        fen = "8/8/8/4k3/8/8/8/4K2R w - - 0 1"
        bs = _make_board(fen=fen)
        analysis = bs.analyze_position_advanced()
        assert analysis.game_phase in (GamePhase.ENDGAME, GamePhase.PURE_ENDGAME)


class TestBoardStateDetectGamePhase:
    def test_opening_phase(self):
        bs = BoardState()
        phase = bs._detect_game_phase()
        assert phase == GamePhase.OPENING

    def test_endgame_phase(self):
        fen = "8/8/8/4k3/8/8/4K3/4R3 w - - 0 50"
        bs = _make_board(fen=fen)
        phase = bs._detect_game_phase()
        assert phase in (GamePhase.ENDGAME, GamePhase.PURE_ENDGAME)


class TestBoardStateDetectPositionType:
    def test_starting_position_type(self):
        bs = BoardState()
        pt = bs._detect_position_type()
        assert isinstance(pt, PositionType)

    def test_open_position(self):
        # Position with many open files
        fen = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
        bs = _make_board(fen=fen)
        pt = bs._detect_position_type()
        assert pt == PositionType.OPEN


class TestBoardStateMaterialBalance:
    def test_equal_material(self):
        bs = BoardState()
        balance = bs._calculate_material_balance()
        assert balance == 0

    def test_white_ahead(self):
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBN1 w Qkq - 0 1"
        bs = _make_board(fen=fen)
        balance = bs._calculate_material_balance()
        assert balance < 0  # White missing a rook

    def test_material_positive_when_white_up(self):
        # White has extra knight (black missing g8 knight)
        fen = "rnbqkb1r/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        bs = _make_board(fen=fen)
        balance = bs._calculate_material_balance()
        assert balance > 0  # White ahead


class TestBoardStateKingSafety:
    def test_starting_position_king_safety(self):
        bs = BoardState()
        ks = bs._analyze_king_safety(chess.WHITE)
        assert isinstance(ks, KingSafety)
        assert ks.king_square == chess.E1
        assert ks.is_castled is False

    def test_castled_king(self):
        # White kingside castled
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQ1RK1 w kq - 0 1"
        bs = _make_board(fen=fen)
        ks = bs._analyze_king_safety(chess.WHITE)
        assert ks.is_castled is True
        assert ks.castling_side == CastlingStatus.KINGSIDE


class TestBoardStatePawnStructure:
    def test_starting_pawn_structure(self):
        bs = BoardState()
        psa = bs._analyze_pawn_structure(chess.WHITE)
        assert isinstance(psa, PawnStructureAnalysis)
        assert len(psa.doubled_pawns) == 0
        assert len(psa.isolated_pawns) == 0
        assert psa.pawn_islands == 1  # All connected

    def test_doubled_pawns(self):
        # White has doubled pawns on e-file
        fen = "rnbqkbnr/pppppppp/8/8/4P3/4P3/PPPP1PPP/RNBQKBNR w KQkq - 0 1"
        bs = _make_board(fen=fen)
        psa = bs._analyze_pawn_structure(chess.WHITE)
        assert len(psa.doubled_pawns) > 0

    def test_isolated_pawn(self):
        # Isolated a-pawn (no b-pawn)
        fen = "rnbqkbnr/pppppppp/8/8/8/8/P2PPPPP/RNBQKBNR w KQkq - 0 1"
        bs = _make_board(fen=fen)
        psa = bs._analyze_pawn_structure(chess.WHITE)
        assert len(psa.isolated_pawns) > 0


class TestBoardStateSpaceMobility:
    def test_space_calculation(self):
        bs = BoardState()
        ws, bsp = bs._calculate_space()
        assert ws > 0
        assert bsp > 0

    def test_mobility_calculation(self):
        bs = BoardState()
        wm, bm = bs._calculate_mobility()
        assert wm == 20  # 20 legal moves at start for white
        assert bm == 20  # 20 legal moves for black


class TestBoardStateTensionComplexity:
    def test_tension_starting_position(self):
        bs = BoardState()
        tension = bs._calculate_tension()
        assert tension >= 0.0
        assert tension <= 100.0

    def test_complexity_starting_position(self):
        bs = BoardState()
        phase = bs._detect_game_phase()
        tension = bs._calculate_tension()
        wm, bm = bs._calculate_mobility()
        complexity = bs._calculate_complexity(phase, tension, wm + bm)
        assert complexity >= 0.0
        assert complexity <= 100.0


# =============================================================================
# POSITION CACHE
# =============================================================================

class TestPositionCache:
    def test_cache_populates(self):
        bs = BoardState()
        bs.analyze_position_advanced(use_cache=True)
        assert len(bs._position_cache) == 1

    def test_cache_eviction(self):
        bs = BoardState()
        bs._max_position_cache = 2
        # Analyze 3 different positions
        bs.analyze_position_advanced(use_cache=True)
        _push(bs, "e4")
        bs.analyze_position_advanced(use_cache=True)
        _push(bs, "e5")
        bs.analyze_position_advanced(use_cache=True)
        assert len(bs._position_cache) <= 2

    def test_cache_clears_on_reset(self):
        bs = BoardState()
        bs.analyze_position_advanced(use_cache=True)
        bs.reset()
        assert len(bs._position_cache) == 0
