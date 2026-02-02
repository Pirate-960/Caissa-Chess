#!/usr/bin/env python3
"""
script_multi_provider_demo.py

Demonstrates how to use multiple LLM providers with CAISSA.
Shows configuration and usage for:
- OpenAI (GPT-4, GPT-3.5-turbo)
- Anthropic (Claude 3.5 Sonnet, Opus)
- Azure OpenAI
- Google Gemini
- Ollama (local models)
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.generator import GameGenerator
from core.prompt_manager import PromptManager
from core.llm_provider import (
    OpenAIProvider,
    AnthropicProvider,
    AzureOpenAIProvider,
    GoogleGeminiProvider,
    OllamaProvider,
)


def demo_openai():
    """Demonstrate OpenAI provider (GPT-4 or GPT-3.5-turbo)."""
    print("\n" + "="*60)
    print("DEMO: OpenAI Provider")
    print("="*60)
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("⚠️  OPENAI_API_KEY not set. Skipping OpenAI demo.")
        return
    
    try:
        # Initialize provider
        provider = OpenAIProvider(
            api_key=api_key,
            model="gpt-4",  # or "gpt-3.5-turbo" for faster/cheaper
            max_tokens=4096
        )
        
        # Generate game
        prompt_manager = PromptManager()
        generator = GameGenerator(provider, prompt_manager)
        
        game = generator.generate_game(
            aesthetic_goal="Romantic attacking chess with tactical sacrifices",
            move_limit=15,
            max_retries=3
        )
        
        print("\n✅ Generated game successfully!")
        print(f"Moves: {len(game.moves)}")
        print(f"Opening: {game.metadata.opening}")
        print(f"\nPGN:\n{game.pgn_str}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def demo_anthropic():
    """Demonstrate Anthropic provider (Claude)."""
    print("\n" + "="*60)
    print("DEMO: Anthropic Provider (Claude)")
    print("="*60)
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️  ANTHROPIC_API_KEY not set. Skipping Anthropic demo.")
        return
    
    try:
        # Initialize provider
        provider = AnthropicProvider(
            api_key=api_key,
            model="claude-3-5-sonnet-20241022",  # or "claude-3-opus-20240229"
            max_tokens=4096
        )
        
        # Generate game
        prompt_manager = PromptManager()
        generator = GameGenerator(provider, prompt_manager)
        
        game = generator.generate_game(
            aesthetic_goal="Positional masterpiece with strategic depth",
            move_limit=15,
            max_retries=3
        )
        
        print("\n✅ Generated game successfully!")
        print(f"Moves: {len(game.moves)}")
        print(f"Opening: {game.metadata.opening}")
        print(f"\nPGN:\n{game.pgn_str}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def demo_azure_openai():
    """Demonstrate Azure OpenAI provider."""
    print("\n" + "="*60)
    print("DEMO: Azure OpenAI Provider")
    print("="*60)
    
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    
    if not api_key or not endpoint:
        print("⚠️  AZURE_OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT not set.")
        print("   Skipping Azure OpenAI demo.")
        return
    
    try:
        # Initialize provider
        provider = AzureOpenAIProvider(
            api_key=api_key,
            azure_endpoint=endpoint,
            deployment_name="gpt-4",  # Your deployment name
            api_version="2024-02-15-preview",
            max_tokens=4096
        )
        
        # Generate game
        prompt_manager = PromptManager()
        generator = GameGenerator(provider, prompt_manager)
        
        game = generator.generate_game(
            aesthetic_goal="Dynamic game with unclear positions",
            move_limit=15,
            max_retries=3
        )
        
        print("\n✅ Generated game successfully!")
        print(f"Moves: {len(game.moves)}")
        print(f"Opening: {game.metadata.opening}")
        print(f"\nPGN:\n{game.pgn_str}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def demo_google_gemini():
    """Demonstrate Google Gemini provider."""
    print("\n" + "="*60)
    print("DEMO: Google Gemini Provider")
    print("="*60)
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("⚠️  GOOGLE_API_KEY not set. Skipping Google Gemini demo.")
        return
    
    try:
        # Initialize provider
        provider = GoogleGeminiProvider(
            api_key=api_key,
            model="gemini-pro",  # or "gemini-pro-vision" for multimodal
            max_tokens=4096
        )
        
        # Generate game
        prompt_manager = PromptManager()
        generator = GameGenerator(provider, prompt_manager)
        
        game = generator.generate_game(
            aesthetic_goal="Hyper-modern opening with fianchetto",
            move_limit=15,
            max_retries=3
        )
        
        print("\n✅ Generated game successfully!")
        print(f"Moves: {len(game.moves)}")
        print(f"Opening: {game.metadata.opening}")
        print(f"\nPGN:\n{game.pgn_str}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def demo_ollama():
    """Demonstrate Ollama provider (local models)."""
    print("\n" + "="*60)
    print("DEMO: Ollama Provider (Local Models)")
    print("="*60)
    
    try:
        # Initialize provider
        provider = OllamaProvider(
            model="llama2",  # or "mistral", "codellama", "mixtral", etc.
            base_url="http://localhost:11434",
            max_tokens=4096
        )
        
        # Generate game
        prompt_manager = PromptManager()
        generator = GameGenerator(provider, prompt_manager)
        
        game = generator.generate_game(
            aesthetic_goal="Classical game with pawn structures",
            move_limit=15,
            max_retries=3
        )
        
        print("\n✅ Generated game successfully!")
        print(f"Moves: {len(game.moves)}")
        print(f"Opening: {game.metadata.opening}")
        print(f"\nPGN:\n{game.pgn_str}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nMake sure Ollama is running:")
        print("  1. Install: https://ollama.ai/")
        print("  2. Run: ollama serve")
        print("  3. Pull model: ollama pull llama2")


def main():
    """Run all provider demos."""
    print("\n" + "🎭 "*30)
    print("CAISSA Multi-Provider Demonstration")
    print("🎭 "*30)
    
    print("\n📋 Configuration:")
    print(f"  OPENAI_API_KEY:        {'✅ Set' if os.getenv('OPENAI_API_KEY') else '❌ Not set'}")
    print(f"  ANTHROPIC_API_KEY:     {'✅ Set' if os.getenv('ANTHROPIC_API_KEY') else '❌ Not set'}")
    print(f"  AZURE_OPENAI_API_KEY:  {'✅ Set' if os.getenv('AZURE_OPENAI_API_KEY') else '❌ Not set'}")
    print(f"  GOOGLE_API_KEY:        {'✅ Set' if os.getenv('GOOGLE_API_KEY') else '❌ Not set'}")
    
    # Run demos for available providers
    demo_openai()
    demo_anthropic()
    demo_azure_openai()
    demo_google_gemini()
    demo_ollama()
    
    print("\n" + "="*60)
    print("✅ Demo complete!")
    print("="*60)
    
    print("\n📚 Setup Instructions:")
    print("\nFor OpenAI:")
    print("  export OPENAI_API_KEY='sk-...'")
    
    print("\nFor Anthropic:")
    print("  export ANTHROPIC_API_KEY='sk-ant-...'")
    
    print("\nFor Azure OpenAI:")
    print("  export AZURE_OPENAI_API_KEY='...'")
    print("  export AZURE_OPENAI_ENDPOINT='https://your-resource.openai.azure.com/'")
    
    print("\nFor Google Gemini:")
    print("  export GOOGLE_API_KEY='...'")
    
    print("\nFor Ollama (local):")
    print("  1. Install from https://ollama.ai/")
    print("  2. Run: ollama serve")
    print("  3. Pull a model: ollama pull llama2")


if __name__ == "__main__":
    main()
