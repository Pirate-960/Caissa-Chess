"""
core/generator.py

The primary orchestrator: LLM → Move Parser → Legality Check → Board Update
This is the heartbeat of CAISSA.

Phase 2: Now includes self-correction loop for handling illegal moves.
"""

import json
import os
import re
import logging
from typing import Optional, Tuple, List
from dataclasses import asdict
import chess

from core.prompt_manager import PromptManager, GameContext, GameEra, GameTheme
from core.llm_provider import LLMProvider
from engine.legality import LegalityValidator

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class CaissaGenerator:
    """
    Main generation pipeline with self-correction loop:
    1. Prompt LLM to generate moves
    2. Parse moves
    3. Validate legality
    4. If illegal, provide feedback and retry
    5. Update board state
    6. Iterate until game complete or max retries exceeded
    
    Phase 2: Implements robust error handling and self-correction.
    """

    def __init__(
        self, 
        provider: Optional[LLMProvider] = None,
        max_retries: int = 3
    ):
        """
        Initialize the generator with dependency injection.
        
        Args:
            provider: LLMProvider instance (OpenAI, Mock, etc.)
                     Injected for testability and flexibility.
            max_retries: Maximum number of retry attempts for illegal moves
        """
        self.provider = provider
        self.prompt_manager = PromptManager()
        self.validator = LegalityValidator()
        self.max_retries = max_retries
        self.game_moves = []
        self.game_context = None
        self.conversation_history: List[Tuple[str, str]] = []
        
        logger.info(f"Initialized CaissaGenerator with max_retries={max_retries}")

    def set_provider(self, provider: LLMProvider) -> None:
        """
        Set the LLM provider after initialization.
        
        Args:
            provider: LLMProvider instance
        """
        self.provider = provider
        logger.info(f"Provider set: {type(provider).__name__}")

    def generate_game(self, context: GameContext) -> Tuple[bool, str, List[str]]:
        """
        Generate a complete chess game with self-correction loop.
        
        Phase 2: Implements iterative refinement:
        - If LLM generates illegal moves, we provide detailed feedback
        - LLM attempts correction up to max_retries times
        - Conversation history is maintained for context
        
        Args:
            context: GameContext with all generation parameters
        
        Returns:
            (success, pgn_or_error_message, moves_list)
        """
        self.game_context = context
        self.validator.reset_board()
        self.game_moves = []
        self.conversation_history = []
        
        logger.info(
            f"Generating game with style: {context.era.value}, "
            f"theme: {context.theme.value if context.theme else 'None'}, "
            f"aggression: {context.aggression_score}/10"
        )
        
        # Validate provider is configured
        if not self.provider:
            error_msg = "LLM provider not configured. Use set_provider() first."
            logger.error(error_msg)
            return False, error_msg, []
        
        # Build initial prompts
        system_prompt = self.prompt_manager.build_system_prompt(context)
        user_prompt = self.prompt_manager.build_user_prompt(context)
        
        # Self-correction loop
        retry_count = 0
        last_error = None
        
        while retry_count < self.max_retries:
            try:
                # Step A: Generate from LLM
                logger.debug(f"Calling LLM (attempt {retry_count + 1}/{self.max_retries})")
                
                # Append error feedback if this is a retry
                effective_user_prompt = user_prompt
                if last_error:
                    effective_user_prompt += f"\n\n### CORRECTION NEEDED\n{last_error}\n\nPlease generate a corrected version of the game."
                
                llm_response = self.provider.generate(
                    system_prompt=system_prompt,
                    user_prompt=effective_user_prompt,
                    temperature=0.8
                )
                
                # Store in conversation history
                self.conversation_history.append((effective_user_prompt, llm_response))
                
                # Step C: Clean the response
                pgn_text = self._clean_response(llm_response)
                if not pgn_text:
                    last_error = "ERROR: Could not extract valid PGN from your response. Ensure the game is in standard PGN format starting with [Event] or move notation."
                    retry_count += 1
                    logger.warning(f"Failed to extract PGN. Retrying (Attempt {retry_count}/{self.max_retries})...")
                    continue
                
                logger.debug(f"Cleaned PGN text: {pgn_text[:200]}...")  # Debug: show cleaned PGN
                
                # Step D: Validate legality
                is_valid, errors = self.validator.validate_game_pgn(pgn_text)
                
                logger.debug(f"Validation result: is_valid={is_valid}, errors={errors}")  # Debug
                
                if is_valid:
                    # Step E: Success!
                    logger.info("Game successfully generated.")
                    return True, pgn_text, self.game_moves
                
                else:
                    # Step F: Failure - construct detailed error feedback
                    last_error = self._construct_error_feedback(errors)
                    retry_count += 1
                    logger.warning(
                        f"Illegal move detected. Retrying (Attempt {retry_count}/{self.max_retries})..."
                    )
                    logger.debug(f"Error details: {last_error}")
            
            except Exception as e:
                error_msg = f"LLM API error: {type(e).__name__}: {str(e)}"
                logger.error(error_msg)
                return False, error_msg, []
        
        # Max retries exceeded
        final_error = f"Failed to generate valid game after {self.max_retries} attempts. Last error: {last_error}"
        logger.error(final_error)
        return False, final_error, []

    def _clean_response(self, response: str) -> Optional[str]:
        """
        Extract and clean PGN from potentially "chatty" LLM response.
        
        Handles:
        - Markdown code blocks (```pgn ... ```)
        - Preamble text ("Here is the game:")
        - Extracts content between [Event and game result
        
        Args:
            response: Raw LLM response
        
        Returns:
            Cleaned PGN string, or None if extraction fails
        """
        if not response:
            return None
        
        # Remove leading/trailing whitespace
        response = response.strip()
        
        # Try to extract from markdown code block first
        if "```" in response:
            # Pattern: ```pgn or just ```
            code_block_pattern = r"```(?:pgn)?\s*\n?(.*?)\n?```"
            match = re.search(code_block_pattern, response, re.DOTALL)
            if match:
                response = match.group(1).strip()
                logger.debug("Extracted PGN from markdown code block")
        
        # Try to find PGN content between [Event and result
        # PGN games start with headers like [Event "..."] and end with 1-0, 0-1, 1/2-1/2, or *
        # Use greedy matching to get all content including moves
        pgn_pattern = r'(\[Event.*(?:1-0|0-1|1/2-1/2|\*))'
        match = re.search(pgn_pattern, response, re.DOTALL)
        if match:
            pgn_text = match.group(1).strip()
            logger.debug(f"Extracted PGN game ({len(pgn_text)} chars)")
            return pgn_text
        
        # If no headers found, but there are moves, assume it's moves-only PGN
        # Look for chess move patterns
        if re.search(r'\d+\.\s*[a-h1-8NBRQK]', response):
            logger.debug("Found move notation without headers")
            return response
        
        logger.warning("Could not extract valid PGN from response")
        return None
    
    def _construct_error_feedback(self, errors: List[str]) -> str:
        """
        Construct detailed feedback for the LLM about what went wrong.
        
        Args:
            errors: List of validation errors from LegalityValidator
        
        Returns:
            Formatted error message for the LLM
        """
        feedback = "The game contains the following legal violations:\n\n"
        
        for i, error in enumerate(errors[:3], 1):  # Limit to first 3 errors
            feedback += f"{i}. {error}\n"
        
        if len(errors) > 3:
            feedback += f"\n... and {len(errors) - 3} more errors.\n"
        
        feedback += "\nPlease review the position carefully and ensure all moves are legal according to chess rules."
        
        return feedback

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

# Example usage
if __name__ == "__main__":
    from core.llm_provider import OpenAIProvider
    
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
    
    # Initialize generator with OpenAI provider
    try:
        provider = OpenAIProvider()
        generator = CaissaGenerator(provider=provider)
        
        print("✓ Generator initialized with OpenAI provider")
        print(f"✓ Prompt manager ready")
        print(f"✓ Legality validator ready")
        print()
        
        print("To generate a game, call:")
        print("  success, pgn, moves = generator.generate_game(context)")
    except ValueError as e:
        print(f"⚠ {e}")
        print("Set OPENAI_API_KEY environment variable to use OpenAI provider")

