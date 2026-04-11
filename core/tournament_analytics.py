"""
Tournament Analytics Module for CAISSA Chess v0.5.0

This module provides advanced analytics for tournament matches:
- Style fingerprinting (detecting playing patterns)
- Provider performance metrics
- Opening analysis
- Game quality scoring
- Statistical comparisons

Author: CAISSA Team
Version: 0.5.0
"""

import logging
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
import chess

from core.match_engine import MatchResult, MoveRecord
from core.tournament_player import TournamentPlayer
from core.elo_calculator import GameResult


logger = logging.getLogger(__name__)


class PlayingStyle(Enum):
    """Detected playing style categories."""
    AGGRESSIVE = "aggressive"       # Attacks, sacrifices, king-side play
    POSITIONAL = "positional"       # Slow maneuvering, piece placement
    TACTICAL = "tactical"           # Combinations, forcing sequences
    SOLID = "solid"                 # Safety-first, defensive
    DYNAMIC = "dynamic"             # Active, piece activity focused
    UNIVERSAL = "universal"         # Balanced, adapts to position


class OpeningCategory(Enum):
    """Opening classification categories."""
    E4_OPEN = "e4_open"             # Open games (1.e4 e5)
    E4_SEMI_OPEN = "e4_semi_open"   # Semi-open (1.e4 other)
    D4_CLOSED = "d4_closed"         # Closed games (1.d4)
    INDIAN = "indian"               # Indian defenses
    FLANK = "flank"                 # Flank openings (1.c4, 1.Nf3, etc.)
    IRREGULAR = "irregular"         # Unusual openings
    UNKNOWN = "unknown"


@dataclass
class StyleFingerprint:
    """
    Playing style fingerprint for a player.
    
    Captures characteristic patterns and tendencies.
    """
    player_id: str
    player_name: str
    games_analyzed: int = 0
    
    # Primary style classification
    primary_style: PlayingStyle = PlayingStyle.UNIVERSAL
    style_scores: Dict[PlayingStyle, float] = field(default_factory=dict)
    
    # Opening preferences
    opening_preferences: Dict[OpeningCategory, int] = field(default_factory=dict)
    favorite_openings: List[str] = field(default_factory=list)
    
    # Tactical tendencies
    avg_pieces_traded: float = 0.0
    sacrifice_rate: float = 0.0          # % of games with material sacrifice
    avg_complexity: float = 0.0          # 0-10 scale
    avg_game_length: float = 0.0
    
    # Time management
    avg_think_time: float = 0.0
    time_pressure_performance: float = 0.0  # How well they play with less time
    
    # Accuracy metrics
    avg_centipawn_loss: float = 0.0
    blunder_rate: float = 0.0            # Blunders per 100 moves
    brilliancy_rate: float = 0.0         # Brilliancies per 100 moves
    
    # Color performance
    white_win_rate: float = 0.0
    black_win_rate: float = 0.0
    
    # Endgame tendencies
    endgame_conversion_rate: float = 0.0  # % of winning endgames converted
    avg_endgame_length: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "player_id": self.player_id,
            "player_name": self.player_name,
            "games_analyzed": self.games_analyzed,
            "primary_style": self.primary_style.value,
            "style_scores": {k.value: v for k, v in self.style_scores.items()},
            "opening_preferences": {k.value: v for k, v in self.opening_preferences.items()},
            "favorite_openings": self.favorite_openings,
            "avg_complexity": self.avg_complexity,
            "avg_game_length": self.avg_game_length,
            "avg_centipawn_loss": self.avg_centipawn_loss,
            "white_win_rate": self.white_win_rate,
            "black_win_rate": self.black_win_rate,
        }


@dataclass
class ProviderMetrics:
    """
    Performance metrics for an LLM provider.
    
    Tracks how well a provider performs at chess.
    """
    provider_name: str
    model_name: str
    games_played: int = 0
    
    # Win/Loss/Draw
    wins: int = 0
    losses: int = 0
    draws: int = 0
    
    # Points (1 for win, 0.5 for draw)
    total_points: float = 0.0
    
    # Instruction following
    total_moves: int = 0
    illegal_move_attempts: int = 0
    forfeits: int = 0
    
    # Quality metrics
    total_centipawn_loss: float = 0.0
    total_blunders: int = 0
    total_mistakes: int = 0
    total_inaccuracies: int = 0
    total_brilliancies: int = 0
    
    # Time usage
    total_think_time: float = 0.0
    
    # ELO
    current_elo: int = 1500
    peak_elo: int = 1500
    lowest_elo: int = 1500
    
    @property
    def win_rate(self) -> float:
        """Win rate percentage."""
        if self.games_played == 0:
            return 0.0
        return (self.wins / self.games_played) * 100
    
    @property
    def draw_rate(self) -> float:
        """Draw rate percentage."""
        if self.games_played == 0:
            return 0.0
        return (self.draws / self.games_played) * 100
    
    @property
    def illegal_move_rate(self) -> float:
        """Illegal moves per 100 moves."""
        if self.total_moves == 0:
            return 0.0
        return (self.illegal_move_attempts / self.total_moves) * 100
    
    @property
    def avg_centipawn_loss(self) -> float:
        """Average centipawn loss per game."""
        if self.games_played == 0:
            return 0.0
        return self.total_centipawn_loss / self.games_played
    
    @property
    def avg_think_time(self) -> float:
        """Average think time per move."""
        if self.total_moves == 0:
            return 0.0
        return self.total_think_time / self.total_moves
    
    @property
    def instruction_following_score(self) -> float:
        """
        Score from 0-100 measuring instruction following ability.
        
        Based on:
        - Illegal move rate (lower is better)
        - Forfeit rate (lower is better)
        """
        if self.total_moves == 0:
            return 100.0
        
        illegal_penalty = min(50, self.illegal_move_rate * 5)
        forfeit_penalty = min(50, (self.forfeits / max(1, self.games_played)) * 100)
        
        return max(0, 100 - illegal_penalty - forfeit_penalty)
    
    @property
    def overall_rating(self) -> float:
        """
        Composite performance rating (0-100).
        
        Combines:
        - Win rate (30%)
        - Instruction following (30%)
        - Accuracy (25%)
        - Efficiency (15%)
        """
        win_score = self.win_rate * 0.3
        instruction_score = self.instruction_following_score * 0.3
        
        # Accuracy: lower ACL is better (scale 0-50 ACL -> 100-0 score)
        accuracy_score = max(0, 100 - self.avg_centipawn_loss * 2) * 0.25
        
        # Efficiency: faster is better (scale 0-30s -> 100-0 score)
        efficiency_score = max(0, 100 - self.avg_think_time * 3.33) * 0.15
        
        return win_score + instruction_score + accuracy_score + efficiency_score
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "games_played": self.games_played,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "win_rate": self.win_rate,
            "illegal_move_rate": self.illegal_move_rate,
            "avg_centipawn_loss": self.avg_centipawn_loss,
            "instruction_following_score": self.instruction_following_score,
            "overall_rating": self.overall_rating,
            "current_elo": self.current_elo,
            "peak_elo": self.peak_elo,
        }


@dataclass
class OpeningStats:
    """Statistics for a specific opening."""
    eco_code: str
    name: str
    games: int = 0
    white_wins: int = 0
    black_wins: int = 0
    draws: int = 0
    avg_game_length: float = 0.0
    
    @property
    def white_win_rate(self) -> float:
        if self.games == 0:
            return 0.0
        return (self.white_wins / self.games) * 100
    
    @property
    def draw_rate(self) -> float:
        if self.games == 0:
            return 0.0
        return (self.draws / self.games) * 100


class TournamentAnalytics:
    """
    Analytics engine for tournament data.
    
    Provides comprehensive analysis of matches, players, and providers.
    
    Example:
        ```python
        analytics = TournamentAnalytics()
        
        for match in tournament.matches:
            analytics.add_match(match)
        
        fingerprints = analytics.generate_style_fingerprints()
        provider_metrics = analytics.get_provider_metrics()
        report = analytics.generate_report()
        ```
    """
    
    def __init__(self):
        """Initialize the analytics engine."""
        self.matches: List[MatchResult] = []
        self.players: Dict[str, TournamentPlayer] = {}
        
        # Computed metrics
        self._provider_metrics: Dict[str, ProviderMetrics] = {}
        self._style_fingerprints: Dict[str, StyleFingerprint] = {}
        self._opening_stats: Dict[str, OpeningStats] = {}
        logger.info("TournamentAnalytics initialized")
    
    def add_match(self, match: MatchResult):
        """
        Add a match to the analytics dataset.
        
        Args:
            match: Completed match result
        """
        self.matches.append(match)
        self.players[match.white.id] = match.white
        self.players[match.black.id] = match.black
        logger.debug(
            "Added match to analytics: %s (%s vs %s, result=%s)",
            match.match_id,
            match.white.name,
            match.black.name,
            match.result.value,
        )
        
        # Update provider metrics
        self._update_provider_metrics(match)
    
    def _update_provider_metrics(self, match: MatchResult):
        """Update provider metrics with match data."""
        for player, color in [(match.white, "white"), (match.black, "black")]:
            key = f"{player.provider_name}:{player.model_name}"
            
            if key not in self._provider_metrics:
                self._provider_metrics[key] = ProviderMetrics(
                    provider_name=player.provider_name,
                    model_name=player.model_name,
                )
            
            metrics = self._provider_metrics[key]
            metrics.games_played += 1
            
            # Win/Loss/Draw
            if match.result == GameResult.WHITE_WINS:
                if color == "white":
                    metrics.wins += 1
                    metrics.total_points += 1.0
                else:
                    metrics.losses += 1
            elif match.result == GameResult.BLACK_WINS:
                if color == "black":
                    metrics.wins += 1
                    metrics.total_points += 1.0
                else:
                    metrics.losses += 1
            else:
                metrics.draws += 1
                metrics.total_points += 0.5
            
            # Move stats
            player_moves = [m for m in match.moves if m.color == color]
            metrics.total_moves += len(player_moves)
            
            if color == "white":
                metrics.illegal_move_attempts += match.white_illegal_attempts
                metrics.total_think_time += match.white_think_time
                metrics.total_centipawn_loss += match.white_avg_centipawn_loss
                metrics.total_blunders += match.white_blunders
            else:
                metrics.illegal_move_attempts += match.black_illegal_attempts
                metrics.total_think_time += match.black_think_time
                metrics.total_centipawn_loss += match.black_avg_centipawn_loss
                metrics.total_blunders += match.black_blunders
            
            # Update ELO tracking
            if match.elo_change:
                new_elo = match.elo_change.white_new if color == "white" else match.elo_change.black_new
                metrics.current_elo = new_elo
                metrics.peak_elo = max(metrics.peak_elo, new_elo)
                metrics.lowest_elo = min(metrics.lowest_elo, new_elo)
    
    def get_provider_metrics(self) -> Dict[str, ProviderMetrics]:
        """Get metrics for all providers."""
        return self._provider_metrics
    
    def get_provider_ranking(self) -> List[Tuple[str, ProviderMetrics]]:
        """Get providers ranked by overall rating."""
        return sorted(
            self._provider_metrics.items(),
            key=lambda x: x[1].overall_rating,
            reverse=True,
        )
    
    def generate_style_fingerprints(self) -> Dict[str, StyleFingerprint]:
        """
        Generate style fingerprints for all players.
        
        Analyzes games to detect playing patterns and tendencies.
        """
        logger.info("Generating style fingerprints for %d players", len(self.players))
        for player_id, player in self.players.items():
            fingerprint = self._analyze_player_style(player)
            self._style_fingerprints[player_id] = fingerprint
            logger.debug(
                "Style fingerprint ready: %s -> %s (%d games)",
                player.name,
                fingerprint.primary_style.value,
                fingerprint.games_analyzed,
            )
        
        return self._style_fingerprints
    
    def _analyze_player_style(self, player: TournamentPlayer) -> StyleFingerprint:
        """Analyze a player's games to create style fingerprint."""
        fingerprint = StyleFingerprint(
            player_id=player.id,
            player_name=player.name,
        )
        
        # Get all games for this player
        player_matches = [
            m for m in self.matches
            if m.white.id == player.id or m.black.id == player.id
        ]
        
        if not player_matches:
            return fingerprint
        
        fingerprint.games_analyzed = len(player_matches)
        
        # Calculate metrics
        total_moves = 0
        total_captures = 0
        total_checks = 0
        white_wins = 0
        black_wins = 0
        white_games = 0
        black_games = 0
        
        for match in player_matches:
            color = "white" if match.white.id == player.id else "black"
            
            # Color stats
            if color == "white":
                white_games += 1
                if match.result == GameResult.WHITE_WINS:
                    white_wins += 1
            else:
                black_games += 1
                if match.result == GameResult.BLACK_WINS:
                    black_wins += 1
            
            # Move analysis
            for move in match.moves:
                if move.player == player.id:
                    total_moves += 1
                    if move.is_capture:
                        total_captures += 1
                    if move.is_check:
                        total_checks += 1
        
        # Calculate rates
        if total_moves > 0:
            capture_rate = total_captures / total_moves
            check_rate = total_checks / total_moves
            
            # Classify style based on metrics
            if capture_rate > 0.15 and check_rate > 0.08:
                fingerprint.primary_style = PlayingStyle.AGGRESSIVE
            elif capture_rate < 0.08 and check_rate < 0.04:
                fingerprint.primary_style = PlayingStyle.POSITIONAL
            elif check_rate > 0.1:
                fingerprint.primary_style = PlayingStyle.TACTICAL
            else:
                fingerprint.primary_style = PlayingStyle.UNIVERSAL
        
        # Color performance
        fingerprint.white_win_rate = (white_wins / max(1, white_games)) * 100
        fingerprint.black_win_rate = (black_wins / max(1, black_games)) * 100
        
        # Average game length
        fingerprint.avg_game_length = sum(m.total_moves for m in player_matches) / len(player_matches)
        
        return fingerprint
    
    def compare_players(
        self,
        player1_id: str,
        player2_id: str,
    ) -> Dict[str, Any]:
        """
        Compare two players head-to-head.
        
        Args:
            player1_id: First player ID
            player2_id: Second player ID
        
        Returns:
            Dict containing comparison metrics
        """
        head_to_head = [
            m for m in self.matches
            if (m.white.id == player1_id and m.black.id == player2_id) or
               (m.white.id == player2_id and m.black.id == player1_id)
        ]
        
        p1_wins = sum(1 for m in head_to_head if 
                     (m.white.id == player1_id and m.result == GameResult.WHITE_WINS) or
                     (m.black.id == player1_id and m.result == GameResult.BLACK_WINS))
        p2_wins = sum(1 for m in head_to_head if
                     (m.white.id == player2_id and m.result == GameResult.WHITE_WINS) or
                     (m.black.id == player2_id and m.result == GameResult.BLACK_WINS))
        draws = len(head_to_head) - p1_wins - p2_wins
        
        p1_name = self.players[player1_id].name if player1_id in self.players else player1_id
        p2_name = self.players[player2_id].name if player2_id in self.players else player2_id
        
        return {
            "player1": p1_name,
            "player2": p2_name,
            "total_games": len(head_to_head),
            "player1_wins": p1_wins,
            "player2_wins": p2_wins,
            "draws": draws,
            "player1_score": p1_wins + draws * 0.5,
            "player2_score": p2_wins + draws * 0.5,
            "player1_win_rate": (p1_wins / max(1, len(head_to_head))) * 100,
        }
    
    def get_tournament_summary(self) -> Dict[str, Any]:
        """Generate overall tournament summary."""
        if not self.matches:
            return {"error": "No matches to analyze"}
        
        total_games = len(self.matches)
        decisive = sum(1 for m in self.matches if m.is_decisive)
        draws = total_games - decisive
        
        total_moves = sum(m.total_moves for m in self.matches)
        avg_game_length = total_moves / total_games if total_games > 0 else 0
        
        # Best/worst performers
        rankings = self.get_provider_ranking()
        
        return {
            "total_games": total_games,
            "decisive_games": decisive,
            "draws": draws,
            "draw_rate": (draws / total_games) * 100 if total_games > 0 else 0,
            "total_moves": total_moves,
            "avg_game_length": avg_game_length,
            "total_players": len(self.players),
            "best_performer": rankings[0][0] if rankings else None,
            "best_rating": rankings[0][1].overall_rating if rankings else 0,
            "providers_analyzed": len(self._provider_metrics),
        }
    
    def generate_report(self) -> str:
        """Generate a comprehensive analytics report."""
        summary = self.get_tournament_summary()
        rankings = self.get_provider_ranking()
        logger.info(
            "Generating analytics report: games=%s providers=%d",
            summary.get("total_games", 0),
            len(rankings),
        )
        
        lines = [
            "# Tournament Analytics Report",
            "",
            "## Overview",
            f"- Total games: {summary['total_games']}",
            f"- Decisive games: {summary['decisive_games']} ({100 - summary['draw_rate']:.1f}%)",
            f"- Draws: {summary['draws']} ({summary['draw_rate']:.1f}%)",
            f"- Average game length: {summary['avg_game_length']:.1f} moves",
            f"- Players analyzed: {summary['total_players']}",
            "",
            "## Provider Rankings",
            "",
            "| Rank | Provider | Rating | Win% | Games | Illegal% | ACL |",
            "|------|----------|--------|------|-------|----------|-----|",
        ]
        
        for i, (key, metrics) in enumerate(rankings, 1):
            lines.append(
                f"| {i} | {key} | {metrics.overall_rating:.1f} | "
                f"{metrics.win_rate:.1f}% | {metrics.games_played} | "
                f"{metrics.illegal_move_rate:.1f}% | {metrics.avg_centipawn_loss:.1f} |"
            )
        
        lines.extend([
            "",
            "## Style Analysis",
            "",
        ])
        
        for fingerprint in self._style_fingerprints.values():
            lines.append(f"**{fingerprint.player_name}**: {fingerprint.primary_style.value}")
            lines.append(f"  - Avg game length: {fingerprint.avg_game_length:.1f}")
            lines.append(f"  - White win rate: {fingerprint.white_win_rate:.1f}%")
            lines.append(f"  - Black win rate: {fingerprint.black_win_rate:.1f}%")
            lines.append("")
        
        return "\n".join(lines)


def analyze_single_game(match: MatchResult) -> Dict[str, Any]:
    """
    Analyze a single game for quality metrics.
    
    Args:
        match: The match to analyze
    
    Returns:
        Dict with analysis results
    """
    analysis = {
        "match_id": match.match_id,
        "result": match.result.value,
        "total_moves": match.total_moves,
        "duration": match.duration,
        "beauty_score": match.beauty_score,
    }
    
    # Move type breakdown
    captures = sum(1 for m in match.moves if m.is_capture)
    checks = sum(1 for m in match.moves if m.is_check)
    promotions = sum(1 for m in match.moves if m.is_promotion)
    
    analysis["captures"] = captures
    analysis["checks"] = checks
    analysis["promotions"] = promotions
    
    if match.total_moves > 0:
        analysis["capture_rate"] = captures / match.total_moves
        analysis["check_rate"] = checks / match.total_moves
    
    # Accuracy
    analysis["white_acpl"] = match.white_avg_centipawn_loss
    analysis["black_acpl"] = match.black_avg_centipawn_loss
    
    # Time usage
    analysis["white_think_time"] = match.white_think_time
    analysis["black_think_time"] = match.black_think_time
    
    # Illegal moves
    analysis["white_illegals"] = match.white_illegal_attempts
    analysis["black_illegals"] = match.black_illegal_attempts
    
    return analysis
