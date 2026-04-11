"""
Tournament Orchestrator for CAISSA Chess v0.5.0

This module manages complete tournaments with multiple players and rounds.
Supports various formats: round-robin, Swiss, knockout, and arena.

Author: CAISSA Team
Version: 0.5.0
"""

import chess
import json
import logging
import random
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any, Set

from core.tournament_player import TournamentPlayer, TimeControl, PlayerStatus
from core.match_engine import MatchEngine, MatchResult
from core.elo_calculator import GameResult, EloLeaderboard
from config_manager import cfg


logger = logging.getLogger(__name__)


def _sanitize_path_component(name: str) -> str:
    """Create a filesystem-safe path component (Windows-safe)."""
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip().strip(".")
    if not sanitized:
        sanitized = "tournament"
    return sanitized


class TournamentFormat(Enum):
    """Supported tournament formats."""
    SINGLE_MATCH = "single_match"           # One game between two LLMs
    MATCH_SERIES = "match_series"           # Best-of-N series
    ROUND_ROBIN = "round_robin"             # Everyone plays everyone once
    DOUBLE_ROUND_ROBIN = "double_round_robin"  # Everyone plays everyone twice (W/B)
    SWISS = "swiss"                         # Swiss pairing system
    KNOCKOUT = "knockout"                   # Single elimination
    DOUBLE_ELIMINATION = "double_elim"      # Double elimination bracket
    ARENA = "arena"                         # Continuous rapid games


class TournamentStatus(Enum):
    """Current status of the tournament."""
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TiebreakMethod(Enum):
    """Tiebreak methods for standings."""
    HEAD_TO_HEAD = "h2h"          # Direct encounter
    SONNEBORN_BERGER = "sb"       # Sum of opponents' scores * result
    BUCHHOLZ = "buchholz"         # Sum of opponents' scores
    WINS = "wins"                 # Number of wins
    BLACK_WINS = "black_wins"     # Wins with black
    NEUSTADTL = "neustadtl"       # Modified SB
    PERFORMANCE = "performance"   # Performance rating


@dataclass
class Standing:
    """
    Tournament standing for a single player.
    """
    rank: int
    player: TournamentPlayer
    points: float
    games_played: int
    wins: int
    draws: int
    losses: int
    
    # Tiebreak scores
    tiebreaks: Dict[TiebreakMethod, float] = field(default_factory=dict)
    
    # Additional stats
    win_rate: float = 0.0
    performance_rating: int = 0
    avg_opponent_rating: int = 0
    
    @property
    def score_display(self) -> str:
        """Display score as wins-draws-losses."""
        return f"{self.wins}W-{self.draws}D-{self.losses}L ({self.points}pts)"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "rank": self.rank,
            "player_id": self.player.id,
            "player_name": self.player.name,
            "points": self.points,
            "games_played": self.games_played,
            "wins": self.wins,
            "draws": self.draws,
            "losses": self.losses,
            "win_rate": self.win_rate,
            "performance_rating": self.performance_rating,
            "tiebreaks": {k.value: v for k, v in self.tiebreaks.items()},
        }


@dataclass
class Round:
    """
    A tournament round containing multiple pairings.
    """
    round_number: int
    pairings: List[Tuple[TournamentPlayer, TournamentPlayer]]  # (white, black)
    byes: List[TournamentPlayer] = field(default_factory=list)  # Players with bye
    results: List[Optional[MatchResult]] = field(default_factory=list)
    completed: bool = False
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def is_complete(self) -> bool:
        """Check if all matches in round are complete."""
        return len(self.results) == len(self.pairings) and all(r is not None for r in self.results)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "round_number": self.round_number,
            "pairings": [(w.id, b.id) for w, b in self.pairings],
            "byes": [p.id for p in self.byes],
            "results": [r.to_dict() if r else None for r in self.results],
            "completed": self.completed,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


@dataclass
class TournamentConfig:
    """
    Complete tournament configuration.
    """
    name: str
    format: TournamentFormat
    players: List[TournamentPlayer]
    
    # Format-specific settings
    rounds: int = 0                    # For Swiss (0 = auto-calculate)
    games_per_match: int = 1           # For match series
    
    # Game settings
    time_control: TimeControl = TimeControl.RAPID
    starting_fen: str = ""             # Empty = standard start
    
    # Scoring
    win_points: float = 1.0
    draw_points: float = 0.5
    loss_points: float = 0.0
    bye_points: float = 1.0
    
    # Tiebreak priority
    tiebreaks: List[TiebreakMethod] = field(default_factory=lambda: [
        TiebreakMethod.HEAD_TO_HEAD,
        TiebreakMethod.SONNEBORN_BERGER,
        TiebreakMethod.WINS,
    ])
    
    # Output
    output_dir: Path = field(default_factory=lambda: Path("tournaments"))
    
    # Options
    shuffle_colors: bool = True        # Randomize first-round colors
    allow_draws: bool = True           # False = play until decisive
    max_moves: int = 500               # Per game
    
    # Commentary
    commentary_enabled: bool = False
    commentary_provider: Optional[Any] = None
    
    def __post_init__(self):
        """Validate and set defaults."""
        if self.rounds == 0:
            n = len(self.players)
            if n == 0:
                self.rounds = 1  # Default for empty tournament
            elif self.format == TournamentFormat.SWISS:
                # Default Swiss rounds: ceil(log2(n))
                import math
                self.rounds = max(1, math.ceil(math.log2(n))) if n > 1 else 1
            elif self.format in (TournamentFormat.ROUND_ROBIN, TournamentFormat.DOUBLE_ROUND_ROBIN):
                n = len(self.players)
                self.rounds = n - 1 if n % 2 == 0 else n
                if self.format == TournamentFormat.DOUBLE_ROUND_ROBIN:
                    self.rounds *= 2


@dataclass 
class TournamentResult:
    """
    Complete tournament results and analytics.
    """
    config: TournamentConfig
    status: TournamentStatus
    rounds: List[Round]
    standings: List[Standing]
    matches: List[MatchResult]
    
    # Statistics
    total_games: int = 0
    decisive_games: int = 0
    draws: int = 0
    forfeits: int = 0
    total_moves: int = 0
    avg_game_length: float = 0.0
    
    # Timing
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    # Highlights
    best_game: Optional[MatchResult] = None      # Highest beauty
    longest_game: Optional[MatchResult] = None   # Most moves
    shortest_game: Optional[MatchResult] = None  # Fewest moves
    biggest_upset: Optional[MatchResult] = None  # Largest rating difference
    
    @property
    def duration(self) -> float:
        """Tournament duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0
    
    @property
    def winner(self) -> Optional[TournamentPlayer]:
        """Tournament winner (first place)."""
        if self.standings:
            return self.standings[0].player
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.config.name,
            "format": self.config.format.value,
            "status": self.status.value,
            "rounds": [r.to_dict() for r in self.rounds],
            "standings": [s.to_dict() for s in self.standings],
            "total_games": self.total_games,
            "decisive_games": self.decisive_games,
            "draws": self.draws,
            "avg_game_length": self.avg_game_length,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "winner": self.winner.name if self.winner else None,
        }


class Tournament:
    """
    Orchestrates a complete tournament with multiple players and rounds.
    
    Supports various formats and handles all aspects of tournament management:
    - Player registration and seeding
    - Round generation and pairings
    - Match execution
    - Standings calculation with tiebreaks
    - ELO updates
    - Results persistence
    
    Example:
        ```python
        config = TournamentConfig(
            name="April 2026 Championship",
            format=TournamentFormat.ROUND_ROBIN,
            players=[player1, player2, player3, player4],
        )
        tournament = Tournament(config)
        result = await tournament.run()
        print(f"Winner: {result.winner.name}")
        ```
    """
    
    def __init__(self, config: TournamentConfig):
        """
        Initialize the tournament.
        
        Args:
            config: Tournament configuration
        """
        self.config = config
        self.players = list(config.players)
        self.status = TournamentStatus.CREATED
        
        # Initialize leaderboard
        self.leaderboard = EloLeaderboard()
        for player in self.players:
            self.leaderboard.set_rating(player.id, player.elo_rating)
        
        # State
        self.rounds: List[Round] = []
        self.matches: List[MatchResult] = []
        self.current_round = 0
        
        # Player scores: player_id -> points
        self.scores: Dict[str, float] = {p.id: 0.0 for p in self.players}
        
        # Game results: (player1_id, player2_id) -> list of results
        self.results_matrix: Dict[Tuple[str, str], List[GameResult]] = {}
        
        # Output directory (filesystem-safe, especially on Windows)
        safe_name = _sanitize_path_component(config.name).replace(" ", "_").lower()
        self.output_dir = config.output_dir / safe_name
        
        logger.info(f"Tournament '{config.name}' initialized with {len(self.players)} players")
    
    async def run(self) -> TournamentResult:
        """
        Execute the complete tournament.
        
        Returns:
            TournamentResult: Complete tournament results
        """
        start_time = datetime.now()
        self.status = TournamentStatus.IN_PROGRESS
        
        logger.info(f"Starting tournament: {self.config.name}")
        
        try:
            # Generate all rounds based on format
            if self.config.format == TournamentFormat.ROUND_ROBIN:
                await self._run_round_robin()
            elif self.config.format == TournamentFormat.DOUBLE_ROUND_ROBIN:
                await self._run_double_round_robin()
            elif self.config.format == TournamentFormat.SWISS:
                await self._run_swiss()
            elif self.config.format == TournamentFormat.KNOCKOUT:
                await self._run_knockout()
            elif self.config.format == TournamentFormat.SINGLE_MATCH:
                await self._run_single_match()
            elif self.config.format == TournamentFormat.MATCH_SERIES:
                await self._run_match_series()
            else:
                raise ValueError(f"Unsupported format: {self.config.format}")
            
            self.status = TournamentStatus.COMPLETED
        
        except Exception as e:
            logger.error(f"Tournament error: {e}")
            self.status = TournamentStatus.CANCELLED
            raise
        
        end_time = datetime.now()
        
        # Calculate final standings
        standings = self._calculate_standings()
        
        # Find highlights
        highlights = self._find_highlights()
        
        # Build result
        result = TournamentResult(
            config=self.config,
            status=self.status,
            rounds=self.rounds,
            standings=standings,
            matches=self.matches,
            total_games=len(self.matches),
            decisive_games=sum(1 for m in self.matches if m.is_decisive),
            draws=sum(1 for m in self.matches if m.result == GameResult.DRAW),
            total_moves=sum(m.total_moves for m in self.matches),
            avg_game_length=sum(m.total_moves for m in self.matches) / max(1, len(self.matches)),
            start_time=start_time,
            end_time=end_time,
            best_game=highlights.get("best"),
            longest_game=highlights.get("longest"),
            shortest_game=highlights.get("shortest"),
            biggest_upset=highlights.get("upset"),
        )
        
        # Save results
        await self._save_results(result)
        
        logger.info(f"Tournament completed. Winner: {result.winner.name if result.winner else 'N/A'}")
        
        return result
    
    async def _run_single_match(self):
        """Run a single match between two players."""
        if len(self.players) != 2:
            raise ValueError("Single match requires exactly 2 players")
        
        white, black = self.players[0], self.players[1]
        
        # Play match
        result = await self._play_match(white, black)
        self.matches.append(result)
        
        # Record result
        self._record_result(white, black, result)
        
        # Create round
        round_obj = Round(
            round_number=1,
            pairings=[(white, black)],
            results=[result],
            completed=True,
            start_time=result.start_time,
            end_time=result.end_time,
        )
        self.rounds.append(round_obj)
    
    async def _run_match_series(self):
        """Run a best-of-N match series."""
        if len(self.players) != 2:
            raise ValueError("Match series requires exactly 2 players")
        
        player1, player2 = self.players[0], self.players[1]
        games_to_win = (self.config.games_per_match + 1) // 2
        
        p1_wins = 0
        p2_wins = 0
        game_num = 0
        
        while p1_wins < games_to_win and p2_wins < games_to_win:
            game_num += 1
            # Alternate colors
            if game_num % 2 == 1:
                white, black = player1, player2
            else:
                white, black = player2, player1
            
            result = await self._play_match(white, black)
            self.matches.append(result)
            self._record_result(white, black, result)
            
            # Update series score
            if result.result == GameResult.WHITE_WINS:
                if white == player1:
                    p1_wins += 1
                else:
                    p2_wins += 1
            elif result.result == GameResult.BLACK_WINS:
                if black == player1:
                    p1_wins += 1
                else:
                    p2_wins += 1
            
            logger.info(f"Series score: {player1.name} {p1_wins} - {p2_wins} {player2.name}")
    
    async def _run_round_robin(self):
        """Run a single round-robin tournament."""
        pairings_schedule = self._generate_round_robin_pairings()
        
        for round_num, round_pairings in enumerate(pairings_schedule, 1):
            logger.info(f"Round {round_num}/{len(pairings_schedule)}")
            
            round_obj = Round(
                round_number=round_num,
                pairings=round_pairings,
                start_time=datetime.now(),
            )
            
            # Play all matches in round
            for white, black in round_pairings:
                result = await self._play_match(white, black)
                self.matches.append(result)
                round_obj.results.append(result)
                self._record_result(white, black, result)
            
            round_obj.end_time = datetime.now()
            round_obj.completed = True
            self.rounds.append(round_obj)
    
    async def _run_double_round_robin(self):
        """Run a double round-robin (home and away)."""
        pairings_schedule = self._generate_round_robin_pairings()
        
        # First half: as generated
        for round_num, round_pairings in enumerate(pairings_schedule, 1):
            logger.info(f"Round {round_num}/{len(pairings_schedule) * 2}")
            
            round_obj = Round(round_number=round_num, pairings=round_pairings, start_time=datetime.now())
            
            for white, black in round_pairings:
                result = await self._play_match(white, black)
                self.matches.append(result)
                round_obj.results.append(result)
                self._record_result(white, black, result)
            
            round_obj.end_time = datetime.now()
            round_obj.completed = True
            self.rounds.append(round_obj)
        
        # Second half: reversed colors
        for round_num, round_pairings in enumerate(pairings_schedule, len(pairings_schedule) + 1):
            logger.info(f"Round {round_num}/{len(pairings_schedule) * 2}")
            
            # Reverse colors
            reversed_pairings = [(black, white) for white, black in round_pairings]
            round_obj = Round(round_number=round_num, pairings=reversed_pairings, start_time=datetime.now())
            
            for white, black in reversed_pairings:
                result = await self._play_match(white, black)
                self.matches.append(result)
                round_obj.results.append(result)
                self._record_result(white, black, result)
            
            round_obj.end_time = datetime.now()
            round_obj.completed = True
            self.rounds.append(round_obj)
    
    async def _run_swiss(self):
        """Run a Swiss-system tournament."""
        for round_num in range(1, self.config.rounds + 1):
            logger.info(f"Swiss Round {round_num}/{self.config.rounds}")
            
            # Generate pairings based on current scores
            pairings, byes = self._generate_swiss_pairings(round_num)
            
            round_obj = Round(
                round_number=round_num,
                pairings=pairings,
                byes=byes,
                start_time=datetime.now(),
            )
            
            # Award bye points
            for player in byes:
                self.scores[player.id] += self.config.bye_points
            
            # Play matches
            for white, black in pairings:
                result = await self._play_match(white, black)
                self.matches.append(result)
                round_obj.results.append(result)
                self._record_result(white, black, result)
            
            round_obj.end_time = datetime.now()
            round_obj.completed = True
            self.rounds.append(round_obj)
    
    async def _run_knockout(self):
        """Run a single-elimination knockout tournament."""
        remaining = list(self.players)
        
        # Shuffle for random seeding
        if self.config.shuffle_colors:
            random.shuffle(remaining)
        
        round_num = 0
        while len(remaining) > 1:
            round_num += 1
            logger.info(f"Knockout Round {round_num} - {len(remaining)} players")
            
            # Generate pairings
            pairings = []
            for i in range(0, len(remaining) - 1, 2):
                pairings.append((remaining[i], remaining[i + 1]))
            
            # Handle bye if odd number
            byes = []
            if len(remaining) % 2 == 1:
                byes.append(remaining[-1])
            
            round_obj = Round(
                round_number=round_num,
                pairings=pairings,
                byes=byes,
                start_time=datetime.now(),
            )
            
            # Play matches and determine winners
            winners = list(byes)  # Bye players advance
            
            for white, black in pairings:
                result = await self._play_match(white, black)
                self.matches.append(result)
                round_obj.results.append(result)
                self._record_result(white, black, result)
                
                # Determine winner
                if result.result == GameResult.WHITE_WINS:
                    winners.append(white)
                    black.status = PlayerStatus.ELIMINATED
                elif result.result == GameResult.BLACK_WINS:
                    winners.append(black)
                    white.status = PlayerStatus.ELIMINATED
                else:
                    # Draw - play again (simplified: white wins on second draw)
                    result2 = await self._play_match(black, white)  # Reverse colors
                    self.matches.append(result2)
                    if result2.result == GameResult.BLACK_WINS:
                        winners.append(white)
                        black.status = PlayerStatus.ELIMINATED
                    else:
                        winners.append(black)
                        white.status = PlayerStatus.ELIMINATED
            
            round_obj.end_time = datetime.now()
            round_obj.completed = True
            self.rounds.append(round_obj)
            
            remaining = winners
    
    def _generate_round_robin_pairings(self) -> List[List[Tuple[TournamentPlayer, TournamentPlayer]]]:
        """
        Generate round-robin pairings using the circle method.
        
        Returns:
            List of rounds, each containing list of (white, black) pairings
        """
        players = list(self.players)
        
        # Add bye player if odd
        if len(players) % 2 == 1:
            # Create a dummy "bye" player
            bye_player = TournamentPlayer(id="BYE", name="BYE")
            players.append(bye_player)
        
        n = len(players)
        schedule = []
        
        # Circle method
        for round_idx in range(n - 1):
            round_pairings = []
            for i in range(n // 2):
                p1 = players[i]
                p2 = players[n - 1 - i]
                
                # Skip bye player
                if p1.id == "BYE" or p2.id == "BYE":
                    continue
                
                # Alternate colors
                if round_idx % 2 == 0:
                    round_pairings.append((p1, p2))
                else:
                    round_pairings.append((p2, p1))
            
            schedule.append(round_pairings)
            
            # Rotate players (keep first fixed)
            players = [players[0]] + [players[-1]] + players[1:-1]
        
        return schedule
    
    def _generate_swiss_pairings(
        self,
        round_num: int,
    ) -> Tuple[List[Tuple[TournamentPlayer, TournamentPlayer]], List[TournamentPlayer]]:
        """
        Generate Swiss pairings based on current scores.
        
        Returns:
            Tuple of (pairings, byes)
        """
        # Sort by score, then rating
        sorted_players = sorted(
            self.players,
            key=lambda p: (-self.scores[p.id], -p.elo_rating),
        )
        
        # Track who has played whom
        played_pairs: Set[Tuple[str, str]] = set()
        for match in self.matches:
            played_pairs.add((match.white.id, match.black.id))
            played_pairs.add((match.black.id, match.white.id))
        
        pairings = []
        paired = set()
        byes = []
        
        for player in sorted_players:
            if player.id in paired:
                continue
            
            # Find opponent (next unpaired player not yet played)
            for opponent in sorted_players:
                if opponent.id == player.id:
                    continue
                if opponent.id in paired:
                    continue
                if (player.id, opponent.id) in played_pairs:
                    continue
                
                # Determine colors
                white_games = sum(1 for m in self.matches if m.white.id == player.id)
                black_games = sum(1 for m in self.matches if m.black.id == player.id)
                
                if white_games <= black_games:
                    pairings.append((player, opponent))
                else:
                    pairings.append((opponent, player))
                
                paired.add(player.id)
                paired.add(opponent.id)
                break
            else:
                # No valid opponent - player gets bye
                if player.id not in paired:
                    byes.append(player)
                    paired.add(player.id)
        
        return pairings, byes
    
    async def _play_match(
        self,
        white: TournamentPlayer,
        black: TournamentPlayer,
    ) -> MatchResult:
        """
        Play a single match between two players.
        """
        logger.info(f"Playing: {white.name} vs {black.name}")
        
        # Use standard starting position if no custom FEN specified
        starting_fen = self.config.starting_fen if self.config.starting_fen else chess.STARTING_FEN
        
        engine = MatchEngine(
            white=white,
            black=black,
            time_control=self.config.time_control,
            max_moves=self.config.max_moves,
            starting_fen=starting_fen,
            timeout_fallback_enabled=getattr(cfg.tournament.match, "timeout_fallback_enabled", True),
            timeout_fallback_max_consecutive=getattr(cfg.tournament.match, "timeout_fallback_max_consecutive", 3),
            timeout_fallback_cooldown_moves=getattr(cfg.tournament.match, "timeout_fallback_cooldown_moves", 2),
            include_time_control_in_prompt=getattr(cfg.tournament.match, "include_time_control_in_prompt", True),
        )
        
        result = await engine.play_match()
        
        # Update ELO
        elo_change = self.leaderboard.record_game(
            white.id, black.id, result.result, result.match_id
        )
        result.elo_change = elo_change
        
        # Update player ratings
        white.elo_rating = elo_change.white_new
        black.elo_rating = elo_change.black_new
        
        logger.info(f"Result: {result.result.value} | ELO: {elo_change.summary}")
        
        return result
    
    def _record_result(
        self,
        white: TournamentPlayer,
        black: TournamentPlayer,
        result: MatchResult,
    ):
        """Record a match result in the tournament state."""
        pair = (white.id, black.id)
        if pair not in self.results_matrix:
            self.results_matrix[pair] = []
        self.results_matrix[pair].append(result.result)
        
        # Update scores
        if result.result == GameResult.WHITE_WINS:
            self.scores[white.id] += self.config.win_points
            self.scores[black.id] += self.config.loss_points
        elif result.result == GameResult.BLACK_WINS:
            self.scores[white.id] += self.config.loss_points
            self.scores[black.id] += self.config.win_points
        else:  # Draw
            self.scores[white.id] += self.config.draw_points
            self.scores[black.id] += self.config.draw_points
        
        # Update player stats
        white.stats.games_played += 1
        black.stats.games_played += 1
        
        if result.result == GameResult.WHITE_WINS:
            white.stats.wins += 1
            white.stats.wins_as_white += 1
            black.stats.losses += 1
        elif result.result == GameResult.BLACK_WINS:
            black.stats.wins += 1
            black.stats.wins_as_black += 1
            white.stats.losses += 1
        else:
            white.stats.draws += 1
            white.stats.draws_as_white += 1
            black.stats.draws += 1
            black.stats.draws_as_black += 1
    
    def _calculate_standings(self) -> List[Standing]:
        """Calculate tournament standings with tiebreaks."""
        standings = []
        
        for player in self.players:
            points = self.scores[player.id]
            
            # Calculate W/D/L
            wins = player.stats.wins
            draws = player.stats.draws
            losses = player.stats.losses
            games = player.stats.games_played
            
            standing = Standing(
                rank=0,
                player=player,
                points=points,
                games_played=games,
                wins=wins,
                draws=draws,
                losses=losses,
                win_rate=(wins / games * 100) if games > 0 else 0,
            )
            
            # Calculate tiebreaks
            standing.tiebreaks = self._calculate_tiebreaks(player)
            
            standings.append(standing)
        
        # Sort by points and tiebreaks
        standings.sort(key=lambda s: (
            -s.points,
            *[-s.tiebreaks.get(tb, 0) for tb in self.config.tiebreaks]
        ))
        
        # Assign ranks
        for i, standing in enumerate(standings, 1):
            standing.rank = i
        
        return standings
    
    def _calculate_tiebreaks(self, player: TournamentPlayer) -> Dict[TiebreakMethod, float]:
        """Calculate all tiebreak scores for a player."""
        tiebreaks = {}
        
        # Sonneborn-Berger: sum of opponents' scores weighted by result
        sb_score = 0.0
        for match in self.matches:
            if match.white.id == player.id:
                opp_score = self.scores[match.black.id]
                if match.result == GameResult.WHITE_WINS:
                    sb_score += opp_score
                elif match.result == GameResult.DRAW:
                    sb_score += opp_score * 0.5
            elif match.black.id == player.id:
                opp_score = self.scores[match.white.id]
                if match.result == GameResult.BLACK_WINS:
                    sb_score += opp_score
                elif match.result == GameResult.DRAW:
                    sb_score += opp_score * 0.5
        tiebreaks[TiebreakMethod.SONNEBORN_BERGER] = sb_score
        
        # Buchholz: sum of opponents' scores
        buchholz = 0.0
        for match in self.matches:
            if match.white.id == player.id:
                buchholz += self.scores[match.black.id]
            elif match.black.id == player.id:
                buchholz += self.scores[match.white.id]
        tiebreaks[TiebreakMethod.BUCHHOLZ] = buchholz
        
        # Wins
        tiebreaks[TiebreakMethod.WINS] = float(player.stats.wins)
        
        # Black wins
        tiebreaks[TiebreakMethod.BLACK_WINS] = float(player.stats.wins_as_black)
        
        return tiebreaks
    
    def _find_highlights(self) -> Dict[str, Optional[MatchResult]]:
        """Find highlight games from the tournament."""
        if not self.matches:
            return {}
        
        return {
            "best": max(self.matches, key=lambda m: m.beauty_score, default=None),
            "longest": max(self.matches, key=lambda m: m.total_moves, default=None),
            "shortest": min((m for m in self.matches if m.total_moves > 0), 
                          key=lambda m: m.total_moves, default=None),
            "upset": max(
                (m for m in self.matches if m.is_decisive),
                key=lambda m: abs(m.white.elo_rating - m.black.elo_rating),
                default=None,
            ),
        }
    
    async def _save_results(self, result: TournamentResult):
        """Save tournament results to disk."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save JSON
        json_path = self.output_dir / "tournament.json"
        with open(json_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        
        # Save standings markdown
        md_path = self.output_dir / "standings.md"
        with open(md_path, "w") as f:
            f.write(f"# {self.config.name} - Standings\n\n")
            f.write(f"**Format**: {self.config.format.value}\n")
            f.write(f"**Players**: {len(self.players)}\n")
            f.write(f"**Games**: {result.total_games}\n\n")
            
            f.write("| Rank | Player | Points | W | D | L | Rating |\n")
            f.write("|------|--------|--------|---|---|---|--------|\n")
            for standing in result.standings:
                f.write(
                    f"| {standing.rank} | {standing.player.name} | {standing.points} | "
                    f"{standing.wins} | {standing.draws} | {standing.losses} | "
                    f"{standing.player.elo_rating} |\n"
                )
        
        # Save individual games
        games_dir = self.output_dir / "games"
        games_dir.mkdir(exist_ok=True)
        for i, match in enumerate(self.matches, 1):
            pgn_path = games_dir / f"game_{i:03d}_{match.white.name}_vs_{match.black.name}.pgn"
            with open(pgn_path, "w") as f:
                f.write(match.pgn)
        
        logger.info(f"Results saved to {self.output_dir}")


async def run_tournament(config: TournamentConfig) -> TournamentResult:
    """
    Convenience function to run a tournament.
    
    Args:
        config: Tournament configuration
    
    Returns:
        TournamentResult: Complete results
    """
    tournament = Tournament(config)
    return await tournament.run()
