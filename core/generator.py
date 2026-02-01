"""
core/generator.py

The primary orchestrator: LLM → Move Parser → Legality Check → Board Update
This is the heartbeat of CAISSA.
"""

import json
import os
from typing import Optional, Tuple
from dataclasses import asdict
import chess

from core.prompt_manager import PromptManager, GameContext, GameEra, GameTheme
from engine.legality import LegalityValidator


class CaissaGenerator:
    """
    Main generation pipeline:
    1. Prompt LLM to generate moves
    2. Parse moves
    3. Validate legality
    4. Update board state
    5. Iterate until game complete or error
    """

    def __init__(self, llm_client=None):
        """
        Initialize the generator.
        
        Args:
            llm_client: LLM API client (OpenAI, Anthropic, etc).
                       If None, will be initialized on first use.
        """
        self.prompt_manager = PromptManager()
        self.validator = LegalityValidator()
        self.llm_client = llm_client
        self.game_moves = []
        self.game_context = None

    def set_llm_client(self, client):
        """Set the LLM client after initialization."""
        self.llm_client = client

    def generate_game(self, context: GameContext) -> Tuple[bool, str, list]:
        """
        Generate a complete chess game.
        
        Args:
            context: GameContext with all parameters
        
        Returns:
            (success, pgn_or_error, moves_list)
        """
        self.game_context = context
        self.validator.reset_board()
        self.game_moves = []
        
        # Step 1: Build prompts
        system_prompt = self.prompt_manager.build_system_prompt(context)
        user_prompt = self.prompt_manager.build_user_prompt(context)
        
        # Step 2: Call LLM (requires client setup)
        if not self.llm_client:
            return False, "LLM client not configured", []
        
        try:
            llm_response = self.llm_client.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.8,  # Creative but not wild
            )
        except Exception as e:
            return False, f"LLM API error: {str(e)}", []
        
        # Step 3: Parse PGN from response
        pgn_text = self._extract_pgn_from_response(llm_response)
        if not pgn_text:
            return False, "Could not extract PGN from LLM response", []
        
        # Step 4: Validate legality
        is_valid, errors = self.validator.validate_game_pgn(pgn_text)
        if not is_valid:
            return False, f"Illegal move detected: {errors[0]}", []
        
        return True, pgn_text, self.game_moves

    def _extract_pgn_from_response(self, response: str) -> Optional[str]:
        """
        Extract PGN from LLM response.
        LLM might wrap it in markdown code blocks or add commentary.
        """
        # Try to find PGN block
        if "```" in response:
            # Extract from markdown code block
            start = response.find("```") + 3
            end = response.find("```", start)
            if start > 2 and end > start:
                return response[start:end].strip()
        
        # Otherwise, return the whole response
        # (assuming LLM follows instructions)
        return response.strip() if response else None

    def validate_and_continue(self, move_str: str) -> Tuple[bool, str]:
        """
        Validate a single move and add it to the game if legal.
        Used for step-by-step generation if needed.
        
        Args:
            move_str: Move in algebraic notation
        
        Returns:
            (is_legal, message)
        """
        report = self.validator.parse_and_validate_move(move_str)
        
        if not report.is_legal:
            return False, f"Illegal: {report.error_message}"
        
        self.validator.apply_move(report.move_object)
        self.game_moves.append(move_str)
        
        return True, f"Move accepted: {move_str}"

    def export_to_pgn(self, filename: str, headers: Optional[dict] = None) -> bool:
        """Export the generated game to PGN file."""
        try:
            with open(filename, "w") as f:
                # Write headers
                if headers:
                    for key, value in headers.items():
                        f.write(f'[{key} "{value}"]\n')
                
                f.write('\n')
                
                # Write moves
                move_text = ""
                for i, move in enumerate(self.game_moves, 1):
                    if i % 2 == 1:  # White's move
                        move_text += f"{(i + 1) // 2}. {move} "
                    else:  # Black's move
                        move_text += f"{move} "
                
                f.write(move_text.rstrip() + " 1-0\n")
            
            return True
        except Exception as e:
            print(f"Error exporting to PGN: {str(e)}")
            return False


class SimpleOpenAIClient:
    """
    Simple wrapper around OpenAI API.
    Requires OPENAI_API_KEY environment variable.
    """
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("openai package required. Install with: pip install openai")
    
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.8,
        max_tokens: int = 4000,
    ) -> str:
        """Call OpenAI API and return the response."""
        response = self.client.chat.completions.create(
            model="gpt-4-turbo",
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content


# Example usage
if __name__ == "__main__":
    # Set up context
    context = GameContext(
        era=GameEra.ROMANTIC,
        theme=GameTheme.QUEEN_SACRIFICE,
        white_player="Caissa the Bold",
        black_player="Caissa the Sage",
        aggression_score=7,
        chaos_score=5,
        depth=40,
    )
    
    print("=" * 60)
    print("CAISSA GENERATOR - Example Usage")
    print("=" * 60)
    print(f"Configuration: {context.era.value}, Theme: {context.theme.value if context.theme else 'None'}")
    print(f"Aggression: {context.aggression_score}/10, Chaos: {context.chaos_score}/10")
    print()
    
    # Initialize generator (without LLM client for demo)
    generator = CaissaGenerator()
    
    print("✓ Generator initialized")
    print(f"✓ Prompt manager ready")
    print(f"✓ Legality validator ready")
    print()
    
    print("To generate a game, call:")
    print("  generator.set_llm_client(SimpleOpenAIClient())")
    print("  success, pgn, moves = generator.generate_game(context)")
