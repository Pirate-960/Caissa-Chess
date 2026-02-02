"""
script_test_openai.py

Manual test script for verifying OpenAI integration with real API.
Requires OPENAI_API_KEY environment variable to be set.

Usage:
    python script_test_openai.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.llm_provider import OpenAIProvider
from core.generator import CaissaGenerator
from core.prompt_manager import GameContext, GameEra, GameTheme


def main():
    """Run manual test with OpenAI API."""
    
    print("=" * 70)
    print("CAISSA Phase 2: OpenAI Integration Test")
    print("=" * 70)
    print()
    
    # Check API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY environment variable not set!")
        print()
        print("Please set your API key:")
        print("  Windows (PowerShell): $env:OPENAI_API_KEY='your-key-here'")
        print("  Windows (CMD):        set OPENAI_API_KEY=your-key-here")
        print("  Linux/Mac:            export OPENAI_API_KEY='your-key-here'")
        print()
        return 1
    
    print(f"✓ API Key found: {api_key[:8]}...{api_key[-4:]}")
    print()
    
    # Initialize provider
    try:
        print("Initializing OpenAI provider...")
        provider = OpenAIProvider(
            api_key=api_key,
            model="gpt-4-turbo",
            max_tokens=4096
        )
        print("✓ Provider initialized")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize provider: {e}")
        return 1
    
    # Create generator
    print("Initializing generator with self-correction loop...")
    generator = CaissaGenerator(
        provider=provider,
        max_retries=3
    )
    print("✓ Generator ready")
    print()
    
    # Set up game context
    context = GameContext(
        era=GameEra.ROMANTIC,
        theme=GameTheme.QUEEN_SACRIFICE,
        white_player="Caissa the Bold",
        black_player="Caissa the Sage",
        aggression_score=8,
        chaos_score=6,
        depth=40,
        force_win=True
    )
    
    print("Game Configuration:")
    print(f"  Era:        {context.era.value}")
    print(f"  Theme:      {context.theme.value if context.theme else 'None'}")
    print(f"  White:      {context.white_player}")
    print(f"  Black:      {context.black_player}")
    print(f"  Aggression: {context.aggression_score}/10")
    print(f"  Chaos:      {context.chaos_score}/10")
    print(f"  Depth:      {context.depth} half-moves")
    print()
    
    # Generate game
    print("🎨 Generating game... (this may take 30-60 seconds)")
    print("-" * 70)
    
    try:
        success, result, moves = generator.generate_game(context)
        
        print("-" * 70)
        print()
        
        if success:
            print("✅ SUCCESS! Game generated successfully!")
            print()
            print("=" * 70)
            print("GENERATED PGN:")
            print("=" * 70)
            print(result)
            print("=" * 70)
            print()
            
            # Optionally save to file
            output_file = "generated_game.pgn"
            with open(output_file, "w") as f:
                f.write(result)
            print(f"✓ Game saved to: {output_file}")
            print()
            
            # Show conversation history
            print(f"Conversation History: {len(generator.conversation_history)} exchanges")
            if len(generator.conversation_history) > 1:
                print("  (Self-correction was used)")
            print()
            
            return 0
        
        else:
            print("❌ FAILURE: Could not generate valid game")
            print()
            print("Error Details:")
            print(result)
            print()
            
            # Show what attempts were made
            if generator.conversation_history:
                print(f"Attempts made: {len(generator.conversation_history)}")
                print()
            
            return 1
    
    except KeyboardInterrupt:
        print()
        print("⚠ Interrupted by user")
        return 130
    
    except Exception as e:
        print()
        print(f"❌ Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
