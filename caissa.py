"""
caissa.py

Main entry point for CAISSA.
Example: python caissa.py generate --style romantic --theme "Queen Sacrifice"
"""

import argparse
import sys
from typing import Optional

from core.generator import CaissaGenerator, GameContext
from core.prompt_manager import GameEra, GameTheme
from aesthetic.style_slider import StyleSlider, StylePreset


def create_parser():
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="CAISSA: The Aesthetic Chess Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python caissa.py generate --style romantic --theme "Queen Sacrifice"
  python caissa.py generate --style neural --aggression 9
  python caissa.py list-styles
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Generate command
    generate_parser = subparsers.add_parser("generate", help="Generate a game")
    generate_parser.add_argument(
        "--style",
        type=str,
        default="morphy",
        help="Game style (tal, capablanca, morphy, coffee_house, neural, karpov)",
    )
    generate_parser.add_argument(
        "--theme",
        type=str,
        default=None,
        help="Thematic concept (e.g., 'Queen Sacrifice', 'Windmill')",
    )
    generate_parser.add_argument(
        "--aggression",
        type=int,
        default=7,
        help="Aggression level (1-10)",
    )
    generate_parser.add_argument(
        "--chaos",
        type=int,
        default=5,
        help="Chaos level (1-10)",
    )
    generate_parser.add_argument(
        "--output",
        type=str,
        default="game.pgn",
        help="Output PGN filename",
    )
    generate_parser.add_argument(
        "--white",
        type=str,
        default="Caissa White",
        help="White player name",
    )
    generate_parser.add_argument(
        "--black",
        type=str,
        default="Caissa Black",
        help="Black player name",
    )
    
    # List styles command
    subparsers.add_parser("list-styles", help="List available styles")
    
    # Info command
    subparsers.add_parser("info", help="Display project information")
    
    return parser


def cmd_generate(args):
    """Handle the generate command."""
    print("=" * 70)
    print("CAISSA: Game Generation")
    print("=" * 70)
    
    # Parse style
    try:
        style = StylePreset(args.style.lower())
    except ValueError:
        print(f"Error: Unknown style '{args.style}'")
        print(f"Available styles: tal, capablanca, morphy, coffee_house, neural, karpov")
        return False
    
    # Parse theme
    theme = None
    if args.theme:
        try:
            # Try to match theme to enum
            theme_name = args.theme.upper().replace(" ", "_")
            theme = GameTheme[theme_name]
        except KeyError:
            print(f"Warning: Unknown theme '{args.theme}'. Proceeding without specific theme.")
    
    # Create context
    slider = StyleSlider()
    style_config = slider.get_config(style)
    
    context = GameContext(
        era=GameEra.ROMANTIC,  # TODO: Make this configurable
        theme=theme,
        white_player=args.white,
        black_player=args.black,
        aggression_score=args.aggression,
        chaos_score=args.chaos,
        depth=40,
    )
    
    print(f"\nConfiguration:")
    print(f"  Style: {style_config.style_name}")
    print(f"  Theme: {theme.value if theme else 'None'}")
    print(f"  White: {args.white}")
    print(f"  Black: {args.black}")
    print(f"  Aggression: {args.aggression}/10")
    print(f"  Chaos: {args.chaos}/10")
    print(f"  Output: {args.output}")
    print()
    
    # Initialize generator
    generator = CaissaGenerator()
    
    print("Status: Generator initialized")
    print("Status: LLM client required (set OPENAI_API_KEY)")
    print()
    print("Note: To actually generate a game, configure an LLM client:")
    print("  from core.generator import SimpleOpenAIClient")
    print("  generator.set_llm_client(SimpleOpenAIClient())")
    print("  success, pgn, moves = generator.generate_game(context)")
    
    return True


def cmd_list_styles(args):
    """Handle the list-styles command."""
    slider = StyleSlider()
    
    print("=" * 70)
    print("Available Styles")
    print("=" * 70)
    print()
    
    for style, description in slider.get_all_styles().items():
        config = slider.get_config(style)
        print(f"{config.style_name} ({style.value})")
        print(f"  {description}")
        print(f"  Depth: {config.stockfish_depth}, Blunder Tolerance: {config.blunder_threshold} cp")
        print()


def cmd_info(args):
    """Display project information."""
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║         ♟️  CAISSA: The Aesthetic Chess Engine  ♟️                ║
    ║                                                                    ║
    ║  "We don't generate chess games. We generate immortality."         ║
    ╚════════════════════════════════════════════════════════════════════╝
    
    CAISSA is a Generative Adversarial-Cooperative Pipeline (GACP) that
    combines Large Language Model creativity with Stockfish verification
    to generate chess games that are:
    
    ✓ LEGALLY VALID (using python-chess)
    ✓ STRATEGICALLY COHERENT (Chain-of-Thought prompting)
    ✓ AESTHETICALLY STUNNING (Beauty Score Algorithm)
    
    The Pipeline:
    1. The Dreamer (LLM): Hallucinates a game narrative
    2. The Architect (python-chess): Enforces legal moves
    3. The Critic (Stockfish): Evaluates tactical soundness
    4. The Curator (Beauty Eval): Assigns aesthetic score
    5. The Storyteller (LLM): Writes GM commentary
    
    Architecture: Modular, testable, and extensible.
    Status: v0.1.0 - Core pipeline complete, LLM integration ready.
    
    Quick Start:
    -----------
    python caissa.py generate --style tal --theme "Queen Sacrifice" --output game.pgn
    python caissa.py list-styles
    
    Documentation:
    ---------------
    See README.md for full architecture overview.
    """)


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    if args.command == "generate":
        return 0 if cmd_generate(args) else 1
    elif args.command == "list-styles":
        cmd_list_styles(args)
        return 0
    elif args.command == "info":
        cmd_info(args)
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
