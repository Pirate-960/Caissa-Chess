"""
benchmarks/quality_analyzer.py

Automated quality analysis for generated chess games.

PHASE 3.2+: Quality Scoring System
- Move quality assessment (accuracy, creativity, tactical sharpness)
- Game structure analysis (opening, middlegame, endgame)
- Aesthetic scoring integration
- Comparative quality metrics

Scoring Dimensions:
- Legality Score: 0-100 (% legal moves)
- Tactical Score: 0-100 (sacrifices, combinations, checks)
- Aesthetic Score: 0-100 (beauty, creativity, memorability)
- Structural Score: 0-100 (opening theory, coherent play)
- Overall Score: Weighted combination
"""

import re
import sys
import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import chess
    import chess.pgn
    from io import StringIO
except ImportError:
    chess = None

logger = logging.getLogger(__name__)


# =============================================================================
# QUALITY SCORING CONSTANTS
# =============================================================================

class QualityDimension(Enum):
    """Quality scoring dimensions."""
    LEGALITY = "legality"
    TACTICAL = "tactical"
    AESTHETIC = "aesthetic"
    STRUCTURAL = "structural"
    OVERALL = "overall"


# Default weights for overall score
DEFAULT_WEIGHTS = {
    QualityDimension.LEGALITY: 0.30,
    QualityDimension.TACTICAL: 0.25,
    QualityDimension.AESTHETIC: 0.25,
    QualityDimension.STRUCTURAL: 0.20,
}

# Tactical patterns and their scores
TACTICAL_PATTERNS = {
    # Piece sacrifices (indicated by capture followed by opponent recapture)
    "knight_sacrifice": 15,
    "bishop_sacrifice": 15,
    "rook_sacrifice": 20,
    "queen_sacrifice": 30,
    
    # Attack patterns
    "check": 5,
    "double_check": 15,
    "discovered_attack": 10,
    "fork": 12,
    "pin": 8,
    "skewer": 10,
    
    # Endgame patterns
    "checkmate": 25,
    "stalemate": 10,
}

# Opening book moves (common first moves that indicate theory knowledge)
OPENING_MOVES = {
    "e4", "d4", "Nf3", "c4", "g3", "b3", "f4",  # White openings
    "e5", "d5", "c5", "Nf6", "c6", "e6", "g6",  # Black responses
}

# Common opening names to detect
KNOWN_OPENINGS = [
    ("e4 e5 Nf3 Nc6 Bb5", "Ruy Lopez"),
    ("e4 e5 Nf3 Nc6 Bc4", "Italian Game"),
    ("e4 e5 Nf3 Nc6 d4", "Scotch Game"),
    ("e4 c5", "Sicilian Defense"),
    ("d4 d5 c4", "Queen's Gambit"),
    ("d4 Nf6 c4 g6", "King's Indian"),
    ("e4 e6", "French Defense"),
    ("e4 c6", "Caro-Kann"),
    ("d4 d5 Bf4", "London System"),
    ("Nf3 d5 g3", "Reti Opening"),
]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class MoveAnalysis:
    """Analysis of a single move."""
    san: str
    is_capture: bool = False
    is_check: bool = False
    is_castle: bool = False
    is_promotion: bool = False
    piece_moved: str = ""
    tactical_value: int = 0


@dataclass
class DimensionScore:
    """Score for a single quality dimension."""
    dimension: QualityDimension
    score: float  # 0-100
    factors: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension.value,
            "score": self.score,
            "factors": self.factors,
        }


@dataclass
class QualityReport:
    """Complete quality analysis report."""
    scores: Dict[QualityDimension, DimensionScore] = field(default_factory=dict)
    overall_score: float = 0.0
    grade: str = ""  # A, B, C, D, F
    move_count: int = 0
    detected_opening: str = ""
    tactical_highlights: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "grade": self.grade,
            "move_count": self.move_count,
            "detected_opening": self.detected_opening,
            "tactical_highlights": self.tactical_highlights,
            "warnings": self.warnings,
            "dimensions": {d.value: s.to_dict() for d, s in self.scores.items()},
        }
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Quality Report: {self.grade} ({self.overall_score:.0f}/100)",
            f"  Moves: {self.move_count}",
        ]
        
        if self.detected_opening:
            lines.append(f"  Opening: {self.detected_opening}")
        
        lines.append("")
        lines.append("  Dimension Scores:")
        for dim, score in self.scores.items():
            lines.append(f"    {dim.value.capitalize():12} {score.score:5.1f}/100")
        
        if self.tactical_highlights:
            lines.append("")
            lines.append("  Tactical Highlights:")
            for highlight in self.tactical_highlights[:5]:
                lines.append(f"    • {highlight}")
        
        if self.warnings:
            lines.append("")
            lines.append("  Warnings:")
            for warning in self.warnings[:3]:
                lines.append(f"    ⚠ {warning}")
        
        return "\n".join(lines)


# =============================================================================
# QUALITY ANALYZER
# =============================================================================

class QualityAnalyzer:
    """
    Analyzes the quality of generated chess games.
    
    Provides multi-dimensional scoring across legality, tactics,
    aesthetics, and structure.
    """
    
    def __init__(self, weights: Optional[Dict[QualityDimension, float]] = None):
        """
        Initialize analyzer with optional custom weights.
        
        Args:
            weights: Custom weights for each dimension (must sum to 1.0)
        """
        self.weights = weights or DEFAULT_WEIGHTS.copy()
        self._beauty_evaluator = None
    
    @property
    def beauty_evaluator(self):
        """Lazy-load beauty evaluator."""
        if self._beauty_evaluator is None:
            try:
                from aesthetic.beauty_eval import BeautyEvaluator
                self._beauty_evaluator = BeautyEvaluator()
            except ImportError:
                pass
        return self._beauty_evaluator
    
    def analyze(self, pgn_or_moves: str) -> QualityReport:
        """
        Analyze a game and return a quality report.
        
        Args:
            pgn_or_moves: Either a full PGN string or move list
            
        Returns:
            QualityReport with scores and analysis
        """
        report = QualityReport()
        logger.debug("Starting quality analysis (input_length=%d)", len(pgn_or_moves or ""))
        
        # Parse the game
        game, moves, board = self._parse_game(pgn_or_moves)
        
        if not moves:
            report.warnings.append("No valid moves found")
            report.grade = "F"
            logger.warning("Quality analysis failed: no valid moves found")
            return report
        
        report.move_count = len(moves)
        
        # Analyze each dimension
        report.scores[QualityDimension.LEGALITY] = self._analyze_legality(moves, board)
        report.scores[QualityDimension.TACTICAL] = self._analyze_tactical(moves, game)
        report.scores[QualityDimension.AESTHETIC] = self._analyze_aesthetic(moves, game)
        report.scores[QualityDimension.STRUCTURAL] = self._analyze_structural(moves, game)
        
        # Detect opening
        report.detected_opening = self._detect_opening(moves)
        
        # Extract tactical highlights
        report.tactical_highlights = self._extract_highlights(moves, game)
        
        # Calculate overall score
        report.overall_score = self._calculate_overall(report.scores)
        report.grade = self._score_to_grade(report.overall_score)
        logger.info(
            "Quality analysis complete: moves=%d score=%.1f grade=%s opening=%s",
            report.move_count,
            report.overall_score,
            report.grade,
            report.detected_opening or "unknown",
        )
        
        return report
    
    def _parse_game(self, pgn_or_moves: str) -> Tuple[Any, List[str], Any]:
        """Parse PGN or move list into game object."""
        if chess is None:
            return None, [], None
        
        moves = []
        game = None
        board = chess.Board()
        
        # Try to parse as PGN
        try:
            game = chess.pgn.read_game(StringIO(pgn_or_moves))
            if game:
                board = game.board()
                for move in game.mainline_moves():
                    moves.append(board.san(move))
                    board.push(move)
                return game, moves, board
        except Exception:
            pass
        
        # Try to parse as move list
        try:
            # Extract just the moves (remove move numbers)
            clean = re.sub(r'\d+\.+\s*', '', pgn_or_moves)
            potential_moves = clean.split()
            
            board = chess.Board()
            for move_san in potential_moves:
                # Skip result markers
                if move_san in ["1-0", "0-1", "1/2-1/2", "*"]:
                    continue
                try:
                    move = board.parse_san(move_san)
                    moves.append(move_san)
                    board.push(move)
                except Exception:
                    break
            
            return None, moves, board
        except Exception:
            pass
        
        return None, [], board
    
    def _analyze_legality(self, moves: List[str], board: Any) -> DimensionScore:
        """Analyze legality of moves."""
        if not moves:
            return DimensionScore(QualityDimension.LEGALITY, 0.0, {"error": "No moves"})
        
        # If we got here, all moves were valid (parsed successfully)
        legal_count = len(moves)
        
        # Penalize very short games
        length_factor = min(1.0, len(moves) / 10)
        
        score = 100 * length_factor
        
        return DimensionScore(
            QualityDimension.LEGALITY,
            score,
            {
                "legal_moves": legal_count,
                "total_moves": legal_count,
                "length_factor": length_factor,
            }
        )
    
    def _analyze_tactical(self, moves: List[str], game: Any) -> DimensionScore:
        """Analyze tactical content of the game."""
        factors = {
            "checks": 0,
            "captures": 0,
            "castles": 0,
            "promotions": 0,
            "piece_sacrifices": 0,
        }
        
        for move in moves:
            if "+" in move or "#" in move:
                factors["checks"] += 1
            if "x" in move:
                factors["captures"] += 1
            if "O-O" in move:
                factors["castles"] += 1
            if "=" in move:
                factors["promotions"] += 1
            
            # Detect potential sacrifices (piece captures followed by recapture)
            # This is a heuristic - real sacrifice detection needs board analysis
            if "x" in move:
                piece = move[0] if move[0].isupper() else "P"
                if piece in ["R", "Q"]:
                    factors["piece_sacrifices"] += 1
        
        # Calculate tactical score
        base_score = 30  # Minimum for any valid game
        
        # Add points for tactical elements
        tactical_points = (
            factors["checks"] * 5 +
            factors["captures"] * 2 +
            factors["piece_sacrifices"] * 15 +
            factors["promotions"] * 10
        )
        
        # Normalize to 0-70 range and add to base
        normalized_tactical = min(70, tactical_points)
        score = base_score + normalized_tactical
        
        return DimensionScore(QualityDimension.TACTICAL, min(100, score), factors)
    
    def _analyze_aesthetic(self, moves: List[str], game: Any) -> DimensionScore:
        """Analyze aesthetic quality of the game."""
        factors = {}
        
        # Try to use beauty evaluator
        if self.beauty_evaluator and chess:
            try:
                # Parse moves into chess.Move objects
                board = chess.Board()
                move_objects = []
                for san in moves:
                    try:
                        move = board.parse_san(san)
                        move_objects.append(move)
                        board.push(move)
                    except Exception:
                        break
                
                if move_objects:
                    beauty_result = self.beauty_evaluator.evaluate_game(move_objects)
                    if hasattr(beauty_result, 'total_beauty_score'):
                        # Normalize beauty score to 0-100
                        # Assuming beauty score can range from -50 to 50
                        normalized = (beauty_result.total_beauty_score + 50) / 100 * 100
                        factors["beauty_score"] = beauty_result.total_beauty_score
                        factors["sacrifice_count"] = getattr(beauty_result, 'sacrifice_count', 0)
                        factors["quiet_brilliancies"] = getattr(beauty_result, 'quiet_brilliancies', 0)
                        return DimensionScore(
                            QualityDimension.AESTHETIC,
                            min(100, max(0, normalized)),
                            factors
                        )
            except Exception as e:
                factors["error"] = str(e)
        
        # Fallback: Simple aesthetic heuristic
        score = 50  # Base score
        
        # Variety bonus
        unique_pieces = set(m[0] for m in moves if m[0].isupper())
        score += len(unique_pieces) * 3
        
        # Complexity bonus (longer games are more interesting)
        if len(moves) > 20:
            score += 10
        if len(moves) > 40:
            score += 10
        
        # Check for memorable patterns
        if any("#" in m for m in moves):
            score += 15  # Checkmate bonus
        
        return DimensionScore(QualityDimension.AESTHETIC, min(100, score), factors)
    
    def _analyze_structural(self, moves: List[str], game: Any) -> DimensionScore:
        """Analyze structural quality (opening theory, coherent play)."""
        factors = {
            "follows_opening_theory": False,
            "balanced_development": False,
            "clear_phases": False,
        }
        
        score = 40  # Base score
        
        if not moves:
            return DimensionScore(QualityDimension.STRUCTURAL, 0, factors)
        
        # Check opening moves
        if len(moves) >= 2:
            if moves[0] in OPENING_MOVES:
                score += 10
                factors["follows_opening_theory"] = True
            if len(moves) >= 2 and moves[1] in OPENING_MOVES:
                score += 10
        
        # Check for balanced development (multiple piece types used early)
        first_10 = moves[:10]
        pieces_developed = set(m[0] for m in first_10 if m[0].isupper())
        if len(pieces_developed) >= 3:
            score += 15
            factors["balanced_development"] = True
        
        # Check for castling (indicates proper development)
        if any("O-O" in m for m in moves[:15]):
            score += 15
        
        # Check game has clear phases (opening, middle, endgame length)
        if len(moves) > 30:
            score += 10
            factors["clear_phases"] = True
        
        return DimensionScore(QualityDimension.STRUCTURAL, min(100, score), factors)
    
    def _detect_opening(self, moves: List[str]) -> str:
        """Detect the opening played."""
        if len(moves) < 2:
            return ""
        
        # Build move string
        move_string = " ".join(moves[:10])
        
        # Check against known openings
        for pattern, name in KNOWN_OPENINGS:
            if move_string.startswith(pattern) or pattern in move_string:
                return name
        
        # Generic opening detection
        if moves[0] == "e4":
            if len(moves) > 1 and moves[1] == "e5":
                return "Open Game (e4 e5)"
            return "King's Pawn Opening"
        elif moves[0] == "d4":
            if len(moves) > 1 and moves[1] == "d5":
                return "Closed Game (d4 d5)"
            return "Queen's Pawn Opening"
        elif moves[0] == "Nf3":
            return "Reti Opening"
        elif moves[0] == "c4":
            return "English Opening"
        
        return "Unknown Opening"
    
    def _extract_highlights(self, moves: List[str], game: Any) -> List[str]:
        """Extract notable tactical moments from the game."""
        highlights = []
        
        for i, move in enumerate(moves):
            move_num = i // 2 + 1
            color = "White" if i % 2 == 0 else "Black"
            
            if "#" in move:
                highlights.append(f"Move {move_num}: {color} delivers checkmate with {move}")
            elif "Q" in move and "x" in move and "+" in move:
                highlights.append(f"Move {move_num}: {color} Queen sacrifice with check! ({move})")
            elif move.count("=") > 0:
                highlights.append(f"Move {move_num}: {color} promotes pawn ({move})")
            elif "++" in move:
                highlights.append(f"Move {move_num}: Double check by {color} ({move})")
        
        return highlights[:10]  # Limit to 10 highlights
    
    def _calculate_overall(self, scores: Dict[QualityDimension, DimensionScore]) -> float:
        """Calculate weighted overall score."""
        total = 0.0
        weight_sum = 0.0
        
        for dim, weight in self.weights.items():
            if dim in scores:
                total += scores[dim].score * weight
                weight_sum += weight
        
        return total / weight_sum if weight_sum > 0 else 0.0
    
    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "A-"
        elif score >= 75:
            return "B+"
        elif score >= 70:
            return "B"
        elif score >= 65:
            return "B-"
        elif score >= 60:
            return "C+"
        elif score >= 55:
            return "C"
        elif score >= 50:
            return "C-"
        elif score >= 45:
            return "D+"
        elif score >= 40:
            return "D"
        else:
            return "F"


# =============================================================================
# BATCH ANALYZER
# =============================================================================

class BatchQualityAnalyzer:
    """Analyze quality across multiple games."""
    
    def __init__(self, analyzer: Optional[QualityAnalyzer] = None):
        self.analyzer = analyzer or QualityAnalyzer()
    
    def analyze_batch(self, games: List[str]) -> Dict[str, Any]:
        """
        Analyze a batch of games.
        
        Args:
            games: List of PGN strings or move lists
            
        Returns:
            Aggregate statistics and individual reports
        """
        reports = []
        logger.info("Starting batch quality analysis for %d games", len(games))
        
        for game in games:
            try:
                report = self.analyzer.analyze(game)
                reports.append(report)
            except Exception as e:
                reports.append(QualityReport(warnings=[str(e)], grade="F"))
        
        # Aggregate statistics
        valid_reports = [r for r in reports if r.overall_score > 0]
        
        if not valid_reports:
            logger.warning("Batch quality analysis produced no valid reports")
            return {
                "total_games": len(games),
                "valid_games": 0,
                "average_score": 0,
                "grade_distribution": {},
                "reports": [r.to_dict() for r in reports],
            }
        
        import statistics
        
        scores = [r.overall_score for r in valid_reports]
        grades = [r.grade for r in valid_reports]
        
        grade_dist = {}
        for grade in grades:
            grade_dist[grade] = grade_dist.get(grade, 0) + 1
        
        result = {
            "total_games": len(games),
            "valid_games": len(valid_reports),
            "average_score": statistics.mean(scores),
            "median_score": statistics.median(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "std_dev": statistics.stdev(scores) if len(scores) > 1 else 0,
            "grade_distribution": grade_dist,
            "dimension_averages": self._dimension_averages(valid_reports),
            "reports": [r.to_dict() for r in reports],
        }
        logger.info(
            "Batch quality analysis complete: valid=%d/%d avg=%.1f",
            result["valid_games"],
            result["total_games"],
            result["average_score"],
        )
        return result
    
    def _dimension_averages(self, reports: List[QualityReport]) -> Dict[str, float]:
        """Calculate average scores per dimension."""
        if not reports:
            return {}
        
        dim_scores = {}
        for report in reports:
            for dim, score in report.scores.items():
                if dim.value not in dim_scores:
                    dim_scores[dim.value] = []
                dim_scores[dim.value].append(score.score)
        
        import statistics
        return {dim: statistics.mean(scores) for dim, scores in dim_scores.items()}


# =============================================================================
# CLI
# =============================================================================

def main():
    """CLI for quality analysis."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze chess game quality")
    parser.add_argument("input", help="PGN file or inline PGN string")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Read input
    if os.path.isfile(args.input):
        with open(args.input) as f:
            pgn = f.read()
    else:
        pgn = args.input
    
    # Analyze
    analyzer = QualityAnalyzer()
    report = analyzer.analyze(pgn)
    
    if args.json:
        import json
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.summary())
        
        if args.verbose:
            print("\nDetailed Factors:")
            for dim, score in report.scores.items():
                print(f"\n  {dim.value.upper()}:")
                for key, value in score.factors.items():
                    print(f"    {key}: {value}")


if __name__ == "__main__":
    main()
