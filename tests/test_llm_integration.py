"""
tests/test_llm_integration.py

Comprehensive test suite for Phase 2: LLM Integration.
Tests the self-correction loop without requiring API calls.
"""

import pytest
from typing import List

from core.llm_provider import LLMProvider, MockProvider
from core.generator import CaissaGenerator
from core.prompt_manager import GameContext, GameEra, GameTheme


# Sample valid PGN for testing - Simple Scholar's Mate
VALID_PGN = """[Event "Test Game"]
[Site "Test"]
[Date "2026.02.02"]
[Round "1"]
[White "Test White"]
[Black "Test Black"]
[Result "1-0"]

1. e4 e5 2. Bc4 Nc6 3. Qh5 Nf6 4. Qxf7# 1-0"""

# PGN with an illegal move (Qxe5 - queen cannot reach e5 from d1)
INVALID_PGN_ILLEGAL_MOVE = """[Event "Test"]
[White "Test White"]
[Black "Test Black"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. Qxe5 *"""

# Completely malformed PGN
GARBAGE_PGN = """This is not a valid PGN at all! 
Just random text with no chess notation.
Hello world! 123 abc xyz"""


class TestMockProvider:
    """Test the MockProvider functionality."""
    
    def test_mock_provider_single_response(self):
        """Test MockProvider returns single response correctly."""
        provider = MockProvider(responses=["Response 1"])
        
        result = provider.generate("system", "user", 0.7)
        assert result == "Response 1"
        assert provider.call_count == 1
    
    def test_mock_provider_multiple_responses(self):
        """Test MockProvider cycles through multiple responses."""
        provider = MockProvider(responses=["First", "Second", "Third"])
        
        assert provider.generate("", "", 0.5) == "First"
        assert provider.generate("", "", 0.5) == "Second"
        assert provider.generate("", "", 0.5) == "Third"
        assert provider.call_count == 3
    
    def test_mock_provider_exhaustion(self):
        """Test MockProvider raises error when exhausted."""
        provider = MockProvider(responses=["Only one"])
        
        provider.generate("", "", 0.5)
        
        with pytest.raises(IndexError):
            provider.generate("", "", 0.5)
    
    def test_mock_provider_reset(self):
        """Test MockProvider reset functionality."""
        provider = MockProvider(responses=["A", "B"])
        
        provider.generate("", "", 0.5)
        provider.generate("", "", 0.5)
        assert provider.call_count == 2
        
        provider.reset()
        assert provider.call_count == 0
        assert provider.generate("", "", 0.5) == "A"


class TestPerfectGeneration:
    """Test Case 1: Perfect generation on first try."""
    
    def test_perfect_generation(self):
        """
        Scenario: LLM returns valid PGN immediately.
        Expected: Success on first attempt.
        """
        # Arrange
        provider = MockProvider(responses=[VALID_PGN])
        generator = CaissaGenerator(provider=provider, max_retries=3)
        
        context = GameContext(
            era=GameEra.ROMANTIC,
            theme=GameTheme.QUEEN_SACRIFICE,
            white_player="Test White",
            black_player="Test Black"
        )
        
        # Act
        success, result, moves = generator.generate_game(context)
        
        # Assert
        assert success is True, f"Expected success, got: {result}"
        assert provider.call_count == 1, "Should only call LLM once"
        assert "[Event" in result, "Result should contain PGN headers"
        assert "1-0" in result, "Result should contain game result"


class TestSelfCorrection:
    """Test Case 2: Self-correction loop."""
    
    def test_self_correction_one_retry(self):
        """
        Scenario: First response is invalid, second is valid.
        Expected: Success after one retry.
        """
        # Arrange
        provider = MockProvider(responses=[
            INVALID_PGN_ILLEGAL_MOVE,  # First attempt: illegal
            VALID_PGN                   # Second attempt: valid
        ])
        generator = CaissaGenerator(provider=provider, max_retries=3)
        
        context = GameContext(
            era=GameEra.ROMANTIC,
            white_player="Test White",
            black_player="Test Black"
        )
        
        # Act
        success, result, moves = generator.generate_game(context)
        
        # Assert
        assert success is True, f"Expected success after retry, got: {result}"
        assert provider.call_count == 2, "Should call LLM twice (1 failure + 1 success)"
        assert "[Event" in result, "Final result should be valid PGN"
    
    def test_self_correction_conversation_history(self):
        """
        Verify that conversation history is maintained during retries.
        """
        # Arrange
        provider = MockProvider(responses=[
            GARBAGE_PGN,
            VALID_PGN
        ])
        generator = CaissaGenerator(provider=provider, max_retries=3)
        
        context = GameContext(era=GameEra.ROMANTIC)
        
        # Act
        success, result, moves = generator.generate_game(context)
        
        # Assert
        assert success is True
        assert len(generator.conversation_history) == 2, "Should track both attempts"
        
        # First conversation should be initial prompt
        first_user_prompt, first_response = generator.conversation_history[0]
        assert "Generate" in first_user_prompt or "game" in first_user_prompt
        assert first_response == GARBAGE_PGN
        
        # Second conversation should include correction feedback
        second_user_prompt, second_response = generator.conversation_history[1]
        assert "CORRECTION" in second_user_prompt or "ERROR" in second_user_prompt
        assert second_response == VALID_PGN


class TestMaxRetriesExceeded:
    """Test Case 3: Max retries exceeded."""
    
    def test_max_retries_exceeded(self):
        """
        Scenario: LLM consistently returns garbage.
        Expected: Failure after max retries.
        """
        # Arrange
        provider = MockProvider(responses=[
            GARBAGE_PGN,
            GARBAGE_PGN,
            GARBAGE_PGN
        ])
        generator = CaissaGenerator(provider=provider, max_retries=3)
        
        context = GameContext(era=GameEra.ROMANTIC)
        
        # Act
        success, result, moves = generator.generate_game(context)
        
        # Assert
        assert success is False, "Should fail after max retries"
        assert provider.call_count == 3, "Should attempt exactly max_retries times"
        assert "Failed to generate valid game" in result or "attempts" in result
    
    def test_max_retries_with_illegal_moves(self):
        """
        Scenario: LLM consistently returns illegal moves.
        Expected: Failure with detailed error message.
        """
        # Arrange
        provider = MockProvider(responses=[
            INVALID_PGN_ILLEGAL_MOVE,
            INVALID_PGN_ILLEGAL_MOVE,
            INVALID_PGN_ILLEGAL_MOVE
        ])
        generator = CaissaGenerator(provider=provider, max_retries=3)
        
        context = GameContext(era=GameEra.ROMANTIC)
        
        # Act
        success, result, moves = generator.generate_game(context)
        
        # Assert
        assert success is False
        assert provider.call_count == 3
        assert "violation" in result or "illegal" in result.lower()


class TestPGNCleaning:
    """Test the _clean_response method."""
    
    def test_clean_markdown_code_block(self):
        """Test extraction from markdown code blocks."""
        generator = CaissaGenerator()
        
        # With ```pgn marker
        response_pgn = f"Here is your game:\n```pgn\n{VALID_PGN}\n```\nEnjoy!"
        cleaned = generator._clean_response(response_pgn)
        assert cleaned is not None
        assert "[Event" in cleaned
        assert "```" not in cleaned
        
        # With just ``` marker
        response_generic = f"Here is your game:\n```\n{VALID_PGN}\n```"
        cleaned = generator._clean_response(response_generic)
        assert cleaned is not None
        assert "[Event" in cleaned
    
    def test_clean_with_preamble(self):
        """Test extraction when LLM adds commentary."""
        generator = CaissaGenerator()
        
        response = f"""I've created a beautiful romantic game for you!

{VALID_PGN}

This game features a stunning queen sacrifice!"""
        
        cleaned = generator._clean_response(response)
        assert cleaned is not None
        assert "[Event" in cleaned
        assert "beautiful romantic" not in cleaned
    
    def test_clean_moves_only(self):
        """Test handling moves without headers."""
        generator = CaissaGenerator()
        
        response = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5"
        cleaned = generator._clean_response(response)
        assert cleaned is not None
        assert "1. e4" in cleaned
    
    def test_clean_empty_response(self):
        """Test handling empty or None responses."""
        generator = CaissaGenerator()
        
        assert generator._clean_response(None) is None
        assert generator._clean_response("") is None
        assert generator._clean_response("   ") is None


class TestGeneratorConfiguration:
    """Test generator initialization and configuration."""
    
    def test_generator_without_provider(self):
        """Test that generator fails gracefully without provider."""
        generator = CaissaGenerator()
        context = GameContext(era=GameEra.ROMANTIC)
        
        success, result, moves = generator.generate_game(context)
        
        assert success is False
        assert "provider not configured" in result.lower()
    
    def test_generator_set_provider(self):
        """Test setting provider after initialization."""
        generator = CaissaGenerator()
        provider = MockProvider(responses=[VALID_PGN])
        
        generator.set_provider(provider)
        
        context = GameContext(era=GameEra.ROMANTIC)
        success, result, moves = generator.generate_game(context)
        
        assert success is True
    
    def test_generator_custom_max_retries(self):
        """Test custom max_retries setting."""
        provider = MockProvider(responses=[GARBAGE_PGN] * 5)
        generator = CaissaGenerator(provider=provider, max_retries=5)
        
        context = GameContext(era=GameEra.ROMANTIC)
        success, result, moves = generator.generate_game(context)
        
        assert success is False
        assert provider.call_count == 5


class TestErrorFeedback:
    """Test error feedback construction."""
    
    def test_construct_error_feedback_single_error(self):
        """Test feedback for single error."""
        generator = CaissaGenerator()
        errors = ["Move 4. Bxe5 is illegal: no piece on e5"]
        
        feedback = generator._construct_error_feedback(errors)
        
        assert "legal violation" in feedback.lower()
        assert "Bxe5" in feedback
    
    def test_construct_error_feedback_multiple_errors(self):
        """Test feedback limits to first 5 errors."""
        generator = CaissaGenerator()
        errors = [
            "Error 1",
            "Error 2",
            "Error 3",
            "Error 4",
            "Error 5",
            "Error 6",
            "Error 7",
        ]
        
        feedback = generator._construct_error_feedback(errors)
        
        assert "Error 1" in feedback
        assert "Error 2" in feedback
        assert "Error 3" in feedback
        assert "Error 4" in feedback
        assert "Error 5" in feedback
        assert "2 more errors" in feedback  # 7 - 5 = 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
