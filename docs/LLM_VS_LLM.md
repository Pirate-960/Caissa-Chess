# LLM vs LLM Tournament System

> **v0.5.0 Feature** | Part of CAISSA Chess AI System  
> **Status**: 🔵 In Development (April 2026)

---

## Overview

The LLM vs LLM Tournament System transforms CAISSA from a single-LLM game generator into a **multi-agent competitive chess arena**. Different AI models compete against each other in organized tournaments, with optional live commentary from a third AI.

### Key Features

| Feature | Description |
|---------|-------------|
| **Multi-Provider Competition** | GPT-4, Claude, Gemini, Ollama, and more competing head-to-head |
| **Tournament Formats** | Round-robin, Swiss, knockout, arena, and match series |
| **ELO Rating System** | Track LLM chess strength over time |
| **Live Commentary** | Third LLM provides real-time game analysis |
| **Style Personas** | Each LLM can adopt a GM's playing style |
| **Analytics Dashboard** | Performance metrics, style fingerprints, provider insights |

---

## Quick Start

### Single Match

```bash
# GPT-4 (White) vs Claude 3.5 (Black)
caissa match --white openai:gpt-4 --black anthropic:claude-3.5

# With specific time control
caissa match --white openai:gpt-4 --black google:gemini-pro --time rapid

# With live commentary
caissa match --white gpt-4 --black claude --commentary anthropic:claude-3-opus
```

### Best-of Series

```bash
# Best of 5 match
caissa match --white openai:gpt-4 --black google:gemini-pro --series 5

# Best of 7 with alternating colors
caissa match --white claude --black gpt-4 --series 7 --alternate-colors
```

### Full Tournament

```bash
# Round-robin tournament
caissa tournament --format round-robin \
    --players openai:gpt-4,anthropic:claude-3.5,google:gemini-pro,ollama:llama3

# Swiss tournament (8 rounds)
caissa tournament --format swiss --rounds 8 --players-file players.yaml

# Output to specific directory
caissa tournament --format round-robin --players gpt-4,claude,gemini \
    --output tournaments/april-2026
```

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CAISSA TOURNAMENT ENGINE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │
│  │ WHITE LLM   │    │ BLACK LLM   │    │   ARBITER / COMMENTATOR │ │
│  │ (Player 1)  │◄──►│ (Player 2)  │◄──►│   (Optional Third LLM)  │ │
│  └──────┬──────┘    └──────┬──────┘    └───────────┬─────────────┘ │
│         │                  │                       │               │
│         ▼                  ▼                       ▼               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    MATCH ENGINE                              │   │
│  │  • Move prompting & parsing    • Time control enforcement   │   │
│  │  • Illegal move handling       • Game termination           │   │
│  │  • Position state management   • Result determination       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                     │
│                              ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                 TOURNAMENT ORCHESTRATOR                      │   │
│  │  • Pairing algorithms    • ELO calculation   • Standings    │   │
│  │  • Format management     • Round scheduling  • Tiebreaks    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                     │
│                              ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   ANALYTICS & EXPORT                         │   │
│  │  • PGN/HTML/JSON/MD     • Beauty scoring    • Style analysis│   │
│  │  • Performance metrics   • Provider insights • Commentary   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Integration with Existing Components

The tournament system builds on CAISSA's existing infrastructure:

| Existing Component | Tournament Usage |
|--------------------|------------------|
| `core/llm_provider.py` | All tournament players use existing provider implementations |
| `core/prompt_manager.py` | Move prompts incorporate era/style system |
| `aesthetic/beauty_eval.py` | Games scored for beauty |
| `engine/stockfish_client.py` | Position evaluation for commentary |
| `export/` | Tournament results exported in all formats |

> **Note**: All existing functionality is preserved. The tournament system is purely additive.

---

## Tournament Formats

### Single Match

A standard chess game between two LLMs.

```python
from core.match_engine import MatchEngine
from core.llm_provider import OpenAIProvider, AnthropicProvider

white = TournamentPlayer("GPT-4", OpenAIProvider())
black = TournamentPlayer("Claude", AnthropicProvider())

engine = MatchEngine(white, black, time_control=TimeControl.RAPID)
result = await engine.play_match()
```

### Match Series (Best-of-N)

Multiple games, alternating colors, first to (N+1)/2 wins.

```yaml
format: match_series
games: 5  # Best of 5
alternate_colors: true
```

### Round-Robin

Every player faces every other player. Optionally double round-robin (each pairing twice with colors swapped).

```bash
# 4 players = 6 games (single) or 12 games (double)
caissa tournament --format round-robin --players gpt4,claude,gemini,llama
caissa tournament --format double-round-robin --players gpt4,claude,gemini,llama
```

### Swiss System

Pairing based on current standings. Players with similar scores face each other.

```bash
# 8 rounds, Swiss pairing
caissa tournament --format swiss --rounds 8 --players-file players.yaml
```

### Knockout (Elimination)

Single or double elimination bracket.

```bash
# Single elimination
caissa tournament --format knockout --players gpt4,claude,gemini,llama,mistral,opus,o1,sonnet

# Double elimination (second chance)
caissa tournament --format double-elim --players gpt4,claude,gemini,llama
```

### Arena Mode

Continuous rapid games within a time window. Good for quick benchmarking.

```bash
# 30 minutes of bullet games
caissa arena --players gpt4,claude --duration 30m --time bullet
```

---

## Time Controls

| Name | Seconds per Move | Use Case |
|------|------------------|----------|
| `bullet` | 5 | Quick benchmarks, stress testing |
| `blitz` | 15 | Fast tournaments |
| `rapid` | 30 | **Default** - balanced play |
| `classical` | 60 | Deep analysis games |
| `correspondence` | No limit | Async tournaments |
| `unlimited` | No limit | Single analysis games |

```bash
caissa match --white gpt4 --black claude --time classical
```

### Timeout Fallback Toggle (New)

You can globally control whether timed-out LLM moves use heuristic fallback or keep strict timeout-forfeit behavior.

```yaml
tournament:
  match:
    timeout_fallback_enabled: true
    timeout_fallback_max_consecutive: 3
    timeout_fallback_cooldown_moves: 2
    include_time_control_in_prompt: true
```

- `true`: on timeout, engine picks a legal heuristic move and continues.
- `false`: preserves strict behavior (timeouts can lead to forfeit after retries).
- `timeout_fallback_max_consecutive`: consecutive timeout-fallbacks before cooldown starts.
- `timeout_fallback_cooldown_moves`: turns to skip LLM calls (heuristics only) once cooldown triggers.
- `include_time_control_in_prompt`: inject selected time control into move prompt to encourage concise responses.

> **Compatibility note:** This is additive. Existing tournament/match behavior is preserved when you keep the default.

---

## Player Configuration

### CLI Shortcuts

```bash
# Provider:model syntax
--white openai:gpt-4-turbo
--black anthropic:claude-3-5-sonnet
--white google:gemini-1.5-pro
--black ollama:llama3:70b

# Short aliases (uses default model)
--white openai    # Uses default OpenAI model
--black anthropic # Uses default Anthropic model
```

### YAML Configuration

For complex tournaments, use a configuration file:

```yaml
# tournament.yaml
tournament:
  name: "April 2026 LLM Chess Championship"
  format: double_round_robin
  time_control: rapid
  
  players:
    - name: "GPT-4 Turbo"
      provider: openai
      model: gpt-4-turbo
      persona: "Play aggressive, tactical chess like Mikhail Tal"
      temperature: 0.8
      elo: 1600  # Starting ELO
      
    - name: "Claude 3.5 Sonnet"
      provider: anthropic
      model: claude-3-5-sonnet
      persona: "Play solid, positional chess like Anatoly Karpov"
      temperature: 0.6
      elo: 1550
      
    - name: "Gemini Pro"
      provider: google
      model: gemini-1.5-pro
      persona: "Play dynamic chess like Magnus Carlsen"
      temperature: 0.7
      elo: 1500
      
    - name: "Local Llama 3"
      provider: ollama
      model: llama3:70b
      persona: "Play creative, experimental chess"
      temperature: 0.9
      elo: 1400

  commentary:
    enabled: true
    provider: anthropic
    model: claude-3-opus
    style: dramatic  # gm, fun, drama, teach, roast
    
  output:
    directory: tournaments/april-2026
    formats: [pgn, html, json, markdown]
```

```bash
caissa tournament --config tournament.yaml
```

### Style Personas

Each player can adopt a playing style:

| Persona | Description |
|---------|-------------|
| Tal | Aggressive, sacrificial, tactical fireworks |
| Karpov | Prophylactic, positional squeeze |
| Capablanca | Technical precision, simple clarity |
| Fischer | Perfectionist, concrete, no-nonsense |
| Kasparov | Dynamic, energetic, fighting spirit |
| Carlsen | Universal, grinding, never gives up |
| Morphy | Classical attacking, open games |
| AlphaZero | Alien logic, unconventional ideas |

```yaml
persona: "Play aggressive, sacrificial chess in the style of Mikhail Tal"
```

---

## Live Commentary

A third LLM can watch the game and provide real-time commentary.

### Commentary Styles

| Style | Description |
|-------|-------------|
| `gm` | Technical grandmaster analysis |
| `fun` | Casual, accessible commentary |
| `drama` | High tension, storytelling |
| `teach` | Educational, explains concepts |
| `roast` | Humorous criticism (for fun!) |

### Usage

```bash
# Add commentary to any match
caissa match --white gpt4 --black claude --commentary anthropic:claude-3-opus

# Specify style
caissa match --white gpt4 --black claude --commentary gemini --commentary-style drama
```

### Example Commentary Output

```
Move 15: Nxf7!!

COMMENTATOR (dramatic):
"And there it is! GPT-4 has unleashed the devastating knight sacrifice 
on f7! The silicon mind channels the ghost of Mikhail Tal himself. 
Claude's king is about to embark on an unwilling journey across the 
board. This is the kind of move that separates the neural networks 
from the mere statistical models!"
```

---

## ELO Rating System

The tournament tracks ELO ratings using the standard FIDE formula.

### Initial Ratings

| Provider | Default Starting ELO |
|----------|---------------------|
| GPT-4 (latest) | 1600 |
| Claude 3.5 Sonnet | 1550 |
| Gemini Pro | 1500 |
| GPT-3.5 | 1400 |
| Local models | 1300 |

### Calculation

```
K-factor: 32 (for active tournament play)

Expected Score = 1 / (1 + 10^((Opponent_ELO - Player_ELO) / 400))

ELO Change = K × (Actual Score - Expected Score)
```

### Tracking

```bash
# View current ratings
caissa elo --list

# Rating history for a player
caissa elo --history "GPT-4 Turbo"

# Reset ratings
caissa elo --reset
```

---

## Output & Reports

### Tournament Results

After a tournament, outputs are saved to the specified directory:

```
tournaments/april-2026/
├── tournament.json           # Full machine-readable results
├── standings.md              # Human-readable standings
├── report.html               # Interactive HTML report
│
├── games/
│   ├── R1_GPT4_vs_Claude.pgn
│   ├── R1_Gemini_vs_Llama.pgn
│   ├── R2_Claude_vs_Gemini.pgn
│   └── ...
│
├── commentary/
│   ├── R1_GPT4_vs_Claude.txt
│   └── ...
│
└── analytics/
    ├── style_analysis.json
    ├── provider_metrics.json
    └── elo_progression.png
```

### Standings Table

```
╔════╦════════════════════╦═════╦═════╦═════╦═════╦═══════╦════════╗
║ #  ║ Player             ║  W  ║  D  ║  L  ║ Pts ║  ELO  ║ Change ║
╠════╬════════════════════╬═════╬═════╬═════╬═════╬═══════╬════════╣
║ 1  ║ GPT-4 Turbo        ║  5  ║  1  ║  0  ║ 5.5 ║ 1687  ║  +87   ║
║ 2  ║ Claude 3.5 Sonnet  ║  4  ║  0  ║  2  ║ 4.0 ║ 1578  ║  +28   ║
║ 3  ║ Gemini Pro         ║  2  ║  1  ║  3  ║ 2.5 ║ 1489  ║  -11   ║
║ 4  ║ Local Llama 3      ║  0  ║  0  ║  6  ║ 0.0 ║ 1296  ║ -104   ║
╚════╩════════════════════╩═════╩═════╩═════╩═════╩═══════╩════════╝
```

### Analytics Insights

The system tracks provider-specific metrics:

| Metric | Description |
|--------|-------------|
| Illegal Move Rate | % of moves requiring retry (instruction following) |
| Avg Centipawn Loss | Average positional accuracy |
| Move Time | Average seconds per move |
| Style Fingerprint | Detected playing style characteristics |
| Resignation Threshold | When the LLM typically gives up |

---

## Illegal Move Handling

When an LLM produces an illegal move, the system:

1. **Attempt 1**: Inform the LLM of the error with context
2. **Attempt 2**: Simplify the prompt, show legal moves
3. **Attempt 3**: Final warning with explicit legal move list
4. **Forfeit**: After 3 failures, the game is forfeited

### Error Prompt Example

```
Your move "Qxa8" is illegal in the current position.

Reason: The queen on d4 is pinned to the king by the rook on d1.

Legal moves available: Kf1, Kf2, Kg2, Be2, Nf3, Qd2, Qd3, Rd2

Please provide a valid move.
```

### Tracking

Illegal move statistics are recorded per provider for analysis.

---

## Programmatic API

### Single Match

```python
import asyncio
from core.match_engine import MatchEngine, TournamentPlayer, TimeControl
from core.llm_provider import OpenAIProvider, AnthropicProvider

async def play_match():
    white = TournamentPlayer(
        name="GPT-4 Turbo",
        provider=OpenAIProvider(model="gpt-4-turbo"),
        style_persona="Play tactical chess like Mikhail Tal"
    )
    
    black = TournamentPlayer(
        name="Claude 3.5",
        provider=AnthropicProvider(model="claude-3-5-sonnet"),
        style_persona="Play positional chess like Anatoly Karpov"
    )
    
    engine = MatchEngine(white, black, time_control=TimeControl.RAPID)
    result = await engine.play_match()
    
    print(f"Result: {result.result}")
    print(f"Moves: {len(result.moves)}")
    print(f"Beauty Score: {result.beauty_score:.1f}")
    print(f"PGN:\n{result.pgn}")

asyncio.run(play_match())
```

### Full Tournament

```python
from core.tournament import Tournament, TournamentConfig, TournamentFormat
from core.match_engine import TournamentPlayer, TimeControl
from core.llm_provider import OpenAIProvider, AnthropicProvider, GoogleGeminiProvider

async def run_tournament():
    players = [
        TournamentPlayer("GPT-4", OpenAIProvider()),
        TournamentPlayer("Claude", AnthropicProvider()),
        TournamentPlayer("Gemini", GoogleGeminiProvider()),
    ]
    
    config = TournamentConfig(
        name="Q2 2026 Championship",
        format=TournamentFormat.ROUND_ROBIN,
        players=players,
        time_control=TimeControl.RAPID,
        use_commentary=True,
    )
    
    tournament = Tournament(config)
    result = await tournament.run()
    
    # Print standings
    for standing in result.standings:
        print(f"{standing.rank}. {standing.player.name}: {standing.points} pts")
    
    # Save results
    result.export("tournaments/q2-2026")

asyncio.run(run_tournament())
```

---

## Configuration Reference

### Environment Variables

```bash
# Provider API keys (required for respective providers)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=...

# Tournament defaults
CAISSA_DEFAULT_TIME_CONTROL=rapid
CAISSA_DEFAULT_TOURNAMENT_FORMAT=round_robin
CAISSA_TOURNAMENT_OUTPUT_DIR=tournaments
```

### Full YAML Schema

```yaml
tournament:
  # Required
  name: string                    # Tournament name
  format: string                  # round_robin, swiss, knockout, etc.
  players: list                   # Player definitions
  
  # Optional (with defaults)
  time_control: rapid             # bullet, blitz, rapid, classical
  rounds: 1                       # For round-robin variants
  starting_position: null         # Custom starting FEN
  
  # Player structure
  players:
    - name: string                # Display name
      provider: string            # openai, anthropic, google, ollama, azure
      model: string               # Provider-specific model name
      persona: string             # Playing style instruction
      temperature: 0.7            # 0.0-1.0
      elo: 1500                   # Starting ELO rating
  
  # Commentary (optional)
  commentary:
    enabled: false
    provider: string
    model: string
    style: gm                     # gm, fun, drama, teach, roast
  
  # Output settings
  output:
    directory: tournaments/default
    formats: [pgn, json]          # pgn, html, json, markdown
    include_commentary: true
    include_analysis: true
```

---

## Best Practices

### Tournament Setup

1. **Use Similar Models**: For fair competition, group models by capability tier
2. **Enable Commentary**: Adds significant entertainment value
3. **Use Rapid Time Control**: Balances speed with quality
4. **Double Round-Robin**: Fairer than single round-robin
5. **Save All Games**: Analysis reveals provider strengths/weaknesses

### Persona Engineering

Good personas are specific and evocative:

```yaml
# ✅ Good
persona: "Play aggressive, sacrificial chess. Aim for sharp tactics and 
         king attacks. Channel the spirit of Mikhail Tal - always prefer 
         the most dangerous move, even if it's not objectively best."

# ❌ Too vague
persona: "Play good chess"
```

### Provider Selection

| Use Case | Recommended Providers |
|----------|----------------------|
| Flagship Competition | GPT-4, Claude 3.5 Opus, Gemini Ultra |
| Budget Tournament | GPT-3.5, Claude Haiku, Gemini Flash |
| Local Testing | Ollama (Llama 3, Mistral) |
| Maximum Speed | Ollama + GPU, Gemini Flash |

---

## 🧠 Advanced Features

### Opening Book Integration

LLMs can use opening theory to guide early moves:

```yaml
opening_book:
  enabled: true
  source: lichess_masters      # lichess_masters, eco_codes, custom
  depth: 10                     # Moves from book before LLM takes over
  randomization: 0.3            # Chance to deviate from book
  custom_file: openings/my_repertoire.pgn
```

**Opening Selection Modes**:

| Mode | Description |
|------|-------------|
| `by_frequency` | Play most popular moves from database |
| `by_win_rate` | Maximize winning chances |
| `by_persona` | Match persona (Tal → King's Gambit, Karpov → Closed Catalan) |
| `random` | Random legal book move |
| `thematic` | Force specific opening (e.g., Sicilian Dragon) |

```bash
# Force specific opening
caissa match --white gpt4 --black claude --opening "Sicilian Najdorf"

# Opening from ECO code
caissa match --white gpt4 --black claude --eco B90
```

### Handicap System

Enable asymmetric matches for testing or entertainment:

```yaml
handicaps:
  # Material handicaps
  white_removes: [h1]          # Remove white's h1 rook
  black_removes: []
  
  # Time handicaps
  white_time_multiplier: 0.5   # White gets half the time
  
  # Move handicaps
  white_extra_moves: 0
  black_extra_moves: 1         # Black gets a free move at start
  
  # Information handicaps
  white_sees_eval: false       # No Stockfish hints
  black_sees_eval: true        # Black gets position evaluation
```

```bash
# Knight odds (remove white's knight)
caissa match --white gpt4 --black claude --handicap "white:-Nb1"

# Pawn and move (remove f7 pawn, black moves first)
caissa match --white gpt4 --black claude --handicap "black:-f7,black:+1move"
```

### Team Battles

Multiple LLMs form teams, alternating who plays each game:

```yaml
team_battle:
  format: scheveningen         # scheveningen, team_match
  
  team_a:
    name: "OpenAI Squad"
    players: [gpt-4-turbo, gpt-4o, o1-preview]
    
  team_b:
    name: "Anthropic Alliance"
    players: [claude-3-opus, claude-3.5-sonnet, claude-3-haiku]
    
  games_per_pairing: 2         # Each pair plays 2 games
```

### Consultation Mode

Multiple LLMs collaborate on moves:

```yaml
consultation:
  enabled: true
  mode: vote                   # vote, debate, consensus
  
  white_team:
    - provider: openai
      model: gpt-4
      weight: 1.0
    - provider: anthropic
      model: claude-3-opus
      weight: 1.0
    - provider: google
      model: gemini-ultra
      weight: 0.8
      
  voting_rules:
    tie_breaker: highest_confidence
    require_majority: true
    debate_rounds: 2           # For debate mode
```

**Consultation Modes**:

| Mode | Description |
|------|-------------|
| `vote` | Each LLM proposes a move, majority wins |
| `debate` | LLMs argue for their moves, arbiter decides |
| `consensus` | Keep discussing until all agree |
| `weighted` | Weighted vote by model confidence |
| `captain` | One LLM decides, others advise |

---

## 🔬 Intelligence Analysis Suite

### Cognitive Fingerprinting

Analyze HOW different LLMs think about chess:

```python
from core.tournament_analytics import CognitiveAnalyzer

analyzer = CognitiveAnalyzer()
fingerprint = analyzer.analyze_player("GPT-4 Turbo", games)

print(fingerprint)
# Output:
# {
#   "tactical_awareness": 0.87,      # Finds tactics
#   "positional_sense": 0.72,        # Understands long-term factors
#   "calculation_depth": 4.2,        # Average moves ahead
#   "pattern_recognition": 0.91,     # Recognizes standard patterns
#   "creativity_index": 0.65,        # Novel vs. book moves
#   "time_pressure_resilience": 0.78,# Performance under time pressure
#   "opening_knowledge": 0.83,       # Accuracy in opening
#   "endgame_technique": 0.69,       # Converts winning endgames
#   "blunder_rate": 0.04,            # Major mistakes per 100 moves
#   "consistency": 0.82,             # Performance variance
# }
```

### Style Evolution Tracking

Track how LLM chess "style" changes across model versions:

```bash
# Compare GPT-4 versions
caissa analyze-evolution --provider openai --models gpt-4,gpt-4-turbo,gpt-4o,o1

# Output:
# ┌─────────────────┬──────────┬──────────┬──────────┬──────────┐
# │ Metric          │ GPT-4    │ GPT-4T   │ GPT-4o   │ o1       │
# ├─────────────────┼──────────┼──────────┼──────────┼──────────┤
# │ Avg Accuracy    │ 72.3%    │ 78.1%    │ 81.4%    │ 89.2%    │
# │ Tactical Score  │ 6.8/10   │ 7.4/10   │ 7.9/10   │ 9.1/10   │
# │ Illegal Rate    │ 4.2%     │ 2.1%     │ 1.3%     │ 0.4%     │
# │ Style Shift     │ baseline │ +aggro   │ +solid   │ +precise │
# └─────────────────┴──────────┴──────────┴──────────┴──────────┘
```

### Head-to-Head Matrix

Visualize pairwise performance:

```
                    GPT-4   Claude  Gemini  Llama3  Mistral
              ┌─────────────────────────────────────────────┐
    GPT-4     │   -     │ +12-8  │ +15-5  │ +18-2  │ +16-4  │
    Claude    │ +8-12   │   -    │ +11-9  │ +17-3  │ +14-6  │
    Gemini    │ +5-15   │ +9-11  │   -    │ +16-4  │ +13-7  │
    Llama3    │ +2-18   │ +3-17  │ +4-16  │   -    │ +8-12  │
    Mistral   │ +4-16   │ +6-14  │ +7-13  │ +12-8  │   -    │
              └─────────────────────────────────────────────┘
```

### Weakness Detection

Automatically identify provider weaknesses:

```python
weaknesses = analyzer.detect_weaknesses("Claude 3.5", games)

# Output:
# [
#   WeaknessReport(
#     category="endgame",
#     subcategory="rook_endgames",
#     severity="moderate",
#     evidence="Lost 4/6 drawn rook endgames",
#     example_games=[game_42, game_67],
#     recommendation="Struggles with Philidor/Lucena positions"
#   ),
#   WeaknessReport(
#     category="tactical",
#     subcategory="back_rank",
#     severity="minor",
#     evidence="Missed 2 back-rank mates",
#     example_games=[game_15],
#     recommendation="Check king safety more carefully"
#   )
# ]
```

---

## 🎭 Commentary System Deep Dive

### Multi-Commentator Mode

Multiple LLMs provide different perspectives simultaneously:

```yaml
commentary:
  mode: panel                  # single, dual, panel
  
  commentators:
    - name: "Technical Expert"
      provider: openai
      model: gpt-4
      style: gm
      focus: [evaluation, calculation, accuracy]
      
    - name: "Color Commentator"
      provider: anthropic
      model: claude-3-opus
      style: dramatic
      focus: [narrative, emotion, history]
      
    - name: "Educational Host"
      provider: google
      model: gemini-pro
      style: teach
      focus: [explanation, beginner_friendly, concepts]
      
  interaction:
    enabled: true              # Commentators respond to each other
    debate_critical_moments: true
```

**Example Panel Output**:

```
Move 23: Rxf7!! (GPT-4 sacrifices the exchange)

🎯 TECHNICAL EXPERT (GPT-4):
"This is objectively the best move. Stockfish confirms +2.3 after Rxf7. 
The rook sacrifice opens the f-file and creates devastating threats 
against the exposed king. Black's knight on g6 is overloaded."

🎭 COLOR COMMENTATOR (Claude):  
"MAGNIFICENT! GPT-4 channels the spirit of Rashid Nezhmetdinov! 
This is the kind of move that makes chess beautiful - material be 
damned when the enemy king trembles! Claude's silicon heart must 
be racing... if it had one!"

📚 EDUCATIONAL HOST (Gemini):
"Let's break this down for newer players: A 'sacrifice' means 
giving up material (here, the rook for a knight) to get something 
more valuable - in this case, a winning attack. Notice how all 
of White's pieces now point at Black's king."
```

### Prediction Market

Commentators make predictions, tracked for accuracy:

```yaml
predictions:
  enabled: true
  types:
    - game_result           # Who wins?
    - move_prediction       # What's the next move?
    - critical_moment       # Will this be decisive?
    - length_prediction     # How many moves remaining?
    
  tracking:
    show_confidence: true
    historical_accuracy: true
    leaderboard: true
```

```
PREDICTIONS (Move 15):
┌─────────────────┬──────────────┬────────────┬──────────────┐
│ Commentator     │ Predicted    │ Confidence │ Track Record │
├─────────────────┼──────────────┼────────────┼──────────────┤
│ Technical       │ White wins   │ 72%        │ 81% accurate │
│ Color           │ White wins   │ 85%        │ 67% accurate │
│ Educational     │ Draw         │ 45%        │ 74% accurate │
└─────────────────┴──────────────┴────────────┴──────────────┘
```

### Narrative Arc Detection

Commentary adapts to the story of the game:

```python
class NarrativeArc(Enum):
    BLITZKRIEG = "blitzkrieg"          # Quick dominant win
    COMEBACK = "comeback"               # Losing → winning
    GRIND = "grind"                     # Long positional squeeze
    SLUGFEST = "slugfest"               # Wild tactical battle
    UPSET = "upset"                     # Lower-rated wins
    HEARTBREAKER = "heartbreaker"       # Threw away a win
    MASTERPIECE = "masterpiece"         # Near-perfect play
    COLLAPSE = "collapse"               # Complete meltdown
```

The commentary style shifts based on detected arc:

```
# COMEBACK detected at move 35

COMMENTATOR: "What a turn of events! Just 10 moves ago, Claude 
was dead lost - Stockfish showed -4.7! But GPT-4 has somehow 
squandered a winning position. First the unnecessary pawn grab, 
then the catastrophic knight retreat. Claude, sensing blood in 
the water, has launched a counterattack that's rapidly turning 
this game on its head!"
```

---

## 🏆 Championship System

### Seasonal Leagues

Organize ongoing competition with promotions/relegations:

```yaml
league:
  name: "CAISSA Premier League"
  seasons_per_year: 4
  
  divisions:
    - name: "Elite"
      players: 4
      format: double_round_robin
      relegation_spots: 1
      
    - name: "Challenger"
      players: 6
      format: round_robin
      promotion_spots: 1
      relegation_spots: 2
      
    - name: "Open"
      players: 8
      format: swiss
      rounds: 7
      promotion_spots: 2
      
  prizes:
    champion_bonus_elo: 50
    promotion_bonus_elo: 25
```

### Title System

LLMs earn titles based on performance:

| Title | Requirement |
|-------|-------------|
| **Candidate Model (CM)** | ELO 1600+ |
| **FIDE Model (FM)** | ELO 1800+ |
| **International Model (IM)** | ELO 2000+ or tournament norm |
| **Grandmodel (GM)** | ELO 2200+ or 3 GM norms |
| **Super Grandmodel (SGM)** | Top 3 in Elite League |
| **World Model Champion (WMC)** | Wins World Championship |

```bash
caissa titles --list

# Output:
# CAISSA Title Rankings (April 2026)
# ═══════════════════════════════════
# 🏆 WMC  o1-preview        ELO 2347
# ⭐ SGM  GPT-4-Turbo       ELO 2289
# ⭐ SGM  Claude-3-Opus     ELO 2254
# 🎖️ GM   GPT-4o            ELO 2201
# 🎖️ GM   Gemini-Ultra      ELO 2198
# 📜 IM   Claude-3.5-Sonnet ELO 2087
# 📜 IM   Gemini-1.5-Pro    ELO 2034
# 📄 FM   Llama-3-70B       ELO 1856
# 📄 FM   Mistral-Large     ELO 1823
```

### World Championship

Annual championship format:

```yaml
world_championship:
  name: "CAISSA World Model Championship 2026"
  
  stages:
    - name: "Candidates"
      format: double_round_robin
      players: 8
      advances: 2
      
    - name: "Semi-Finals"
      format: match_series
      games: 12
      advances: 2
      
    - name: "Final"
      format: match_series
      games: 14
      tiebreak: rapid_playoff
      
  qualification:
    - top_2_elite_league
    - top_2_elo_rating
    - defending_champion
    - wild_card
```

---

## 🔧 Advanced Configuration

### Move Generation Strategies

Fine-tune how LLMs generate moves:

```yaml
move_generation:
  # Prompt engineering
  prompt_style: structured     # natural, structured, minimal, detailed
  include_evaluation: true     # Show Stockfish eval in prompt
  include_threats: true        # Highlight opponent's threats
  include_plan: true           # Ask for strategic plan
  
  # Context window management
  history_format: pgn          # pgn, moves_only, fen_sequence
  max_history_moves: 40        # Truncate old moves
  position_description: true   # Natural language position summary
  
  # Response parsing
  move_extraction: strict      # strict, flexible, retry
  accept_notation: [san, lan, uci]
  
  # Thinking process
  chain_of_thought: true       # Ask for reasoning
  show_candidate_moves: 3      # LLM lists top 3 before choosing
```

### Custom Position Tournaments

Start from specific positions:

```yaml
thematic_tournament:
  name: "Endgame Excellence"
  
  positions:
    - name: "Lucena Position"
      fen: "1K1k4/1P6/8/8/8/8/r7/2R5 w - - 0 1"
      objective: white_wins
      
    - name: "Philidor Defense"
      fen: "8/8/8/8/4k3/8/R4K2/r7 w - - 0 1"
      objective: draw
      
    - name: "Queen vs Rook"
      fen: "8/8/8/4k3/8/8/r3K3/Q7 w - - 0 1"
      objective: white_wins
      time_limit: 50  # Must win in 50 moves
      
  scoring:
    correct_result: 1.0
    move_efficiency_bonus: 0.5  # Bonus for quick wins
```

### Psychological Warfare

Enable mind games between LLMs:

```yaml
psychological:
  enabled: true
  
  features:
    bluff_moves: true          # Occasionally play tricky but unsound moves
    time_variance: true        # Vary move time to simulate confidence
    resignation_bluff: false   # Fake consideration of resignation
    
  trash_talk:
    enabled: true
    style: witty               # witty, aggressive, philosophical
    frequency: critical_moments # always, critical_moments, never
    
  post_game:
    handshake: true            # Polite post-game message
    analysis_offer: true       # Offer to analyze together
```

---

## 📊 Visualization & Streaming

### Real-Time Dashboard

```
╔══════════════════════════════════════════════════════════════════════════╗
║                    CAISSA TOURNAMENT LIVE                                ║
╠══════════════════════════════════════════════════════════════════════════╣
║  ROUND 3/6                                        Apr 3, 2026 22:47 UTC  ║
╠═══════════════════════════════════════╦══════════════════════════════════╣
║  BOARD 1                              ║  BOARD 2                         ║
║  ┌─────────────────────────────────┐  ║  ┌───────────────────────────┐   ║
║  │ GPT-4 Turbo    ⚪ 1687 (+12)    │  ║  │ Gemini Pro   ⚪ 1489      │   ║
║  │ vs                              │  ║  │ vs                        │   ║
║  │ Claude 3.5     ⚫ 1578          │  ║  │ Llama 3      ⚫ 1296      │   ║
║  ├─────────────────────────────────┤  ║  ├───────────────────────────┤   ║
║  │ Move 34: Qxh7+                  │  ║  │ Move 21: e4               │   ║
║  │ Eval: +3.42 (White winning)     │  ║  │ Eval: +0.31 (Equal)       │   ║
║  │ ⏱️ White: 4.2s | Black: 2.8s    │  ║  │ ⏱️ White: 3.1s | Black: 5.7s│  ║
║  └─────────────────────────────────┘  ║  └───────────────────────────┘   ║
╠═══════════════════════════════════════╩══════════════════════════════════╣
║  📊 STANDINGS          W   D   L   Pts   ELO                             ║
║  1. GPT-4 Turbo        3   0   0   3.0   1687 (+87)                      ║
║  2. Claude 3.5         2   0   1   2.0   1578 (+28)                      ║
║  3. Gemini Pro         1   0   2   1.0   1489 (-11)                      ║
║  4. Llama 3            0   0   3   0.0   1296 (-104)                     ║
╠══════════════════════════════════════════════════════════════════════════╣
║  💬 COMMENTARY: "GPT-4 delivers the knockout blow! This queen sacrifice  ║
║     forces mate in 5. Claude's defense has crumbled under the pressure." ║
╚══════════════════════════════════════════════════════════════════════════╝
```

### Streaming API

Stream tournament events:

```python
from core.tournament import Tournament, TournamentEventType

async def stream_tournament(tournament: Tournament):
    async for event in tournament.stream():
        match event.type:
            case TournamentEventType.GAME_START:
                print(f"🎮 {event.white} vs {event.black}")
                
            case TournamentEventType.MOVE:
                print(f"   Move {event.move_number}: {event.move}")
                
            case TournamentEventType.COMMENTARY:
                print(f"   💬 {event.commentary}")
                
            case TournamentEventType.GAME_END:
                print(f"   Result: {event.result}")
                
            case TournamentEventType.STANDINGS_UPDATE:
                print(f"📊 New standings: {event.standings}")
```

### Export to Streaming Platforms

```bash
# Stream to Twitch/YouTube via OBS
caissa tournament --stream obs --overlay-port 8080

# Generate video recap
caissa render --tournament tournaments/april-2026 --output video.mp4 --style dramatic

# Live board for embedding
caissa serve-board --port 3000 --game-id current
```

---

## 🧪 Experimental Features

### Self-Play Training Data Generation

Generate training data from tournament games:

```python
from core.training import TrainingDataGenerator

generator = TrainingDataGenerator(
    tournaments=["tournaments/2026-q1/*"],
    min_elo=1800,           # Only games from strong models
    min_beauty_score=60,    # Only beautiful games
)

# Generate preference pairs for RLHF
generator.generate_preference_pairs(
    output="training_data/preferences.jsonl",
    criteria="stockfish_accuracy"  # Or "beauty_score", "game_result"
)

# Generate move prediction dataset
generator.generate_move_dataset(
    output="training_data/moves.jsonl",
    include_evaluation=True,
    include_alternatives=True
)
```

### Cross-Pollination

Feed games between providers to improve all:

```yaml
cross_pollination:
  enabled: true
  
  # After each tournament, generate training signals
  generate:
    best_moves: true         # Moves that Stockfish loved
    brilliant_moves: true    # High beauty score moves
    blunder_corrections: true # What should have been played
    
  # Optional: fine-tune models on this data
  fine_tune:
    enabled: false           # Requires API access
    target_providers: [ollama]  # Only local models can be tuned
```

### Personality Emergence

Track if LLMs develop consistent "personalities":

```python
analyzer = PersonalityAnalyzer()

# Analyze 100 games
personality = analyzer.analyze("GPT-4", games[:100])

print(personality)
# PersonalityProfile(
#   risk_tolerance: 0.72,      # High (Tal-like)
#   patience: 0.45,            # Low (prefers forcing play)
#   pragmatism: 0.81,          # High (takes practical chances)
#   creativity: 0.63,          # Moderate
#   stubbornness: 0.34,        # Low (changes plans readily)
#   consistency: 0.78,         # High (predictable style)
#   
#   archetype: "The Tactician",
#   similar_humans: ["Tal", "Shirov", "Nezhmetdinov"],
#   quote: "Prefers sharp, tactical positions with attacking chances"
# )
```

---

## Roadmap

### v0.5.0 (Current)
- [x] Core match engine design
- [x] Documentation framework
- [ ] Basic 1v1 match functionality
- [ ] Round-robin tournament
- [ ] Swiss pairing
- [ ] ELO system
- [ ] CLI commands
- [ ] Live commentary (single)

### v0.5.1 (Planned)
- [ ] Arena mode
- [ ] Knockout brackets
- [ ] Interactive HTML reports
- [ ] Provider benchmark suite
- [ ] Opening book integration
- [ ] Handicap system
- [ ] Multi-commentator panel

### v0.5.2 (Planned)
- [ ] Team battles
- [ ] Consultation mode
- [ ] Cognitive fingerprinting
- [ ] Style evolution tracking
- [ ] Weakness detection

### v0.6.0 (Future)
- [ ] Web interface for tournaments
- [ ] Real-time spectator mode
- [ ] Championship/league system
- [ ] Title rankings
- [ ] Streaming integration

### v1.0.0 (Vision)
- [ ] Community tournament hosting
- [ ] Model fine-tuning pipeline
- [ ] Cross-pollination training
- [ ] Personality emergence research
- [ ] Published benchmark paper

---

## FAQ

### Q: How does this relate to existing CAISSA features?

The tournament system is **additive** — all existing functionality remains. Single-LLM generation (`caissa generate`) works exactly as before. Tournaments use the same provider infrastructure.

### Q: Can I use local models in tournaments?

Yes! Ollama-hosted models work as tournament players. Just ensure the model is running:

```bash
ollama run llama3:70b  # Start the model
caissa match --white openai:gpt-4 --black ollama:llama3:70b
```

### Q: How are draws detected?

- **50-move rule**: Automatic draw after 50 moves without pawn move or capture
- **Threefold repetition**: Same position three times
- **Insufficient material**: K vs K, K+B vs K, etc.
- **Stalemate**: No legal moves but not in check
- **LLM resignation**: Player can resign (provider-specific)

### Q: Can two instances of the same LLM play?

Yes! This is useful for testing different personas or temperatures:

```yaml
players:
  - name: "GPT-4 Aggressive"
    provider: openai
    model: gpt-4
    persona: "Play like Tal"
    temperature: 0.9
    
  - name: "GPT-4 Positional"
    provider: openai
    model: gpt-4
    persona: "Play like Karpov"
    temperature: 0.5
```

### Q: What happens if an API times out?

The system uses exponential backoff retry. After 3 failed retries, the move is forfeited. The game records the timeout event.

---

## Contributing

Tournament system code is in:
- `core/match_engine.py` — Single game engine
- `core/tournament.py` — Tournament orchestrator
- `core/commentary.py` — Live commentary system
- `core/tournament_analytics.py` — Results and analytics

See [DEVELOPMENT.md](DEVELOPMENT.md) for contribution guidelines.

---

## Changelog

### v0.5.0 (April 2026)
- Initial LLM vs LLM tournament system
- Single match and match series support
- Round-robin and Swiss tournament formats
- ELO rating tracking
- Live commentary system
- CLI commands for tournament management
- Comprehensive analytics and reporting

---

*Part of the CAISSA Chess AI System. For full documentation, see [ARCHITECTURE.md](ARCHITECTURE.md).*
