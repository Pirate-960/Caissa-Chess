# Phase 2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CAISSA Phase 2: LLM Integration              │
└─────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────┐
                        │  User / Script  │
                        └────────┬────────┘
                                 │
                                 │ 1. Create GameContext
                                 ▼
                    ┌────────────────────────┐
                    │  CaissaGenerator       │
                    │  ────────────────────  │
                    │  + generate_game()     │
                    │  + _clean_response()   │
                    │  + _construct_error()  │
                    └────┬──────────────┬────┘
                         │              │
        2. Build Prompts │              │ 7. Validate
                         │              │
            ┌────────────▼──────────┐   │   ┌───────────────────┐
            │  PromptManager        │   │   │ LegalityValidator │
            │  ───────────────────  │   │   │ ───────────────── │
            │  + build_system()     │   │   │ + validate_pgn()  │
            │  + build_user()       │   │   │ + parse_move()    │
            └───────────────────────┘   │   └───────────────────┘
                         │              │              │
                         │              └──────────────┘
                         │
        3. Call LLM      │
                         ▼
                ┌────────────────┐
                │  LLMProvider   │ ◄────── Abstract Interface
                │  ────────────  │
                │  + generate()  │
                └───────┬────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌───────────────┐ ┌──────────────┐ ┌──────────────┐
│ OpenAIProvider│ │ MockProvider │ │ Future: ...  │
│ ────────────  │ │ ──────────── │ │ Anthropic,   │
│ + generate()  │ │ + generate() │ │ Local LLMs   │
│ + @retry      │ │ + reset()    │ └──────────────┘
└──────┬────────┘ └──────┬───────┘
       │                 │
       │                 │
       ▼                 ▼
  ┌─────────┐      ┌──────────┐
  │ OpenAI  │      │  Test    │
  │   API   │      │  Data    │
  └─────────┘      └──────────┘


╔══════════════════════════════════════════════════════════════╗
║              SELF-CORRECTION LOOP (The Brain)                ║
╚══════════════════════════════════════════════════════════════╝

  START
    │
    ▼
┌─────────────────────┐
│ 1. Generate Prompt  │ ◄─────────────┐
│    (PromptManager)  │               │
└──────────┬──────────┘               │
           │                          │
           ▼                          │
┌─────────────────────┐               │
│ 2. Call LLM         │               │
│    (Provider)       │               │ Retry Loop
└──────────┬──────────┘               │ (max 3x)
           │                          │
           ▼                          │
┌─────────────────────┐               │
│ 3. Clean Response   │               │
│    (Strip Markdown) │               │
└──────────┬──────────┘               │
           │                          │
           ▼                          │
┌─────────────────────┐               │
│ 4. Validate PGN     │               │
│    (LegalityCheck)  │               │
└──────────┬──────────┘               │
           │                          │
      ┌────┴────┐                     │
      │ Valid..?│                     │
      └────┬────┘                     │
           │                          │
     ┌─────┴─────┐                    │
     │           │                    │
    YES          NO                   │
     │           │                    │
     │           ▼                    │
     │   ┌─────────────────┐          │
     │   │ 5. Construct    │          │
     │   │    Error        │          │
     │   │    Feedback     │          │
     │   └────────┬────────┘          │
     │            │                   │
     │            ▼                   │
     │   ┌─────────────────┐          │
     │   │ 6. Append to    │          │
     │   │    Conversation │          │
     │   │    History      │          │
     │   └────────┬────────┘          │
     │            │                   │
     │            └───────────────────┘
     │
     ▼
┌─────────────┐
│ RETURN PGN  │
│   SUCCESS   │
└─────────────┘


╔══════════════════════════════════════════════════════════════╗
║                    Key Design Decisions                      ║
╚══════════════════════════════════════════════════════════════╝

✅ Dependency Injection
   └─> Easy testing with MockProvider
   └─> Swap LLM providers without code changes

✅ Exponential Backoff (Tenacity)
   └─> Handles rate limits gracefully
   └─> 2s → 4s → 8s delays between retries

✅ Conversation History
   └─> Tracks all LLM interactions
   └─> Enables debugging and future features

✅ Robust PGN Extraction
   └─> Regex patterns for markdown removal
   └─> Handles chatty LLM responses

✅ Detailed Error Feedback
   └─> Tells LLM exactly what's wrong
   └─> Increases correction success rate


╔══════════════════════════════════════════════════════════════╗
║                    File Structure                            ║
╚══════════════════════════════════════════════════════════════╝

caissa-chess/
│
├── core/
│   ├── __init__.py
│   ├── llm_provider.py          ◄── NEW: Provider interface
│   ├── generator.py             ◄── REFACTORED: Self-correction
│   ├── prompt_manager.py        (existing)
│   └── board_state.py           (existing)
│
├── tests/
│   ├── __init__.py
│   ├── test_llm_integration.py  ◄── NEW: 15+ test cases
│   └── test_legality.py         (existing)
│
├── script_test_openai.py        ◄── NEW: Manual test script
├── pyproject.toml               ◄── UPDATED: Added tenacity
│
└── docs/
    ├── PHASE2_COMPLETE.md       ◄── NEW: Full documentation
    ├── IMPLEMENTATION_SUMMARY.md◄── NEW: Task completion
    └── QUICKSTART_PHASE2.md     ◄── NEW: Quick commands
