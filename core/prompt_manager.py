"""
core/prompt_manager.py

Dynamically assembles prompts for the LLM based on game style, era, theme, and constraints.
This is the "creative director" that tells the LLM what kind of masterpiece to dream up.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Literal
from enum import Enum


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


class PromptManager:
    """
    Constructs the system and user prompts for the LLM.
    Implements Chain-of-Thought (CoT) reasoning for move generation.
    """

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

    def __init__(self):
        pass

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
