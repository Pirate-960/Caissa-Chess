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

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Literal, List, Dict, Callable, Tuple
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
    force_win: bool = True  # Does White need to win?


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
            "force_win": self.force_win,
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
   - The game should end with White winning or Black making a brilliant defensive stand.

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
[Result "1-0"]
[Annotator "Caissa"]

1. e4 e5 2. Nf3 Nc6 3. Bb5! ...

[Your complete game here in PGN format]
```

### STRATEGIC GUIDELINES BY ERA
{era_guidelines}

### FINAL INSTRUCTION
Generate now. Think deeply. Make every move count. The chessboard awaits your masterpiece.
"""

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

    # =========================================================================
    # ORIGINAL METHODS (100% PRESERVED - IDENTICAL SIGNATURES)
    # =========================================================================

    def build_system_prompt(self, context: GameContext) -> str:
        """Build the system prompt for the LLM."""
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
        
        return self.SYSTEM_TEMPLATE.format(
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
        )

    def build_user_prompt(self, context: GameContext) -> str:
        """Build the user prompt (final trigger) for the LLM."""
        user_prompt = f"""
Generate a {context.depth} half-move chess game with the following specifications:

**Theme**: {context.theme.value if context.theme else "Brilliant and original"}
**Era**: {context.era.value}
**Style**: Aggression={context.aggression_score}/10, Chaos={context.chaos_score}/10
**White Player**: {context.white_player}
**Black Player**: {context.black_player}

**Expected Outcome**: White should {'win decisively' if context.force_win else 'achieve a decisive advantage or draw'}.

Now, thinking step-by-step through the Concept → Spark → Climax → Conclusion framework, 
generate the complete PGN game:
"""
        return user_prompt.strip()

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
Expected result: {'1-0 (White wins)' if context.force_win else 'Any decisive result'}

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
