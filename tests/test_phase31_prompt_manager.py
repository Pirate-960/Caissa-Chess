"""
tests/test_phase31_prompt_manager.py

Tests for Phase 3.1 prompt manager enhancements:
- HistoricalPlayer personalities
- NarrativeArc templates
- AdvancedGameContext
- Multi-stage prompts
"""

import unittest

from core.prompt_manager import (
    PromptManager,
    GameContext,
    GameEra,
    GameTheme,
    HistoricalPlayer,
    NarrativeArc,
    PromptStage,
    DifficultyLevel,
    PlayerPersonality,
    AdvancedGameContext,
    NarrativeTemplate,
    StagePrompt,
)


class TestHistoricalPlayer(unittest.TestCase):
    """Tests for HistoricalPlayer enum."""

    def test_all_players_defined(self):
        """All historical players should be defined."""
        players = [
            HistoricalPlayer.MORPHY,
            HistoricalPlayer.ANDERSSEN,
            HistoricalPlayer.TAL,
            HistoricalPlayer.CAPABLANCA,
            HistoricalPlayer.FISCHER,
            HistoricalPlayer.KASPAROV,
            HistoricalPlayer.KARPOV,
            HistoricalPlayer.CARLSEN,
            HistoricalPlayer.ALPHA_ZERO,
        ]
        for player in players:
            self.assertIsNotNone(player.value)

    def test_player_values_are_names(self):
        """Player values should be full names."""
        self.assertEqual(HistoricalPlayer.TAL.value, "Mikhail Tal")
        self.assertEqual(HistoricalPlayer.FISCHER.value, "Bobby Fischer")


class TestNarrativeArc(unittest.TestCase):
    """Tests for NarrativeArc enum."""

    def test_all_arcs_defined(self):
        """All narrative arcs should be defined."""
        arcs = [
            NarrativeArc.BLITZKRIEG,
            NarrativeArc.COMEBACK,
            NarrativeArc.SLOW_SQUEEZE,
            NarrativeArc.BRILLIANCY,
            NarrativeArc.PERFECT_TECHNIQUE,
        ]
        for arc in arcs:
            self.assertIsNotNone(arc.value)


class TestDifficultyLevel(unittest.TestCase):
    """Tests for DifficultyLevel enum."""

    def test_all_levels_defined(self):
        """All difficulty levels should be defined."""
        levels = [
            DifficultyLevel.BEGINNER,
            DifficultyLevel.INTERMEDIATE,
            DifficultyLevel.ADVANCED,
            DifficultyLevel.MASTER,
            DifficultyLevel.GRANDMASTER,
        ]
        self.assertEqual(len(levels), 5)


class TestPlayerPersonality(unittest.TestCase):
    """Tests for PlayerPersonality dataclass."""

    def test_personality_creation(self):
        """PlayerPersonality should be created correctly."""
        personality = PlayerPersonality(
            player=HistoricalPlayer.TAL,
            opening_repertoire=["Sicilian Najdorf", "King's Indian"],
            style_description="The Magician from Riga",
            aggression_baseline=9,
            risk_tolerance=10,
        )
        self.assertEqual(personality.player, HistoricalPlayer.TAL)
        self.assertEqual(personality.aggression_baseline, 9)

    def test_to_prompt_injection(self):
        """to_prompt_injection should generate valid text."""
        personality = PlayerPersonality(
            player=HistoricalPlayer.CAPABLANCA,
            opening_repertoire=["Queen's Gambit", "Ruy Lopez"],
            tactical_tendencies=["Simple but deadly"],
            style_description="The Chess Machine",
            aggression_baseline=4,
        )
        injection = personality.to_prompt_injection()
        self.assertIn("José Raúl Capablanca", injection)
        self.assertIn("Chess Machine", injection)
        self.assertIn("Queen's Gambit", injection)


class TestAdvancedGameContext(unittest.TestCase):
    """Tests for AdvancedGameContext dataclass."""

    def test_inherits_from_game_context(self):
        """AdvancedGameContext should inherit GameContext fields."""
        context = AdvancedGameContext(
            era=GameEra.ROMANTIC,
            theme=GameTheme.QUEEN_SACRIFICE,
            white_player="White",
            black_player="Black",
            aggression_score=7,
            narrative_arc=NarrativeArc.BRILLIANCY,
            difficulty=DifficultyLevel.ADVANCED,
        )
        self.assertEqual(context.era, GameEra.ROMANTIC)
        self.assertEqual(context.narrative_arc, NarrativeArc.BRILLIANCY)
        self.assertEqual(context.difficulty, DifficultyLevel.ADVANCED)

    def test_to_dict(self):
        """to_dict should return proper dictionary."""
        context = AdvancedGameContext(
            era=GameEra.NEURAL,
            difficulty=DifficultyLevel.GRANDMASTER,
            target_beauty_score=85.0,
        )
        result = context.to_dict()
        # Era value comes from GameEra enum's actual value
        self.assertIn("Neural", result["era"])
        self.assertEqual(result["difficulty"], "grandmaster")
        self.assertEqual(result["target_beauty_score"], 85.0)


class TestPromptManagerPersonalities(unittest.TestCase):
    """Tests for PromptManager personality features."""

    def setUp(self):
        """Set up PromptManager."""
        self.manager = PromptManager()

    def test_player_personalities_database(self):
        """PLAYER_PERSONALITIES should have all major players."""
        personalities = self.manager.PLAYER_PERSONALITIES
        self.assertIn(HistoricalPlayer.TAL, personalities)
        self.assertIn(HistoricalPlayer.CAPABLANCA, personalities)
        self.assertIn(HistoricalPlayer.KASPAROV, personalities)
        self.assertIn(HistoricalPlayer.ALPHA_ZERO, personalities)

    def test_get_personality(self):
        """get_personality should return PlayerPersonality."""
        personality = self.manager.get_personality(HistoricalPlayer.TAL)
        self.assertIsInstance(personality, PlayerPersonality)
        self.assertEqual(personality.player, HistoricalPlayer.TAL)
        self.assertGreater(personality.aggression_baseline, 5)  # Tal is aggressive

    def test_get_personality_unknown_player(self):
        """get_personality should return default for unknown player."""
        # Create a mock enum value
        personality = self.manager.get_personality(HistoricalPlayer.STEINITZ)
        self.assertIsInstance(personality, PlayerPersonality)


class TestPromptManagerNarratives(unittest.TestCase):
    """Tests for PromptManager narrative features."""

    def setUp(self):
        """Set up PromptManager."""
        self.manager = PromptManager()

    def test_narrative_templates_database(self):
        """NARRATIVE_TEMPLATES should have all arcs."""
        templates = self.manager.NARRATIVE_TEMPLATES
        self.assertIn(NarrativeArc.BLITZKRIEG, templates)
        self.assertIn(NarrativeArc.COMEBACK, templates)
        self.assertIn(NarrativeArc.BRILLIANCY, templates)

    def test_get_narrative_template(self):
        """get_narrative_template should return NarrativeTemplate."""
        template = self.manager.get_narrative_template(NarrativeArc.BRILLIANCY)
        self.assertIsInstance(template, NarrativeTemplate)
        self.assertEqual(template.arc, NarrativeArc.BRILLIANCY)
        self.assertIn("brilliant", template.key_moments[0].lower())

    def test_narrative_template_to_prompt(self):
        """NarrativeTemplate should generate prompt text."""
        template = self.manager.NARRATIVE_TEMPLATES[NarrativeArc.BLITZKRIEG]
        prompt = template.to_prompt_section()
        self.assertIn("Blitzkrieg", prompt)
        self.assertIn("fast", prompt.lower())


class TestPromptManagerAdvancedMethods(unittest.TestCase):
    """Tests for PromptManager advanced prompt generation."""

    def setUp(self):
        """Set up PromptManager."""
        self.manager = PromptManager()

    def test_build_system_prompt_advanced(self):
        """build_system_prompt_advanced should include personalities."""
        white_personality = self.manager.get_personality(HistoricalPlayer.TAL)
        context = AdvancedGameContext(
            era=GameEra.SOVIET,
            white_player="Tal",
            black_player="Opponent",
            white_personality=white_personality,
            narrative_arc=NarrativeArc.BRILLIANCY,
            difficulty=DifficultyLevel.MASTER,
        )
        prompt = self.manager.build_system_prompt_advanced(context)
        self.assertIn("Mikhail Tal", prompt)
        self.assertIn("Brilliancy", prompt)
        self.assertIn("Master", prompt)

    def test_build_multi_stage_prompts(self):
        """build_multi_stage_prompts should return stage prompts."""
        context = AdvancedGameContext(
            era=GameEra.ROMANTIC,
            narrative_arc=NarrativeArc.BLITZKRIEG,
        )
        stages = self.manager.build_multi_stage_prompts(context)
        self.assertIsInstance(stages, list)
        self.assertGreater(len(stages), 0)
        
        # Check first stage
        first_stage = stages[0]
        self.assertIsInstance(first_stage, StagePrompt)
        self.assertEqual(first_stage.stage, PromptStage.CONCEPT)

    def test_create_context_for_matchup(self):
        """create_context_for_matchup should create proper context."""
        context = self.manager.create_context_for_matchup(
            white_player=HistoricalPlayer.TAL,
            black_player=HistoricalPlayer.PETROSIAN,
            theme=GameTheme.ROOK_SACRIFICE,
            narrative=NarrativeArc.BRILLIANCY,
        )
        self.assertIsInstance(context, AdvancedGameContext)
        self.assertEqual(context.white_player, "Mikhail Tal")
        self.assertEqual(context.black_player, "Tigran Petrosian")
        self.assertIsNotNone(context.white_personality)
        self.assertIsNotNone(context.black_personality)

    def test_get_era_for_player(self):
        """get_era_for_player should return correct era."""
        self.assertEqual(
            self.manager.get_era_for_player(HistoricalPlayer.MORPHY),
            GameEra.ROMANTIC
        )
        self.assertEqual(
            self.manager.get_era_for_player(HistoricalPlayer.TAL),
            GameEra.SOVIET
        )
        self.assertEqual(
            self.manager.get_era_for_player(HistoricalPlayer.CARLSEN),
            GameEra.NEURAL
        )

    def test_build_commentary_prompt(self):
        """build_commentary_prompt should return system and user prompts."""
        pgn = "1. e4 e5 2. Nf3 Nc6 1-0"
        system, user = self.manager.build_commentary_prompt(
            pgn=pgn,
            style="educational",
            depth="detailed",
        )
        self.assertIn("commentator", system.lower())
        self.assertIn(pgn, user)


class TestDifficultyGuidelines(unittest.TestCase):
    """Tests for difficulty level guidelines."""

    def setUp(self):
        """Set up PromptManager."""
        self.manager = PromptManager()

    def test_all_difficulties_have_guidelines(self):
        """All difficulty levels should have guidelines."""
        for level in DifficultyLevel:
            self.assertIn(level, self.manager.DIFFICULTY_GUIDELINES)
            self.assertIsNotNone(self.manager.DIFFICULTY_GUIDELINES[level])

    def test_beginner_guidelines_are_simple(self):
        """Beginner guidelines should mention clear, instructive concepts."""
        guidelines = self.manager.DIFFICULTY_GUIDELINES[DifficultyLevel.BEGINNER]
        # Guidelines use "clear" and "instructive" rather than "simple"
        self.assertIn("clear", guidelines.lower())
        self.assertIn("beginner", guidelines.lower())


if __name__ == "__main__":
    unittest.main()
