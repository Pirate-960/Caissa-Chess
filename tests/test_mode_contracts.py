from core.generator import CaissaGenerator


def test_extract_result_marker_terminal():
    pgn = '[Event "x"]\n[Result "1-0"]\n\n1. e4 e5 1-0'
    assert CaissaGenerator._extract_result_marker(pgn) == "1-0"


def test_extract_result_marker_non_terminal():
    pgn = '[Event "x"]\n[Result "*"]\n\n1. e4 e5 *'
    assert CaissaGenerator._extract_result_marker(pgn) == "*"
