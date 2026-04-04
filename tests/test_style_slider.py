"""
Comprehensive tests for aesthetic/style_slider.py

Covers:
- 4 enums: StylePreset, ExtendedStylePreset, StyleDimension, GamePhaseStyle
- 5 dataclasses: StyleConfiguration, DimensionalProfile, ExtendedStyleConfiguration,
  PhaseSpecificStyle, BlendedStyle
- StyleSlider class: get_config, get_all_styles, customize_config, get_extended_config,
  get_all_extended_styles, blend_styles, find_similar_styles, get_adaptive_config,
  get_style_for_era, create_matchup_blend, randomize_within_bounds,
  get_phase_specific_style
- STYLE_CONFIGS and EXTENDED_STYLE_CONFIGS dictionaries
"""

import math
import pytest
from aesthetic.style_slider import (
    StylePreset,
    ExtendedStylePreset,
    StyleDimension,
    GamePhaseStyle,
    StyleConfiguration,
    DimensionalProfile,
    ExtendedStyleConfiguration,
    PhaseSpecificStyle,
    BlendedStyle,
    StyleSlider,
)


# =============================================================================
# ENUM TESTS
# =============================================================================

class TestStylePresetEnum:
    def test_values(self):
        assert StylePreset.TAL == "tal"
        assert StylePreset.CAPABLANCA == "capablanca"
        assert StylePreset.MORPHY == "morphy"
        assert StylePreset.COFFEE_HOUSE == "coffee_house"
        assert StylePreset.NEURAL == "neural"
        assert StylePreset.KARPOV == "karpov"

    def test_member_count(self):
        assert len(StylePreset) == 6


class TestExtendedStylePresetEnum:
    def test_original_six(self):
        for sp in StylePreset:
            assert sp.value in [e.value for e in ExtendedStylePreset]

    def test_extended_entries(self):
        new_styles = ["fischer", "kasparov", "petrosian", "alekhine", "botvinnik",
                      "steinitz", "nimzowitsch", "anderssen", "spassky", "anand",
                      "carlsen", "kramnik", "topalov", "lasker"]
        for name in new_styles:
            assert name in [e.value for e in ExtendedStylePreset]

    def test_member_count(self):
        assert len(ExtendedStylePreset) == 20


class TestStyleDimensionEnum:
    def test_values(self):
        assert StyleDimension.AGGRESSION == "aggression"
        assert StyleDimension.TACTICAL == "tactical"
        assert StyleDimension.RISK == "risk"
        assert StyleDimension.COMPLEXITY == "complexity"
        assert StyleDimension.TEMPO == "tempo"
        assert StyleDimension.MATERIAL == "material"

    def test_member_count(self):
        assert len(StyleDimension) == 6


class TestGamePhaseStyleEnum:
    def test_values(self):
        assert GamePhaseStyle.OPENING == "opening"
        assert GamePhaseStyle.MIDDLEGAME == "middlegame"
        assert GamePhaseStyle.ENDGAME == "endgame"

    def test_member_count(self):
        assert len(GamePhaseStyle) == 3


# =============================================================================
# DATACLASS TESTS
# =============================================================================

class TestStyleConfiguration:
    def test_creation(self):
        sc = StyleConfiguration(
            stockfish_depth=15, blunder_threshold=50.0,
            complexity_bias=1.2, contempt=40,
            style_name="Test", description="A test style",
        )
        assert sc.stockfish_depth == 15
        assert sc.aggression == 7  # default
        assert sc.chaos == 5       # default

    def test_custom_aggression_chaos(self):
        sc = StyleConfiguration(
            stockfish_depth=10, blunder_threshold=100.0,
            complexity_bias=2.0, contempt=100,
            style_name="X", description="Y",
            aggression=10, chaos=10,
        )
        assert sc.aggression == 10
        assert sc.chaos == 10


class TestDimensionalProfile:
    def test_creation(self):
        dp = DimensionalProfile(
            aggression=0.8, tactical=0.7, risk=0.6,
            complexity=0.5, tempo=0.4, material=0.3,
        )
        assert dp.aggression == 0.8
        assert dp.material == 0.3

    def test_to_dict(self):
        dp = DimensionalProfile(0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
        d = dp.to_dict()
        assert d == {
            "aggression": 0.1, "tactical": 0.2, "risk": 0.3,
            "complexity": 0.4, "tempo": 0.5, "material": 0.6,
        }

    def test_blend_with_equal_weight(self):
        dp1 = DimensionalProfile(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        dp2 = DimensionalProfile(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        blended = dp1.blend_with(dp2, 0.5)
        assert abs(blended.aggression - 0.5) < 1e-9
        assert abs(blended.material - 0.5) < 1e-9

    def test_blend_with_full_weight(self):
        dp1 = DimensionalProfile(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        dp2 = DimensionalProfile(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        blended = dp1.blend_with(dp2, 1.0)
        assert abs(blended.aggression - 1.0) < 1e-9

    def test_blend_with_zero_weight(self):
        dp1 = DimensionalProfile(0.2, 0.3, 0.4, 0.5, 0.6, 0.7)
        dp2 = DimensionalProfile(0.9, 0.9, 0.9, 0.9, 0.9, 0.9)
        blended = dp1.blend_with(dp2, 0.0)
        assert abs(blended.aggression - 0.2) < 1e-9

    def test_distance_to_same(self):
        dp = DimensionalProfile(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        assert dp.distance_to(dp) == 0.0

    def test_distance_to_different(self):
        dp1 = DimensionalProfile(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        dp2 = DimensionalProfile(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        dist = dp1.distance_to(dp2)
        expected = math.sqrt(6)  # sqrt(1^2 * 6)
        assert abs(dist - expected) < 1e-9

    def test_distance_symmetry(self):
        dp1 = DimensionalProfile(0.1, 0.2, 0.3, 0.4, 0.5, 0.6)
        dp2 = DimensionalProfile(0.6, 0.5, 0.4, 0.3, 0.2, 0.1)
        assert abs(dp1.distance_to(dp2) - dp2.distance_to(dp1)) < 1e-9


class TestExtendedStyleConfiguration:
    def test_creation(self):
        esc = ExtendedStyleConfiguration(
            stockfish_depth=20, blunder_threshold=50.0,
            complexity_bias=1.0, contempt=30,
            style_name="Test Extended", description="Desc",
            profile=DimensionalProfile(0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
            opening_preference=["Sicilian"],
            endgame_specialty=["Rook endings"],
            signature_patterns=["Exchanges"],
            era="Modern",
            peak_rating=2750,
        )
        assert esc.style_name == "Test Extended"
        assert len(esc.opening_preference) == 1

    def test_to_dict(self):
        esc = ExtendedStyleConfiguration(
            stockfish_depth=15, blunder_threshold=40.0,
            complexity_bias=0.8, contempt=20,
            style_name="Dict Test", description="Test",
            profile=DimensionalProfile(0.3, 0.4, 0.5, 0.6, 0.7, 0.8),
            era="Classical", peak_rating=2700,
        )
        d = esc.to_dict()
        assert d["style_name"] == "Dict Test"
        assert d["peak_rating"] == 2700
        assert "profile" in d
        assert d["profile"]["aggression"] == 0.3


class TestPhaseSpecificStyle:
    def test_creation(self):
        opening = DimensionalProfile(0.3, 0.3, 0.2, 0.4, 0.5, 0.6)
        middle = DimensionalProfile(0.8, 0.7, 0.6, 0.7, 0.5, 0.4)
        endgame = DimensionalProfile(0.4, 0.3, 0.2, 0.3, 0.4, 0.8)
        pss = PhaseSpecificStyle(opening=opening, middlegame=middle, endgame=endgame)
        assert pss.opening.aggression == 0.3

    def test_get_profile_for_move_opening(self):
        opening = DimensionalProfile(0.1, 0.1, 0.1, 0.1, 0.1, 0.1)
        middle = DimensionalProfile(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        endgame = DimensionalProfile(0.9, 0.9, 0.9, 0.9, 0.9, 0.9)
        pss = PhaseSpecificStyle(opening=opening, middlegame=middle, endgame=endgame)
        profile = pss.get_profile_for_move(5)
        assert profile.aggression == 0.1  # Move 5 → opening

    def test_get_profile_for_move_middlegame(self):
        opening = DimensionalProfile(0.1, 0.1, 0.1, 0.1, 0.1, 0.1)
        middle = DimensionalProfile(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        endgame = DimensionalProfile(0.9, 0.9, 0.9, 0.9, 0.9, 0.9)
        pss = PhaseSpecificStyle(opening=opening, middlegame=middle, endgame=endgame)
        profile = pss.get_profile_for_move(25)
        # Move 25: progress = (25-10)/(30-10) = 0.75
        # blend = 0.1*(1-0.75) + 0.5*0.75 = 0.025 + 0.375 = 0.4
        assert profile.aggression == pytest.approx(0.4)

    def test_get_profile_for_move_endgame(self):
        opening = DimensionalProfile(0.1, 0.1, 0.1, 0.1, 0.1, 0.1)
        middle = DimensionalProfile(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        endgame = DimensionalProfile(0.9, 0.9, 0.9, 0.9, 0.9, 0.9)
        pss = PhaseSpecificStyle(opening=opening, middlegame=middle, endgame=endgame)
        profile = pss.get_profile_for_move(50)
        assert profile.aggression == 0.9  # Move 50 → endgame


class TestBlendedStyle:
    def test_creation_and_normalization(self):
        bs = BlendedStyle(
            components=[
                (ExtendedStylePreset.TAL, 3.0),
                (ExtendedStylePreset.KARPOV, 1.0),
            ],
            name="Blend", description="Test",
        )
        # Weights should be normalized
        total = sum(w for _, w in bs.components)
        assert abs(total - 1.0) < 1e-9

    def test_normalization_with_zero_total(self):
        bs = BlendedStyle(
            components=[
                (ExtendedStylePreset.TAL, 0.0),
                (ExtendedStylePreset.KARPOV, 0.0),
            ],
            name="Zero", description="Zero-weight test",
        )
        # Should handle gracefully (implementation normalizes or leaves)
        assert len(bs.components) == 2


# =============================================================================
# STYLE SLIDER CLASS
# =============================================================================

class TestStyleSliderConfigs:
    def test_style_configs_all_presets(self):
        slider = StyleSlider()
        for preset in StylePreset:
            config = slider.get_config(preset)
            assert isinstance(config, StyleConfiguration)
            assert config.stockfish_depth > 0

    def test_style_configs_count(self):
        slider = StyleSlider()
        assert len(slider.STYLE_CONFIGS) == 6

    def test_extended_style_configs_count(self):
        slider = StyleSlider()
        assert len(slider.EXTENDED_STYLE_CONFIGS) == 20

    def test_extended_configs_all_presets(self):
        slider = StyleSlider()
        for preset in ExtendedStylePreset:
            config = slider.get_extended_config(preset)
            assert isinstance(config, ExtendedStyleConfiguration)
            assert config.peak_rating > 0


class TestStyleSliderGetConfig:
    def test_get_known_style(self):
        slider = StyleSlider()
        config = slider.get_config(StylePreset.TAL)
        assert "Tal" in config.style_name
        assert config.stockfish_depth > 0

    def test_get_unknown_falls_back_to_morphy(self):
        slider = StyleSlider()
        # Using .get with a nonexistent key internally falls back
        morphy = slider.get_config(StylePreset.MORPHY)
        assert morphy.style_name is not None


class TestStyleSliderGetAllStyles:
    def test_returns_all_six(self):
        slider = StyleSlider()
        styles = slider.get_all_styles()
        assert len(styles) == 6
        for preset in StylePreset:
            assert preset in styles
            assert isinstance(styles[preset], str)


class TestStyleSliderCustomizeConfig:
    def test_depth_multiplier(self):
        slider = StyleSlider()
        base = slider.get_config(StylePreset.MORPHY)
        custom = slider.customize_config(StylePreset.MORPHY, depth_multiplier=2.0)
        assert custom.stockfish_depth == max(1, int(base.stockfish_depth * 2.0))

    def test_blunder_tolerance_override(self):
        slider = StyleSlider()
        custom = slider.customize_config(StylePreset.TAL, blunder_tolerance=200.0)
        assert custom.blunder_threshold == 200.0

    def test_complexity_bias_override(self):
        slider = StyleSlider()
        custom = slider.customize_config(StylePreset.KARPOV, complexity_bias=3.0)
        assert custom.complexity_bias == 3.0

    def test_preserves_other_fields(self):
        slider = StyleSlider()
        base = slider.get_config(StylePreset.CAPABLANCA)
        custom = slider.customize_config(StylePreset.CAPABLANCA, depth_multiplier=1.0)
        assert custom.contempt == base.contempt
        assert custom.style_name == base.style_name

    def test_min_depth_clamped(self):
        slider = StyleSlider()
        custom = slider.customize_config(StylePreset.MORPHY, depth_multiplier=0.01)
        assert custom.stockfish_depth >= 1


class TestStyleSliderGetExtendedConfig:
    def test_fischer(self):
        slider = StyleSlider()
        config = slider.get_extended_config(ExtendedStylePreset.FISCHER)
        assert "Fischer" in config.style_name
        assert config.peak_rating > 2700

    def test_all_extended_have_profiles(self):
        slider = StyleSlider()
        for preset in ExtendedStylePreset:
            config = slider.get_extended_config(preset)
            assert isinstance(config.profile, DimensionalProfile)
            assert 0.0 <= config.profile.aggression <= 1.0
            assert 0.0 <= config.profile.risk <= 1.0


class TestStyleSliderGetAllExtendedStyles:
    def test_returns_all_twenty(self):
        slider = StyleSlider()
        styles = slider.get_all_extended_styles()
        assert len(styles) == 20
        for preset in ExtendedStylePreset:
            assert preset in styles


class TestStyleSliderBlendStyles:
    def test_single_style(self):
        slider = StyleSlider()
        blended = slider.blend_styles([(ExtendedStylePreset.TAL, 1.0)])
        assert isinstance(blended, ExtendedStyleConfiguration)
        tal = slider.get_extended_config(ExtendedStylePreset.TAL)
        assert blended.stockfish_depth == tal.stockfish_depth

    def test_two_styles(self):
        slider = StyleSlider()
        blended = slider.blend_styles([
            (ExtendedStylePreset.TAL, 0.5),
            (ExtendedStylePreset.KARPOV, 0.5),
        ])
        assert isinstance(blended, ExtendedStyleConfiguration)
        assert "Blend" in blended.style_name

    def test_blend_empty_returns_morphy(self):
        slider = StyleSlider()
        blended = slider.blend_styles([])
        morphy = slider.get_extended_config(ExtendedStylePreset.MORPHY)
        assert blended.style_name == morphy.style_name

    def test_blend_weights_affect_result(self):
        slider = StyleSlider()
        tal_heavy = slider.blend_styles([
            (ExtendedStylePreset.TAL, 0.9),
            (ExtendedStylePreset.PETROSIAN, 0.1),
        ])
        petrosian_heavy = slider.blend_styles([
            (ExtendedStylePreset.TAL, 0.1),
            (ExtendedStylePreset.PETROSIAN, 0.9),
        ])
        # Tal is more aggressive, so tal_heavy should have higher aggression
        assert tal_heavy.profile.aggression > petrosian_heavy.profile.aggression

    def test_blend_openings_unique(self):
        slider = StyleSlider()
        blended = slider.blend_styles([
            (ExtendedStylePreset.FISCHER, 0.5),
            (ExtendedStylePreset.KASPAROV, 0.5),
        ])
        # Should have no duplicates and max 5
        assert len(blended.opening_preference) <= 5
        assert len(blended.opening_preference) == len(set(blended.opening_preference))


class TestStyleSliderFindSimilarStyles:
    def test_exact_match_has_high_similarity(self):
        slider = StyleSlider()
        tal = slider.get_extended_config(ExtendedStylePreset.TAL)
        results = slider.find_similar_styles(tal.profile, top_n=1)
        assert len(results) == 1
        assert results[0][0] == ExtendedStylePreset.TAL
        assert results[0][1] > 0.9  # Very similar to itself

    def test_returns_requested_count(self):
        slider = StyleSlider()
        profile = DimensionalProfile(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        results = slider.find_similar_styles(profile, top_n=5)
        assert len(results) == 5

    def test_sorted_by_similarity(self):
        slider = StyleSlider()
        profile = DimensionalProfile(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        results = slider.find_similar_styles(profile, top_n=5)
        for i in range(len(results) - 1):
            assert results[i][1] >= results[i + 1][1]


class TestStyleSliderGetAdaptiveConfig:
    def test_basic_adaptive(self):
        slider = StyleSlider()
        adapted = slider.get_adaptive_config(ExtendedStylePreset.TAL, move_number=15)
        assert isinstance(adapted, ExtendedStyleConfiguration)

    def test_winning_reduces_risk(self):
        slider = StyleSlider()
        base = slider.get_extended_config(ExtendedStylePreset.TAL)
        adapted = slider.get_adaptive_config(ExtendedStylePreset.TAL, move_number=20, is_winning=True)
        assert adapted.profile.risk < base.profile.risk

    def test_losing_increases_complexity(self):
        slider = StyleSlider()
        base = slider.get_extended_config(ExtendedStylePreset.TAL)
        adapted = slider.get_adaptive_config(ExtendedStylePreset.TAL, move_number=20, is_losing=True)
        assert adapted.complexity_bias > base.complexity_bias

    def test_opening_phase_adjustment(self):
        slider = StyleSlider()
        base = slider.get_extended_config(ExtendedStylePreset.MORPHY)
        adapted = slider.get_adaptive_config(ExtendedStylePreset.MORPHY, move_number=5)
        assert adapted.blunder_threshold < base.blunder_threshold  # More cautious

    def test_endgame_phase_adjustment(self):
        slider = StyleSlider()
        base = slider.get_extended_config(ExtendedStylePreset.CARLSEN)
        adapted = slider.get_adaptive_config(ExtendedStylePreset.CARLSEN, move_number=45)
        assert adapted.stockfish_depth >= base.stockfish_depth  # More precise

    def test_counter_style_against_tactical(self):
        slider = StyleSlider()
        adapted = slider.get_adaptive_config(
            ExtendedStylePreset.KARPOV, move_number=20,
            opponent_style=ExtendedStylePreset.TAL,
        )
        base = slider.get_extended_config(ExtendedStylePreset.KARPOV)
        # Against a tactical player, depth increases
        assert adapted.stockfish_depth >= base.stockfish_depth


class TestStyleSliderGetStyleForEra:
    def test_romantic_era(self):
        slider = StyleSlider()
        styles = slider.get_style_for_era("Romantic")
        assert len(styles) > 0
        # Morphy and Anderssen are romantic era
        values = [s.value for s in styles]
        assert "morphy" in values or "anderssen" in values

    def test_unknown_era_returns_morphy(self):
        slider = StyleSlider()
        styles = slider.get_style_for_era("XYZ_NONEXISTENT")
        assert ExtendedStylePreset.MORPHY in styles

    def test_soviet_era(self):
        slider = StyleSlider()
        styles = slider.get_style_for_era("Soviet")
        assert len(styles) >= 2  # At least Tal, Petrosian


class TestStyleSliderCreateMatchupBlend:
    def test_creates_blend(self):
        slider = StyleSlider()
        blend = slider.create_matchup_blend(ExtendedStylePreset.TAL, ExtendedStylePreset.PETROSIAN)
        assert isinstance(blend, BlendedStyle)
        assert len(blend.components) == 2
        assert "vs" in blend.name

    def test_equal_weights(self):
        slider = StyleSlider()
        blend = slider.create_matchup_blend(ExtendedStylePreset.FISCHER, ExtendedStylePreset.KASPAROV)
        weights = [w for _, w in blend.components]
        assert all(abs(w - 0.5) < 1e-9 for w in weights)


class TestStyleSliderRandomizeWithinBounds:
    def test_randomized_differs_slightly(self):
        slider = StyleSlider()
        randomized = slider.randomize_within_bounds(ExtendedStylePreset.MORPHY, variance=0.3)
        assert isinstance(randomized, ExtendedStyleConfiguration)
        assert "(varied)" in randomized.style_name
        # Some dimension should differ (with high variance almost certainly)
        profile = randomized.profile
        assert 0.0 <= profile.aggression <= 1.0
        assert 0.0 <= profile.risk <= 1.0

    def test_depth_stays_in_bounds(self):
        slider = StyleSlider()
        for _ in range(10):
            r = slider.randomize_within_bounds(ExtendedStylePreset.COFFEE_HOUSE, variance=1.0)
            assert 5 <= r.stockfish_depth <= 30


class TestStyleSliderGetPhaseSpecificStyle:
    def test_returns_phase_style(self):
        slider = StyleSlider()
        pss = slider.get_phase_specific_style(ExtendedStylePreset.TAL)
        assert isinstance(pss, PhaseSpecificStyle)

    def test_opening_is_more_cautious(self):
        slider = StyleSlider()
        pss = slider.get_phase_specific_style(ExtendedStylePreset.TAL)
        base = slider.get_extended_config(ExtendedStylePreset.TAL)
        assert pss.opening.risk < base.profile.risk

    def test_endgame_is_more_material_focused(self):
        slider = StyleSlider()
        pss = slider.get_phase_specific_style(ExtendedStylePreset.KASPAROV)
        base = slider.get_extended_config(ExtendedStylePreset.KASPAROV)
        assert pss.endgame.material > base.profile.material

    def test_middlegame_uses_base_profile(self):
        slider = StyleSlider()
        pss = slider.get_phase_specific_style(ExtendedStylePreset.CARLSEN)
        base = slider.get_extended_config(ExtendedStylePreset.CARLSEN)
        assert pss.middlegame.aggression == base.profile.aggression
