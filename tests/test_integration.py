"""
Quick integration test for improved tournament CLI.
"""

# Test imports
try:
    from core.tournament_cli_improved import (
        ImprovedMatchBuilder,
        ImprovedTournamentBuilder,
        parse_smart_player_input,
        PlayerSelectionResult,
        MatchConfig,
        TournamentConfig,
    )
    print("✓ All imports successful")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    exit(1)

# Test smart player parsing
print("\n" + "="*60)
print("Testing Smart Player Selection")
print("="*60)

test_providers = ["gemini", "claude", "gpt4", "ollama"]

test_cases = [
    ("gemini x 100", "100 gemini players"),
    ("1-4", "All 4 providers by range"),
    ("all x 10", "All providers 10 times each"),
    ("gemini x 50, claude x 30, gpt4 x 20", "Mixed bulk"),
    ("1,2,3,4", "Comma-separated indices"),
    ("all", "All providers once"),
    ("back", "Navigate back"),
    ("gemini, claude", "Provider names"),
]

for input_str, description in test_cases:
    result = parse_smart_player_input(input_str, test_providers)
    
    if result.go_back:
        print(f"\nInput: '{input_str}'\n  → Go back")
    elif result.error:
        print(f"\nInput: '{input_str}'\n  → Error: {result.error}")
    else:
        # Count providers
        from collections import Counter
        counts = Counter(result.providers)
        total = sum(counts.values())
        print(f"\nInput: '{input_str}'\n  → {total} players: {dict(counts)}\n  → ({description})")

print("\n" + "="*60)
print("✓ Integration test complete")
print("="*60)
