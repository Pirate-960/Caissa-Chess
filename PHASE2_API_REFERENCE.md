# Phase 2 API Reference

## `core.llm_provider`

### Abstract Base Class

#### `LLMProvider`

Abstract base class for all LLM providers.

```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        temperature: float = 0.8
    ) -> str:
        """Generate response from LLM."""
        pass
```

---

### Concrete Implementations

#### `OpenAIProvider`

```python
from core.llm_provider import OpenAIProvider

provider = OpenAIProvider(
    api_key="sk-...",           # Optional, reads from env
    model="gpt-4-turbo",        # Default model
    max_tokens=4096             # Default token limit
)

response = provider.generate(
    system_prompt="You are a chess grandmaster...",
    user_prompt="Generate a romantic game...",
    temperature=0.8
)
```

**Features:**
- ✅ Automatic retry with exponential backoff
- ✅ Handles `RateLimitError` and `APIConnectionError`
- ✅ Configurable model and token limits

**Retry Behavior:**
- **Wait**: Random exponential, 2-60 seconds
- **Attempts**: Max 3
- **Exceptions**: `RateLimitError`, `APIConnectionError`

---

#### `MockProvider`

```python
from core.llm_provider import MockProvider

provider = MockProvider(responses=[
    "Response 1",
    "Response 2",
    "Response 3"
])

# Returns responses sequentially
response1 = provider.generate("", "", 0.5)  # "Response 1"
response2 = provider.generate("", "", 0.5)  # "Response 2"

# Check call count
print(provider.call_count)  # 2

# Reset for reuse
provider.reset()
```

**Use Cases:**
- ✅ Unit testing without API calls
- ✅ Testing self-correction logic
- ✅ Deterministic test scenarios

---

## `core.generator`

### Main Class

#### `CaissaGenerator`

```python
from core.generator import CaissaGenerator
from core.llm_provider import OpenAIProvider
from core.prompt_manager import GameContext, GameEra

# Initialize with provider
provider = OpenAIProvider()
generator = CaissaGenerator(
    provider=provider,
    max_retries=3
)

# Or set provider later
generator = CaissaGenerator()
generator.set_provider(provider)

# Generate game
context = GameContext(
    era=GameEra.ROMANTIC,
    aggression_score=8
)

success, pgn, moves = generator.generate_game(context)

if success:
    print("Generated PGN:")
    print(pgn)
else:
    print(f"Error: {pgn}")
```

**Constructor:**
```python
def __init__(
    self, 
    provider: Optional[LLMProvider] = None,
    max_retries: int = 3
):
```

**Parameters:**
- `provider`: LLMProvider instance (OpenAI, Mock, etc.)
- `max_retries`: Max correction attempts (default: 3)

---

### Methods

#### `generate_game(context: GameContext) -> Tuple[bool, str, List[str]]`

Generate a complete chess game with self-correction.

**Parameters:**
- `context`: GameContext with generation parameters

**Returns:**
```python
(success: bool, pgn_or_error: str, moves: List[str])
```

**Example:**
```python
success, result, moves = generator.generate_game(context)

if success:
    print(f"Generated {len(moves)} moves")
    print(result)  # PGN string
else:
    print(f"Failed: {result}")  # Error message
```

---

#### `set_provider(provider: LLMProvider) -> None`

Set or update the LLM provider.

**Example:**
```python
from core.llm_provider import MockProvider

generator = CaissaGenerator()
generator.set_provider(MockProvider(["PGN here"]))
```

---

### Internal Methods

#### `_clean_response(response: str) -> Optional[str]`

Extract PGN from potentially chatty LLM response.

**Handles:**
- Markdown code blocks: ` ```pgn ... ``` `
- Preamble text: "Here is your game: ..."
- PGN headers: `[Event "..."]`
- Move notation: `1. e4 e5 ...`

**Returns:**
- Cleaned PGN string
- `None` if extraction fails

---

#### `_construct_error_feedback(errors: List[str]) -> str`

Construct detailed error feedback for LLM correction.

**Features:**
- Lists first 3 errors with details
- Adds guidance for correction
- Prevents token overflow

**Example Output:**
```
The game contains the following legal violations:

1. Move 4. Bxe5 is illegal: no piece on e5
2. Move 12. Qxf7+ is illegal: queen cannot reach f7
3. Move 18. O-O-O is illegal: king has moved

Please review the position carefully and ensure all moves are legal.
```

---

## Type Definitions

### From `core.prompt_manager`

#### `GameContext`

```python
@dataclass
class GameContext:
    era: GameEra = GameEra.ROMANTIC
    theme: Optional[GameTheme] = None
    white_player: str = "Caissa White"
    black_player: str = "Caissa Black"
    aggression_score: int = 7      # 1-10
    chaos_score: int = 5            # 1-10
    depth: int = 40                 # Half-moves
    blunder_tolerance: float = 1.5  # Centipawns
    force_win: bool = True
```

#### `GameEra` (Enum)

```python
class GameEra(str, Enum):
    ROMANTIC = "Romantic 1850s"
    CLASSICAL = "Classical 1880s-1920s"
    HYPERMODERN = "Hypermodern 1920s-1930s"
    SOVIET = "Soviet School 1920s-1970s"
    COMPUTER = "Computer Era 1980s-2000s"
    NEURAL = "Neural Network Era 2010s-2024"
```

#### `GameTheme` (Enum)

```python
class GameTheme(str, Enum):
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
```

---

## Usage Examples

### Example 1: Basic Generation

```python
from core.llm_provider import OpenAIProvider
from core.generator import CaissaGenerator
from core.prompt_manager import GameContext, GameEra

# Setup
provider = OpenAIProvider()
generator = CaissaGenerator(provider)

# Simple context
context = GameContext(era=GameEra.ROMANTIC)

# Generate
success, pgn, moves = generator.generate_game(context)
print(pgn)
```

---

### Example 2: Custom Configuration

```python
from core.llm_provider import OpenAIProvider
from core.generator import CaissaGenerator
from core.prompt_manager import GameContext, GameEra, GameTheme

# Custom provider
provider = OpenAIProvider(
    model="gpt-4",
    max_tokens=2000
)

# Custom generator
generator = CaissaGenerator(
    provider=provider,
    max_retries=5  # More patient
)

# Rich context
context = GameContext(
    era=GameEra.ROMANTIC,
    theme=GameTheme.QUEEN_SACRIFICE,
    white_player="Mikhail Tal",
    black_player="Bobby Fischer",
    aggression_score=9,
    chaos_score=7
)

success, pgn, moves = generator.generate_game(context)
```

---

### Example 3: Testing with MockProvider

```python
from core.llm_provider import MockProvider
from core.generator import CaissaGenerator
from core.prompt_manager import GameContext

# Valid PGN for testing
VALID_PGN = """[Event "Test"]
[White "Test White"]
[Black "Test Black"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 1-0"""

# Mock provider
provider = MockProvider(responses=[VALID_PGN])

# Test
generator = CaissaGenerator(provider)
context = GameContext()
success, pgn, moves = generator.generate_game(context)

assert success == True
assert provider.call_count == 1
```

---

### Example 4: Testing Self-Correction

```python
from core.llm_provider import MockProvider
from core.generator import CaissaGenerator

# First response is invalid, second is valid
provider = MockProvider(responses=[
    "Not valid PGN at all!",
    "[Event \"Test\"]\n1. e4 e5 1-0"
])

generator = CaissaGenerator(provider, max_retries=3)
success, pgn, moves = generator.generate_game(context)

# Should succeed after retry
assert success == True
assert provider.call_count == 2
assert len(generator.conversation_history) == 2
```

---

### Example 5: Error Handling

```python
from core.llm_provider import OpenAIProvider
from core.generator import CaissaGenerator

try:
    provider = OpenAIProvider()  # May raise if no API key
    generator = CaissaGenerator(provider)
    success, result, moves = generator.generate_game(context)
    
    if not success:
        print(f"Generation failed: {result}")
        # Check conversation history for debugging
        for i, (prompt, response) in enumerate(generator.conversation_history):
            print(f"\nAttempt {i+1}:")
            print(f"Response: {response[:100]}...")
            
except ValueError as e:
    print(f"Configuration error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

---

## Logging

### Enable Debug Logging

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Now all operations will be logged
generator.generate_game(context)
```

### Log Levels

- `DEBUG`: Detailed operation logs
- `INFO`: High-level progress
- `WARNING`: Retry attempts, recoverable errors
- `ERROR`: Fatal errors

### Example Output

```
2026-02-02 10:15:23 - core.llm_provider - INFO - Initialized OpenAIProvider with model: gpt-4-turbo
2026-02-02 10:15:23 - core.generator - INFO - Generating game with style: Romantic 1850s, theme: The Queen Sacrifice, aggression: 8/10
2026-02-02 10:15:45 - core.generator - WARNING - Illegal move detected. Retrying (Attempt 1/3)...
2026-02-02 10:16:07 - core.generator - INFO - Game successfully generated.
```

---

## Environment Variables

### `OPENAI_API_KEY`

Required for `OpenAIProvider`.

```bash
# Set before running
export OPENAI_API_KEY='sk-...'
```

**Or** pass directly to constructor:

```python
provider = OpenAIProvider(api_key="sk-...")
```

---

## Error Handling

### Exceptions

#### `ValueError`
- Raised when API key not provided
- Raised when MockProvider has no responses

#### `RateLimitError`
- OpenAI rate limit hit
- Automatically retried (max 3 attempts)

#### `APIConnectionError`
- Network connection failed
- Automatically retried (max 3 attempts)

#### `IndexError`
- MockProvider exhausted responses
- Only in testing scenarios

### Return Values

#### Success Case
```python
success = True
result = "[Event \"Romantic Beauty\"]\n1. e4 e5 ..."
moves = ["e4", "e5", "Nf3", ...]
```

#### Failure Case
```python
success = False
result = "Failed to generate valid game after 3 attempts. Last error: ..."
moves = []
```

---

## Performance

### Typical Timings

| Scenario | LLM Calls | Time (avg) | Tokens Used |
|----------|-----------|------------|-------------|
| Perfect generation | 1 | 30-45s | 2000-3000 |
| One retry | 2 | 60-90s | 4000-6000 |
| Max retries (3) | 3 | 90-120s | 6000-9000 |

### Cost Estimates (GPT-4 Turbo)

- **Input**: ~1500 tokens/request = $0.015
- **Output**: ~1000 tokens/request = $0.030
- **Total per successful game**: $0.05 - $0.15

---

## Best Practices

### 1. Always Use Try-Except

```python
try:
    success, pgn, moves = generator.generate_game(context)
except Exception as e:
    logger.error(f"Generation failed: {e}")
```

### 2. Check Success Flag

```python
success, result, moves = generator.generate_game(context)
if success:
    save_to_file(result)
else:
    log_error(result)
```

### 3. Use MockProvider for Tests

```python
# Don't hit API in tests
provider = MockProvider(responses=[VALID_PGN])
```

### 4. Configure Logging

```python
# See what's happening
logging.basicConfig(level=logging.INFO)
```

### 5. Set Reasonable Retries

```python
# Balance quality vs cost
generator = CaissaGenerator(provider, max_retries=3)
```

---

## Migration Guide

### From Phase 1 to Phase 2

**Old Code:**
```python
from core.generator import CaissaGenerator, SimpleOpenAIClient

client = SimpleOpenAIClient()
generator = CaissaGenerator(llm_client=client)
```

**New Code:**
```python
from core.generator import CaissaGenerator
from core.llm_provider import OpenAIProvider

provider = OpenAIProvider()
generator = CaissaGenerator(provider=provider)
```

**Changes:**
- `llm_client` → `provider`
- `SimpleOpenAIClient` → `OpenAIProvider`
- `set_llm_client()` → `set_provider()`

---

## Support

For issues or questions:
1. Check logs: `logging.basicConfig(level=logging.DEBUG)`
2. Run tests: `pytest tests/test_llm_integration.py -v`
3. Review error messages in return value
4. Check conversation history: `generator.conversation_history`

---

**API Version**: Phase 2 (v0.2.0)  
**Last Updated**: February 2, 2026
