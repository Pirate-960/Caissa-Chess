"""
tests/test_phase32_metrics.py

Tests for Phase 3.2 metrics and benchmarking features.

Tests cover:
- TokenUsage dataclass
- CostEstimate dataclass
- GenerationMetrics dataclass
- ProviderMetrics aggregation
- Cost estimation functions
- Token estimation functions
- Benchmark dataclasses
"""

import unittest
from dataclasses import asdict

from core.llm_provider import (
    TokenUsage,
    CostEstimate,
    GenerationMetrics,
    ProviderMetrics,
    CostTier,
    estimate_cost,
    estimate_tokens,
    MODEL_PRICING,
)


class TestTokenUsage(unittest.TestCase):
    """Tests for TokenUsage dataclass."""
    
    def test_creation(self):
        """Test TokenUsage creation."""
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        
        self.assertEqual(usage.input_tokens, 100)
        self.assertEqual(usage.output_tokens, 50)
    
    def test_total_tokens(self):
        """Test total_tokens property."""
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        
        self.assertEqual(usage.total_tokens, 150)
    
    def test_to_dict(self):
        """Test to_dict method."""
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        result = usage.to_dict()
        
        self.assertEqual(result["input_tokens"], 100)
        self.assertEqual(result["output_tokens"], 50)
        self.assertEqual(result["total_tokens"], 150)
    
    def test_default_values(self):
        """Test default values."""
        usage = TokenUsage()
        
        self.assertEqual(usage.input_tokens, 0)
        self.assertEqual(usage.output_tokens, 0)
        self.assertEqual(usage.total_tokens, 0)


class TestCostEstimate(unittest.TestCase):
    """Tests for CostEstimate dataclass."""
    
    def test_creation(self):
        """Test CostEstimate creation."""
        cost = CostEstimate(input_cost_usd=0.01, output_cost_usd=0.03)
        
        self.assertEqual(cost.input_cost_usd, 0.01)
        self.assertEqual(cost.output_cost_usd, 0.03)
    
    def test_total_cost(self):
        """Test total_cost_usd property."""
        cost = CostEstimate(input_cost_usd=0.01, output_cost_usd=0.03)
        
        self.assertAlmostEqual(cost.total_cost_usd, 0.04)
    
    def test_to_dict(self):
        """Test to_dict method."""
        cost = CostEstimate(input_cost_usd=0.01, output_cost_usd=0.03)
        result = cost.to_dict()
        
        self.assertEqual(result["input_cost_usd"], 0.01)
        self.assertEqual(result["output_cost_usd"], 0.03)
        self.assertAlmostEqual(result["total_cost_usd"], 0.04)


class TestGenerationMetrics(unittest.TestCase):
    """Tests for GenerationMetrics dataclass."""
    
    def test_creation(self):
        """Test GenerationMetrics creation."""
        metrics = GenerationMetrics(
            latency_ms=150.0,
            model="gpt-4o-mini",
            provider="OpenAI",
            success=True,
        )
        
        self.assertEqual(metrics.latency_ms, 150.0)
        self.assertEqual(metrics.model, "gpt-4o-mini")
        self.assertTrue(metrics.success)
    
    def test_with_tokens_and_cost(self):
        """Test with token usage and cost."""
        metrics = GenerationMetrics(
            latency_ms=150.0,
            tokens=TokenUsage(input_tokens=100, output_tokens=50),
            cost=CostEstimate(input_cost_usd=0.01, output_cost_usd=0.03),
            model="gpt-4o-mini",
            provider="OpenAI",
        )
        
        self.assertEqual(metrics.tokens.total_tokens, 150)
        self.assertAlmostEqual(metrics.cost.total_cost_usd, 0.04)
    
    def test_to_dict(self):
        """Test to_dict method."""
        metrics = GenerationMetrics(
            latency_ms=150.0,
            model="gpt-4o-mini",
            provider="OpenAI",
        )
        result = metrics.to_dict()
        
        self.assertEqual(result["latency_ms"], 150.0)
        self.assertEqual(result["model"], "gpt-4o-mini")
        self.assertIn("timestamp", result)
    
    def test_error_metrics(self):
        """Test metrics for failed generation."""
        metrics = GenerationMetrics(
            latency_ms=50.0,
            model="gpt-4o-mini",
            provider="OpenAI",
            success=False,
            error_message="Rate limit exceeded",
        )
        
        self.assertFalse(metrics.success)
        self.assertEqual(metrics.error_message, "Rate limit exceeded")


class TestProviderMetrics(unittest.TestCase):
    """Tests for ProviderMetrics aggregation."""
    
    def setUp(self):
        """Set up test metrics."""
        self.metrics = ProviderMetrics(
            provider_name="OpenAI",
            model="gpt-4o-mini",
        )
    
    def test_initial_state(self):
        """Test initial state."""
        self.assertEqual(self.metrics.total_calls, 0)
        self.assertEqual(self.metrics.successful_calls, 0)
        self.assertEqual(self.metrics.failed_calls, 0)
    
    def test_record_successful_call(self):
        """Test recording a successful call."""
        gen_metrics = GenerationMetrics(
            latency_ms=150.0,
            tokens=TokenUsage(input_tokens=100, output_tokens=50),
            cost=CostEstimate(input_cost_usd=0.01, output_cost_usd=0.03),
            model="gpt-4o-mini",
            provider="OpenAI",
            success=True,
        )
        
        self.metrics.record_call(gen_metrics)
        
        self.assertEqual(self.metrics.total_calls, 1)
        self.assertEqual(self.metrics.successful_calls, 1)
        self.assertEqual(self.metrics.failed_calls, 0)
        self.assertEqual(self.metrics.total_input_tokens, 100)
        self.assertEqual(self.metrics.total_output_tokens, 50)
    
    def test_record_failed_call(self):
        """Test recording a failed call."""
        gen_metrics = GenerationMetrics(
            latency_ms=50.0,
            model="gpt-4o-mini",
            provider="OpenAI",
            success=False,
            error_message="Error",
        )
        
        self.metrics.record_call(gen_metrics)
        
        self.assertEqual(self.metrics.total_calls, 1)
        self.assertEqual(self.metrics.successful_calls, 0)
        self.assertEqual(self.metrics.failed_calls, 1)
    
    def test_success_rate(self):
        """Test success rate calculation."""
        # Record 3 successful, 1 failed
        for _ in range(3):
            self.metrics.record_call(GenerationMetrics(
                latency_ms=100.0, success=True
            ))
        self.metrics.record_call(GenerationMetrics(
            latency_ms=50.0, success=False
        ))
        
        self.assertAlmostEqual(self.metrics.success_rate, 0.75)
    
    def test_avg_latency(self):
        """Test average latency calculation."""
        self.metrics.record_call(GenerationMetrics(
            latency_ms=100.0, success=True
        ))
        self.metrics.record_call(GenerationMetrics(
            latency_ms=200.0, success=True
        ))
        
        self.assertAlmostEqual(self.metrics.avg_latency_ms, 150.0)
    
    def test_min_max_latency(self):
        """Test min/max latency tracking."""
        self.metrics.record_call(GenerationMetrics(
            latency_ms=100.0, success=True
        ))
        self.metrics.record_call(GenerationMetrics(
            latency_ms=200.0, success=True
        ))
        self.metrics.record_call(GenerationMetrics(
            latency_ms=150.0, success=True
        ))
        
        self.assertEqual(self.metrics.min_latency_ms, 100.0)
        self.assertEqual(self.metrics.max_latency_ms, 200.0)
    
    def test_reset(self):
        """Test metrics reset."""
        self.metrics.record_call(GenerationMetrics(
            latency_ms=100.0, success=True,
            tokens=TokenUsage(input_tokens=100, output_tokens=50),
        ))
        
        self.assertEqual(self.metrics.total_calls, 1)
        
        self.metrics.reset()
        
        self.assertEqual(self.metrics.total_calls, 0)
        self.assertEqual(self.metrics.total_input_tokens, 0)
    
    def test_to_dict(self):
        """Test to_dict method."""
        self.metrics.record_call(GenerationMetrics(
            latency_ms=100.0, success=True,
            tokens=TokenUsage(input_tokens=100, output_tokens=50),
            cost=CostEstimate(input_cost_usd=0.01, output_cost_usd=0.03),
        ))
        
        result = self.metrics.to_dict()
        
        self.assertEqual(result["provider_name"], "OpenAI")
        self.assertEqual(result["total_calls"], 1)
        self.assertEqual(result["total_tokens"], 150)


class TestCostEstimation(unittest.TestCase):
    """Tests for cost estimation functions."""
    
    def test_estimate_cost_gpt4o_mini(self):
        """Test cost estimation for GPT-4o-mini."""
        cost = estimate_cost("gpt-4o-mini", 1000, 500)
        
        # GPT-4o-mini: $0.15/1M input, $0.60/1M output
        expected_input = (1000 / 1_000_000) * 0.15
        expected_output = (500 / 1_000_000) * 0.60
        
        self.assertAlmostEqual(cost.input_cost_usd, expected_input, places=8)
        self.assertAlmostEqual(cost.output_cost_usd, expected_output, places=8)
    
    def test_estimate_cost_claude_haiku(self):
        """Test cost estimation for Claude Haiku."""
        cost = estimate_cost("claude-3-haiku", 1000, 500)
        
        # Claude Haiku: $0.25/1M input, $1.25/1M output
        expected_input = (1000 / 1_000_000) * 0.25
        expected_output = (500 / 1_000_000) * 1.25
        
        self.assertAlmostEqual(cost.input_cost_usd, expected_input, places=8)
        self.assertAlmostEqual(cost.output_cost_usd, expected_output, places=8)
    
    def test_estimate_cost_ollama(self):
        """Test cost estimation for Ollama (free)."""
        cost = estimate_cost("llama2", 1000, 500)
        
        self.assertEqual(cost.input_cost_usd, 0.0)
        self.assertEqual(cost.output_cost_usd, 0.0)
    
    def test_estimate_cost_unknown_model(self):
        """Test cost estimation for unknown model (defaults to GPT-4o-mini)."""
        cost = estimate_cost("unknown-model-xyz", 1000, 500)
        
        # Should use default pricing
        self.assertGreater(cost.total_cost_usd, 0)


class TestTokenEstimation(unittest.TestCase):
    """Tests for token estimation functions."""
    
    def test_estimate_tokens_short(self):
        """Test token estimation for short text."""
        tokens = estimate_tokens("Hello world")
        
        # ~4 chars per token, "Hello world" = 11 chars = ~2-3 tokens
        self.assertGreater(tokens, 0)
        self.assertLess(tokens, 10)
    
    def test_estimate_tokens_long(self):
        """Test token estimation for longer text."""
        long_text = "This is a longer piece of text that should have more tokens. " * 10
        tokens = estimate_tokens(long_text)
        
        self.assertGreater(tokens, 50)
    
    def test_estimate_tokens_empty(self):
        """Test token estimation for empty text."""
        tokens = estimate_tokens("")
        
        self.assertEqual(tokens, 0)


class TestModelPricing(unittest.TestCase):
    """Tests for MODEL_PRICING dictionary."""
    
    def test_openai_models_present(self):
        """Test that OpenAI models are present."""
        self.assertIn("gpt-4-turbo", MODEL_PRICING)
        self.assertIn("gpt-4o", MODEL_PRICING)
        self.assertIn("gpt-4o-mini", MODEL_PRICING)
    
    def test_anthropic_models_present(self):
        """Test that Anthropic models are present."""
        self.assertIn("claude-3-opus", MODEL_PRICING)
        self.assertIn("claude-3-sonnet", MODEL_PRICING)
        self.assertIn("claude-3-haiku", MODEL_PRICING)
    
    def test_google_models_present(self):
        """Test that Google models are present."""
        self.assertIn("gemini-pro", MODEL_PRICING)
        self.assertIn("gemini-1.5-pro", MODEL_PRICING)
    
    def test_local_models_are_free(self):
        """Test that local models have zero cost."""
        self.assertEqual(MODEL_PRICING["ollama"], (0.0, 0.0))
        self.assertEqual(MODEL_PRICING["llama2"], (0.0, 0.0))
    
    def test_pricing_format(self):
        """Test that all prices are tuples of (input, output)."""
        for model, pricing in MODEL_PRICING.items():
            self.assertIsInstance(pricing, tuple)
            self.assertEqual(len(pricing), 2)
            self.assertIsInstance(pricing[0], float)
            self.assertIsInstance(pricing[1], float)


class TestCostTier(unittest.TestCase):
    """Tests for CostTier enum."""
    
    def test_all_tiers_defined(self):
        """Test that all cost tiers are defined."""
        expected_tiers = ["FREE", "BUDGET", "STANDARD", "PREMIUM"]
        
        for tier in expected_tiers:
            self.assertTrue(hasattr(CostTier, tier))
    
    def test_tier_values(self):
        """Test tier string values."""
        self.assertEqual(CostTier.FREE.value, "free")
        self.assertEqual(CostTier.BUDGET.value, "budget")
        self.assertEqual(CostTier.STANDARD.value, "standard")
        self.assertEqual(CostTier.PREMIUM.value, "premium")


if __name__ == "__main__":
    unittest.main(verbosity=2)
