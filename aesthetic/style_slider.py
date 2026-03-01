"""
aesthetic/style_slider.py

Maps user-selected game styles to engine parameters.
The "Style Controller" that personalizes game generation.

PHASE 3.1 ENHANCEMENTS:
- Extended player profiles (15+ historical styles)
- Style blending (mix multiple styles)
- Adaptive configuration based on game phase
- Opening-specific style adjustments
- Era-appropriate style recommendations
- Dynamic parameter adjustment during game
- Style evolution tracking

Original functionality 100% preserved.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Callable
from enum import Enum
import logging
import random

logger = logging.getLogger(__name__)


# =============================================================================
# ORIGINAL ENUMS AND DATACLASSES (100% PRESERVED)
# =============================================================================

class StylePreset(str, Enum):
    """Predefined game styles."""
    TAL = "tal"                      # Intuitive, risky, attacking
    CAPABLANCA = "capablanca"        # Perfect, positional, clinical
    MORPHY = "morphy"                # Classical, attacking, sound
    COFFEE_HOUSE = "coffee_house"    # Gambits, tricks, complications
    NEURAL = "neural"                # AlphaZero-like, alien logic
    KARPOV = "karpov"                # Positional squeeze, silent strength


@dataclass
class StyleConfiguration:
    """Engine parameters for a given style."""
    stockfish_depth: int
    blunder_threshold: float          # Allowed eval drop in centipawns
    complexity_bias: float            # 1.0 = normal, >1 = prefer complex positions
    contempt: int                     # 0-200, higher = engine fights harder
    style_name: str
    description: str
    aggression: int = 7              # 1-10, higher = more attacking
    chaos: int = 5                   # 1-10, higher = more surprising


# =============================================================================
# PHASE 3.1: EXTENDED STYLE SYSTEM
# =============================================================================

class ExtendedStylePreset(str, Enum):
    """Extended historical player styles."""
    # Original 6 (mapped to StylePreset)
    TAL = "tal"
    CAPABLANCA = "capablanca"
    MORPHY = "morphy"
    COFFEE_HOUSE = "coffee_house"
    NEURAL = "neural"
    KARPOV = "karpov"
    
    # New styles
    FISCHER = "fischer"              # Perfect technical chess
    KASPAROV = "kasparov"            # Dynamic, powerful attacks
    PETROSIAN = "petrosian"          # Prophylactic, defensive master
    ALEKHINE = "alekhine"            # Brilliant combinations
    BOTVINNIK = "botvinnik"          # Scientific, methodical
    STEINITZ = "steinitz"            # First positional player
    NIMZOWITSCH = "nimzowitsch"      # Hypermodern revolutionary
    ANDERSSEN = "anderssen"          # Romantic era sacrifices
    SPASSKY = "spassky"              # Universal, balanced
    ANAND = "anand"                  # Rapid, intuitive
    CARLSEN = "carlsen"              # Grinding, endgame master
    KRAMNIK = "kramnik"              # Strategic depth
    TOPALOV = "topalov"              # Aggressive, dynamic
    LASKER = "lasker"                # Practical, psychological


class StyleDimension(str, Enum):
    """Style dimensions for blending."""
    AGGRESSION = "aggression"         # Attacking vs defensive
    TACTICAL = "tactical"             # Tactics vs positional
    RISK = "risk"                     # Risk-taking vs safe
    COMPLEXITY = "complexity"         # Complex vs simple
    TEMPO = "tempo"                   # Rapid play vs slow maneuvering
    MATERIAL = "material"             # Material-focused vs initiative


class GamePhaseStyle(str, Enum):
    """Different styles for different game phases."""
    OPENING = "opening"
    MIDDLEGAME = "middlegame"
    ENDGAME = "endgame"


@dataclass
class DimensionalProfile:
    """Multi-dimensional style profile."""
    aggression: float = 0.5       # 0 = defensive, 1 = attacking
    tactical: float = 0.5         # 0 = positional, 1 = tactical
    risk: float = 0.5             # 0 = safe, 1 = risky
    complexity: float = 0.5       # 0 = simple, 1 = complex
    tempo: float = 0.5            # 0 = slow, 1 = rapid
    material: float = 0.5         # 0 = material, 1 = initiative
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "aggression": self.aggression,
            "tactical": self.tactical,
            "risk": self.risk,
            "complexity": self.complexity,
            "tempo": self.tempo,
            "material": self.material,
        }
    
    def blend_with(self, other: "DimensionalProfile", ratio: float = 0.5) -> "DimensionalProfile":
        """Blend this profile with another."""
        return DimensionalProfile(
            aggression=self.aggression * (1 - ratio) + other.aggression * ratio,
            tactical=self.tactical * (1 - ratio) + other.tactical * ratio,
            risk=self.risk * (1 - ratio) + other.risk * ratio,
            complexity=self.complexity * (1 - ratio) + other.complexity * ratio,
            tempo=self.tempo * (1 - ratio) + other.tempo * ratio,
            material=self.material * (1 - ratio) + other.material * ratio,
        )
    
    def distance_to(self, other: "DimensionalProfile") -> float:
        """Calculate Euclidean distance to another profile."""
        return (
            (self.aggression - other.aggression) ** 2 +
            (self.tactical - other.tactical) ** 2 +
            (self.risk - other.risk) ** 2 +
            (self.complexity - other.complexity) ** 2 +
            (self.tempo - other.tempo) ** 2 +
            (self.material - other.material) ** 2
        ) ** 0.5


@dataclass
class ExtendedStyleConfiguration(StyleConfiguration):
    """Enhanced style configuration with dimensional profile."""
    # Inherits: stockfish_depth, blunder_threshold, complexity_bias, contempt, style_name, description
    profile: DimensionalProfile = field(default_factory=DimensionalProfile)
    opening_preference: List[str] = field(default_factory=list)
    endgame_specialty: List[str] = field(default_factory=list)
    signature_patterns: List[str] = field(default_factory=list)
    era: str = "Modern"
    peak_rating: int = 2700
    
    def to_dict(self) -> Dict:
        return {
            "stockfish_depth": self.stockfish_depth,
            "blunder_threshold": self.blunder_threshold,
            "complexity_bias": self.complexity_bias,
            "contempt": self.contempt,
            "style_name": self.style_name,
            "description": self.description,
            "profile": self.profile.to_dict(),
            "opening_preference": self.opening_preference,
            "endgame_specialty": self.endgame_specialty,
            "signature_patterns": self.signature_patterns,
            "era": self.era,
            "peak_rating": self.peak_rating,
        }


@dataclass
class PhaseSpecificStyle:
    """Style parameters that vary by game phase."""
    opening: DimensionalProfile
    middlegame: DimensionalProfile
    endgame: DimensionalProfile
    transition_points: Tuple[int, int] = (10, 30)  # Move numbers for phase transitions
    
    def get_profile_for_move(self, move_number: int) -> DimensionalProfile:
        """Get the appropriate profile for a move number."""
        if move_number <= self.transition_points[0]:
            return self.opening
        elif move_number >= self.transition_points[1]:
            return self.endgame
        else:
            # Interpolate between opening and endgame
            progress = (move_number - self.transition_points[0]) / (
                self.transition_points[1] - self.transition_points[0]
            )
            return self.opening.blend_with(self.middlegame, progress)


@dataclass
class BlendedStyle:
    """A blend of multiple style presets."""
    components: List[Tuple[ExtendedStylePreset, float]]  # (style, weight) pairs
    name: str = "Custom Blend"
    description: str = ""
    
    def __post_init__(self):
        # Normalize weights
        total_weight = sum(w for _, w in self.components)
        if total_weight > 0:
            self.components = [(s, w / total_weight) for s, w in self.components]


# =============================================================================
# ORIGINAL CLASS (100% PRESERVED) + PHASE 3.1 ENHANCEMENTS
# =============================================================================

class StyleSlider:
    """
    Translates game styles into concrete engine parameters.
    
    PHASE 3.1: Enhanced with style blending, dimensional profiles,
    phase-specific adjustments, and adaptive configuration.
    """

    # ORIGINAL STYLE CONFIGS (100% PRESERVED)
    STYLE_CONFIGS = {
        StylePreset.TAL: StyleConfiguration(
            stockfish_depth=10,
            blunder_threshold=200.0,
            complexity_bias=1.5,
            contempt=50,
            style_name="The Tal",
            description="Intuitive attacks, even if unsound. Complications over precision.",
            aggression=10,
            chaos=9,
        ),
        StylePreset.CAPABLANCA: StyleConfiguration(
            stockfish_depth=20,
            blunder_threshold=30.0,
            complexity_bias=0.5,
            contempt=0,
            style_name="The Capablanca",
            description="Positional perfection. Every move justified. Pure strength.",
            aggression=3,
            chaos=2,
        ),
        StylePreset.MORPHY: StyleConfiguration(
            stockfish_depth=15,
            blunder_threshold=50.0,
            complexity_bias=1.2,
            contempt=30,
            style_name="The Morphy",
            description="Classical attacking chess. Sound sacrifices for the initiative.",
            aggression=8,
            chaos=6,
        ),
        StylePreset.COFFEE_HOUSE: StyleConfiguration(
            stockfish_depth=5,
            blunder_threshold=500.0,
            complexity_bias=2.0,
            contempt=100,
            style_name="The Coffee House",
            description="Gambits, tricks, hope-chess. Embrace the chaos.",
            aggression=9,
            chaos=10,
        ),
        StylePreset.NEURAL: StyleConfiguration(
            stockfish_depth=25,
            blunder_threshold=30.0,
            complexity_bias=1.8,
            contempt=150,
            style_name="The Neural",
            description="AlphaZero-like sacrifices. Inexplicable until you see it.",
            aggression=6,
            chaos=7,
        ),
        StylePreset.KARPOV: StyleConfiguration(
            stockfish_depth=18,
            blunder_threshold=40.0,
            complexity_bias=0.7,
            contempt=10,
            style_name="The Karpov",
            description="Silent positional squeeze. Suffocate your opponent.",
            aggression=3,
            chaos=3,
        ),
    }

    # =========================================================================
    # PHASE 3.1: EXTENDED STYLE DATABASE
    # =========================================================================
    
    EXTENDED_STYLE_CONFIGS: Dict[ExtendedStylePreset, ExtendedStyleConfiguration] = {
        ExtendedStylePreset.TAL: ExtendedStyleConfiguration(
            stockfish_depth=10,
            blunder_threshold=200.0,
            complexity_bias=1.5,
            contempt=50,
            style_name="The Magician (Tal)",
            description="Intuitive attacks, even if unsound. Complications over precision.",
            profile=DimensionalProfile(aggression=0.95, tactical=0.9, risk=0.95, 
                                       complexity=0.85, tempo=0.8, material=0.2),
            opening_preference=["Sicilian Najdorf", "King's Indian", "Benoni"],
            endgame_specialty=["Avoid endgames", "Tactical conversions"],
            signature_patterns=["Exchange sacrifice", "King hunt", "Piece sacrifices"],
            era="Soviet 1960s",
            peak_rating=2700,
        ),
        ExtendedStylePreset.CAPABLANCA: ExtendedStyleConfiguration(
            stockfish_depth=20,
            blunder_threshold=30.0,
            complexity_bias=0.5,
            contempt=0,
            style_name="The Chess Machine (Capablanca)",
            description="Positional perfection. Every move justified. Pure strength.",
            profile=DimensionalProfile(aggression=0.3, tactical=0.4, risk=0.1,
                                       complexity=0.3, tempo=0.4, material=0.7),
            opening_preference=["Queen's Gambit", "Ruy Lopez", "Four Knights"],
            endgame_specialty=["Rook endings", "Technical wins", "Simplification"],
            signature_patterns=["Piece exchanges", "Endgame technique", "Prophylaxis"],
            era="Classical 1920s",
            peak_rating=2725,
        ),
        ExtendedStylePreset.MORPHY: ExtendedStyleConfiguration(
            stockfish_depth=15,
            blunder_threshold=50.0,
            complexity_bias=1.2,
            contempt=30,
            style_name="The Pride of Chess (Morphy)",
            description="Classical attacking chess. Sound sacrifices for the initiative.",
            profile=DimensionalProfile(aggression=0.8, tactical=0.75, risk=0.6,
                                       complexity=0.6, tempo=0.9, material=0.4),
            opening_preference=["King's Gambit", "Italian Game", "Scotch Game"],
            endgame_specialty=["Rarely reached endgame", "Crushing attacks"],
            signature_patterns=["Rapid development", "Open files", "King attacks"],
            era="Romantic 1850s",
            peak_rating=2680,
        ),
        ExtendedStylePreset.COFFEE_HOUSE: ExtendedStyleConfiguration(
            stockfish_depth=5,
            blunder_threshold=500.0,
            complexity_bias=2.0,
            contempt=100,
            style_name="Coffee House Special",
            description="Gambits, tricks, hope-chess. Embrace the chaos.",
            profile=DimensionalProfile(aggression=0.9, tactical=0.95, risk=1.0,
                                       complexity=0.95, tempo=0.95, material=0.0),
            opening_preference=["King's Gambit", "Evans Gambit", "Danish Gambit"],
            endgame_specialty=["Never gets there", "All-or-nothing attacks"],
            signature_patterns=["Unsound gambits", "Tricks", "Swindles"],
            era="Any",
            peak_rating=1800,
        ),
        ExtendedStylePreset.NEURAL: ExtendedStyleConfiguration(
            stockfish_depth=25,
            blunder_threshold=30.0,
            complexity_bias=1.8,
            contempt=150,
            style_name="AlphaZero Style",
            description="AlphaZero-like sacrifices. Inexplicable until you see it.",
            profile=DimensionalProfile(aggression=0.6, tactical=0.5, risk=0.7,
                                       complexity=0.8, tempo=0.5, material=0.3),
            opening_preference=["English Opening", "King's Indian", "Queen's Indian"],
            endgame_specialty=["Active king", "Piece activity over pawns"],
            signature_patterns=["h4 advances", "Positional exchange sacs", "Alien moves"],
            era="Neural 2017+",
            peak_rating=3600,
        ),
        ExtendedStylePreset.KARPOV: ExtendedStyleConfiguration(
            stockfish_depth=18,
            blunder_threshold=40.0,
            complexity_bias=0.7,
            contempt=10,
            style_name="The Boa Constrictor (Karpov)",
            description="Silent positional squeeze. Suffocate your opponent.",
            profile=DimensionalProfile(aggression=0.25, tactical=0.35, risk=0.15,
                                       complexity=0.4, tempo=0.3, material=0.8),
            opening_preference=["Queen's Gambit Declined", "Caro-Kann", "English"],
            endgame_specialty=["All endgames", "Technical precision"],
            signature_patterns=["Prophylaxis", "Space advantage", "Slow squeeze"],
            era="Computer 1975-1990",
            peak_rating=2780,
        ),
        ExtendedStylePreset.FISCHER: ExtendedStyleConfiguration(
            stockfish_depth=22,
            blunder_threshold=35.0,
            complexity_bias=1.0,
            contempt=60,
            style_name="The Greatest (Fischer)",
            description="Perfect technical chess. Classical with modern precision.",
            profile=DimensionalProfile(aggression=0.65, tactical=0.6, risk=0.4,
                                       complexity=0.5, tempo=0.7, material=0.5),
            opening_preference=["Sicilian Najdorf", "King's Indian", "Grünfeld"],
            endgame_specialty=["Bishop pair endings", "Technical perfection"],
            signature_patterns=["1.e4 best by test", "Perfect calculation", "Classical attacks"],
            era="Modern 1960-1975",
            peak_rating=2785,
        ),
        ExtendedStylePreset.KASPAROV: ExtendedStyleConfiguration(
            stockfish_depth=20,
            blunder_threshold=50.0,
            complexity_bias=1.3,
            contempt=80,
            style_name="The Beast (Kasparov)",
            description="Dynamic, powerful attacks with deep preparation.",
            profile=DimensionalProfile(aggression=0.85, tactical=0.7, risk=0.6,
                                       complexity=0.7, tempo=0.75, material=0.35),
            opening_preference=["Sicilian Najdorf", "King's Indian Defense", "Scotch Game"],
            endgame_specialty=["Tactical endgames", "Dynamic conversions"],
            signature_patterns=["h-pawn storms", "Powerful knights", "Initiative at all costs"],
            era="Computer 1985-2005",
            peak_rating=2851,
        ),
        ExtendedStylePreset.PETROSIAN: ExtendedStyleConfiguration(
            stockfish_depth=18,
            blunder_threshold=25.0,
            complexity_bias=0.6,
            contempt=5,
            style_name="Iron Tigran (Petrosian)",
            description="Master of prophylaxis. Sees threats before they exist.",
            profile=DimensionalProfile(aggression=0.15, tactical=0.25, risk=0.1,
                                       complexity=0.4, tempo=0.2, material=0.6),
            opening_preference=["Queen's Indian", "English", "Petroff"],
            endgame_specialty=["Defensive technique", "Fortress building"],
            signature_patterns=["Prophylactic exchange sacs", "a3/h3 moves", "Prevention"],
            era="Soviet 1960s",
            peak_rating=2680,
        ),
        ExtendedStylePreset.ALEKHINE: ExtendedStyleConfiguration(
            stockfish_depth=16,
            blunder_threshold=70.0,
            complexity_bias=1.4,
            contempt=60,
            style_name="The Russian Wizard (Alekhine)",
            description="Brilliant combinations with strategic depth.",
            profile=DimensionalProfile(aggression=0.8, tactical=0.85, risk=0.7,
                                       complexity=0.8, tempo=0.6, material=0.3),
            opening_preference=["French Defense", "Queen's Gambit", "Alekhine Defense"],
            endgame_specialty=["Complex endgames", "Piece activity"],
            signature_patterns=["Deep combinations", "Surprise attacks", "Hypermodern ideas"],
            era="Classical 1920-1940",
            peak_rating=2690,
        ),
        ExtendedStylePreset.BOTVINNIK: ExtendedStyleConfiguration(
            stockfish_depth=22,
            blunder_threshold=30.0,
            complexity_bias=0.9,
            contempt=20,
            style_name="The Patriarch (Botvinnik)",
            description="Scientific chess. Deep preparation and methodology.",
            profile=DimensionalProfile(aggression=0.5, tactical=0.5, risk=0.35,
                                       complexity=0.6, tempo=0.4, material=0.6),
            opening_preference=["Queen's Gambit", "English Opening", "French Defense"],
            endgame_specialty=["Methodical technique", "Theoretical endings"],
            signature_patterns=["Opening preparation", "Scientific approach", "Pawn chains"],
            era="Soviet 1948-1963",
            peak_rating=2690,
        ),
        ExtendedStylePreset.NIMZOWITSCH: ExtendedStyleConfiguration(
            stockfish_depth=14,
            blunder_threshold=60.0,
            complexity_bias=1.3,
            contempt=40,
            style_name="The Revolutionary (Nimzowitsch)",
            description="Hypermodern prophet. Control center from afar.",
            profile=DimensionalProfile(aggression=0.4, tactical=0.5, risk=0.5,
                                       complexity=0.7, tempo=0.4, material=0.4),
            opening_preference=["Nimzo-Indian", "Queen's Indian", "Nimzowitsch Defense"],
            endgame_specialty=["Prophylactic play", "Blockade positions"],
            signature_patterns=["Overprotection", "Blockade", "Mysterious rook moves"],
            era="Hypermodern 1920s",
            peak_rating=2650,
        ),
        ExtendedStylePreset.CARLSEN: ExtendedStyleConfiguration(
            stockfish_depth=24,
            blunder_threshold=20.0,
            complexity_bias=0.8,
            contempt=30,
            style_name="The Mozart (Carlsen)",
            description="Universal style. Grinds down opponents with technique.",
            profile=DimensionalProfile(aggression=0.5, tactical=0.5, risk=0.35,
                                       complexity=0.5, tempo=0.6, material=0.55),
            opening_preference=["Berlin Defense", "English", "Sveshnikov"],
            endgame_specialty=["All endgames", "Converting minimal advantages"],
            signature_patterns=["Playing on with nothing", "Technical grinding", "Psychological pressure"],
            era="Neural 2010-2024",
            peak_rating=2882,
        ),
        ExtendedStylePreset.KRAMNIK: ExtendedStyleConfiguration(
            stockfish_depth=20,
            blunder_threshold=25.0,
            complexity_bias=0.7,
            contempt=15,
            style_name="The Strategist (Kramnik)",
            description="Deep strategic understanding. Berlin Wall creator.",
            profile=DimensionalProfile(aggression=0.35, tactical=0.4, risk=0.25,
                                       complexity=0.55, tempo=0.35, material=0.65),
            opening_preference=["Berlin Defense", "Catalan", "Petroff"],
            endgame_specialty=["Rook endings", "Technical precision"],
            signature_patterns=["Berlin Wall", "Strategic depth", "Positional sacrifices"],
            era="Computer 1995-2018",
            peak_rating=2817,
        ),
        ExtendedStylePreset.STEINITZ: ExtendedStyleConfiguration(
            stockfish_depth=12,
            blunder_threshold=80.0,
            complexity_bias=0.8,
            contempt=20,
            style_name="The Father (Steinitz)",
            description="First positional player. Scientific foundations.",
            profile=DimensionalProfile(aggression=0.4, tactical=0.5, risk=0.4,
                                       complexity=0.6, tempo=0.3, material=0.7),
            opening_preference=["Italian Game", "Vienna Game", "Steinitz Gambit"],
            endgame_specialty=["Foundational technique"],
            signature_patterns=["Pawn structure focus", "Piece centralization", "King safety"],
            era="Classical 1880s",
            peak_rating=2630,
        ),
        ExtendedStylePreset.ANDERSSEN: ExtendedStyleConfiguration(
            stockfish_depth=8,
            blunder_threshold=300.0,
            complexity_bias=1.7,
            contempt=70,
            style_name="The Romantic (Anderssen)",
            description="King of the Romantic era. Immortal Game creator.",
            profile=DimensionalProfile(aggression=0.95, tactical=0.95, risk=0.9,
                                       complexity=0.7, tempo=0.95, material=0.1),
            opening_preference=["King's Gambit", "Evans Gambit", "Italian Game"],
            endgame_specialty=["Doesn't reach endgame"],
            signature_patterns=["Queen sacrifices", "Piece sacrifices", "King hunts"],
            era="Romantic 1850s",
            peak_rating=2600,
        ),
        ExtendedStylePreset.SPASSKY: ExtendedStyleConfiguration(
            stockfish_depth=16,
            blunder_threshold=55.0,
            complexity_bias=1.1,
            contempt=35,
            style_name="The Universal (Spassky)",
            description="Balanced, universal style. Can play anything.",
            profile=DimensionalProfile(aggression=0.55, tactical=0.55, risk=0.5,
                                       complexity=0.55, tempo=0.5, material=0.5),
            opening_preference=["King's Gambit", "Closed Spanish", "Tarrasch Defense"],
            endgame_specialty=["All types"],
            signature_patterns=["Adaptability", "Balance", "Intuitive play"],
            era="Soviet 1960-1970s",
            peak_rating=2690,
        ),
        ExtendedStylePreset.ANAND: ExtendedStyleConfiguration(
            stockfish_depth=18,
            blunder_threshold=45.0,
            complexity_bias=1.1,
            contempt=40,
            style_name="The Lightning (Anand)",
            description="Rapid, intuitive chess. Speed demon.",
            profile=DimensionalProfile(aggression=0.6, tactical=0.65, risk=0.5,
                                       complexity=0.55, tempo=0.9, material=0.45),
            opening_preference=["Sicilian", "Ruy Lopez", "Queen's Indian"],
            endgame_specialty=["Practical decisions"],
            signature_patterns=["Rapid calculation", "Opening preparation", "Time management"],
            era="Computer 1995-2010",
            peak_rating=2817,
        ),
        ExtendedStylePreset.TOPALOV: ExtendedStyleConfiguration(
            stockfish_depth=16,
            blunder_threshold=80.0,
            complexity_bias=1.5,
            contempt=70,
            style_name="The Tiger (Topalov)",
            description="Aggressive, dynamic, never boring.",
            profile=DimensionalProfile(aggression=0.85, tactical=0.75, risk=0.75,
                                       complexity=0.8, tempo=0.8, material=0.25),
            opening_preference=["Sicilian", "Grünfeld", "King's Indian"],
            endgame_specialty=["Tactical conversions"],
            signature_patterns=["Dynamic play", "Risk-taking", "Initiative"],
            era="Computer 2000-2010",
            peak_rating=2816,
        ),
        ExtendedStylePreset.LASKER: ExtendedStyleConfiguration(
            stockfish_depth=14,
            blunder_threshold=65.0,
            complexity_bias=1.1,
            contempt=50,
            style_name="The Psychologist (Lasker)",
            description="Practical genius. Plays the opponent.",
            profile=DimensionalProfile(aggression=0.5, tactical=0.55, risk=0.55,
                                       complexity=0.6, tempo=0.5, material=0.45),
            opening_preference=["Exchange Ruy Lopez", "Queen's Gambit", "French"],
            endgame_specialty=["Practical endgames", "Fighting draws"],
            signature_patterns=["Psychological play", "Practical decisions", "Swindling"],
            era="Classical 1894-1921",
            peak_rating=2680,
        ),
    }

    def __init__(self):
        pass

    # =========================================================================
    # ORIGINAL METHODS (100% PRESERVED - IDENTICAL SIGNATURES)
    # =========================================================================

    def get_config(self, style: StylePreset) -> StyleConfiguration:
        """Get the engine configuration for a style."""
        return self.STYLE_CONFIGS.get(
            style, self.STYLE_CONFIGS[StylePreset.MORPHY]
        )

    def get_all_styles(self) -> dict:
        """Get all available styles and their descriptions."""
        return {
            style: self.STYLE_CONFIGS[style].description
            for style in StylePreset
        }

    def customize_config(
        self,
        base_style: StylePreset,
        depth_multiplier: float = 1.0,
        blunder_tolerance: Optional[float] = None,
        complexity_bias: Optional[float] = None,
    ) -> StyleConfiguration:
        """
        Create a custom configuration based on a style.
        
        Args:
            base_style: Starting style
            depth_multiplier: Multiply depth by this factor
            blunder_tolerance: Override blunder threshold
            complexity_bias: Override complexity bias
        
        Returns:
            Modified StyleConfiguration
        """
        base_config = self.get_config(base_style)
        
        return StyleConfiguration(
            stockfish_depth=max(1, int(base_config.stockfish_depth * depth_multiplier)),
            blunder_threshold=blunder_tolerance or base_config.blunder_threshold,
            complexity_bias=complexity_bias or base_config.complexity_bias,
            contempt=base_config.contempt,
            style_name=base_config.style_name,
            description=base_config.description,
            aggression=base_config.aggression,
            chaos=base_config.chaos,
        )

    # =========================================================================
    # PHASE 3.1: EXTENDED STYLE METHODS
    # =========================================================================

    def get_extended_config(self, style: ExtendedStylePreset) -> ExtendedStyleConfiguration:
        """
        Get extended configuration for a style.
        
        Args:
            style: ExtendedStylePreset enum
            
        Returns:
            ExtendedStyleConfiguration with full profile
        """
        return self.EXTENDED_STYLE_CONFIGS.get(
            style,
            self.EXTENDED_STYLE_CONFIGS[ExtendedStylePreset.MORPHY]
        )

    def get_all_extended_styles(self) -> Dict[ExtendedStylePreset, str]:
        """Get all extended styles and their descriptions."""
        return {
            style: config.description
            for style, config in self.EXTENDED_STYLE_CONFIGS.items()
        }

    def blend_styles(
        self,
        components: List[Tuple[ExtendedStylePreset, float]]
    ) -> ExtendedStyleConfiguration:
        """
        Create a blended style from multiple presets.
        
        Args:
            components: List of (style, weight) tuples
            
        Returns:
            Blended ExtendedStyleConfiguration
        """
        if not components:
            return self.get_extended_config(ExtendedStylePreset.MORPHY)
        
        # Normalize weights
        total_weight = sum(w for _, w in components)
        if total_weight == 0:
            return self.get_extended_config(components[0][0])
        
        normalized = [(s, w / total_weight) for s, w in components]
        
        # Get all configs
        configs = [(self.get_extended_config(s), w) for s, w in normalized]
        
        # Blend numerical parameters
        blended_depth = sum(c.stockfish_depth * w for c, w in configs)
        blended_blunder = sum(c.blunder_threshold * w for c, w in configs)
        blended_complexity = sum(c.complexity_bias * w for c, w in configs)
        blended_contempt = sum(c.contempt * w for c, w in configs)
        
        # Blend dimensional profiles
        blended_profile = DimensionalProfile(
            aggression=sum(c.profile.aggression * w for c, w in configs),
            tactical=sum(c.profile.tactical * w for c, w in configs),
            risk=sum(c.profile.risk * w for c, w in configs),
            complexity=sum(c.profile.complexity * w for c, w in configs),
            tempo=sum(c.profile.tempo * w for c, w in configs),
            material=sum(c.profile.material * w for c, w in configs),
        )
        
        # Combine opening preferences (unique)
        all_openings = []
        for c, w in configs:
            all_openings.extend(c.opening_preference)
        unique_openings = list(dict.fromkeys(all_openings))[:5]
        
        # Generate name
        style_names = [c.style_name.split('(')[0].strip() for c, _ in configs[:2]]
        blend_name = " × ".join(style_names) if len(style_names) > 1 else style_names[0]
        
        return ExtendedStyleConfiguration(
            stockfish_depth=int(blended_depth),
            blunder_threshold=blended_blunder,
            complexity_bias=blended_complexity,
            contempt=int(blended_contempt),
            style_name=f"Blend: {blend_name}",
            description=f"Custom blend of {len(components)} styles",
            profile=blended_profile,
            opening_preference=unique_openings,
            endgame_specialty=["Blended approach"],
            signature_patterns=["Mixed patterns"],
            era="Custom",
            peak_rating=int(sum(c.peak_rating * w for c, w in configs)),
        )

    def find_similar_styles(
        self,
        target_profile: DimensionalProfile,
        top_n: int = 3
    ) -> List[Tuple[ExtendedStylePreset, float]]:
        """
        Find styles most similar to a target profile.
        
        Args:
            target_profile: The target DimensionalProfile
            top_n: Number of results to return
            
        Returns:
            List of (style, similarity_score) tuples
        """
        similarities = []
        
        for style, config in self.EXTENDED_STYLE_CONFIGS.items():
            distance = target_profile.distance_to(config.profile)
            # Convert distance to similarity (0-1, higher is more similar)
            similarity = 1 / (1 + distance)
            similarities.append((style, similarity))
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_n]

    def get_adaptive_config(
        self,
        base_style: ExtendedStylePreset,
        move_number: int,
        is_winning: bool = False,
        is_losing: bool = False,
        opponent_style: Optional[ExtendedStylePreset] = None
    ) -> ExtendedStyleConfiguration:
        """
        Get adaptively modified configuration based on game state.
        
        Args:
            base_style: Starting style
            move_number: Current move number
            is_winning: Is the player clearly winning?
            is_losing: Is the player clearly losing?
            opponent_style: Opponent's style for counter-play
            
        Returns:
            Adapted ExtendedStyleConfiguration
        """
        base_config = self.get_extended_config(base_style)
        
        # Create a copy to modify
        adapted = ExtendedStyleConfiguration(
            stockfish_depth=base_config.stockfish_depth,
            blunder_threshold=base_config.blunder_threshold,
            complexity_bias=base_config.complexity_bias,
            contempt=base_config.contempt,
            style_name=base_config.style_name,
            description=base_config.description,
            profile=DimensionalProfile(**base_config.profile.to_dict()),
            opening_preference=base_config.opening_preference.copy(),
            endgame_specialty=base_config.endgame_specialty.copy(),
            signature_patterns=base_config.signature_patterns.copy(),
            era=base_config.era,
            peak_rating=base_config.peak_rating,
        )
        
        # Phase-based adjustments
        if move_number <= 10:
            # Opening: slightly more cautious
            adapted.blunder_threshold *= 0.8
        elif move_number >= 40:
            # Endgame: more precision
            adapted.stockfish_depth = min(25, adapted.stockfish_depth + 3)
            adapted.blunder_threshold *= 0.7
        
        # Winning adjustments
        if is_winning:
            # Simplify, avoid risks
            adapted.profile.risk *= 0.6
            adapted.profile.complexity *= 0.7
            adapted.complexity_bias *= 0.7
            adapted.contempt = max(0, adapted.contempt - 30)
            logger.debug("Adapting to winning position: reducing risk")
        
        # Losing adjustments
        elif is_losing:
            # Complicate, take risks
            adapted.profile.risk *= 1.4
            adapted.profile.complexity *= 1.3
            adapted.complexity_bias *= 1.4
            adapted.blunder_threshold *= 1.5
            logger.debug("Adapting to losing position: increasing complexity")
        
        # Counter-style adjustments
        if opponent_style:
            opponent_config = self.get_extended_config(opponent_style)
            
            # Against tactical players, be more solid
            if opponent_config.profile.tactical > 0.7:
                adapted.profile.risk *= 0.8
                adapted.stockfish_depth += 2
            
            # Against positional players, be more dynamic
            if opponent_config.profile.tactical < 0.4:
                adapted.profile.tactical *= 1.2
                adapted.complexity_bias *= 1.1
        
        return adapted

    def get_style_for_era(self, era: str) -> List[ExtendedStylePreset]:
        """
        Get appropriate styles for a historical era.
        
        Args:
            era: Era name (Romantic, Classical, etc.)
            
        Returns:
            List of appropriate ExtendedStylePresets
        """
        era_lower = era.lower()
        matching_styles = []
        
        for style, config in self.EXTENDED_STYLE_CONFIGS.items():
            config_era_lower = config.era.lower()
            if era_lower in config_era_lower or config_era_lower in era_lower:
                matching_styles.append(style)
        
        return matching_styles or [ExtendedStylePreset.MORPHY]

    def create_matchup_blend(
        self,
        player1: ExtendedStylePreset,
        player2: ExtendedStylePreset
    ) -> BlendedStyle:
        """
        Create a historically interesting style blend for a matchup.
        
        Args:
            player1: First player's style
            player2: Second player's style
            
        Returns:
            BlendedStyle for an interesting game
        """
        config1 = self.get_extended_config(player1)
        config2 = self.get_extended_config(player2)
        
        return BlendedStyle(
            components=[(player1, 0.5), (player2, 0.5)],
            name=f"{config1.style_name} vs {config2.style_name}",
            description=f"A clash between {player1.value} and {player2.value} styles",
        )

    def randomize_within_bounds(
        self,
        base_style: ExtendedStylePreset,
        variance: float = 0.1
    ) -> ExtendedStyleConfiguration:
        """
        Create a slightly randomized version of a style.
        
        Args:
            base_style: Base style to randomize
            variance: Amount of random variance (0-1)
            
        Returns:
            Randomized ExtendedStyleConfiguration
        """
        base_config = self.get_extended_config(base_style)
        
        def vary(value: float, factor: float = variance) -> float:
            delta = (random.random() - 0.5) * 2 * factor
            return max(0.0, min(1.0, value + delta))
        
        return ExtendedStyleConfiguration(
            stockfish_depth=max(5, min(30, base_config.stockfish_depth + random.randint(-2, 2))),
            blunder_threshold=base_config.blunder_threshold * (1 + (random.random() - 0.5) * variance),
            complexity_bias=base_config.complexity_bias * (1 + (random.random() - 0.5) * variance),
            contempt=max(0, min(200, base_config.contempt + random.randint(-10, 10))),
            style_name=f"{base_config.style_name} (varied)",
            description=base_config.description,
            profile=DimensionalProfile(
                aggression=vary(base_config.profile.aggression),
                tactical=vary(base_config.profile.tactical),
                risk=vary(base_config.profile.risk),
                complexity=vary(base_config.profile.complexity),
                tempo=vary(base_config.profile.tempo),
                material=vary(base_config.profile.material),
            ),
            opening_preference=base_config.opening_preference,
            endgame_specialty=base_config.endgame_specialty,
            signature_patterns=base_config.signature_patterns,
            era=base_config.era,
            peak_rating=base_config.peak_rating,
        )

    def get_phase_specific_style(self, style: ExtendedStylePreset) -> PhaseSpecificStyle:
        """
        Get phase-specific style adjustments for a player style.
        
        Args:
            style: Player style
            
        Returns:
            PhaseSpecificStyle with opening/middle/endgame profiles
        """
        base_config = self.get_extended_config(style)
        base_profile = base_config.profile
        
        # Opening: slightly more cautious for most players
        opening_profile = DimensionalProfile(
            aggression=base_profile.aggression * 0.8,
            tactical=base_profile.tactical * 0.7,
            risk=base_profile.risk * 0.6,
            complexity=base_profile.complexity * 0.8,
            tempo=base_profile.tempo,
            material=base_profile.material,
        )
        
        # Middlegame: full strength
        middlegame_profile = base_profile
        
        # Endgame: more precise, less tactical (for most)
        endgame_profile = DimensionalProfile(
            aggression=base_profile.aggression * 0.7,
            tactical=base_profile.tactical * 0.6,
            risk=base_profile.risk * 0.5,
            complexity=base_profile.complexity * 0.6,
            tempo=base_profile.tempo * 0.8,
            material=base_profile.material * 1.2,  # More material-focused
        )
        
        return PhaseSpecificStyle(
            opening=opening_profile,
            middlegame=middlegame_profile,
            endgame=endgame_profile,
        )


# Example usage
if __name__ == "__main__":
    slider = StyleSlider()
    
    print("=" * 70)
    print("CAISSA STYLE PRESETS (Original)")
    print("=" * 70)
    
    for style, description in slider.get_all_styles().items():
        config = slider.get_config(style)
        print(f"\n{config.style_name}:")
        print(f"  Description: {description}")
        print(f"  Stockfish Depth: {config.stockfish_depth}")
        print(f"  Blunder Tolerance: {config.blunder_threshold} cp")
        print(f"  Complexity Bias: {config.complexity_bias}x")
        print(f"  Contempt: {config.contempt}")
    
    # PHASE 3.1: Extended examples
    print("\n" + "=" * 70)
    print("PHASE 3.1: EXTENDED STYLES")
    print("=" * 70)
    
    print("\nExtended style count:", len(slider.EXTENDED_STYLE_CONFIGS))
    
    # Show a few extended profiles
    for style in [ExtendedStylePreset.FISCHER, ExtendedStylePreset.KASPAROV, ExtendedStylePreset.CARLSEN]:
        config = slider.get_extended_config(style)
        print(f"\n{config.style_name}:")
        print(f"  Era: {config.era}")
        print(f"  Peak Rating: {config.peak_rating}")
        print(f"  Profile: {config.profile.to_dict()}")
        print(f"  Openings: {', '.join(config.opening_preference)}")
    
    print("\n" + "=" * 70)
    print("STYLE BLENDING: TAL + PETROSIAN")
    print("=" * 70)
    
    blended = slider.blend_styles([
        (ExtendedStylePreset.TAL, 0.7),
        (ExtendedStylePreset.PETROSIAN, 0.3),
    ])
    print(f"Name: {blended.style_name}")
    print(f"Profile: {blended.profile.to_dict()}")
    
    print("\n" + "=" * 70)
    print("FINDING SIMILAR STYLES")
    print("=" * 70)
    
    # Find styles similar to a balanced profile
    balanced_profile = DimensionalProfile(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    similar = slider.find_similar_styles(balanced_profile)
    print("Styles most similar to balanced profile:")
    for style, similarity in similar:
        print(f"  {style.value}: {similarity:.2f}")
