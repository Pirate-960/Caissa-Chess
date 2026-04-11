"""
core/prompt_manager.py

Dynamically assembles prompts for the LLM based on game style, era, theme, and constraints.
This is the "creative director" that tells the LLM what kind of masterpiece to dream up.

PHASE 3.1 ENHANCEMENTS:
- Historical player personality templates (Tal, Capablanca, Fischer, etc.)
- Multi-stage prompt generation (concept → refinement → polishing)
- Dynamic prompt weighting based on game state
- Opening repertoire injection
- Narrative arc templates
- Difficulty scaling prompts
- Commentary generation prompts

Original functionality 100% preserved.
"""

import json
import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from string import Formatter
from typing import Optional, Literal, List, Dict, Callable, Tuple, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# ORIGINAL ENUMS (100% PRESERVED)
# =============================================================================

class GameEra(str, Enum):
    """Historical chess eras for stylistic generation."""
    ROMANTIC = "Romantic 1850s"
    CLASSICAL = "Classical 1880s-1920s"
    HYPERMODERN = "Hypermodern 1920s-1930s"
    SOVIET = "Soviet School 1920s-1970s"
    COMPUTER = "Computer Era 1980s-2000s"
    NEURAL = "Neural Network Era 2010s-2024"


class GameTheme(str, Enum):
    """Thematic game concepts to guide generation."""
    QUEEN_SACRIFICE = "The Queen Sacrifice"
    ROOK_SACRIFICE = "The Rook Sacrifice"
    WINDMILL = "The Windmill Attack"
    MINORITY_ATTACK = "The Minority Attack"
    PAWN_STORM = "The Pawn Storm"
    QUIET_KILLER = "The Quiet Killer Move"
    PERPETUAL_CHECK = "Perpetual Check"
    STALEMATE_TRAP = "The Stalemate Trap"
    BACK_RANK = "Back Rank Weakness"
    FIANCHETTO = "The Fianchetto Setup"


# =============================================================================
# PHASE 3.1: NEW ENUMS
# =============================================================================

class HistoricalPlayer(str, Enum):
    """Historical chess masters for personality-based generation."""
    MORPHY = "Paul Morphy"
    ANDERSSEN = "Adolf Anderssen"
    STEINITZ = "Wilhelm Steinitz"
    LASKER = "Emanuel Lasker"
    CAPABLANCA = "José Raúl Capablanca"
    ALEKHINE = "Alexander Alekhine"
    BOTVINNIK = "Mikhail Botvinnik"
    TAL = "Mikhail Tal"
    PETROSIAN = "Tigran Petrosian"
    SPASSKY = "Boris Spassky"
    FISCHER = "Bobby Fischer"
    KARPOV = "Anatoly Karpov"
    KASPAROV = "Garry Kasparov"
    CARLSEN = "Magnus Carlsen"
    ALPHA_ZERO = "AlphaZero"


class NarrativeArc(str, Enum):
    """Story arc templates for game generation."""
    BLITZKRIEG = "Blitzkrieg"           # Fast, overwhelming attack
    COMEBACK = "The Comeback"            # Near-loss turned into victory
    SLOW_SQUEEZE = "The Slow Squeeze"    # Gradual positional domination
    MUTUAL_DESTRUCTION = "Mutual Destruction"  # Wild, chaotic tactical melee
    PERFECT_TECHNIQUE = "Perfect Technique"    # Flawless, clinical execution
    BRILLIANCY = "The Brilliancy"        # Single stunning move turns game
    ENDGAME_MAGIC = "Endgame Magic"      # Simple position, complex conversion


class PromptStage(str, Enum):
    """Multi-stage prompt generation stages."""
    CONCEPT = "concept"          # Initial game concept
    OPENING = "opening"          # Opening moves
    DEVELOPMENT = "development"  # Middlegame development
    TACTICAL = "tactical"        # Tactical execution
    CONCLUSION = "conclusion"    # Game conclusion
    REFINEMENT = "refinement"    # Post-generation refinement


class DifficultyLevel(str, Enum):
    """Target difficulty for generated games."""
    BEGINNER = "beginner"        # Simple tactics, clear lessons
    INTERMEDIATE = "intermediate"  # Moderate complexity
    ADVANCED = "advanced"        # Complex middlegame ideas
    MASTER = "master"            # Deep strategic themes
    GRANDMASTER = "grandmaster"  # Highest level complexity


# =============================================================================
# ORIGINAL DATACLASS (100% PRESERVED)
# =============================================================================

class PromptBias(str, Enum):
    """Bias for game generation.

    WHITE   – Force White to win (1-0).
    BLACK   – Force Black to win (0-1).
    DRAW    – Force a draw (1/2-1/2).
    RANDOM  – Randomly assign one of 1-0 / 0-1 / 1/2-1/2 each game.
    NEUTRAL – Let the LLM decide the most dramatically satisfying result.
    """
    WHITE = "white"
    BLACK = "black"
    DRAW = "draw"
    RANDOM = "random"
    NEUTRAL = "neutral"


@dataclass
class GameContext:
    """Configuration for a single game generation."""
    era: GameEra = GameEra.ROMANTIC
    theme: Optional[GameTheme] = None
    white_player: str = "Caissa White"
    black_player: str = "Caissa Black"
    aggression_score: int = 7  # 1-10, higher = more risky
    chaos_score: int = 5  # 1-10, higher = more surprising moves
    depth: int = 40  # Half-moves in the game
    blunder_tolerance: float = 1.5  # Centipawns allowed on weaker moves
    bias: PromptBias = PromptBias.NEUTRAL  # Bias the game outcome


# =============================================================================
# PHASE 3.1: NEW ADVANCED DATACLASSES
# =============================================================================

@dataclass
class PlayerPersonality:
    """Detailed personality profile for a historical player."""
    player: HistoricalPlayer
    opening_repertoire: List[str] = field(default_factory=list)
    preferred_structures: List[str] = field(default_factory=list)
    tactical_tendencies: List[str] = field(default_factory=list)
    positional_tendencies: List[str] = field(default_factory=list)
    signature_moves: List[str] = field(default_factory=list)
    weakness_areas: List[str] = field(default_factory=list)
    famous_games: List[str] = field(default_factory=list)
    style_description: str = ""
    aggression_baseline: int = 5
    risk_tolerance: int = 5
    
    def to_prompt_injection(self) -> str:
        """Generate prompt text for this personality."""
        lines = [f"### Playing as {self.player.value}"]
        lines.append(f"Style: {self.style_description}")
        
        if self.opening_repertoire:
            lines.append(f"Preferred Openings: {', '.join(self.opening_repertoire)}")
        if self.tactical_tendencies:
            lines.append(f"Tactical Style: {', '.join(self.tactical_tendencies)}")
        if self.positional_tendencies:
            lines.append(f"Positional Approach: {', '.join(self.positional_tendencies)}")
        if self.signature_moves:
            lines.append(f"Signature Ideas: {', '.join(self.signature_moves)}")
        if self.famous_games:
            lines.append(f"Study These Games: {', '.join(self.famous_games[:3])}")
        
        return "\n".join(lines)


@dataclass
class AdvancedGameContext(GameContext):
    """Extended game context with Phase 3.1 features."""
    # Inherits all GameContext fields
    white_personality: Optional[PlayerPersonality] = None
    black_personality: Optional[PlayerPersonality] = None
    narrative_arc: Optional[NarrativeArc] = None
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    target_beauty_score: float = 70.0
    include_annotations: bool = True
    include_commentary: bool = False
    opening_eco: Optional[str] = None  # Force specific ECO opening
    endgame_type: Optional[str] = None  # e.g., "Rook endgame", "Queen vs Rook"
    custom_constraints: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "era": self.era.value,
            "theme": self.theme.value if self.theme else None,
            "white_player": self.white_player,
            "black_player": self.black_player,
            "aggression_score": self.aggression_score,
            "chaos_score": self.chaos_score,
            "depth": self.depth,
            "blunder_tolerance": self.blunder_tolerance,
            "bias": self.bias.value,
            "narrative_arc": self.narrative_arc.value if self.narrative_arc else None,
            "difficulty": self.difficulty.value,
            "target_beauty_score": self.target_beauty_score,
            "include_annotations": self.include_annotations,
            "include_commentary": self.include_commentary,
        }


@dataclass
class StagePrompt:
    """A single stage in multi-stage prompt generation."""
    stage: PromptStage
    system_prompt: str
    user_prompt: str
    expected_output_format: str = "PGN"
    temperature: float = 0.7
    max_tokens: int = 2000


@dataclass
class NarrativeTemplate:
    """Template for narrative arc execution."""
    arc: NarrativeArc
    phases: List[str]
    key_moments: List[str]
    emotional_trajectory: str
    typical_length: int  # Half-moves
    
    def to_prompt_section(self) -> str:
        lines = [f"### Narrative Arc: {self.arc.value}"]
        lines.append(f"Emotional Journey: {self.emotional_trajectory}")
        lines.append(f"Key Phases: {' → '.join(self.phases)}")
        lines.append(f"Expected Moments: {', '.join(self.key_moments)}")
        return "\n".join(lines)


# =============================================================================
# ORIGINAL CLASS (100% PRESERVED) + PHASE 3.1 ENHANCEMENTS
# =============================================================================

class PromptManager:
    """
    Constructs the system and user prompts for the LLM.
    Implements Chain-of-Thought (CoT) reasoning for move generation.
    
    PHASE 3.1: Enhanced with personality injection, multi-stage prompts,
    narrative templates, and dynamic weighting.
    """

    # ORIGINAL TEMPLATE (100% PRESERVED)
    SYSTEM_TEMPLATE = """### CAISSA: The Aesthetic Chess Engine
You are Grandmaster Caissa. You possess the tactical sharpness of Kasparov, the intuition of Tal, 
and the positional squeeze of Karpov. You are not playing to win; you are playing to CREATE ART.

### YOUR OBJECTIVE
Generate a chess game in PGN (Portable Game Notation) that is:
1. **LEGALLY VALID** (Critical)
2. **STRATEGICALLY COHERENT** (No random shuffling)
3. **AESTHETICALLY STUNNING** (Memorable, instructive, beautiful)

### CURRENT GENERATION PARAMETERS
- **Era**: {era}
- **Theme**: {theme}
- **White**: {white_player}
- **Black**: {black_player}
- **Aggression**: {aggression_score}/10 (Higher = more risky/tactical)
- **Chaos**: {chaos_score}/10 (Higher = more surprising moves)
- **Target Length**: {depth} half-moves

### THE GAME GENERATION FRAMEWORK (Chain of Thought)

Before you generate a single move, THINK through the narrative arc:

1. **The Concept Phase**:
   - Define the strategic theme. Who attacks? Who defends?
   - What is the "story arc" of this game?
   - Example: "White sacrifices the queen on move 12, exposing Black's king to a mating net."

2. **The Opening Phase** (Moves 1-8):
   - Play standard, sound opening moves consistent with the era and theme.
   - Establish pawn structure and piece coordination.
   - For {era}, style moves should reflect historical preferences.

3. **The Spark Phase** (Moves 9-15):
   - This is where the game deviates from theory into brilliance.
   - {theme_instruction}
   - Aggression={aggression_score} means you can be {aggression_description}.

4. **The Climax Phase** (Moves 16-{climax_end}):
   - Execute the decisive combination or squeeze.
   - If a sacrifice was promised, now is when it pays dividends.
   - Include forcing moves: checks, threats, material gain.

5. **The Conclusion Phase** (Final moves):
   - Force checkmate or win material decisively.
   - {conclusion_objective}

### CRITICAL RULES
1. **ONLY USE STANDARD ALGEBRAIC NOTATION** (e.g., "e4", "Nf3", "O-O")
2. **LEGAL MOVES ONLY**. If a move is illegal, the entire game is invalid.
3. **SOUND SACRIFICES**: If you plan a sacrifice, there MUST be compensation (attack, fork, pin, mate threat).
4. **ANNOTATIONS**: Use '!!' for brilliant moves, '!' for good moves, '?' for curious moves.
5. **NO HALLUCINATIONS**: Don't invent piece movements that violate chess rules.

### OUTPUT FORMAT
Return the game in this exact format:

```
[Event "Caissa Masterpiece Generation"]
[Site "The Aesthetic Engine"]
[Date "{date}"]
[White "{white_player}"]
[Black "{black_player}"]
[Result "{expected_result}"]
[Annotator "Caissa"]

1. e4 e5 2. Nf3 Nc6 3. Bb5! ...

[Your complete game here in PGN format]
```

### STRATEGIC GUIDELINES BY ERA
{era_guidelines}

### FINAL INSTRUCTION
Generate now. Think deeply. Make every move count. The chessboard awaits your masterpiece.
"""
    _SYSTEM_TEMPLATE_OVERRIDE: Optional[str] = None
    _USER_PROMPT_PREFIX_OVERRIDE: Optional[str] = None
    _USER_PROMPT_SUFFIX_OVERRIDE: Optional[str] = None
    _OPENING_KEY_OVERRIDE: Optional[str] = None
    _PROMPT_MODE_OVERRIDE: str = "single"
    _COMMENTARY_PROFILE_OVERRIDE: str = "off"
    _COMMENTARY_INTENSITY_OVERRIDE: int = 5
    _OPENINGS_CACHE: Optional[Dict[str, Dict[str, Any]]] = None
    _OPENING_RECENTS: List[str] = []
    _OPENING_FAVORITES: List[str] = []
    _SYSTEM_REQUIRED_FIELDS = {
        "era",
        "theme",
        "white_player",
        "black_player",
        "aggression_score",
        "chaos_score",
        "depth",
        "conclusion_objective",
        "expected_result",
    }
    _DEFAULT_PROFILE_COMPATIBILITY = {"single": True, "match": True, "tournament": True}
    _MODE_CONTRACTS = {
        "single": "Single mode contract: produce a complete legal game with terminal result (no '*').",
        "match": "Match mode contract: legal moves required; forfeit/timeout/in-progress semantics allowed by match engine.",
        "tournament": "Tournament contract: match-level semantics allowed; aggregate standings/export consistency required.",
    }
    _COMMENTARY_PROFILES = {
        "off": "",
        "broadcast": "Provide concise live-commentary hooks for critical moments, momentum shifts, and tactical turning points.",
        "educational": "Prioritize didactic commentary hooks explaining strategic plans, tactical motifs, and instructive mistakes.",
        "dramatic": "Prioritize high-energy commentary hooks with narrative tension and key-moment framing.",
    }

    # ORIGINAL ERA GUIDELINES (100% PRESERVED)
    ERA_GUIDELINES = {
        GameEra.ROMANTIC: """
- **Romantic Era (1850s)**: Swashbuckling, direct attacks. Sacrifices for "the attack" even if unsound by modern standards.
- **Style**: Bold queen sacrifices, pawn storms, open files for the rooks.
- **Example Theme**: The Immortal Game (Anderssen). Expect tactics over positional understanding.
""",
        GameEra.CLASSICAL: """
- **Classical Era (1880s-1920s)**: Transition from Romantic to positional. Steinitz's principles: centralization, pawn structure.
- **Style**: More sound sacrifices. Emphasis on piece activity and pawn structure.
- **Example Theme**: Positional advantage building into tactical finales.
""",
        GameEra.HYPERMODERN: """
- **Hypermodern Era (1920s-1930s)**: The revolution! Control the center from afar, fianchetto setups, prophylaxis.
- **Style**: Riga Indian, King's Indian Defense. Long-term positional maneuvering.
- **Example Theme**: Aron Nimzowitsch's "My System"—quiet, mysterious moves that build invisible pressure.
""",
        GameEra.SOVIET: """
- **Soviet School (1920s-1970s)**: Scientific, methodical, deep preparation. Botvinnik's computer-like precision.
- **Style**: Solid openings, prophylactic thinking, deep endgame technique.
- **Example Theme**: Slow squeeze, then tactical blow when the position crumbles.
""",
        GameEra.COMPUTER: """
- **Computer Era (1980s-2000s)**: Engines begin to influence style. Deep tactical complications, precision.
- **Style**: Sharp openings like the Najdorf, Sicilian Sveshnikov. Minimal sentiment, maximum efficacy.
- **Example Theme**: Crushing attacks based on concrete calculation, not intuition.
""",
        GameEra.NEURAL: """
- **Neural Network Era (2010s-2024)**: AlphaZero, Leela Chess Zero influence. Alien sacrifices that look wrong but are right.
- **Style**: Non-human logic. Mysterious pawn moves, unexpected piece placements that seem illogical until 5 moves later.
- **Example Theme**: Sacrifice material for inexplicable positional compensation. The "neural" understanding.
""",
    }

    # =========================================================================
    # PHASE 3.1: PLAYER PERSONALITY DATABASE
    # =========================================================================
    
    PLAYER_PERSONALITIES: Dict[HistoricalPlayer, PlayerPersonality] = {
        HistoricalPlayer.TAL: PlayerPersonality(
            player=HistoricalPlayer.TAL,
            opening_repertoire=["Sicilian Najdorf", "King's Indian", "Benoni"],
            preferred_structures=["Open center", "Unbalanced pawn structures"],
            tactical_tendencies=["Exchange sacrifices", "Piece sacrifices for initiative", 
                                "Attacking the king at all costs"],
            positional_tendencies=["Piece activity over material", "Initiative above all"],
            signature_moves=["Rook sacrifices on open files", "Queen forays into enemy territory"],
            weakness_areas=["Endgames", "Quiet technical positions"],
            famous_games=["Tal vs Larsen 1965", "Tal vs Smyslov 1959", "Tal vs Botvinnik 1960"],
            style_description="The Magician from Riga. Wild, imaginative attacks. Sacrifices "
                             "pieces like a gambler, but calculates like a machine.",
            aggression_baseline=9,
            risk_tolerance=10,
        ),
        HistoricalPlayer.CAPABLANCA: PlayerPersonality(
            player=HistoricalPlayer.CAPABLANCA,
            opening_repertoire=["Queen's Gambit Declined", "Ruy Lopez", "Caro-Kann"],
            preferred_structures=["Symmetric structures", "Minority attack setups"],
            tactical_tendencies=["Simple but deadly tactics", "Exchange-based winning"],
            positional_tendencies=["Endgame mastery", "Piece exchanges into won endgames",
                                  "Prophylaxis"],
            signature_moves=["Seemingly simple moves with hidden depth", "Technical endgame wins"],
            weakness_areas=["Avoiding complications", "Opening preparation in later career"],
            famous_games=["Capablanca vs Marshall 1918", "Capablanca vs Tartakower 1924"],
            style_description="The Chess Machine. Crystal-clear logic. Simple moves that "
                             "somehow are always correct. Endgame perfection.",
            aggression_baseline=4,
            risk_tolerance=3,
        ),
        HistoricalPlayer.FISCHER: PlayerPersonality(
            player=HistoricalPlayer.FISCHER,
            opening_repertoire=["Sicilian Najdorf", "King's Indian Attack", "Ruy Lopez"],
            preferred_structures=["Open games", "Symmetric structures with piece activity"],
            tactical_tendencies=["Concrete calculation", "Tactical precision", "No unsound sacs"],
            positional_tendencies=["Classical approach", "Piece harmony", "Bishop pair lover"],
            signature_moves=["e4 followed by aggressive piece play", "Crushing endgame technique"],
            weakness_areas=["None significant - nearly perfect technically"],
            famous_games=["Fischer vs Spassky 1972 Game 6", "Fischer vs Byrne 1956"],
            style_description="The most complete player. Classical, clear, crushing. "
                             "Perfect calculation combined with perfect technique.",
            aggression_baseline=7,
            risk_tolerance=5,
        ),
        HistoricalPlayer.KASPAROV: PlayerPersonality(
            player=HistoricalPlayer.KASPAROV,
            opening_repertoire=["Sicilian Najdorf", "King's Indian Defense", "Grünfeld"],
            preferred_structures=["Dynamic imbalances", "Attack on opposite wings"],
            tactical_tendencies=["Overwhelming attacks", "Intuitive sacrifices", 
                                "Piece coordination"],
            positional_tendencies=["Initiative at all costs", "Dynamic piece play"],
            signature_moves=["Powerful knight outposts", "Kingside attacks with h-pawn"],
            weakness_areas=["Occasional time trouble", "Overconfidence against computers"],
            famous_games=["Kasparov vs Topalov 1999", "Kasparov vs Karpov 1985"],
            style_description="The Beast from Baku. Relentless attacking power. Every piece "
                             "coordinated for maximum striking force. Never lets opponents rest.",
            aggression_baseline=8,
            risk_tolerance=7,
        ),
        HistoricalPlayer.KARPOV: PlayerPersonality(
            player=HistoricalPlayer.KARPOV,
            opening_repertoire=["Queen's Gambit", "Caro-Kann", "Ruy Lopez closed"],
            preferred_structures=["Isolated queen pawn", "Minority attack positions"],
            tactical_tendencies=["Quiet tactical threats", "Prophylactic moves"],
            positional_tendencies=["Space advantage", "Restriction", "Slow improvement"],
            signature_moves=["a4/a5 prophylaxis", "Piece maneuvering", "Quiet suffocation"],
            weakness_areas=["Time pressure in complex positions"],
            famous_games=["Karpov vs Kasparov 1984 Game 9", "Karpov vs Spassky 1974"],
            style_description="The Boa Constrictor. Slow, inexorable pressure. Restricts "
                             "opponent's pieces until they suffocate. Silent assassin.",
            aggression_baseline=4,
            risk_tolerance=3,
        ),
        HistoricalPlayer.MORPHY: PlayerPersonality(
            player=HistoricalPlayer.MORPHY,
            opening_repertoire=["Italian Game", "Scotch Game", "King's Gambit"],
            preferred_structures=["Open center", "Rapid development"],
            tactical_tendencies=["Development sacrifices", "Open file attacks", "Rapid mobilization"],
            positional_tendencies=["Classical development", "Piece activity"],
            signature_moves=["Gambits for development", "Open files against the king"],
            weakness_areas=["Lacked modern theoretical knowledge"],
            famous_games=["Morphy vs Duke of Brunswick 1858", "Morphy vs Anderssen 1858"],
            style_description="The Pride and Sorrow of Chess. Pure, classical development. "
                             "Rapid piece mobilization crushing undeveloped positions.",
            aggression_baseline=7,
            risk_tolerance=6,
        ),
        HistoricalPlayer.ALEKHINE: PlayerPersonality(
            player=HistoricalPlayer.ALEKHINE,
            opening_repertoire=["French Defense", "Queen's Gambit", "Alekhine Defense"],
            preferred_structures=["Complex dynamic positions", "Piece activity over material"],
            tactical_tendencies=["Brilliant combinations", "Multi-piece attacks", "Sacrificial storms"],
            positional_tendencies=["Strategic complexity", "Long-term planning"],
            signature_moves=["Deep combinations", "Positional sacrifices"],
            weakness_areas=["Inconsistency in form"],
            famous_games=["Alekhine vs Réti 1925", "Alekhine vs Nimzowitsch 1930"],
            style_description="The Russian Wizard. Combines strategic depth with tactical "
                             "brilliance. Complex, deep, and devastating.",
            aggression_baseline=8,
            risk_tolerance=7,
        ),
        HistoricalPlayer.PETROSIAN: PlayerPersonality(
            player=HistoricalPlayer.PETROSIAN,
            opening_repertoire=["Queen's Indian", "English Opening", "Hedgehog structures"],
            preferred_structures=["Hedgehog", "Closed positions", "Prophylactic setups"],
            tactical_tendencies=["Prophylactic exchanges", "Defensive excellence"],
            positional_tendencies=["Fortress building", "Exchange sacrifices (defense)"],
            signature_moves=["The prophylactic exchange sacrifice", "a3/h3 waiting moves"],
            weakness_areas=["Lack of killer instinct sometimes"],
            famous_games=["Petrosian vs Spassky 1966", "Petrosian vs Fischer 1971"],
            style_description="Iron Tigran. Master of prophylaxis. Sees threats before they "
                             "exist and neutralizes them. Fortress builder extraordinaire.",
            aggression_baseline=3,
            risk_tolerance=2,
        ),
        HistoricalPlayer.CARLSEN: PlayerPersonality(
            player=HistoricalPlayer.CARLSEN,
            opening_repertoire=["Berlin Defense", "Sveshnikov", "English Opening"],
            preferred_structures=["All types - universal player"],
            tactical_tendencies=["Practical decisions", "Endgame conversions", "No draws mindset"],
            positional_tendencies=["Grinding technique", "Playing on with minimal advantages"],
            signature_moves=["Converting drawn positions", "Endless endgame technique"],
            weakness_areas=["Sometimes overconfident in inferior positions"],
            famous_games=["Carlsen vs Anand 2013", "Carlsen vs Karjakin 2016"],
            style_description="The Mozart of Chess. Universal style. Can play anything. "
                             "Grinds opponents down with relentless technique and stamina.",
            aggression_baseline=5,
            risk_tolerance=4,
        ),
        HistoricalPlayer.ALPHA_ZERO: PlayerPersonality(
            player=HistoricalPlayer.ALPHA_ZERO,
            opening_repertoire=["All openings - self-discovered preferences"],
            preferred_structures=["Dynamic piece play", "Unusual pawn structures"],
            tactical_tendencies=["Long-term piece sacrifices", "Positional exchange sacrifices"],
            positional_tendencies=["Activity over material", "Piece mobility", "Central control"],
            signature_moves=["h4 in closed positions", "Bishop pair domination", 
                            "Unexplained pawn moves"],
            weakness_areas=["Can miss simple human tactics occasionally"],
            famous_games=["AlphaZero vs Stockfish 2017 Game 1", "AlphaZero vs Stockfish 2017 Game 10"],
            style_description="The Alien Intelligence. Plays moves that look wrong to humans "
                             "but are deeply correct. Mysterious, beautiful, unstoppable.",
            aggression_baseline=6,
            risk_tolerance=8,  # High risk for long-term gains
        ),
    }

    # =========================================================================
    # PHASE 3.1: NARRATIVE ARC TEMPLATES
    # =========================================================================
    
    NARRATIVE_TEMPLATES: Dict[NarrativeArc, NarrativeTemplate] = {
        NarrativeArc.BLITZKRIEG: NarrativeTemplate(
            arc=NarrativeArc.BLITZKRIEG,
            phases=["Rapid development", "Early attack", "Overwhelming combination", "Quick mate"],
            key_moments=["Development gambit", "Central breakthrough", "King hunt"],
            emotional_trajectory="Tension → Explosion → Victory (fast)",
            typical_length=30,
        ),
        NarrativeArc.COMEBACK: NarrativeTemplate(
            arc=NarrativeArc.COMEBACK,
            phases=["Early setback", "Defensive consolidation", "Counter-attack", "Reversal"],
            key_moments=["Critical mistake by opponent", "Defensive resource", "Counter-blow"],
            emotional_trajectory="Despair → Hope → Determination → Triumph",
            typical_length=50,
        ),
        NarrativeArc.SLOW_SQUEEZE: NarrativeTemplate(
            arc=NarrativeArc.SLOW_SQUEEZE,
            phases=["Solid opening", "Space advantage", "Restriction", "Collapse"],
            key_moments=["Key prophylactic move", "Space-gaining pawn push", "Final breakthrough"],
            emotional_trajectory="Calm → Building pressure → Suffocation → Resignation",
            typical_length=45,
        ),
        NarrativeArc.MUTUAL_DESTRUCTION: NarrativeTemplate(
            arc=NarrativeArc.MUTUAL_DESTRUCTION,
            phases=["Sharp opening", "Tactical melee", "Material chaos", "Survivor wins"],
            key_moments=["Double-edged sacrifice", "Counter-sacrifice", "Calculation battle"],
            emotional_trajectory="Tension → Chaos → More Chaos → Resolution",
            typical_length=40,
        ),
        NarrativeArc.PERFECT_TECHNIQUE: NarrativeTemplate(
            arc=NarrativeArc.PERFECT_TECHNIQUE,
            phases=["Sound opening", "Small advantage", "Gradual conversion", "Technical win"],
            key_moments=["Subtle improvement", "Endgame transition", "Flawless execution"],
            emotional_trajectory="Calm → Control → Precision → Clean victory",
            typical_length=55,
        ),
        NarrativeArc.BRILLIANCY: NarrativeTemplate(
            arc=NarrativeArc.BRILLIANCY,
            phases=["Normal development", "The spark", "The combination", "Beautiful finale"],
            key_moments=["The brilliant move (!!)", "Sacrifice acceptance", "Forced sequence"],
            emotional_trajectory="Normal → Surprise → Wonder → Admiration",
            typical_length=35,
        ),
        NarrativeArc.ENDGAME_MAGIC: NarrativeTemplate(
            arc=NarrativeArc.ENDGAME_MAGIC,
            phases=["Simplification", "Endgame setup", "Deep technique", "Surprising win"],
            key_moments=["Key exchange", "Pawn breakthrough", "Opposition/Zugzwang"],
            emotional_trajectory="Simplicity → Complexity within simplicity → Revelation",
            typical_length=60,
        ),
    }

    # =========================================================================
    # PHASE 3.1: DIFFICULTY TEMPLATES
    # =========================================================================
    
    DIFFICULTY_GUIDELINES: Dict[DifficultyLevel, str] = {
        DifficultyLevel.BEGINNER: """
### Difficulty: Beginner-Friendly
- Use clear, instructive tactics (forks, pins, back rank)
- Avoid overly complex pawn structures
- Include obvious blunders from the losing side
- Game should teach basic opening principles
- Annotations should explain each significant move
""",
        DifficultyLevel.INTERMEDIATE: """
### Difficulty: Intermediate
- Include standard tactical motifs (discovered attacks, double threats)
- Moderate positional complexity
- Opponent makes natural but ultimately losing moves
- Some strategic themes should be present
""",
        DifficultyLevel.ADVANCED: """
### Difficulty: Advanced
- Complex combinations requiring 3-4 move calculation
- Strategic themes: pawn structure, piece activity
- Opponent plays strong moves but gets outplayed
- Include exchange sacrifices or positional sacrifices
""",
        DifficultyLevel.MASTER: """
### Difficulty: Master Level
- Deep strategic understanding required
- Subtle positional advantages built over many moves
- Opponent plays near-optimal moves
- Include prophylactic thinking and long-term planning
""",
        DifficultyLevel.GRANDMASTER: """
### Difficulty: Grandmaster Level
- Highest complexity with cutting-edge ideas
- Near-perfect play from both sides
- Winning advantage comes from very subtle factors
- Include computer-like precision in critical moments
- May feature theoretical novelties or deep preparation
""",
    }

    def __init__(self):
        pass

    @classmethod
    def _catalog_checksum(cls, catalog: Dict[str, str]) -> str:
        blob = json.dumps(catalog, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def _prepared_library(cls) -> Dict[str, Dict[str, str]]:
        base = cls.SYSTEM_TEMPLATE
        templates = {
            "balanced_default": {
                "system_template": base,
                "user_prompt_prefix": "",
                "user_prompt_suffix": "",
            },
            "tactical_sharp": {
                "system_template": base + "\n\n### STYLE OVERRIDE\nPrioritize tactical complications, forcing lines, and sacrificial motifs while preserving legal PGN output.",
                "user_prompt_prefix": "Emphasize tactical motifs and concrete calculation.",
                "user_prompt_suffix": "",
            },
            "positional_classical": {
                "system_template": base + "\n\n### STYLE OVERRIDE\nPrefer strategic accumulation, prophylaxis, and clean technical conversion with legal PGN output.",
                "user_prompt_prefix": "Prioritize positional themes over speculative attacks.",
                "user_prompt_suffix": "",
            },
            "annotation_rich": {
                "system_template": base + "\n\n### ANNOTATION EMPHASIS\nProvide frequent but meaningful annotations for critical and instructive moves.",
                "user_prompt_prefix": "Target rich commentary and annotations on key turning points.",
                "user_prompt_suffix": "",
            },
            "strict_terminal": {
                "system_template": base + "\n\n### TERMINAL RESULT ENFORCEMENT\nAlways finish with a concrete terminal result (1-0, 0-1, 1/2-1/2). Never output '*'.",
                "user_prompt_prefix": "",
                "user_prompt_suffix": "Ensure final PGN headers and final movetext result are consistent and terminal.",
            },
        }
        tal = cls.PLAYER_PERSONALITIES.get(HistoricalPlayer.TAL)
        brilliancy = cls.NARRATIVE_TEMPLATES.get(NarrativeArc.BRILLIANCY)
        gm = cls.DIFFICULTY_GUIDELINES.get(DifficultyLevel.GRANDMASTER, "")
        templates["asset_tal_brilliancy"] = {
            "system_template": (
                base
                + "\n\n### ASSET TEMPLATE: TAL BRILLIANCY\n"
                + (tal.to_prompt_injection() if tal else "")
                + "\n\n"
                + (brilliancy.to_prompt_section() if brilliancy else "")
                + "\n\n"
                + gm
            ),
            "user_prompt_prefix": "Blend tactical fireworks with coherent strategic narrative arc.",
            "user_prompt_suffix": "",
        }
        templates["asset_endgame_magic"] = {
            "system_template": (
                base
                + "\n\n### ASSET TEMPLATE: ENDGAME MAGIC\n"
                + cls.NARRATIVE_TEMPLATES[NarrativeArc.ENDGAME_MAGIC].to_prompt_section()
                + "\n\n"
                + cls.DIFFICULTY_GUIDELINES[DifficultyLevel.MASTER]
            ),
            "user_prompt_prefix": "Aim for a clean technical conversion with one instructive endgame idea.",
            "user_prompt_suffix": "",
        }
        return templates

    # =========================================================================
    # PROMPT STUDIO SUPPORT (non-breaking overrides)
    # =========================================================================

    @classmethod
    def get_prompt_catalog(cls) -> Dict[str, str]:
        """Return the active prompt catalog for inspection/editing."""
        return {
            "system_template": cls._SYSTEM_TEMPLATE_OVERRIDE or cls.SYSTEM_TEMPLATE,
            "user_prompt_prefix": cls._USER_PROMPT_PREFIX_OVERRIDE or "",
            "user_prompt_suffix": cls._USER_PROMPT_SUFFIX_OVERRIDE or "",
        }

    @classmethod
    def get_prompt_context_state(cls) -> Dict[str, str]:
        return {
            "mode": cls._PROMPT_MODE_OVERRIDE,
            "opening_key": cls._OPENING_KEY_OVERRIDE or "",
            "commentary_profile": cls._COMMENTARY_PROFILE_OVERRIDE,
            "commentary_intensity": str(cls._COMMENTARY_INTENSITY_OVERRIDE),
        }

    @classmethod
    def set_prompt_mode(cls, mode: str) -> None:
        if mode not in ("single", "match", "tournament"):
            raise ValueError(f"Unsupported prompt mode: {mode}")
        cls._PROMPT_MODE_OVERRIDE = mode

    @classmethod
    def set_opening_override(cls, opening_key: Optional[str]) -> None:
        cls._OPENING_KEY_OVERRIDE = opening_key or None
        if opening_key:
            cls.track_opening_recent(opening_key)

    @classmethod
    def set_commentary_profile(cls, profile: str, intensity: Optional[int] = None) -> None:
        if profile not in cls._COMMENTARY_PROFILES:
            raise ValueError(f"Unsupported commentary profile: {profile}")
        cls._COMMENTARY_PROFILE_OVERRIDE = profile
        if intensity is not None:
            cls._COMMENTARY_INTENSITY_OVERRIDE = max(0, min(10, int(intensity)))

    @classmethod
    def commentary_injection_text(cls) -> str:
        profile = cls._COMMENTARY_PROFILE_OVERRIDE
        if profile == "off":
            return ""
        guidance = cls._COMMENTARY_PROFILES.get(profile, "")
        return (
            "\n### COMMENTARY PROFILE\n"
            f"- Profile: {profile}\n"
            f"- Intensity: {cls._COMMENTARY_INTENSITY_OVERRIDE}/10\n"
            f"- Guidance: {guidance}\n"
            "- Keep commentary concise and preserve strict legal PGN output.\n"
        )

    @classmethod
    def preview_commentary_injection(cls, profile: str, intensity: int) -> str:
        if profile not in cls._COMMENTARY_PROFILES:
            raise ValueError(f"Unsupported commentary profile: {profile}")
        intensity = max(0, min(10, int(intensity)))
        if profile == "off":
            return "Commentary profile is OFF (no commentary injection will be added)."
        guidance = cls._COMMENTARY_PROFILES.get(profile, "")
        return (
            "### COMMENTARY PROFILE\n"
            f"- Profile: {profile}\n"
            f"- Intensity: {intensity}/10\n"
            f"- Guidance: {guidance}\n"
            "- Keep commentary concise and preserve strict legal PGN output.\n"
        )

    @classmethod
    def _load_openings(cls, root: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
        if cls._OPENINGS_CACHE is not None:
            return cls._OPENINGS_CACHE
        base = root or Path(__file__).parent.parent
        data_path = base / "data" / "openings.json"
        cls._OPENINGS_CACHE = json.loads(data_path.read_text(encoding="utf-8"))
        return cls._OPENINGS_CACHE

    @classmethod
    def reload_openings(cls, root: Optional[Path] = None) -> int:
        """Force reload openings from disk and return count."""
        cls._OPENINGS_CACHE = None
        return len(cls._load_openings(root=root))

    @classmethod
    def fresh_openings_count(cls, root: Optional[Path] = None) -> int:
        """Read openings directly from disk without cache for verification."""
        base = root or Path(__file__).parent.parent
        data_path = base / "data" / "openings.json"
        data = json.loads(data_path.read_text(encoding="utf-8"))
        return len(data.keys())

    @classmethod
    def openings_source_path(cls, root: Optional[Path] = None) -> str:
        base = root or Path(__file__).parent.parent
        return str(base / "data" / "openings.json")

    @classmethod
    def list_opening_keys(cls, root: Optional[Path] = None) -> List[str]:
        book = cls._load_openings(root=root)
        return sorted(book.keys())

    @classmethod
    def track_opening_recent(cls, opening_key: str) -> None:
        if opening_key in cls._OPENING_RECENTS:
            cls._OPENING_RECENTS.remove(opening_key)
        cls._OPENING_RECENTS.insert(0, opening_key)
        cls._OPENING_RECENTS = cls._OPENING_RECENTS[:10]

    @classmethod
    def get_opening_recents(cls) -> List[str]:
        return list(cls._OPENING_RECENTS)

    @classmethod
    def toggle_opening_favorite(cls, opening_key: str) -> bool:
        if opening_key in cls._OPENING_FAVORITES:
            cls._OPENING_FAVORITES.remove(opening_key)
            return False
        cls._OPENING_FAVORITES.append(opening_key)
        cls._OPENING_FAVORITES = sorted(set(cls._OPENING_FAVORITES))
        return True

    @classmethod
    def get_opening_favorites(cls) -> List[str]:
        return list(cls._OPENING_FAVORITES)

    @classmethod
    def get_opening_pack(cls, opening_key: str, root: Optional[Path] = None) -> Dict[str, Any]:
        book = cls._load_openings(root=root)
        if opening_key not in book:
            raise KeyError(f"Unknown opening key: {opening_key}")
        return book[opening_key]

    @classmethod
    def opening_injection_text(cls, opening_key: str, root: Optional[Path] = None) -> str:
        item = cls.get_opening_pack(opening_key, root=root)
        eco = item.get("eco", "N/A")
        notes = item.get("notes", "")
        moves = " ".join(item.get("moves", [])[:16]).strip()
        return (
            f"\n### OPENING PACK\n"
            f"- Opening Key: {opening_key}\n"
            f"- ECO: {eco}\n"
            f"- Guiding line: {moves}\n"
            f"- Strategic note: {notes}\n"
            f"- Stay coherent with this opening family unless tactical necessity dictates deviation.\n"
        )

    @classmethod
    def get_mode_contract(cls, mode: Optional[str] = None) -> str:
        m = mode or cls._PROMPT_MODE_OVERRIDE
        return cls._MODE_CONTRACTS.get(m, cls._MODE_CONTRACTS["single"])

    @classmethod
    def list_prepared_templates(cls) -> List[str]:
        return sorted(cls._prepared_library().keys())

    @classmethod
    def get_prepared_template(cls, name: str) -> Dict[str, str]:
        library = cls._prepared_library()
        if name not in library:
            raise KeyError(f"Unknown prepared template: {name}")
        return dict(library[name])

    @classmethod
    def set_prompt_overrides(
        cls,
        system_template: Optional[str] = None,
        user_prompt_prefix: Optional[str] = None,
        user_prompt_suffix: Optional[str] = None,
    ) -> None:
        """Set session-level prompt overrides without mutating built-ins."""
        if system_template is not None:
            cls._SYSTEM_TEMPLATE_OVERRIDE = system_template
        if user_prompt_prefix is not None:
            cls._USER_PROMPT_PREFIX_OVERRIDE = user_prompt_prefix
        if user_prompt_suffix is not None:
            cls._USER_PROMPT_SUFFIX_OVERRIDE = user_prompt_suffix

    @classmethod
    def clear_prompt_overrides(cls) -> None:
        """Clear all session-level prompt overrides."""
        cls._SYSTEM_TEMPLATE_OVERRIDE = None
        cls._USER_PROMPT_PREFIX_OVERRIDE = None
        cls._USER_PROMPT_SUFFIX_OVERRIDE = None
        cls._OPENING_KEY_OVERRIDE = None
        cls._PROMPT_MODE_OVERRIDE = "single"
        cls._COMMENTARY_PROFILE_OVERRIDE = "off"
        cls._COMMENTARY_INTENSITY_OVERRIDE = 5

    @classmethod
    def validate_system_template(cls, template: str) -> Tuple[bool, str]:
        """
        Validate a system template by formatting with sample values.
        Returns (ok, message).
        """
        report = cls.lint_system_template(template)
        if report["strict_errors"]:
            return False, "; ".join(report["strict_errors"])
        try:
            template.format(
                era="Romantic 1850s",
                theme="The Queen Sacrifice",
                white_player="Caissa White",
                black_player="Caissa Black",
                aggression_score=7,
                chaos_score=5,
                depth=40,
                climax_end=20,
                date="2026.01.01",
                era_guidelines="Guidelines",
                theme_instruction="Instruction",
                aggression_description="calculated but ambitious",
                conclusion_objective="Conclude clearly",
                expected_result="1-0",
            )
            return True, "Template is valid."
        except KeyError as exc:
            return False, f"Missing placeholder: {exc}"
        except Exception as exc:
            return False, f"Template error: {exc}"

    @classmethod
    def lint_system_template(cls, template: str) -> Dict[str, Any]:
        """
        Analyze a system template for strict errors and warnings.
        Strict errors are suitable for blocking apply in strict mode.
        """
        fields = set()
        for _, field_name, _, _ in Formatter().parse(template):
            if field_name:
                fields.add(field_name)

        missing = sorted(cls._SYSTEM_REQUIRED_FIELDS - fields)
        unknown = sorted(fields - (cls._SYSTEM_REQUIRED_FIELDS | {
            "climax_end", "date", "era_guidelines", "theme_instruction", "aggression_description"
        }))

        strict_errors: List[str] = []
        warnings: List[str] = []

        if missing:
            strict_errors.append(f"Missing required placeholders: {', '.join(missing)}")
        if unknown:
            warnings.append(f"Unknown placeholders: {', '.join(unknown)}")
        if len(template.strip()) < 400:
            warnings.append("Template is very short; quality may degrade.")
        if "LEGAL" not in template.upper():
            warnings.append("Legal-move constraint keyword not found (LEGAL).")
        if "PGN" not in template.upper():
            warnings.append("Output contract keyword not found (PGN).")
        if "expected_result" not in fields:
            warnings.append("No expected_result placeholder; terminal-result policy may be weakened.")
        upper_template = template.upper()
        if "DO NOT LEAVE IT AS '*'" not in upper_template and "NEVER OUTPUT '*'" not in upper_template:
            warnings.append("Terminal-result safety phrase not found.")
        if "ONLY USE STANDARD ALGEBRAIC NOTATION" not in upper_template:
            warnings.append("SAN constraint phrase not found.")
        if "DO NOT LEAVE IT AS '*'" in upper_template and "LEAVE IT AS '*'" in upper_template:
            warnings.append("Conflicting terminal-result instructions detected.")

        risk_findings: List[str] = []
        risk_score = 0
        if missing:
            risk_score += min(50, 10 * len(missing))
            risk_findings.append("Missing required placeholders")
        if unknown:
            risk_score += min(15, 3 * len(unknown))
            risk_findings.append("Unknown placeholders")
        if "Legal-move constraint keyword not found (LEGAL)." in warnings:
            risk_score += 14
            risk_findings.append("Missing legal constraint keyword")
        if "Output contract keyword not found (PGN)." in warnings:
            risk_score += 10
            risk_findings.append("Missing PGN output contract keyword")
        if "No expected_result placeholder; terminal-result policy may be weakened." in warnings:
            risk_score += 12
            risk_findings.append("Missing expected_result placeholder")
        if "Terminal-result safety phrase not found." in warnings:
            risk_score += 8
            risk_findings.append("Missing terminal-result safety phrase")
        if "SAN constraint phrase not found." in warnings:
            risk_score += 7
            risk_findings.append("Missing SAN constraint phrase")
        if "Conflicting terminal-result instructions detected." in warnings:
            risk_score += 18
            risk_findings.append("Conflicting terminal-result instructions")
        if "Template is very short; quality may degrade." in warnings:
            risk_score += 6
            risk_findings.append("Template is unusually short")
        risk_score = max(0, min(100, risk_score))
        risk_level = "low" if risk_score <= 24 else "medium" if risk_score <= 54 else "high"

        return {
            "fields": sorted(fields),
            "missing_required": missing,
            "unknown_fields": unknown,
            "strict_errors": strict_errors,
            "warnings": warnings,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_findings": risk_findings,
        }

    @classmethod
    def lint_template_with_mode(cls, template: str, mode: str) -> Dict[str, Any]:
        report = cls.lint_system_template(template)
        strict_errors = list(report["strict_errors"])
        warnings = list(report["warnings"])
        if mode == "single":
            if "expected_result" not in report["fields"]:
                strict_errors.append("single mode requires {expected_result}.")
        elif mode in ("match", "tournament"):
            if "expected_result" not in report["fields"]:
                warnings.append(f"{mode} mode: expected_result placeholder is recommended for clearer exports.")
        report["strict_errors"] = strict_errors
        report["warnings"] = warnings
        extra_risk = 0
        if mode == "single" and "expected_result" not in report["fields"]:
            extra_risk += 20
        if mode in ("match", "tournament") and "expected_result" not in report["fields"]:
            extra_risk += 6
        report["risk_score"] = max(0, min(100, int(report.get("risk_score", 0)) + extra_risk))
        report["risk_level"] = "low" if report["risk_score"] <= 24 else "medium" if report["risk_score"] <= 54 else "high"
        if extra_risk:
            findings = list(report.get("risk_findings", []))
            findings.append(f"Mode-adjusted risk for {mode} contract")
            report["risk_findings"] = findings
        return report

    @classmethod
    def simulate_prompt_context(
        cls,
        mode: str = "single",
        opening_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        from core.prompt_manager import GameContext, GameEra, PromptBias
        pm = cls()
        old_mode = cls._PROMPT_MODE_OVERRIDE
        old_opening = cls._OPENING_KEY_OVERRIDE
        try:
            cls.set_prompt_mode(mode)
            cls.set_opening_override(opening_key)
            sample = GameContext(
                era=GameEra.ROMANTIC,
                theme=None,
                white_player="Sim White",
                black_player="Sim Black",
                aggression_score=7,
                chaos_score=5,
                depth=40,
                bias=PromptBias.NEUTRAL,
            )
            system_prompt = pm.build_system_prompt(sample)
            user_prompt = pm.build_user_prompt(sample)
            return {
                "mode": mode,
                "opening_key": opening_key or "",
                "commentary_profile": cls._COMMENTARY_PROFILE_OVERRIDE,
                "commentary_intensity": cls._COMMENTARY_INTENSITY_OVERRIDE,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "system_chars": len(system_prompt),
                "user_chars": len(user_prompt),
                "token_estimate": (len(system_prompt) + len(user_prompt)) // 4,
                "compatibility": cls.compatibility_badges(system_prompt),
            }
        finally:
            cls._PROMPT_MODE_OVERRIDE = old_mode
            cls._OPENING_KEY_OVERRIDE = old_opening

    @classmethod
    def compatibility_badges(cls, template: str) -> Dict[str, bool]:
        report = cls.lint_system_template(template)
        warnings = set(report["warnings"])
        has_core_contract = (
            "Legal-move constraint keyword not found (LEGAL)." not in warnings
            and "Output contract keyword not found (PGN)." not in warnings
        )
        single_ok = (
            "expected_result" in report["fields"]
            and not report["strict_errors"]
            and has_core_contract
        )
        match_ok = has_core_contract and not report["strict_errors"]
        tournament_ok = has_core_contract and not report["strict_errors"]
        return {
            "single": single_ok,
            "match": match_ok,
            "tournament": tournament_ok,
        }

    @classmethod
    def save_prompt_profile(
        cls,
        profile_name: str,
        root: Optional[Path] = None,
        author: str = "unknown",
        version: str = "1.0.0",
        compatibility: Optional[Dict[str, bool]] = None,
    ) -> Path:
        """Save current prompt overrides to prompts/custom_profiles/<name>.json."""
        base = root or Path(__file__).parent.parent
        out_dir = base / "prompts" / "custom_profiles"
        out_dir.mkdir(parents=True, exist_ok=True)
        filepath = out_dir / f"{profile_name}.json"
        catalog = cls.get_prompt_catalog()
        payload = {
            "metadata": {
                "name": profile_name,
                "author": author,
                "version": version,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "compatibility": compatibility or cls.compatibility_badges(catalog["system_template"]),
                "checksum": cls._catalog_checksum(catalog),
            },
            "catalog": catalog,
        }
        filepath.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return filepath

    @classmethod
    def load_prompt_profile(cls, profile_name: str, root: Optional[Path] = None) -> Path:
        """Load prompt overrides from prompts/custom_profiles/<name>.json."""
        base = root or Path(__file__).parent.parent
        filepath = base / "prompts" / "custom_profiles" / f"{profile_name}.json"
        data = json.loads(filepath.read_text(encoding="utf-8"))
        catalog = data.get("catalog") if isinstance(data, dict) else None
        if not isinstance(catalog, dict):
            # Backward compatibility with old profile format.
            catalog = data
        cls.set_prompt_overrides(
            system_template=catalog.get("system_template"),
            user_prompt_prefix=catalog.get("user_prompt_prefix"),
            user_prompt_suffix=catalog.get("user_prompt_suffix"),
        )
        return filepath

    @classmethod
    def read_prompt_profile_metadata(cls, profile_name: str, root: Optional[Path] = None) -> Dict[str, Any]:
        base = root or Path(__file__).parent.parent
        filepath = base / "prompts" / "custom_profiles" / f"{profile_name}.json"
        data = json.loads(filepath.read_text(encoding="utf-8"))
        return data.get("metadata", {}) if isinstance(data, dict) else {}

    @classmethod
    def list_prompt_profiles(cls, root: Optional[Path] = None) -> List[str]:
        """List available prompt profile names."""
        base = root or Path(__file__).parent.parent
        pdir = base / "prompts" / "custom_profiles"
        if not pdir.exists():
            return []
        return sorted(p.stem for p in pdir.glob("*.json"))

    # =========================================================================
    # ORIGINAL METHODS (100% PRESERVED - IDENTICAL SIGNATURES)
    # =========================================================================

    def build_system_prompt(self, context: GameContext) -> str:
        """Build the system prompt for the LLM."""
        logger.info(
            "Building system prompt: era=%s, theme=%s, aggression=%d/10",
            context.era.value,
            context.theme.value if context.theme else "auto",
            context.aggression_score,
        )
        era_guidelines = self.ERA_GUIDELINES.get(
            context.era, self.ERA_GUIDELINES[GameEra.ROMANTIC]
        )
        
        # Compute theme instruction
        theme_instruction = context.theme.value if context.theme else "Execute your thematic concept here."
        
        # Compute aggression description
        if context.aggression_score >= 8:
            aggression_description = "extremely bold"
        elif context.aggression_score >= 6:
            aggression_description = "calculated but ambitious"
        else:
            aggression_description = "positional"

        # V3.3: Add bias-based conclusion + expected PGN result
        if context.bias == PromptBias.WHITE:
            conclusion_objective = "The game should end with White winning or Black making a brilliant defensive stand."
            expected_result = "1-0"
        elif context.bias == PromptBias.BLACK:
            conclusion_objective = "The game should end with Black winning or White making a brilliant defensive stand."
            expected_result = "0-1"
        elif context.bias == PromptBias.DRAW:
            conclusion_objective = "The game should end in a hard-fought draw — whether by repetition, perpetual check, stalemate, or agreed peace after equal play."
            expected_result = "1/2-1/2"
        elif context.bias == PromptBias.RANDOM:
            # Randomly assign a concrete result for variety
            expected_result = random.choice(["1-0", "0-1", "1/2-1/2"])
            if expected_result == "1-0":
                conclusion_objective = "The game should be a hard-fought battle that White narrowly wins."
            elif expected_result == "0-1":
                conclusion_objective = "The game should be a hard-fought battle that Black narrowly wins."
            else:
                conclusion_objective = "The game should be a hard-fought, evenly-matched battle ending in a draw."
        else:  # NEUTRAL — let the LLM decide
            expected_result = "1-0 | 0-1 | 1/2-1/2 (choose one; do not use *)"
            conclusion_objective = (
                "The outcome is entirely yours to decide. Choose the most dramatically "
                "satisfying ending — White wins (1-0), Black wins (0-1), or draw (1/2-1/2). "
                "You MUST pick a concrete result; do NOT leave it as '*'. "
                "Update the [Result] header in the PGN output to match your chosen conclusion."
            )

        active_system_template = self._SYSTEM_TEMPLATE_OVERRIDE or self.SYSTEM_TEMPLATE
        rendered = active_system_template.format(
            era=context.era.value,
            theme=context.theme.value if context.theme else "Your choice of brilliant concept",
            white_player=context.white_player,
            black_player=context.black_player,
            aggression_score=context.aggression_score,
            chaos_score=context.chaos_score,
            depth=context.depth,
            climax_end=context.depth // 2,
            date=datetime.now().strftime("%Y.%m.%d"),
            era_guidelines=era_guidelines,
            theme_instruction=theme_instruction,
            aggression_description=aggression_description,
            conclusion_objective=conclusion_objective,
            expected_result=expected_result,
        )
        mode_contract = self.get_mode_contract()
        if mode_contract:
            rendered += f"\n\n### MODE CONTRACT\n{mode_contract}\n"
        if self._OPENING_KEY_OVERRIDE:
            try:
                rendered += self.opening_injection_text(self._OPENING_KEY_OVERRIDE)
            except Exception:
                logger.warning("Failed to inject opening pack for key=%s", self._OPENING_KEY_OVERRIDE)
        rendered += self.commentary_injection_text()
        return rendered

    def build_user_prompt(self, context: GameContext) -> str:
        """Build the user prompt (final trigger) for the LLM."""
        logger.info(
            "Building user prompt: depth=%d, white=%s, black=%s",
            context.depth, context.white_player, context.black_player,
        )
        
        # V3.4: Add bias-based outcome
        if context.bias == PromptBias.WHITE:
            outcome_text = "White should win decisively or achieve a significant advantage."
        elif context.bias == PromptBias.BLACK:
            outcome_text = "Black should win decisively or achieve a significant advantage."
        elif context.bias == PromptBias.DRAW:
            outcome_text = "The game should end in a draw after a tense, evenly-matched battle."
        elif context.bias == PromptBias.RANDOM:
            pick = random.choice(["1-0", "0-1", "1/2-1/2"])
            if pick == "1-0":
                outcome_text = "White should narrowly win after a hard-fought battle."
            elif pick == "0-1":
                outcome_text = "Black should narrowly win after a hard-fought battle."
            else:
                outcome_text = "The game should be an evenly-matched battle ending in a draw."
        else:  # NEUTRAL — let the LLM decide
            outcome_text = (
                "You decide the result. Choose whichever concrete outcome — White wins (1-0), "
                "Black wins (0-1), or draw (1/2-1/2) — makes the most dramatically "
                "satisfying conclusion for this game. Do NOT leave the result as '*'."
            )

        user_prompt = f"""
Generate a {context.depth} half-move chess game with the following specifications:

**Theme**: {context.theme.value if context.theme else "Brilliant and original"}
**Era**: {context.era.value}
**Style**: Aggression={context.aggression_score}/10, Chaos={context.chaos_score}/10
**White Player**: {context.white_player}
**Black Player**: {context.black_player}

**Expected Outcome**: {outcome_text}

Now, thinking step-by-step through the Concept → Spark → Climax → Conclusion framework, 
generate the complete PGN game:
"""
        prefix = self._USER_PROMPT_PREFIX_OVERRIDE or ""
        suffix = self._USER_PROMPT_SUFFIX_OVERRIDE or ""
        merged = f"{prefix}\n{user_prompt.strip()}\n{suffix}".strip()
        return merged

    # =========================================================================
    # PHASE 3.1: ADVANCED PROMPT GENERATION METHODS
    # =========================================================================

    def build_system_prompt_advanced(self, context: AdvancedGameContext) -> str:
        """
        Build enhanced system prompt with personality injection and narrative templates.
        
        Args:
            context: AdvancedGameContext with extended configuration
            
        Returns:
            Complete system prompt string
        """
        # Start with base prompt
        base_prompt = self.build_system_prompt(context)
        
        # Add personality injections
        personality_section = ""
        if context.white_personality:
            personality_section += f"\n\n### WHITE PLAYER PERSONALITY\n"
            personality_section += context.white_personality.to_prompt_injection()
        
        if context.black_personality:
            personality_section += f"\n\n### BLACK PLAYER PERSONALITY\n"
            personality_section += context.black_personality.to_prompt_injection()
        
        # Add narrative arc if specified
        narrative_section = ""
        if context.narrative_arc and context.narrative_arc in self.NARRATIVE_TEMPLATES:
            template = self.NARRATIVE_TEMPLATES[context.narrative_arc]
            narrative_section = f"\n\n{template.to_prompt_section()}"
        
        # Add difficulty guidelines
        difficulty_section = ""
        if context.difficulty in self.DIFFICULTY_GUIDELINES:
            difficulty_section = f"\n\n{self.DIFFICULTY_GUIDELINES[context.difficulty]}"
        
        # Add custom constraints
        constraints_section = ""
        if context.custom_constraints:
            constraints_section = "\n\n### CUSTOM CONSTRAINTS\n"
            for i, constraint in enumerate(context.custom_constraints, 1):
                constraints_section += f"{i}. {constraint}\n"
        
        # Add beauty target
        beauty_section = f"\n\n### BEAUTY TARGET\nAim for a beauty score of {context.target_beauty_score}/100 or higher."
        
        # Combine all sections
        full_prompt = base_prompt + personality_section + narrative_section + difficulty_section + constraints_section + beauty_section
        
        logger.debug(f"Built advanced prompt with {len(full_prompt)} characters")
        return full_prompt

    def build_user_prompt_advanced(self, context: AdvancedGameContext) -> str:
        """
        Build enhanced user prompt with advanced requirements.
        
        Args:
            context: AdvancedGameContext with extended configuration
            
        Returns:
            User prompt string
        """
        base_prompt = self.build_user_prompt(context)
        
        additions = []
        
        if context.narrative_arc:
            additions.append(f"**Narrative Arc**: {context.narrative_arc.value}")
        
        if context.opening_eco:
            additions.append(f"**Required Opening ECO**: {context.opening_eco}")
        
        if context.endgame_type:
            additions.append(f"**Target Endgame**: {context.endgame_type}")
        
        if context.include_annotations:
            additions.append("**Include annotations** (!, !!, ?, ??)")
        
        if context.include_commentary:
            additions.append("**Include brief commentary** in {curly braces}")
        
        if additions:
            return base_prompt + "\n\n" + "\n".join(additions)
        
        return base_prompt

    def get_personality(self, player: HistoricalPlayer) -> PlayerPersonality:
        """
        Get personality profile for a historical player.
        
        Args:
            player: HistoricalPlayer enum
            
        Returns:
            PlayerPersonality dataclass
        """
        return self.PLAYER_PERSONALITIES.get(
            player,
            PlayerPersonality(
                player=player,
                style_description="Unknown historical player",
                aggression_baseline=5,
                risk_tolerance=5,
            )
        )

    def get_narrative_template(self, arc: NarrativeArc) -> NarrativeTemplate:
        """
        Get narrative template for a story arc.
        
        Args:
            arc: NarrativeArc enum
            
        Returns:
            NarrativeTemplate dataclass
        """
        return self.NARRATIVE_TEMPLATES.get(
            arc,
            NarrativeTemplate(
                arc=arc,
                phases=["Opening", "Middlegame", "Endgame"],
                key_moments=["Critical moment"],
                emotional_trajectory="Standard game progression",
                typical_length=40,
            )
        )

    def build_multi_stage_prompts(self, context: AdvancedGameContext) -> List[StagePrompt]:
        """
        Generate multi-stage prompts for iterative game generation.
        
        This approach generates games in stages:
        1. Concept: Define the game narrative and key moments
        2. Opening: Generate opening moves (1-10)
        3. Development: Continue to middlegame (11-25)
        4. Tactical: Execute the main tactical theme (26-35)
        5. Conclusion: Finish the game (35+)
        
        Args:
            context: AdvancedGameContext with configuration
            
        Returns:
            List of StagePrompt objects for sequential execution
        """
        stages = []
        
        # Stage 1: Concept
        concept_system = """You are a chess game architect. Your task is to design the narrative arc 
of a chess game before any moves are made. Think like a storyteller.

Output a JSON object with:
- "narrative_summary": 2-3 sentence description of the game
- "key_moments": list of 3-5 critical positions/moves
- "opening_choice": recommended opening for this narrative
- "sacrifice_plan": any planned sacrifices and when
- "ending_type": how the game ends (mate pattern, resignation trigger)
"""
        concept_user = f"""Design a {context.narrative_arc.value if context.narrative_arc else 'dramatic'} 
chess game with these parameters:
- Era: {context.era.value}
- Theme: {context.theme.value if context.theme else 'Original brilliancy'}
- White personality: {context.white_personality.player.value if context.white_personality else 'Classical'}
- Black personality: {context.black_personality.player.value if context.black_personality else 'Solid'}
- Target length: {context.depth} half-moves

Output the game design as JSON."""
        
        stages.append(StagePrompt(
            stage=PromptStage.CONCEPT,
            system_prompt=concept_system,
            user_prompt=concept_user,
            expected_output_format="JSON",
            temperature=0.8,
            max_tokens=500,
        ))
        
        # Stage 2: Opening
        opening_system = """You are generating the opening phase (moves 1-10) of a chess game.
You will receive a game concept and must generate sound opening moves that set up the planned narrative.
Output ONLY the moves in PGN format, numbered: 1. e4 e5 2. Nf3 Nc6 ..."""
        
        opening_user = f"""Based on the game concept, generate moves 1-10.
Era: {context.era.value}
Opening style: {self.ERA_GUIDELINES.get(context.era, '')}

Generate the opening moves in PGN format (1. e4 e5 2. ...)"""
        
        stages.append(StagePrompt(
            stage=PromptStage.OPENING,
            system_prompt=opening_system,
            user_prompt=opening_user,
            expected_output_format="PGN",
            temperature=0.4,  # Lower temp for sound openings
            max_tokens=300,
        ))
        
        # Stage 3: Development (Middlegame)
        development_system = """You are continuing a chess game into the middlegame (moves 11-25).
You have the opening moves. Continue the game following the planned narrative.
The position should become increasingly tense, building to the climax.
Output ONLY the continuation moves in PGN format."""
        
        development_user = f"""Continue from move 11 to approximately move 25.
Build toward the planned climax.
Theme: {context.theme.value if context.theme else 'Brilliant concept'}
Aggression: {context.aggression_score}/10

Continue the game in PGN format."""
        
        stages.append(StagePrompt(
            stage=PromptStage.DEVELOPMENT,
            system_prompt=development_system,
            user_prompt=development_user,
            expected_output_format="PGN",
            temperature=0.6,
            max_tokens=600,
        ))
        
        # Stage 4: Tactical Climax
        tactical_system = """You are executing the tactical climax of a chess game.
This is where the brilliancy happens - sacrifices, combinations, forcing sequences.
The moves must be LEGAL and SOUND. Every sacrifice must have concrete compensation.
Output ONLY the climax moves in PGN format with annotations (!!, !, etc.)."""
        
        tactical_user = f"""Execute the tactical climax starting from the current position.
Theme to execute: {context.theme.value if context.theme else 'Stunning combination'}
This should be the most beautiful part of the game.
Use annotations for brilliant moves (!!).

Continue the game to the decisive moment."""
        
        stages.append(StagePrompt(
            stage=PromptStage.TACTICAL,
            system_prompt=tactical_system,
            user_prompt=tactical_user,
            expected_output_format="PGN",
            temperature=0.7,
            max_tokens=400,
        ))
        
        # Stage 5: Conclusion
        conclusion_system = """You are concluding a chess game after the tactical climax.
Bring the game to a definitive end - checkmate, resignation, or clear technical win.
Make sure the conclusion is aesthetically satisfying.
Output the final moves with the result (1-0, 0-1, or 1/2-1/2)."""
        
        conclusion_user = f"""Conclude the game with a satisfying ending.
Expected result: {'1-0 (White wins)' if context.bias == PromptBias.WHITE else '0-1 (Black wins)' if context.bias == PromptBias.BLACK else 'Any decisive result'}

Finish the game beautifully."""
        
        stages.append(StagePrompt(
            stage=PromptStage.CONCLUSION,
            system_prompt=conclusion_system,
            user_prompt=conclusion_user,
            expected_output_format="PGN",
            temperature=0.5,
            max_tokens=200,
        ))
        
        return stages

    def build_commentary_prompt(
        self,
        pgn: str,
        style: str = "modern",
        depth: str = "detailed"
    ) -> Tuple[str, str]:
        """
        Build prompts for generating GM-level commentary on a game.
        
        Args:
            pgn: The complete game in PGN format
            style: Commentary style ("modern", "classical", "casual", "educational")
            depth: Detail level ("brief", "moderate", "detailed", "analysis")
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        style_instructions = {
            "modern": "Use modern analytical language. Reference engine evaluations when relevant.",
            "classical": "Write like a 1920s chess columnist. Flowery prose, dramatic descriptions.",
            "casual": "Friendly, accessible commentary for club players. Avoid jargon.",
            "educational": "Focus on teaching. Explain why moves are good or bad. Highlight patterns.",
        }
        
        depth_instructions = {
            "brief": "One sentence per critical moment. 100-200 words total.",
            "moderate": "2-3 sentences for key positions. 300-500 words total.",
            "detailed": "Analyze all important moments. 500-800 words total.",
            "analysis": "Full analytical treatment. Variations, alternatives, deep explanations. 1000+ words.",
        }
        
        system_prompt = f"""You are a Grandmaster-level chess commentator.
Your task is to write engaging, insightful commentary on chess games.

Style: {style_instructions.get(style, style_instructions['modern'])}
Depth: {depth_instructions.get(depth, depth_instructions['moderate'])}

Guidelines:
- Focus on the most critical moments
- Explain the strategic themes
- Highlight brilliant moves and missed opportunities
- Use proper chess terminology
- Reference similar historical games when relevant
- Make the commentary engaging and educational
"""
        
        user_prompt = f"""Write commentary for this chess game:

{pgn}

Provide {depth} commentary in {style} style. Focus on:
1. Opening choice and its implications
2. The critical middlegame moments
3. Any tactical highlights or brilliant moves
4. The decisive factor in the game's outcome
"""
        
        return system_prompt, user_prompt

    def build_refinement_prompt(
        self,
        pgn: str,
        issues: List[str],
        context: GameContext
    ) -> Tuple[str, str]:
        """
        Build prompts for refining a generated game that has issues.
        
        Args:
            pgn: The problematic PGN
            issues: List of identified issues
            context: Original GameContext
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = """You are a chess game editor and debugger.
You will receive a chess game with identified issues. Your task is to fix these issues
while preserving the original spirit and narrative of the game.

Rules:
1. ONLY fix the identified issues
2. Keep as much of the original game as possible
3. Ensure all moves are LEGAL
4. Maintain the aesthetic quality
5. Output the corrected PGN only
"""
        
        issues_text = "\n".join(f"- {issue}" for issue in issues)
        
        user_prompt = f"""This game has the following issues:
{issues_text}

Original intended parameters:
- Era: {context.era.value}
- Theme: {context.theme.value if context.theme else 'None'}
- Target length: {context.depth} half-moves

Problematic PGN:
{pgn}

Please provide the corrected PGN that fixes these issues while preserving the game's character.
"""
        
        return system_prompt, user_prompt

    def get_era_for_player(self, player: HistoricalPlayer) -> GameEra:
        """
        Get the appropriate era for a historical player.
        
        Args:
            player: HistoricalPlayer enum
            
        Returns:
            Matching GameEra
        """
        era_mapping = {
            HistoricalPlayer.MORPHY: GameEra.ROMANTIC,
            HistoricalPlayer.ANDERSSEN: GameEra.ROMANTIC,
            HistoricalPlayer.STEINITZ: GameEra.CLASSICAL,
            HistoricalPlayer.LASKER: GameEra.CLASSICAL,
            HistoricalPlayer.CAPABLANCA: GameEra.CLASSICAL,
            HistoricalPlayer.ALEKHINE: GameEra.HYPERMODERN,
            HistoricalPlayer.BOTVINNIK: GameEra.SOVIET,
            HistoricalPlayer.TAL: GameEra.SOVIET,
            HistoricalPlayer.PETROSIAN: GameEra.SOVIET,
            HistoricalPlayer.SPASSKY: GameEra.SOVIET,
            HistoricalPlayer.FISCHER: GameEra.COMPUTER,
            HistoricalPlayer.KARPOV: GameEra.COMPUTER,
            HistoricalPlayer.KASPAROV: GameEra.COMPUTER,
            HistoricalPlayer.CARLSEN: GameEra.NEURAL,
            HistoricalPlayer.ALPHA_ZERO: GameEra.NEURAL,
        }
        return era_mapping.get(player, GameEra.CLASSICAL)

    def create_context_for_matchup(
        self,
        white_player: HistoricalPlayer,
        black_player: HistoricalPlayer,
        theme: Optional[GameTheme] = None,
        narrative: Optional[NarrativeArc] = None,
    ) -> AdvancedGameContext:
        """
        Create an AdvancedGameContext for a historical matchup.
        
        Args:
            white_player: Historical player for White
            black_player: Historical player for Black
            theme: Optional theme override
            narrative: Optional narrative arc override
            
        Returns:
            Configured AdvancedGameContext
        """
        white_personality = self.get_personality(white_player)
        black_personality = self.get_personality(black_player)
        
        # Use white player's era
        era = self.get_era_for_player(white_player)
        
        # Average aggression/chaos from personalities
        aggression = (white_personality.aggression_baseline + black_personality.aggression_baseline) // 2
        chaos = (white_personality.risk_tolerance + black_personality.risk_tolerance) // 2
        
        return AdvancedGameContext(
            era=era,
            theme=theme,
            white_player=white_player.value,
            black_player=black_player.value,
            aggression_score=aggression,
            chaos_score=chaos,
            depth=45,  # Default length
            white_personality=white_personality,
            black_personality=black_personality,
            narrative_arc=narrative,
        )


# Example usage
if __name__ == "__main__":
    context = GameContext(
        era=GameEra.ROMANTIC,
        theme=GameTheme.QUEEN_SACRIFICE,
        white_player="Caissa the Bold",
        black_player="Caissa the Sage",
        aggression_score=8,
        chaos_score=6,
        depth=40,
    )

    manager = PromptManager()
    
    print("=" * 80)
    print("SYSTEM PROMPT:")
    print("=" * 80)
    print(manager.build_system_prompt(context))
    
    print("\n" + "=" * 80)
    print("USER PROMPT:")
    print("=" * 80)
    print(manager.build_user_prompt(context))
    
    # PHASE 3.1: Advanced example
    print("\n" + "=" * 80)
    print("ADVANCED MATCHUP: TAL vs PETROSIAN")
    print("=" * 80)
    
    advanced_context = manager.create_context_for_matchup(
        white_player=HistoricalPlayer.TAL,
        black_player=HistoricalPlayer.PETROSIAN,
        theme=GameTheme.ROOK_SACRIFICE,
        narrative=NarrativeArc.BRILLIANCY,
    )
    
    print(f"Era: {advanced_context.era.value}")
    print(f"Aggression: {advanced_context.aggression_score}")
    print(f"Chaos: {advanced_context.chaos_score}")
    print("\nWhite personality injection:")
    print(advanced_context.white_personality.to_prompt_injection() if advanced_context.white_personality else "None")
