"""
ELO Rating Calculator for CAISSA Chess v0.5.0

This module implements the ELO rating system for the LLM vs LLM tournament.
Uses standard FIDE-style ELO calculations with configurable K-factors.

Author: CAISSA Team
Version: 0.5.0
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple, List, Optional, Dict
import math


class GameResult(Enum):
    """Possible outcomes of a chess game."""
    WHITE_WINS = "1-0"
    BLACK_WINS = "0-1"
    DRAW = "1/2-1/2"
    IN_PROGRESS = "*"
    FORFEIT_WHITE = "1-0F"  # Black forfeited
    FORFEIT_BLACK = "0-1F"  # White forfeited
    DOUBLE_FORFEIT = "0-0F"  # Both forfeited (rare)


class KFactorStrategy(Enum):
    """
    K-factor determination strategies.
    
    K-factor determines how much a single game affects rating.
    Higher K = more volatility, lower K = more stability.
    """
    FIXED = "fixed"              # Always use same K
    FIDE = "fide"                # FIDE rules based on rating/games
    USCF = "uscf"                # USCF rules
    DYNAMIC = "dynamic"          # Based on games played
    PROVISIONAL = "provisional"  # High K until established


# FIDE K-factor thresholds
FIDE_K_THRESHOLDS = {
    2400: 10,   # K=10 for players rated 2400+
    2300: 20,   # K=20 for players 2300-2399
    0: 40,      # K=40 for players below 2300 with <30 games
}

# Standard K-factors by experience
EXPERIENCE_K_FACTORS = {
    10: 40,    # <10 games: provisional
    30: 32,    # 10-30 games: new
    100: 24,   # 30-100 games: developing
    float('inf'): 16,  # 100+ games: established
}


@dataclass
class EloChange:
    """
    Result of an ELO calculation.
    
    Contains all relevant information about rating changes.
    """
    white_old: int
    black_old: int
    white_new: int
    black_new: int
    white_delta: int
    black_delta: int
    white_expected: float
    black_expected: float
    result: GameResult
    white_k: int
    black_k: int
    
    @property
    def summary(self) -> str:
        """Human-readable summary of the ELO change."""
        white_sign = "+" if self.white_delta >= 0 else ""
        black_sign = "+" if self.black_delta >= 0 else ""
        return (
            f"White: {self.white_old} → {self.white_new} ({white_sign}{self.white_delta}), "
            f"Black: {self.black_old} → {self.black_new} ({black_sign}{self.black_delta})"
        )


class EloCalculator:
    """
    ELO rating calculator with various configuration options.
    
    Implements the standard ELO formula:
    - Expected score: E = 1 / (1 + 10^((opponent_rating - player_rating) / 400))
    - New rating: R_new = R_old + K * (actual_score - expected_score)
    
    Features:
    - Configurable K-factors
    - Floor/ceiling rating limits
    - Provisional rating handling
    - Rating history tracking
    - Performance rating calculation
    """
    
    def __init__(
        self,
        k_factor: int = 32,
        k_strategy: KFactorStrategy = KFactorStrategy.DYNAMIC,
        min_rating: int = 100,
        max_rating: int = 4000,
        draw_score: float = 0.5,
    ):
        """
        Initialize the ELO calculator.
        
        Args:
            k_factor: Default K-factor if using FIXED strategy
            k_strategy: Strategy for determining K-factor
            min_rating: Minimum possible rating
            max_rating: Maximum possible rating
            draw_score: Score for a draw (standard is 0.5)
        """
        self.k_factor = k_factor
        self.k_strategy = k_strategy
        self.min_rating = min_rating
        self.max_rating = max_rating
        self.draw_score = draw_score
    
    def expected_score(self, player_rating: int, opponent_rating: int) -> float:
        """
        Calculate expected score for a player against an opponent.
        
        Uses the logistic curve formula:
        E = 1 / (1 + 10^((R_opponent - R_player) / 400))
        
        Args:
            player_rating: Player's current rating
            opponent_rating: Opponent's current rating
        
        Returns:
            float: Expected score between 0 and 1
        """
        exponent = (opponent_rating - player_rating) / 400.0
        return 1.0 / (1.0 + math.pow(10, exponent))
    
    def get_k_factor(
        self,
        rating: int,
        games_played: int,
        k_override: Optional[int] = None
    ) -> int:
        """
        Determine the K-factor for a player.
        
        Args:
            rating: Player's current rating
            games_played: Number of games played
            k_override: Optional override K-factor
        
        Returns:
            int: K-factor to use for rating calculation
        """
        if k_override is not None:
            return k_override
        
        if self.k_strategy == KFactorStrategy.FIXED:
            return self.k_factor
        
        elif self.k_strategy == KFactorStrategy.FIDE:
            if games_played < 30 and rating < 2300:
                return 40
            elif rating >= 2400:
                return 10
            else:
                return 20
        
        elif self.k_strategy == KFactorStrategy.USCF:
            if games_played < 8:
                return 32
            elif rating < 2100:
                return 32
            elif rating < 2400:
                return 24
            else:
                return 16
        
        elif self.k_strategy == KFactorStrategy.DYNAMIC:
            for threshold, k in sorted(EXPERIENCE_K_FACTORS.items()):
                if games_played < threshold:
                    return k
            return 16
        
        elif self.k_strategy == KFactorStrategy.PROVISIONAL:
            if games_played < 20:
                return 64
            elif games_played < 40:
                return 32
            else:
                return 16
        
        return self.k_factor
    
    def calculate(
        self,
        white_rating: int,
        black_rating: int,
        result: GameResult,
        white_games: int = 30,
        black_games: int = 30,
        white_k: Optional[int] = None,
        black_k: Optional[int] = None,
    ) -> EloChange:
        """
        Calculate ELO changes for a game result.
        
        Args:
            white_rating: White's current rating
            black_rating: Black's current rating
            result: Game result
            white_games: White's games played (for K-factor)
            black_games: Black's games played (for K-factor)
            white_k: Optional K-factor override for white
            black_k: Optional K-factor override for black
        
        Returns:
            EloChange: Complete rating change information
        """
        # Get K-factors
        k_white = self.get_k_factor(white_rating, white_games, white_k)
        k_black = self.get_k_factor(black_rating, black_games, black_k)
        
        # Calculate expected scores
        expected_white = self.expected_score(white_rating, black_rating)
        expected_black = 1.0 - expected_white  # Symmetric
        
        # Determine actual scores
        if result in (GameResult.WHITE_WINS, GameResult.FORFEIT_WHITE):
            actual_white = 1.0
            actual_black = 0.0
        elif result in (GameResult.BLACK_WINS, GameResult.FORFEIT_BLACK):
            actual_white = 0.0
            actual_black = 1.0
        elif result == GameResult.DRAW:
            actual_white = self.draw_score
            actual_black = self.draw_score
        elif result == GameResult.DOUBLE_FORFEIT:
            actual_white = 0.0
            actual_black = 0.0
        else:
            # Game in progress or unknown
            return EloChange(
                white_old=white_rating,
                black_old=black_rating,
                white_new=white_rating,
                black_new=black_rating,
                white_delta=0,
                black_delta=0,
                white_expected=expected_white,
                black_expected=expected_black,
                result=result,
                white_k=k_white,
                black_k=k_black,
            )
        
        # Calculate rating changes
        white_delta = round(k_white * (actual_white - expected_white))
        black_delta = round(k_black * (actual_black - expected_black))
        
        # Apply changes with floor/ceiling
        white_new = max(self.min_rating, min(self.max_rating, white_rating + white_delta))
        black_new = max(self.min_rating, min(self.max_rating, black_rating + black_delta))
        
        return EloChange(
            white_old=white_rating,
            black_old=black_rating,
            white_new=white_new,
            black_new=black_new,
            white_delta=white_new - white_rating,
            black_delta=black_new - black_rating,
            white_expected=expected_white,
            black_expected=expected_black,
            result=result,
            white_k=k_white,
            black_k=k_black,
        )
    
    def performance_rating(
        self,
        opponent_ratings: List[int],
        score: float,
    ) -> int:
        """
        Calculate performance rating from a set of games.
        
        Uses the FIDE formula:
        Performance = Average opponent rating + 400 * (W - L) / N
        
        Where W = wins, L = losses, N = total games
        
        Args:
            opponent_ratings: List of opponent ratings
            score: Total score achieved (wins + 0.5*draws)
        
        Returns:
            int: Performance rating
        """
        if not opponent_ratings:
            return 1500
        
        n = len(opponent_ratings)
        avg_opponent = sum(opponent_ratings) / n
        
        # Handle edge cases
        if score == 0:
            return round(avg_opponent - 400)
        elif score == n:
            return round(avg_opponent + 400)
        
        # Standard formula
        wins_minus_losses = 2 * score - n
        performance = avg_opponent + 400 * (wins_minus_losses / n)
        
        return round(max(self.min_rating, min(self.max_rating, performance)))
    
    def expected_score_against_field(
        self,
        player_rating: int,
        opponent_ratings: List[int],
    ) -> float:
        """
        Calculate expected total score against a field of opponents.
        
        Args:
            player_rating: Player's rating
            opponent_ratings: List of opponent ratings
        
        Returns:
            float: Expected total score
        """
        return sum(
            self.expected_score(player_rating, opp)
            for opp in opponent_ratings
        )
    
    def rating_change_if_win(
        self,
        player_rating: int,
        opponent_rating: int,
        player_games: int = 30,
    ) -> int:
        """Calculate rating change for a win."""
        result = self.calculate(
            player_rating, opponent_rating,
            GameResult.WHITE_WINS,
            player_games,
        )
        return result.white_delta
    
    def rating_change_if_loss(
        self,
        player_rating: int,
        opponent_rating: int,
        player_games: int = 30,
    ) -> int:
        """Calculate rating change for a loss."""
        result = self.calculate(
            player_rating, opponent_rating,
            GameResult.BLACK_WINS,
            player_games,
        )
        return result.white_delta
    
    def rating_change_if_draw(
        self,
        player_rating: int,
        opponent_rating: int,
        player_games: int = 30,
    ) -> int:
        """Calculate rating change for a draw."""
        result = self.calculate(
            player_rating, opponent_rating,
            GameResult.DRAW,
            player_games,
        )
        return result.white_delta


class EloLeaderboard:
    """
    Manages ELO ratings for multiple players.
    
    Tracks rating history, provides rankings, and handles
    bulk rating updates.
    """
    
    def __init__(
        self,
        calculator: Optional[EloCalculator] = None,
        initial_rating: int = 1500,
    ):
        """
        Initialize the leaderboard.
        
        Args:
            calculator: ELO calculator to use (creates default if None)
            initial_rating: Starting rating for new players
        """
        self.calculator = calculator or EloCalculator()
        self.initial_rating = initial_rating
        
        # Player ID -> current rating
        self._ratings: Dict[str, int] = {}
        
        # Player ID -> list of (rating, game_id) history
        self._history: Dict[str, List[Tuple[int, str]]] = {}
        
        # Player ID -> games played
        self._games_played: Dict[str, int] = {}
    
    def get_rating(self, player_id: str) -> int:
        """Get current rating for a player."""
        return self._ratings.get(player_id, self.initial_rating)
    
    def set_rating(self, player_id: str, rating: int):
        """Set rating for a player."""
        self._ratings[player_id] = rating
        if player_id not in self._games_played:
            self._games_played[player_id] = 0
    
    def get_games_played(self, player_id: str) -> int:
        """Get number of games played by a player."""
        return self._games_played.get(player_id, 0)
    
    def record_game(
        self,
        white_id: str,
        black_id: str,
        result: GameResult,
        game_id: str = "",
    ) -> EloChange:
        """
        Record a game result and update ratings.
        
        Args:
            white_id: White player ID
            black_id: Black player ID
            result: Game result
            game_id: Optional game identifier for history
        
        Returns:
            EloChange: Rating change information
        """
        white_rating = self.get_rating(white_id)
        black_rating = self.get_rating(black_id)
        white_games = self.get_games_played(white_id)
        black_games = self.get_games_played(black_id)
        
        change = self.calculator.calculate(
            white_rating, black_rating, result,
            white_games, black_games,
        )
        
        # Update ratings
        self._ratings[white_id] = change.white_new
        self._ratings[black_id] = change.black_new
        
        # Update games played
        self._games_played[white_id] = white_games + 1
        self._games_played[black_id] = black_games + 1
        
        # Record history
        if white_id not in self._history:
            self._history[white_id] = []
        if black_id not in self._history:
            self._history[black_id] = []
        
        self._history[white_id].append((change.white_new, game_id))
        self._history[black_id].append((change.black_new, game_id))
        
        return change
    
    def get_rankings(self) -> List[Tuple[str, int, int]]:
        """
        Get ranked list of players.
        
        Returns:
            List of (player_id, rating, games_played) sorted by rating desc
        """
        ranked = [
            (pid, rating, self.get_games_played(pid))
            for pid, rating in self._ratings.items()
        ]
        return sorted(ranked, key=lambda x: (-x[1], x[0]))
    
    def get_history(self, player_id: str) -> List[Tuple[int, str]]:
        """Get rating history for a player."""
        return self._history.get(player_id, [])
    
    def get_rating_range(self) -> Tuple[int, int]:
        """Get min and max ratings in the leaderboard."""
        if not self._ratings:
            return (self.initial_rating, self.initial_rating)
        ratings = list(self._ratings.values())
        return (min(ratings), max(ratings))
    
    def add_players(self, player_ids: List[str], rating: Optional[int] = None):
        """Add multiple players with optional starting rating."""
        start_rating = rating if rating is not None else self.initial_rating
        for pid in player_ids:
            if pid not in self._ratings:
                self._ratings[pid] = start_rating
                self._games_played[pid] = 0
                self._history[pid] = [(start_rating, "initial")]
    
    def to_dict(self) -> Dict:
        """Serialize leaderboard state."""
        return {
            "ratings": self._ratings,
            "games_played": self._games_played,
            "history": self._history,
            "initial_rating": self.initial_rating,
        }
    
    @classmethod
    def from_dict(cls, data: Dict, calculator: Optional[EloCalculator] = None) -> "EloLeaderboard":
        """Deserialize leaderboard state."""
        board = cls(
            calculator=calculator,
            initial_rating=data.get("initial_rating", 1500),
        )
        board._ratings = data.get("ratings", {})
        board._games_played = data.get("games_played", {})
        board._history = data.get("history", {})
        return board


# Convenience functions for simple use cases
def calculate_elo_change(
    white_rating: int,
    black_rating: int,
    result: GameResult,
    k_factor: int = 32,
) -> Tuple[int, int]:
    """
    Simple ELO calculation returning new ratings.
    
    Args:
        white_rating: White's rating
        black_rating: Black's rating
        result: Game result
        k_factor: K-factor to use
    
    Returns:
        Tuple of (new_white_rating, new_black_rating)
    """
    calc = EloCalculator(k_factor=k_factor, k_strategy=KFactorStrategy.FIXED)
    change = calc.calculate(white_rating, black_rating, result)
    return (change.white_new, change.black_new)


def estimate_win_probability(player_rating: int, opponent_rating: int) -> float:
    """
    Estimate probability of winning based on ratings.
    
    This is the expected score, which represents the probability
    of winning + 0.5 * probability of drawing.
    
    Args:
        player_rating: Player's rating
        opponent_rating: Opponent's rating
    
    Returns:
        float: Win probability (0.0 to 1.0)
    """
    calc = EloCalculator()
    return calc.expected_score(player_rating, opponent_rating)
