"""Tests to verify tournament config loads correctly."""

from config_manager import cfg


def _get_field(container, key):
    """Read from dataclass-style objects and dicts."""
    if isinstance(container, dict):
        return container[key]
    return getattr(container, key)


def test_tournament_config_exists():
    assert hasattr(cfg, "tournament")


def test_tournament_basic_defaults():
    tournament = cfg.tournament
    assert _get_field(tournament, "default_format")
    assert _get_field(tournament, "default_time_control")
    assert isinstance(_get_field(tournament, "default_rounds"), int)


def test_tournament_nested_sections():
    tournament = cfg.tournament
    elo = _get_field(tournament, "elo")
    match = _get_field(tournament, "match")
    commentary = _get_field(tournament, "commentary")
    output = _get_field(tournament, "output")

    assert _get_field(elo, "initial_rating") > 0
    assert _get_field(match, "max_moves") > 0
    assert isinstance(_get_field(commentary, "enabled"), bool)
    assert _get_field(output, "output_dir")


def test_tournament_time_per_move_contains_rapid():
    tournament = cfg.tournament
    tpm = _get_field(tournament, "time_per_move")
    assert isinstance(tpm, dict)
    assert "rapid" in tpm
    assert tpm["rapid"] > 0
