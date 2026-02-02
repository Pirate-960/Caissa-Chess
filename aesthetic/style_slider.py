"""
aesthetic/style_slider.py

Maps user-selected game styles to engine parameters.
The "Style Controller" that personalizes game generation.
"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum


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


class StyleSlider:
    """
    Translates game styles into concrete engine parameters.
    """

    STYLE_CONFIGS = {
        StylePreset.TAL: StyleConfiguration(
            stockfish_depth=10,
            blunder_threshold=200.0,
            complexity_bias=1.5,
            contempt=50,
            style_name="The Tal",
            description="Intuitive attacks, even if unsound. Complications over precision.",
        ),
        StylePreset.CAPABLANCA: StyleConfiguration(
            stockfish_depth=20,
            blunder_threshold=30.0,
            complexity_bias=0.5,
            contempt=0,
            style_name="The Capablanca",
            description="Positional perfection. Every move justified. Pure strength.",
        ),
        StylePreset.MORPHY: StyleConfiguration(
            stockfish_depth=15,
            blunder_threshold=50.0,
            complexity_bias=1.2,
            contempt=30,
            style_name="The Morphy",
            description="Classical attacking chess. Sound sacrifices for the initiative.",
        ),
        StylePreset.COFFEE_HOUSE: StyleConfiguration(
            stockfish_depth=5,
            blunder_threshold=500.0,
            complexity_bias=2.0,
            contempt=100,
            style_name="The Coffee House",
            description="Gambits, tricks, hope-chess. Embrace the chaos.",
        ),
        StylePreset.NEURAL: StyleConfiguration(
            stockfish_depth=25,
            blunder_threshold=30.0,
            complexity_bias=1.8,
            contempt=150,
            style_name="The Neural",
            description="AlphaZero-like sacrifices. Inexplicable until you see it.",
        ),
        StylePreset.KARPOV: StyleConfiguration(
            stockfish_depth=18,
            blunder_threshold=40.0,
            complexity_bias=0.7,
            contempt=10,
            style_name="The Karpov",
            description="Silent positional squeeze. Suffocate your opponent.",
        ),
    }

    def __init__(self):
        pass

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
        )


# Example usage
if __name__ == "__main__":
    slider = StyleSlider()
    
    print("=" * 70)
    print("CAISSA STYLE PRESETS")
    print("=" * 70)
    
    for style, description in slider.get_all_styles().items():
        config = slider.get_config(style)
        print(f"\n{config.style_name}:")
        print(f"  Description: {description}")
        print(f"  Stockfish Depth: {config.stockfish_depth}")
        print(f"  Blunder Tolerance: {config.blunder_threshold} cp")
        print(f"  Complexity Bias: {config.complexity_bias}x")
        print(f"  Contempt: {config.contempt}")
