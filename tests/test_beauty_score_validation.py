"""
Pytest validation for beauty-score analysis pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from config_manager import cfg
from core.elo_calculator import GameResult
from core.match_analyzer import MatchAnalyzer
from core.match_engine import MatchResult, MoveRecord, TerminationReason
from core.tournament_player import TournamentPlayer
from export.tournament_exporter import MatchExporter


def _stockfish_available() -> bool:
    return Path(cfg.stockfish.path).exists()


def _build_mock_match() -> MatchResult:
    import chess

    board = chess.Board()

    def make_move(move_num: int, color: str, san_str: str) -> MoveRecord:
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
            is_capture=False,
            is_promotion=False,
        )

    moves = [
        make_move(1, "white", "e4"),
        make_move(1, "black", "e5"),
        make_move(2, "white", "Nf3"),
        make_move(2, "black", "Nc6"),
        make_move(3, "white", "Bc4"),
        make_move(3, "black", "Bc5"),
    ]

    white_player = TournamentPlayer(name="TestWhite", provider_name="test")
    black_player = TournamentPlayer(name="TestBlack", provider_name="test")

    return MatchResult(
        match_id="test-beauty-001",
        white=white_player,
        black=black_player,
        moves=moves,
        result=GameResult.WHITE_WINS,
        termination=TerminationReason.CHECKMATE,
        final_fen=board.fen(),
        total_moves=len(moves),
    )


def test_config_uses_stockfish_path_not_binary_path():
    assert hasattr(cfg.stockfish, "path")
    with pytest.raises(AttributeError):
        _ = cfg.stockfish.binary_path


def test_main_uses_path_attribute():
    main_py_path = Path(__file__).parent.parent / "main.py"
    content = main_py_path.read_text(encoding="utf-8")
    assert "getattr(cfg.stockfish, 'path', None)" in content
    assert "getattr(cfg.stockfish, 'binary_path', None)" not in content


@pytest.mark.asyncio
@pytest.mark.skipif(not _stockfish_available(), reason="Stockfish not available")
async def test_beauty_calculation():
    match = _build_mock_match()
    analyzer = MatchAnalyzer(
        stockfish_path=cfg.stockfish.path,
        commentary_provider=None,
        enable_commentary=False,
    )
    try:
        analysis = await analyzer.analyze_match(match)
        assert analysis is not None
        assert 0 <= analysis.beauty_score <= 100
        assert len(analysis.move_annotations) == len(match.moves)
    finally:
        analyzer.__exit__(None, None, None)


@pytest.mark.asyncio
@pytest.mark.skipif(not _stockfish_available(), reason="Stockfish not available")
async def test_export_with_analysis():
    match = _build_mock_match()

    exporter_no_analysis = MatchExporter(match_result=match, match_analysis=None, include_elo=True)
    json_no_analysis = exporter_no_analysis.export_json()
    assert '"beauty_score": 0.0' in json_no_analysis or '"beauty_score":0.0' in json_no_analysis

    analyzer = MatchAnalyzer(
        stockfish_path=cfg.stockfish.path,
        commentary_provider=None,
        enable_commentary=False,
    )
    try:
        analysis = await analyzer.analyze_match(match)
        exporter_with_analysis = MatchExporter(
            match_result=match,
            match_analysis=analysis,
            include_elo=True,
        )
        json_with_analysis = exporter_with_analysis.export_json()
        assert '"beauty_score": 0.0' not in json_with_analysis
    finally:
        analyzer.__exit__(None, None, None)
