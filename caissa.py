"""
caissa.py

DEPRECATED — Use ``python main.py`` or the ``caissa`` CLI command instead.
This file will be removed in v0.4.

Original entry point for CAISSA - The Aesthetic Chess Engine.
Example: python caissa.py generate --style romantic --theme "Queen Sacrifice"

PHASE 3.1 ENHANCEMENTS:
- Batch generation mode (generate multiple games)
- Configuration file support (YAML/JSON)
- Interactive REPL mode
- Enhanced analysis commands
- Progress tracking and statistics
- Export format options
- Historical player matchups
- Opening book integration

Original functionality 100% preserved.
Enhanced with clean PGN output formatting and Phase 3.1 features.

Key improvements:
1. Beautifully formatted PGN output with proper indentation
2. Annotations neatly organized next to each move
3. Comments in proper PGN format with { } brackets
4. Header section separated from moves
5. Move numbers aligned for readability
"""

import argparse
import sys
import os
import json
import time
import textwrap
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, rely on system environment

from core.generator import CaissaGenerator, GameContext
from core.prompt_manager import GameEra, GameTheme
from aesthetic.style_slider import StyleSlider, StylePreset


# =============================================================================
# PHASE 3.1: NEW ENUMS AND TYPES
# =============================================================================

class OutputFormat(str, Enum):
    """Available output formats."""
    PGN = "pgn"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"


class VerbosityLevel(str, Enum):
    """Output verbosity levels."""
    QUIET = "quiet"
    NORMAL = "normal"
    VERBOSE = "verbose"
    DEBUG = "debug"


# =============================================================================
# PHASE 3.1: NEW DATACLASSES
# =============================================================================

@dataclass
class GenerationConfig:
    """Configuration for game generation."""
    style: str = "morphy"
    theme: Optional[str] = None
    era: str = "romantic"
    aggression: int = 7
    chaos: int = 5
    depth: int = 40
    white: str = "Caissa White"
    black: str = "Caissa Black"
    output: str = "game.pgn"
    format: OutputFormat = OutputFormat.PGN
    annotate: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenerationConfig":
        """Create config from dictionary."""
        return cls(
            style=data.get("style", "morphy"),
            theme=data.get("theme"),
            era=data.get("era", "romantic"),
            aggression=data.get("aggression", 7),
            chaos=data.get("chaos", 5),
            depth=data.get("depth", 40),
            white=data.get("white", "Caissa White"),
            black=data.get("black", "Caissa Black"),
            output=data.get("output", "game.pgn"),
            format=OutputFormat(data.get("format", "pgn")),
            annotate=data.get("annotate", False),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "style": self.style,
            "theme": self.theme,
            "era": self.era,
            "aggression": self.aggression,
            "chaos": self.chaos,
            "depth": self.depth,
            "white": self.white,
            "black": self.black,
            "output": self.output,
            "format": self.format.value,
            "annotate": self.annotate,
        }


@dataclass
class BatchConfig:
    """Configuration for batch generation."""
    num_games: int = 1
    output_dir: str = "./games"
    filename_pattern: str = "game_{n:03d}.pgn"
    parallel: bool = False
    max_workers: int = 4
    fail_fast: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchConfig":
        """Create config from dictionary."""
        return cls(
            num_games=data.get("num_games", 1),
            output_dir=data.get("output_dir", "./games"),
            filename_pattern=data.get("filename_pattern", "game_{n:03d}.pgn"),
            parallel=data.get("parallel", False),
            max_workers=data.get("max_workers", 4),
            fail_fast=data.get("fail_fast", False),
        )


@dataclass
class BatchResult:
    """Result of batch generation."""
    total: int
    successful: int
    failed: int
    elapsed_time: float
    games: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def summary(self) -> str:
        """Generate summary string."""
        rate = self.successful / max(1, self.elapsed_time)
        return (
            f"Generated {self.successful}/{self.total} games "
            f"({self.failed} failed) in {self.elapsed_time:.1f}s "
            f"({rate:.2f} games/sec)"
        )


@dataclass
class SessionStats:
    """Statistics for an interactive session."""
    games_generated: int = 0
    total_moves: int = 0
    styles_used: Dict[str, int] = field(default_factory=dict)
    themes_used: Dict[str, int] = field(default_factory=dict)
    session_start: datetime = field(default_factory=datetime.now)
    
    def add_game(self, style: str, theme: Optional[str], move_count: int) -> None:
        """Record a generated game."""
        self.games_generated += 1
        self.total_moves += move_count
        self.styles_used[style] = self.styles_used.get(style, 0) + 1
        if theme:
            self.themes_used[theme] = self.themes_used.get(theme, 0) + 1
    
    def summary(self) -> str:
        """Generate session summary."""
        duration = (datetime.now() - self.session_start).total_seconds()
        return (
            f"Session Stats:\n"
            f"  Duration: {duration:.0f}s\n"
            f"  Games: {self.games_generated}\n"
            f"  Total Moves: {self.total_moves}\n"
            f"  Avg Moves/Game: {self.total_moves / max(1, self.games_generated):.1f}\n"
            f"  Styles: {dict(self.styles_used)}\n"
            f"  Themes: {dict(self.themes_used)}"
        )


# =============================================================================
# PGN FORMATTER - NEW UTILITY FOR CLEAN PGN OUTPUT
# =============================================================================

class PGNWriter:
    """Utility class for creating well-formatted PGN output."""
    
    @staticmethod
    def format_headers(headers: Dict[str, str]) -> str:
        """
        Format PGN headers in standard format.
        
        Args:
            headers: Dictionary of PGN headers
            
        Returns:
            Formatted headers string
        """
        result = []
        # Standard headers in conventional order
        standard_order = ['Event', 'Site', 'Date', 'Round', 'White', 'Black', 'Result']
        
        # Add standard headers first
        for key in standard_order:
            if key in headers:
                value = headers[key]
                result.append(f'[{key} "{value}"]')
        
        # Add any remaining headers
        for key, value in headers.items():
            if key not in standard_order:
                result.append(f'[{key} "{value}"]')
        
        return '\n'.join(result)
    
    @staticmethod
    def format_moves_with_comments(moves: List[Dict[str, Any]], max_line_width: int = 80) -> str:
        """
        Format moves with comments in a readable PGN format.
        
        Args:
            moves: List of move dictionaries with 'san', 'comment', and 'eval' keys
            max_line_width: Maximum line width before wrapping
            
        Returns:
            Formatted moves string
        """
        if not moves:
            return "*"
        
        result_lines = []
        current_line = ""
        move_number = 1
        
        for i, move_data in enumerate(moves):
            is_white_move = (i % 2 == 0)
            
            if is_white_move:
                # Start new line with move number
                if current_line:
                    result_lines.append(current_line.rstrip())
                current_line = f"{move_number}. "
                move_number += 1
            
            # Add the move
            san_move = move_data.get('san', '')
            if san_move:
                current_line += f"{san_move} "
            
            # Add comment if available
            comment = move_data.get('comment', '')
            eval_note = move_data.get('eval', '')
            
            if comment or eval_note:
                # Build comment text
                comment_parts = []
                if eval_note:
                    comment_parts.append(f"Eval: {eval_note}")
                if comment:
                    comment_parts.append(comment)
                
                comment_text = " | ".join(comment_parts)
                
                # Wrap long comments
                if len(comment_text) > 60:
                    wrapped_comment = textwrap.fill(
                        comment_text, 
                        width=60,
                        initial_indent="  ",
                        subsequent_indent="  "
                    )
                    # Split into lines and add as separate comments
                    for line in wrapped_comment.split('\n'):
                        current_line += f"{{ {line.strip()} }} "
                else:
                    current_line += f"{{ {comment_text} }} "
            
            # Check if line is getting too long
            if len(current_line) > max_line_width and is_white_move:
                # Only break at white moves (start of a pair)
                result_lines.append(current_line.rstrip())
                current_line = ""
        
        # Add the last line if not empty
        if current_line:
            result_lines.append(current_line.rstrip())
        
        return '\n'.join(result_lines)
    
    @staticmethod
    def format_full_game(headers: Dict[str, str], moves: List[Dict[str, Any]], 
                         result: str = "*") -> str:
        """
        Format a complete PGN game with headers and moves.
        
        Args:
            headers: Dictionary of PGN headers
            moves: List of move dictionaries
            result: Game result (e.g., "1-0", "0-1", "1/2-1/2")
            
        Returns:
            Complete PGN string
        """
        # Ensure result is in headers
        headers['Result'] = result
        
        # Format headers
        headers_str = PGNWriter.format_headers(headers)
        
        # Format moves
        moves_str = PGNWriter.format_moves_with_comments(moves)
        
        # Combine with proper spacing
        return f"{headers_str}\n\n{moves_str} {result}"
    
    @staticmethod
    def format_for_display(pgn_string: str, show_headers: bool = True) -> str:
        """
        Format PGN string for display in console with enhanced readability.
        
        Args:
            pgn_string: Raw PGN string
            show_headers: Whether to include headers in display
            
        Returns:
            Formatted display string
        """
        lines = pgn_string.split('\n')
        formatted_lines = []
        
        in_moves = False
        for line in lines:
            line = line.rstrip()
            
            if line.startswith('['):
                if show_headers:
                    formatted_lines.append(line)
            elif line:
                if not in_moves:
                    formatted_lines.append("")  # Blank line between headers and moves
                    in_moves = True
                formatted_lines.append(f"  {line}")
        
        return '\n'.join(formatted_lines)


# =============================================================================
# ORIGINAL PARSER (PRESERVED) + PHASE 3.1 ENHANCEMENTS
# =============================================================================

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
    
    # PHASE 3.1: New generate arguments
    generate_parser.add_argument(
        "--era",
        type=str,
        default="romantic",
        choices=["classical", "romantic", "hypermodern", "modern", "computer"],
        help="Chess era style",
    )
    generate_parser.add_argument(
        "--format",
        type=str,
        default="pgn",
        choices=["pgn", "markdown", "html", "json"],
        help="Output format",
    )
    generate_parser.add_argument(
        "--annotate",
        action="store_true",
        help="Include annotations and commentary",
    )
    generate_parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Load configuration from JSON file",
    )
    generate_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Generate pretty PGN format with indentation and comments",
    )
    
    # List styles command
    subparsers.add_parser("list-styles", help="List available styles")
    
    # Info command
    subparsers.add_parser("info", help="Display project information")
    
    # PHASE 3.1: New commands
    
    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Generate multiple games")
    batch_parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of games to generate",
    )
    batch_parser.add_argument(
        "--output-dir",
        type=str,
        default="./games",
        help="Output directory for games",
    )
    batch_parser.add_argument(
        "--style",
        type=str,
        default="morphy",
        help="Game style to use",
    )
    batch_parser.add_argument(
        "--vary-style",
        action="store_true",
        help="Vary style across games",
    )
    batch_parser.add_argument(
        "--parallel",
        action="store_true",
        help="Generate games in parallel (requires async provider)",
    )
    batch_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Generate pretty PGN format",
    )
    batch_parser.add_argument(
        "--annotate",
        action="store_true",
        help="Include annotations and commentary",
    )
    
    # Interactive REPL command
    subparsers.add_parser("interactive", help="Start interactive mode (REPL)")
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a PGN file")
    analyze_parser.add_argument(
        "file",
        type=str,
        help="PGN file to analyze",
    )
    analyze_parser.add_argument(
        "--depth",
        type=int,
        default=20,
        help="Analysis depth",
    )
    analyze_parser.add_argument(
        "--beauty",
        action="store_true",
        help="Include beauty score analysis",
    )
    
    # Matchup command
    matchup_parser = subparsers.add_parser("matchup", help="Generate historical matchup")
    matchup_parser.add_argument(
        "white_player",
        type=str,
        help="White player style (e.g., Tal, Capablanca)",
    )
    matchup_parser.add_argument(
        "black_player",
        type=str,
        help="Black player style (e.g., Petrosian, Fischer)",
    )
    matchup_parser.add_argument(
        "--opening",
        type=str,
        default=None,
        help="Opening to play (e.g., 'Sicilian')",
    )
    matchup_parser.add_argument(
        "--output",
        type=str,
        default="matchup.pgn",
        help="Output filename",
    )
    matchup_parser.add_argument(
        "--pretty",
        action="store_true",
        help="Generate pretty PGN format",
    )
    
    # Stats command
    subparsers.add_parser("stats", help="Show generation statistics")
    
    # Version command
    subparsers.add_parser("version", help="Show version information")
    
    return parser


# =============================================================================
# ORIGINAL COMMAND HANDLERS (ENHANCED WITH PRETTY PGN)
# =============================================================================

def cmd_generate(args):
    """Handle the generate command."""
    print("=" * 70)
    print("CAISSA: Game Generation")
    print("=" * 70)
    
    # PHASE 3.1: Load config file if specified
    if hasattr(args, 'config') and args.config:
        config = load_config_file(args.config)
        if config:
            # Merge config with args (args take precedence)
            for key, value in config.items():
                if not hasattr(args, key) or getattr(args, key) is None:
                    setattr(args, key, value)
    
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
    
    # Parse era
    era_map = {
        "classical": GameEra.CLASSICAL,
        "romantic": GameEra.ROMANTIC,
        "hypermodern": GameEra.HYPERMODERN,
        "modern": GameEra.SOVIET,      # Map "modern" to Soviet School
        "computer": GameEra.COMPUTER,
        "soviet": GameEra.SOVIET,
        "neural": GameEra.NEURAL,
    }
    era = era_map.get(args.era.lower(), GameEra.ROMANTIC)
    
    # Create context
    slider = StyleSlider()
    style_config = slider.get_config(style)
    
    context = GameContext(
        era=era,
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
    print(f"  Era: {era.value}")
    print(f"  White: {args.white}")
    print(f"  Black: {args.black}")
    print(f"  Aggression: {args.aggression}/10")
    print(f"  Chaos: {args.chaos}/10")
    print(f"  Pretty output: {getattr(args, 'pretty', False)}")
    print(f"  Output: {args.output}")
    print()
    
    # Get LLM provider from environment
    llm_provider_name = os.getenv("LLM_PROVIDER", "openai").lower()
    stockfish_path = os.getenv("STOCKFISH_PATH")
    
    print(f"Status: Configuring LLM provider ({llm_provider_name})...")
    
    try:
        provider = _create_llm_provider(llm_provider_name)
        print(f"Status: ✅ {type(provider).__name__} initialized")
    except Exception as e:
        print(f"Error: Failed to initialize LLM provider: {e}")
        return False
    
    # Initialize generator with Stockfish path and provider
    print(f"Status: Initializing generator...")
    with CaissaGenerator(provider=provider, stockfish_path=stockfish_path) as generator:
        print(f"Status: ✅ Generator ready")
        print()
        print("=" * 70)
        print("🎭 Generating Aesthetic Chess Game...")
        print("=" * 70)
        print()
        
        try:
            success, pgn_string, moves = generator.generate_game(context)
            
            if success:
                # Use unified export pipeline
                from export.annotation_parser import parse_pgn
                from export.game_exporter import GameExporter
                
                parsed_game = parse_pgn(pgn_string)
                exporter = GameExporter(game=parsed_game)
                formatted_pgn = exporter.export_pgn()
                
                # Save PGN to file
                output_path = Path(args.output)
                output_path.write_text(formatted_pgn, encoding="utf-8")
                
                ann_count = sum(1 for m in parsed_game.moves if m.comment or m.nags)
                opening_info = f"  Opening: {parsed_game.eco}: {parsed_game.opening_name}" if parsed_game.eco else ""
                
                print()
                print("=" * 70)
                print(f"✅ Game generated successfully!")
                print(f"📄 Saved to: {output_path.absolute()}")
                print(f"🎯 Total moves: {parsed_game.move_count}")
                print(f"📝 Annotations: {ann_count}")
                if opening_info:
                    print(f"♟️{opening_info}")
                print("=" * 70)
                print()
                print("PGN Preview:")
                print("-" * 70)
                
                # Display formatted PGN
                display_pgn = PGNWriter.format_for_display(formatted_pgn)
                print(display_pgn)
                
                print("-" * 70)
                
                return True
            else:
                print(f"❌ Game generation failed")
                return False
                
        except Exception as e:
            print(f"❌ Error during generation: {e}")
            import traceback
            traceback.print_exc()
            return False


def _enhance_pgn_formatting(pgn_string: str, moves: List[Dict[str, Any]]) -> str:
    """
    Enhance PGN formatting with proper indentation and organization.
    
    Args:
        pgn_string: Original PGN string
        moves: List of move dictionaries with comments
        
    Returns:
        Enhanced PGN string
    """
    # Parse headers from original PGN
    lines = pgn_string.strip().split('\n')
    headers = {}
    moves_start = 0
    
    for i, line in enumerate(lines):
        if line.startswith('['):
            # Parse header
            key_start = line.find('[') + 1
            key_end = line.find(' ')
            value_start = line.find('"') + 1
            value_end = line.rfind('"')
            
            if key_end > key_start and value_end > value_start:
                key = line[key_start:key_end]
                value = line[value_start:value_end]
                headers[key] = value
        elif line.strip() and not moves_start:
            moves_start = i
            break
    
    # Extract result if present
    result = headers.get('Result', '*')
    
    # Convert moves to format expected by PGNWriter
    formatted_moves = []
    for move_data in moves:
        if isinstance(move_data, dict):
            formatted_move = {
                'san': move_data.get('san', ''),
                'comment': move_data.get('comment', ''),
                'eval': move_data.get('eval', '')
            }
        else:
            formatted_move = {
                'san': str(move_data),
                'comment': '',
                'eval': ''
            }
        formatted_moves.append(formatted_move)
    
    # Create enhanced PGN
    return PGNWriter.format_full_game(headers, formatted_moves, result)


def _create_llm_provider(provider_name: str):
    """Create an LLM provider based on the provider name."""
    from core.provider_factory import create_provider
    return create_provider(provider_name)


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
    Previous: v0.1.0 - Core pipeline complete, LLM integration ready.
    Status: v0.2.0 - Multi-provider LLM integration complete, 6 providers supported.
    
    Quick Start:
    -----------
    python caissa.py generate --style tal --theme "Queen Sacrifice" --output game.pgn
    python caissa.py list-styles
    
    Documentation:
    ---------------
    See README.md for full architecture overview.
    """)


# =============================================================================
# PHASE 3.1: NEW COMMAND HANDLERS
# =============================================================================

def load_config_file(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Load configuration from JSON or YAML file.
    
    Args:
        filepath: Path to config file
        
    Returns:
        Configuration dictionary or None
    """
    try:
        with open(filepath, 'r') as f:
            if filepath.endswith('.json'):
                return json.load(f)
            elif filepath.endswith(('.yml', '.yaml')):
                try:
                    import yaml
                    return yaml.safe_load(f)
                except ImportError:
                    print("Warning: PyYAML not installed. Using JSON parser.")
                    return json.load(f)
        return None
    except Exception as e:
        print(f"Error loading config file: {e}")
        return None


def cmd_batch(args):
    """Handle batch generation command."""
    print("=" * 70)
    print("CAISSA: Batch Game Generation")
    print("=" * 70)
    print()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Configuration:")
    print(f"  Games to generate: {args.count}")
    print(f"  Output directory: {output_dir}")
    print(f"  Base style: {args.style}")
    print(f"  Vary styles: {args.vary_style}")
    print(f"  Parallel: {args.parallel}")
    print(f"  Pretty format: {getattr(args, 'pretty', False)}")
    print()
    
    # Get LLM provider
    llm_provider_name = os.getenv("LLM_PROVIDER", "openai").lower()
    stockfish_path = os.getenv("STOCKFISH_PATH")
    
    try:
        provider = _create_llm_provider(llm_provider_name)
        print(f"✅ LLM provider initialized: {type(provider).__name__}")
    except Exception as e:
        print(f"❌ Failed to initialize LLM provider: {e}")
        return False
    
    # Get available styles for variation
    slider = StyleSlider()
    available_styles = list(slider.get_all_styles().keys())
    
    start_time = time.time()
    results = BatchResult(
        total=args.count,
        successful=0,
        failed=0,
        elapsed_time=0,
    )
    
    # Initialize generator once (reused for each game)
    with CaissaGenerator(provider=provider, stockfish_path=stockfish_path) as generator:
        print(f"✅ Generator ready for batch processing")
        print()
        
        for i in range(args.count):
            game_num = i + 1
            
            # Select style
            if args.vary_style:
                style = available_styles[i % len(available_styles)]
                style_name = style.value
                print(f"[{game_num}/{args.count}] Generating with style: {style_name}")
            else:
                style_name = args.style.lower()
                print(f"[{game_num}/{args.count}] Generating with style: {style_name}")
            
            try:
                # Parse style
                try:
                    style_enum = StylePreset(style_name)
                except ValueError:
                    print(f"  Warning: Unknown style '{style_name}', using 'morphy'")
                    style_enum = StylePreset.MORPHY
                
                # Get style config
                style_config = slider.get_config(style_enum)
                
                # Create game context
                context = GameContext(
                    era=GameEra.ROMANTIC,  # Default era
                    theme=None,  # No specific theme for batch
                    white_player=f"Caissa {style_config.style_name}",
                    black_player="Caissa Opponent",
                    aggression_score=style_config.aggression,
                    chaos_score=style_config.chaos,
                    depth=style_config.stockfish_depth,
                )
                
                # Generate the game
                print(f"  Status: Generating...")
                success, pgn_string, moves = generator.generate_game(context)
                
                if success:
                    # Use unified export pipeline
                    from export.annotation_parser import parse_pgn as _parse_pgn
                    from export.game_exporter import GameExporter as _GameExporter
                    
                    parsed = _parse_pgn(pgn_string)
                    _exporter = _GameExporter(game=parsed, style_name=style_name)
                    formatted_pgn = _exporter.export_pgn()
                    
                    # Save PGN to file
                    filename = output_dir / f"game_{game_num:03d}.pgn"
                    filename.write_text(formatted_pgn, encoding="utf-8")
                    
                    results.games.append(str(filename))
                    results.successful += 1
                    
                    print(f"  ✅ Saved to: {filename}")
                    print(f"  Moves: {len(moves)}")
                else:
                    results.failed += 1
                    results.errors.append(f"Game {game_num}: Generation failed")
                    print(f"  ❌ Generation failed")
                    
            except Exception as e:
                results.failed += 1
                error_msg = f"Game {game_num}: {str(e)[:100]}"
                results.errors.append(error_msg)
                print(f"  ❌ Error: {str(e)[:100]}")
            
            print()  # Blank line between games
    
    results.elapsed_time = time.time() - start_time
    
    print()
    print("=" * 70)
    print("BATCH GENERATION COMPLETE")
    print("=" * 70)
    print(results.summary())
    
    if results.failed > 0:
        print(f"\nFailed games ({results.failed}):")
        for error in results.errors[:5]:  # Show first 5 errors
            print(f"  - {error}")
        if len(results.errors) > 5:
            print(f"  ... and {len(results.errors) - 5} more errors")
    
    if results.successful > 0:
        print(f"\nGenerated games ({results.successful}):")
        for game in results.games[:5]:  # Show first 5 games
            print(f"  - {game}")
        if len(results.games) > 5:
            print(f"  ... and {len(results.games) - 5} more games")
    
    print("=" * 70)
    
    return results.failed == 0


def cmd_interactive(args):
    """Handle interactive REPL mode."""
    print("=" * 70)
    print("CAISSA: Interactive Mode")
    print("=" * 70)
    print()
    print("Commands:")
    print("  generate [style]  - Generate a game")
    print("  styles            - List available styles")
    print("  set <key> <value> - Set configuration option")
    print("  config            - Show current configuration")
    print("  stats             - Show session statistics")
    print("  help              - Show this help")
    print("  quit              - Exit interactive mode")
    print()
    
    session = SessionStats()
    config = GenerationConfig()
    
    while True:
        try:
            user_input = input("caissa> ").strip()
            
            if not user_input:
                continue
            
            parts = user_input.split()
            cmd = parts[0].lower()
            
            if cmd in ("quit", "exit", "q"):
                print("\nGoodbye!")
                print(session.summary())
                break
            
            elif cmd == "help":
                print("Commands: generate, styles, set, config, stats, help, quit")
            
            elif cmd == "styles":
                slider = StyleSlider()
                for style, desc in slider.get_all_styles().items():
                    print(f"  {style.value}: {desc}")
            
            elif cmd == "config":
                print(f"Current configuration:")
                for key, value in config.to_dict().items():
                    print(f"  {key}: {value}")
            
            elif cmd == "set":
                if len(parts) >= 3:
                    key, value = parts[1], " ".join(parts[2:])
                    if hasattr(config, key):
                        try:
                            current_type = type(getattr(config, key))
                            if current_type == int:
                                setattr(config, key, int(value))
                            elif current_type == bool:
                                setattr(config, key, value.lower() in ("true", "1", "yes"))
                            else:
                                setattr(config, key, value)
                            print(f"Set {key} = {value}")
                        except ValueError as e:
                            print(f"Error: {e}")
                    else:
                        print(f"Unknown option: {key}")
                else:
                    print("Usage: set <key> <value>")
            
            elif cmd == "generate":
                style_name = parts[1] if len(parts) > 1 else config.style
                print(f"Generating game with style: {style_name}...")
                print("(Note: LLM provider required for actual generation)")
                session.add_game(style_name, config.theme, 40)  # Placeholder
            
            elif cmd == "stats":
                print(session.summary())
            
            else:
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")
        
        except KeyboardInterrupt:
            print("\n\nInterrupted. Type 'quit' to exit.")
        except EOFError:
            print("\nGoodbye!")
            break
    
    return True


def cmd_analyze(args):
    """Handle PGN analysis command."""
    print("=" * 70)
    print("CAISSA: Game Analysis")
    print("=" * 70)
    print()
    
    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        return False
    
    print(f"Analyzing: {filepath}")
    print(f"Analysis depth: {args.depth}")
    print(f"Beauty analysis: {args.beauty}")
    print()
    
    try:
        import chess.pgn
        
        with open(filepath) as f:
            game = chess.pgn.read_game(f)
        
        if game is None:
            print("Error: Could not parse PGN file")
            return False
        
        # Extract headers
        print("Game Information:")
        print(f"  Event: {game.headers.get('Event', 'Unknown')}")
        print(f"  White: {game.headers.get('White', 'Unknown')}")
        print(f"  Black: {game.headers.get('Black', 'Unknown')}")
        print(f"  Result: {game.headers.get('Result', '*')}")
        print()
        
        # Count moves
        board = game.board()
        move_count = 0
        for move in game.mainline_moves():
            board.push(move)
            move_count += 1
        
        print(f"Total Moves: {move_count}")
        print(f"Full Moves: {(move_count + 1) // 2}")
        print()
        
        if args.beauty:
            print("Beauty Analysis:")
            print("  (Note: Stockfish required for full beauty evaluation)")
            print("  Sacrifices detected: [requires implementation]")
            print("  Tactical motifs: [requires implementation]")
        
        return True
        
    except Exception as e:
        print(f"Error analyzing file: {e}")
        return False


def cmd_matchup(args):
    """Handle historical matchup generation."""
    print("=" * 70)
    print(f"CAISSA: Historical Matchup")
    print("=" * 70)
    print()
    print(f"  White: {args.white_player}")
    print(f"  Black: {args.black_player}")
    print(f"  Opening: {args.opening or 'Random'}")
    print(f"  Output: {args.output}")
    print(f"  Pretty format: {getattr(args, 'pretty', False)}")
    print()
    
    # Map player names to styles
    PLAYER_STYLE_MAP = {
        "tal": "tal",
        "capablanca": "capablanca",
        "morphy": "morphy",
        "fischer": "morphy",  # Similar aggressive style
        "kasparov": "tal",
        "karpov": "karpov",
        "petrosian": "karpov",
        "carlsen": "neural",
        "anand": "neural",
    }
    
    white_style = PLAYER_STYLE_MAP.get(args.white_player.lower(), "morphy")
    black_style = PLAYER_STYLE_MAP.get(args.black_player.lower(), "karpov")
    
    print(f"Style mapping:")
    print(f"  {args.white_player} → {white_style}")
    print(f"  {args.black_player} → {black_style}")
    print()
    print("(Note: LLM provider required for actual generation)")
    
    return True


def cmd_stats(args):
    """Display generation statistics."""
    print("=" * 70)
    print("CAISSA: Generation Statistics")
    print("=" * 70)
    print()
    
    # Check for stats file
    stats_file = Path(".caissa_stats.json")
    
    if stats_file.exists():
        try:
            with open(stats_file) as f:
                stats = json.load(f)
            
            print(f"Total games generated: {stats.get('total_games', 0)}")
            print(f"Total moves generated: {stats.get('total_moves', 0)}")
            print(f"Average moves per game: {stats.get('avg_moves', 0):.1f}")
            print()
            print("Games by style:")
            for style, count in stats.get('styles', {}).items():
                print(f"  {style}: {count}")
            
        except Exception as e:
            print(f"Error reading stats: {e}")
    else:
        print("No statistics available yet.")
        print("Generate some games to start collecting statistics.")
    
    return True


def cmd_version(args):
    """Display version information."""
    print("""
    CAISSA: The Aesthetic Chess Engine
    
    Version: 0.3.2 (Phase 3.2+ - Enhanced Benchmarking)
    
    Components:
    - Core Generator: v3.0
    - Prompt Manager: v3.1 (with personalities)
    - Legality Engine: v3.1 (with suggestions)
    - Beauty Evaluator: v3.1 (with pattern recognition)
    - Style Slider: v3.1 (with 20 player profiles)
    - PGN Builder: v3.1 (with Enhanced Formatting)
    
    New Features:
    - Pretty PGN output with proper indentation
    - Organized move comments aligned with moves
    - Standard PGN header formatting
    - Line wrapping for long comments
    
    Python: 3.11+
    License: MIT
    Repository: https://github.com/yourusername/caissa-chess
    """)
    return True


# =============================================================================
# ENHANCED CORE GENERATOR INTEGRATION
# =============================================================================

def enhance_core_generator():
    """
    Monkey-patch the core generator to use the unified export pipeline.
    This function would be called at startup.
    """
    try:
        from core.generator import CaissaGenerator
        from export.annotation_parser import parse_pgn
        from export.game_exporter import GameExporter
        
        original_generate_game = CaissaGenerator.generate_game
        
        def enhanced_generate_game(self, context, pretty_format=True):
            """Enhanced version that returns well-formatted PGN."""
            success, pgn_string, moves = original_generate_game(self, context)
            
            if success and pretty_format:
                parsed = parse_pgn(pgn_string)
                exporter = GameExporter(game=parsed)
                pgn_string = exporter.export_pgn()
            
            return success, pgn_string, moves
        
        # Apply the patch
        CaissaGenerator.generate_game = enhanced_generate_game
        
        print("Enhanced PGN formatting enabled in core generator")
        
    except ImportError as e:
        print(f"Warning: Could not enhance core generator: {e}")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point (DEPRECATED — use ``python main.py`` or ``caissa`` instead)."""
    import warnings
    warnings.warn(
        "caissa.py is deprecated and will be removed in v0.4. "
        "Use 'python main.py' or the 'caissa' CLI command instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Force UTF-8 for Windows console
    if sys.platform == "win32":
        try:
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        except Exception as e:
            # Fallback for environments where this isn't possible
            print(f"Warning: Could not set UTF-8 output encoding: {e}")

    # Enhance core generator for pretty PGN output
    enhance_core_generator()
    
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
    # PHASE 3.1: New commands
    elif args.command == "batch":
        return 0 if cmd_batch(args) else 1
    elif args.command == "interactive":
        return 0 if cmd_interactive(args) else 1
    elif args.command == "analyze":
        return 0 if cmd_analyze(args) else 1
    elif args.command == "matchup":
        return 0 if cmd_matchup(args) else 1
    elif args.command == "stats":
        return 0 if cmd_stats(args) else 1
    elif args.command == "version":
        return 0 if cmd_version(args) else 1
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
