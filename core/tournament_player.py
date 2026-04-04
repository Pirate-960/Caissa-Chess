"""
Tournament Player Module for CAISSA Chess v0.5.0

This module defines the TournamentPlayer dataclass and related types
for the LLM vs LLM tournament system.

Author: CAISSA Team
Version: 0.5.0
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid

from core.llm_provider import LLMProvider


class TimeControl(Enum):
    """
    Time control settings for tournament matches.
    
    Defines the maximum time (in seconds) an LLM has to generate each move.
    These are soft limits - the system will wait for the response but track
    time for analytics and potential timeout handling.
    """
    BULLET = 5          # 5 seconds per move - fast games
    BLITZ = 15          # 15 seconds per move - quick games
    RAPID = 30          # 30 seconds per move - standard games
    CLASSICAL = 60      # 60 seconds per move - deep analysis
    CORRESPONDENCE = 300  # 5 minutes per move - very deep
    UNLIMITED = -1      # No time limit - wait for response


class PlayerStatus(Enum):
    """Current status of a tournament player."""
    ACTIVE = "active"           # Available for matches
    IN_MATCH = "in_match"       # Currently playing
    ELIMINATED = "eliminated"   # Out of tournament (knockout)
    WITHDRAWN = "withdrawn"     # Withdrew from tournament
    DISQUALIFIED = "disqualified"  # Rule violations


class StylePersona(Enum):
    """
    Pre-defined playing style personas for LLMs.
    
    These personas are injected into the move generation prompt to
    influence the LLM's playing style and decision-making.
    """
    # Legendary Players
    TAL = "mikhail_tal"              # Aggressive, sacrificial, tactical
    KARPOV = "anatoly_karpov"        # Positional, prophylactic, grinding
    KASPAROV = "garry_kasparov"      # Dynamic, powerful, dominating
    FISCHER = "bobby_fischer"         # Precise, clinical, perfectionist
    CARLSEN = "magnus_carlsen"       # Universal, pragmatic, endgame wizard
    MORPHY = "paul_morphy"           # Classical, development-focused, elegant
    CAPABLANCA = "jose_capablanca"   # Simple, clear, technically perfect
    PETROSIAN = "tigran_petrosian"   # Defensive, prophylactic, exchange sacs
    ALEKHINE = "alexander_alekhine"  # Attacking, complex, brilliant
    BOTVINNIK = "mikhail_botvinnik"  # Scientific, prepared, methodical
    
    # Style Categories
    AGGRESSIVE = "aggressive"         # Attack-first mentality
    POSITIONAL = "positional"         # Slow maneuvering
    TACTICAL = "tactical"             # Combination-seeking
    SOLID = "solid"                   # Safety-first
    CREATIVE = "creative"             # Unorthodox moves
    CHAOTIC = "chaotic"               # Maximize complexity
    GAMBITER = "gambiter"             # Sacrifice for initiative
    GRINDER = "grinder"               # Play for 200 moves
    
    # Neutral
    NEUTRAL = "neutral"               # No persona injection
    RANDOM = "random"                 # Random style each game


# Persona prompts for each style
PERSONA_PROMPTS: Dict[StylePersona, str] = {
    StylePersona.TAL: (
        "Play in the style of Mikhail Tal - the Magician from Riga. "
        "Seek sacrifices, complications, and tactical fireworks. "
        "Don't be afraid to sacrifice material for initiative and attack."
    ),
    StylePersona.KARPOV: (
        "Play in the style of Anatoly Karpov. Focus on positional play, "
        "prophylaxis, and slowly improving your pieces. Avoid unnecessary risks. "
        "Grind down your opponent through small advantages."
    ),
    StylePersona.KASPAROV: (
        "Play in the style of Garry Kasparov - dominating and dynamic. "
        "Seek powerful central control, active piece play, and devastating attacks. "
        "Calculate deeply and find the most energetic continuations."
    ),
    StylePersona.FISCHER: (
        "Play in the style of Bobby Fischer - precise and clinical. "
        "Calculate accurately, avoid mistakes, and punish any inaccuracy by your opponent. "
        "Strive for perfect moves in every position."
    ),
    StylePersona.CARLSEN: (
        "Play in the style of Magnus Carlsen - universal and pragmatic. "
        "Adapt your style to the position. In equal positions, keep pieces on "
        "and outplay your opponent in the endgame."
    ),
    StylePersona.MORPHY: (
        "Play in the style of Paul Morphy - classical and elegant. "
        "Prioritize rapid development, open lines for your pieces, and punish "
        "slow play with swift attacks on the king."
    ),
    StylePersona.CAPABLANCA: (
        "Play in the style of Jose Raul Capablanca - simple and clear. "
        "Find the most natural moves, avoid complications when ahead, and "
        "steer toward technically winning endgames."
    ),
    StylePersona.PETROSIAN: (
        "Play in the style of Tigran Petrosian - defensive and prophylactic. "
        "Prevent your opponent's plans, exchange when favorable, and sacrifice "
        "the exchange for positional compensation."
    ),
    StylePersona.ALEKHINE: (
        "Play in the style of Alexander Alekhine - attacking and brilliant. "
        "Seek complex positions where your calculating ability shines. "
        "Create attacking masterpieces with sacrifices and deep combinations."
    ),
    StylePersona.BOTVINNIK: (
        "Play in the style of Mikhail Botvinnik - scientific and methodical. "
        "Approach each position analytically. Prepare deeply, play principled chess, "
        "and trust in your preparation and understanding."
    ),
    StylePersona.AGGRESSIVE: (
        "Play aggressively. Always look for attacking chances, push pawns forward, "
        "and create threats. Sacrifice material if it leads to a strong attack."
    ),
    StylePersona.POSITIONAL: (
        "Play positionally. Focus on piece placement, pawn structure, and long-term "
        "strategic goals rather than immediate tactics."
    ),
    StylePersona.TACTICAL: (
        "Play tactically. Constantly look for combinations, pins, forks, skewers, "
        "and discovered attacks. Calculate forcing sequences deeply."
    ),
    StylePersona.SOLID: (
        "Play solid chess. Prioritize king safety, avoid weaknesses, and don't "
        "take unnecessary risks. Build up slowly and wait for opponent's mistakes."
    ),
    StylePersona.CREATIVE: (
        "Play creatively. Look for unusual moves that your opponent won't expect. "
        "Don't be afraid to play unorthodox chess if the position allows it."
    ),
    StylePersona.CHAOTIC: (
        "Maximize chaos and complexity. Choose moves that lead to the most complicated "
        "positions with many possible continuations. Avoid simplification."
    ),
    StylePersona.GAMBITER: (
        "Play like a gambiteer. Sacrifice pawns and pieces for rapid development, "
        "open lines, and initiative. Keep the pressure on and don't let your opponent breathe."
    ),
    StylePersona.GRINDER: (
        "Play to grind. Avoid simplification, keep pieces on the board, and outplay "
        "your opponent move by move. Be patient and wait for the win."
    ),
    StylePersona.NEUTRAL: "",
    StylePersona.RANDOM: "",  # Will be randomly assigned
}


@dataclass
class PlayerStats:
    """
    Cumulative statistics for a tournament player.
    
    Tracks performance metrics across all games in a tournament.
    """
    games_played: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    
    # Points (1 for win, 0.5 for draw, 0 for loss)
    points: float = 0.0
    
    # Move statistics
    total_moves: int = 0
    illegal_move_attempts: int = 0
    total_think_time: float = 0.0  # seconds
    
    # Performance indicators
    avg_centipawn_loss: float = 0.0
    blunders: int = 0  # eval loss > 200cp
    mistakes: int = 0  # eval loss > 100cp
    inaccuracies: int = 0  # eval loss > 50cp
    brilliancies: int = 0  # found best moves in complex positions
    
    # Game outcomes
    wins_as_white: int = 0
    wins_as_black: int = 0
    draws_as_white: int = 0
    draws_as_black: int = 0
    
    # Forfeit tracking
    forfeits_given: int = 0  # Lost by forfeit (illegal moves/timeout)
    forfeits_received: int = 0  # Won by opponent forfeit
    
    @property
    def games_as_white(self) -> int:
        """Total games played as white."""
        return self.wins_as_white + self.draws_as_white + (
            self.losses - self.wins_as_black - (self.draws - self.draws_as_white)
        )
    
    @property
    def games_as_black(self) -> int:
        """Total games played as black."""
        return self.games_played - self.games_as_white
    
    @property
    def win_rate(self) -> float:
        """Win rate as percentage."""
        if self.games_played == 0:
            return 0.0
        return (self.wins / self.games_played) * 100
    
    @property
    def draw_rate(self) -> float:
        """Draw rate as percentage."""
        if self.games_played == 0:
            return 0.0
        return (self.draws / self.games_played) * 100
    
    @property
    def avg_move_time(self) -> float:
        """Average think time per move in seconds."""
        if self.total_moves == 0:
            return 0.0
        return self.total_think_time / self.total_moves
    
    @property
    def illegal_move_rate(self) -> float:
        """Illegal move attempts as percentage of total moves."""
        if self.total_moves == 0:
            return 0.0
        return (self.illegal_move_attempts / self.total_moves) * 100
    
    @property
    def performance_score(self) -> float:
        """
        Composite performance score (0-100).
        
        Based on:
        - Win rate (40%)
        - Centipawn loss inverse (30%)
        - Illegal move rate inverse (20%)
        - Brilliancy rate (10%)
        """
        if self.games_played == 0:
            return 0.0
        
        win_score = self.win_rate * 0.4
        
        # Lower ACL is better, scale 0-100 based on ACL 0-100
        acl_score = max(0, 100 - self.avg_centipawn_loss) * 0.3
        
        # Lower illegal rate is better
        illegal_score = max(0, 100 - self.illegal_move_rate * 10) * 0.2
        
        # Brilliancies per game
        brilliancy_rate = (self.brilliancies / self.games_played) * 20
        brilliancy_score = min(100, brilliancy_rate) * 0.1
        
        return win_score + acl_score + illegal_score + brilliancy_score
    
    def update_from_game(
        self,
        won: bool,
        drew: bool,
        as_white: bool,
        moves: int,
        illegal_attempts: int,
        think_time: float,
        centipawn_loss: float,
        blunders: int = 0,
        mistakes: int = 0,
        inaccuracies: int = 0,
        brilliancies: int = 0,
        forfeit: bool = False
    ):
        """Update stats after a game."""
        self.games_played += 1
        self.total_moves += moves
        self.illegal_move_attempts += illegal_attempts
        self.total_think_time += think_time
        self.blunders += blunders
        self.mistakes += mistakes
        self.inaccuracies += inaccuracies
        self.brilliancies += brilliancies
        
        # Update centipawn loss running average
        if self.games_played > 1:
            self.avg_centipawn_loss = (
                (self.avg_centipawn_loss * (self.games_played - 1) + centipawn_loss)
                / self.games_played
            )
        else:
            self.avg_centipawn_loss = centipawn_loss
        
        if won:
            self.wins += 1
            self.points += 1.0
            if as_white:
                self.wins_as_white += 1
            else:
                self.wins_as_black += 1
            if forfeit:
                self.forfeits_received += 1
        elif drew:
            self.draws += 1
            self.points += 0.5
            if as_white:
                self.draws_as_white += 1
            else:
                self.draws_as_black += 1
        else:
            self.losses += 1
            if forfeit:
                self.forfeits_given += 1


@dataclass
class TournamentPlayer:
    """
    Represents an LLM competitor in the tournament.
    
    This is the core player entity that wraps an LLM provider with
    tournament-specific configuration like persona, temperature, and
    tracking for ELO ratings and statistics.
    
    Attributes:
        id: Unique identifier for the player
        name: Display name (e.g., "GPT-4 Turbo")
        provider: The LLM provider instance
        provider_name: Provider identifier (e.g., "openai")
        model_name: Specific model (e.g., "gpt-4-turbo")
        elo_rating: Current ELO rating (starts at 1500)
        persona: Playing style persona
        temperature: Generation temperature (0.0-2.0)
        max_retries: Max illegal move retries before forfeit
        status: Current player status
        stats: Cumulative game statistics
        metadata: Additional player metadata
    """
    
    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    
    # LLM Configuration
    provider: Optional[LLMProvider] = None
    provider_name: str = ""
    model_name: str = ""
    
    # Tournament Settings
    elo_rating: int = 1500
    elo_k_factor: int = 32  # Higher for new players
    persona: StylePersona = StylePersona.NEUTRAL
    custom_persona: str = ""  # If not using preset
    temperature: float = 0.7
    max_retries: int = 3
    
    # Status
    status: PlayerStatus = PlayerStatus.ACTIVE
    
    # Statistics
    stats: PlayerStats = field(default_factory=PlayerStats)
    
    # Game history (match IDs)
    match_history: List[str] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Initialize name from provider/model if not set."""
        if not self.name:
            if self.model_name:
                self.name = f"{self.provider_name}:{self.model_name}"
            elif self.provider_name:
                self.name = self.provider_name
            else:
                self.name = f"Player-{self.id}"
    
    @property
    def display_name(self) -> str:
        """Formatted name for display."""
        return f"{self.name} ({self.elo_rating})"
    
    @property
    def persona_prompt(self) -> str:
        """Get the persona prompt string."""
        if self.custom_persona:
            return self.custom_persona
        return PERSONA_PROMPTS.get(self.persona, "")
    
    @property
    def is_available(self) -> bool:
        """Check if player is available for matches."""
        return self.status == PlayerStatus.ACTIVE
    
    def update_elo(self, new_rating: int):
        """
        Update ELO rating and adjust K-factor.
        
        K-factor decreases as player plays more games to stabilize rating.
        """
        self.elo_rating = new_rating
        
        # Reduce K-factor after more games
        games = self.stats.games_played
        if games >= 30:
            self.elo_k_factor = 16
        elif games >= 10:
            self.elo_k_factor = 24
        # Keep at 32 for new players
    
    def record_match(self, match_id: str):
        """Record a match in history."""
        self.match_history.append(match_id)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        return {
            "id": self.id,
            "name": self.name,
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "elo_rating": self.elo_rating,
            "elo_k_factor": self.elo_k_factor,
            "persona": self.persona.value if isinstance(self.persona, StylePersona) else self.persona,
            "custom_persona": self.custom_persona,
            "temperature": self.temperature,
            "max_retries": self.max_retries,
            "status": self.status.value,
            "stats": {
                "games_played": self.stats.games_played,
                "wins": self.stats.wins,
                "losses": self.stats.losses,
                "draws": self.stats.draws,
                "points": self.stats.points,
                "win_rate": self.stats.win_rate,
                "avg_centipawn_loss": self.stats.avg_centipawn_loss,
                "illegal_move_rate": self.stats.illegal_move_rate,
                "avg_move_time": self.stats.avg_move_time,
                "blunders": self.stats.blunders,
                "mistakes": self.stats.mistakes,
                "brilliancies": self.stats.brilliancies,
                "performance_score": self.stats.performance_score,
            },
            "match_history": self.match_history,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], provider: Optional[LLMProvider] = None) -> "TournamentPlayer":
        """Deserialize from dictionary."""
        stats = PlayerStats()
        if "stats" in data:
            s = data["stats"]
            stats.games_played = s.get("games_played", 0)
            stats.wins = s.get("wins", 0)
            stats.losses = s.get("losses", 0)
            stats.draws = s.get("draws", 0)
            stats.points = s.get("points", 0.0)
            stats.avg_centipawn_loss = s.get("avg_centipawn_loss", 0.0)
            stats.blunders = s.get("blunders", 0)
            stats.mistakes = s.get("mistakes", 0)
            stats.brilliancies = s.get("brilliancies", 0)
        
        persona_value = data.get("persona", "neutral")
        try:
            persona = StylePersona(persona_value)
        except ValueError:
            persona = StylePersona.NEUTRAL
        
        status_value = data.get("status", "active")
        try:
            status = PlayerStatus(status_value)
        except ValueError:
            status = PlayerStatus.ACTIVE
        
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", ""),
            provider=provider,
            provider_name=data.get("provider_name", ""),
            model_name=data.get("model_name", ""),
            elo_rating=data.get("elo_rating", 1500),
            elo_k_factor=data.get("elo_k_factor", 32),
            persona=persona,
            custom_persona=data.get("custom_persona", ""),
            temperature=data.get("temperature", 0.7),
            max_retries=data.get("max_retries", 3),
            status=status,
            stats=stats,
            match_history=data.get("match_history", []),
            metadata=data.get("metadata", {}),
        )
    
    def __hash__(self):
        """Hash based on ID for set operations."""
        return hash(self.id)
    
    def __eq__(self, other):
        """Equality based on ID."""
        if isinstance(other, TournamentPlayer):
            return self.id == other.id
        return False
    
    def __repr__(self):
        return f"TournamentPlayer(id={self.id}, name={self.name}, elo={self.elo_rating})"


def create_player_from_provider(
    provider: LLMProvider,
    provider_name: str,
    model_name: str,
    name: Optional[str] = None,
    persona: StylePersona = StylePersona.NEUTRAL,
    temperature: float = 0.7,
    elo_rating: int = 1500,
) -> TournamentPlayer:
    """
    Factory function to create a TournamentPlayer from an LLM provider.
    
    Args:
        provider: The LLM provider instance
        provider_name: Provider identifier (e.g., "openai")
        model_name: Model identifier (e.g., "gpt-4")
        name: Display name (auto-generated if not provided)
        persona: Playing style persona
        temperature: Generation temperature
        elo_rating: Starting ELO rating
    
    Returns:
        TournamentPlayer: Configured player ready for tournament
    """
    display_name = name or f"{provider_name}:{model_name}"
    
    return TournamentPlayer(
        name=display_name,
        provider=provider,
        provider_name=provider_name,
        model_name=model_name,
        persona=persona,
        temperature=temperature,
        elo_rating=elo_rating,
    )
