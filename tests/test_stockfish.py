"""
tests/test_stockfish.py

Comprehensive test suite for Stockfish integration with mocking for CI/CD safety.

All tests use mocking to avoid requiring the actual Stockfish binary.
This ensures tests pass in CI/CD pipelines without installation.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import chess

from engine.stockfish_client import StockfishClient, EvaluationResult, EngineMode


class TestStockfishClientInitialization(unittest.TestCase):
    """Test Stockfish client initialization and mode detection."""
    
    @patch('engine.stockfish_client.chess.engine.SimpleEngine')
    def test_initialization_active_mode(self, mock_engine):
        """Verify Active Mode when binary is found and engine starts."""
        with patch('engine.stockfish_client.shutil.which', return_value="/usr/bin/stockfish"):
            mock_engine_instance = MagicMock()
            mock_engine.popen_uci.return_value = mock_engine_instance
            
            client = StockfishClient()
            
            self.assertEqual(client.mode, EngineMode.ACTIVE)
            self.assertIsNotNone(client.engine)
    
    @patch('engine.stockfish_client.shutil.which', return_value=None)
    @patch('engine.stockfish_client.logger')
    def test_initialization_passive_mode_binary_missing(self, mock_logger, mock_which):
        """Verify Passive Mode when binary is unavailable."""
        client = StockfishClient()
        
        self.assertEqual(client.mode, EngineMode.PASSIVE)
        self.assertIsNone(client.engine)
    
    @patch('engine.stockfish_client.chess.engine.SimpleEngine')
    def test_initialization_passive_mode_engine_error(self, mock_engine):
        """Verify Passive Mode when engine initialization fails."""
        with patch('engine.stockfish_client.shutil.which', return_value="/usr/bin/stockfish"):
            mock_engine.popen_uci.side_effect = Exception("Engine startup failed")
            
            client = StockfishClient()
            
            self.assertEqual(client.mode, EngineMode.PASSIVE)


class TestPassiveMode(unittest.TestCase):
    """Test behavior in Passive Mode (graceful degradation)."""
    
    @patch('engine.stockfish_client.shutil.which', return_value=None)
    def test_passive_evaluation(self, mock_which):
        """Verify neutral evaluation in Passive Mode."""
        client = StockfishClient()
        board = chess.Board()
        
        result = client.evaluate(board)
        
        self.assertEqual(result.score_cp, 0)
        self.assertFalse(result.is_mate)
        self.assertIsNone(result.best_move)
        self.assertEqual(result.depth, 0)
    
    @patch('engine.stockfish_client.shutil.which', return_value=None)
    def test_passive_move_evaluation(self, mock_which):
        """Verify neutral move evaluation in Passive Mode."""
        client = StockfishClient()
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")
        
        result = client.evaluate_move(board, move)
        
        self.assertEqual(result["eval_change"], 0)
        self.assertEqual(result["move_quality"], "Unknown")
        self.assertFalse(result["is_best_move"])
    
    @patch('engine.stockfish_client.shutil.which', return_value=None)
    def test_passive_is_blunder(self, mock_which):
        """Verify is_blunder returns False in Passive Mode."""
        client = StockfishClient()
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")
        
        is_blunder = client.is_blunder(board, move)
        
        self.assertFalse(is_blunder)
    
    @patch('engine.stockfish_client.shutil.which', return_value=None)
    def test_passive_is_sacrifice(self, mock_which):
        """Verify is_sacrifice in Passive Mode uses heuristic."""
        client = StockfishClient()
        board = chess.Board("r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1")
        move = chess.Move.from_uci("b5c7")  # Queen exchange
        
        is_sacrifice = client.is_sacrifice(board, move)
        
        # Heuristic: returns False for non-captures or equal trades
        self.assertIsInstance(is_sacrifice, bool)


class TestActiveModeAnalysis(unittest.TestCase):
    """Test move analysis in Active Mode with mocking."""
    
    def setUp(self):
        """Set up mock engine for all tests."""
        self.patcher = patch('engine.stockfish_client.shutil.which')
        self.patcher_engine = patch('engine.stockfish_client.chess.engine.SimpleEngine')
        
        mock_which = self.patcher.start()
        mock_which.return_value = "/usr/bin/stockfish"
        
        self.mock_engine_class = self.patcher_engine.start()
        self.mock_engine = MagicMock()
        self.mock_engine_class.popen_uci.return_value = self.mock_engine
    
    def tearDown(self):
        """Clean up patches."""
        self.patcher.stop()
        self.patcher_engine.stop()
    
    def test_evaluate_starting_position(self):
        """Test evaluation of starting position."""
        # Mock engine response: starting position is about equal (+20cp for White)
        mock_score = MagicMock()
        mock_score.is_mate.return_value = False
        mock_score.white.return_value = MagicMock(cp=20)
        
        self.mock_engine.analyse.return_value = {
            "score": mock_score,
            "pv": [chess.Move.from_uci("e2e4")],
            "depth": 15,
            "time": 0.1,
        }
        
        client = StockfishClient()
        board = chess.Board()
        
        result = client.evaluate(board)
        
        self.assertEqual(result.score_cp, 20)
        self.assertFalse(result.is_mate)
        self.assertEqual(result.best_move, chess.Move.from_uci("e2e4"))
        self.assertEqual(result.depth, 15)
    
    def test_evaluate_move_good_move(self):
        """Test evaluation of a good move."""
        # Mock: before = +20cp, after = +50cp (good for player to move)
        before_score = MagicMock()
        before_score.is_mate.return_value = False
        before_score.white.return_value = MagicMock(cp=20)
        
        after_score = MagicMock()
        after_score.is_mate.return_value = False
        after_score.white.return_value = MagicMock(cp=50)
        
        self.mock_engine.analyse.side_effect = [
            {
                "score": before_score,
                "pv": [chess.Move.from_uci("d2d4")],  # Best move is d4, not e4
                "depth": 15,
                "time": 0.1,
            },
            {
                "score": after_score,
                "pv": [],
                "depth": 15,
                "time": 0.1,
            },
        ]
        
        client = StockfishClient()
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")
        
        result = client.evaluate_move(board, move)
        
        self.assertEqual(result["eval_change"], 30)  # +50 - +20
        self.assertEqual(result["move_quality"], "Good")
    
    def test_blunder_detection(self):
        """Test blunder detection (large eval drop)."""
        # Mock: before = +100cp (good), after = -250cp (disaster)
        before_score = MagicMock()
        before_score.is_mate.return_value = False
        before_score.white.return_value = MagicMock(cp=100)
        
        after_score = MagicMock()
        after_score.is_mate.return_value = False
        after_score.white.return_value = MagicMock(cp=-250)
        
        self.mock_engine.analyse.side_effect = [
            {
                "score": before_score,
                "pv": [chess.Move.from_uci("g1f3")],
                "depth": 15,
                "time": 0.1,
            },
            {
                "score": after_score,
                "pv": [],
                "depth": 15,
                "time": 0.1,
            },
        ]
        
        client = StockfishClient()
        board = chess.Board()
        bad_move = chess.Move.from_uci("e2e4")
        
        is_blunder = client.is_blunder(board, bad_move, threshold=300)
        
        self.assertTrue(is_blunder)
    
    def test_cache_performance(self):
        """Verify caching works and improves performance."""
        mock_score = MagicMock()
        mock_score.is_mate.return_value = False
        mock_score.white.return_value = MagicMock(cp=0)
        
        self.mock_engine.analyse.return_value = {
            "score": mock_score,
            "pv": [],
            "depth": 15,
            "time": 0.1,
        }
        
        client = StockfishClient()
        board = chess.Board()
        
        # First evaluation: cache miss
        client.evaluate(board)
        self.assertEqual(client._cache_misses, 1)
        self.assertEqual(client._cache_hits, 0)
        
        # Same position again: cache hit
        client.evaluate(board)
        self.assertEqual(client._cache_misses, 1)
        self.assertEqual(client._cache_hits, 1)
        
        # Check stats
        stats = client.get_cache_stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hit_rate"], 50.0)
    
    def test_cache_clear(self):
        """Verify cache can be cleared."""
        mock_score = MagicMock()
        mock_score.is_mate.return_value = False
        mock_score.white.return_value = MagicMock(cp=0)
        
        self.mock_engine.analyse.return_value = {
            "score": mock_score,
            "pv": [],
            "depth": 15,
            "time": 0.1,
        }
        
        client = StockfishClient()
        board = chess.Board()
        
        client.evaluate(board)
        client.clear_cache()
        
        self.assertEqual(len(client.analysis_cache), 0)
        self.assertEqual(client._cache_hits, 0)
        self.assertEqual(client._cache_misses, 0)


class TestContextManager(unittest.TestCase):
    """Test context manager support for safe cleanup."""
    
    @patch('engine.stockfish_client.shutil.which', return_value="/usr/bin/stockfish")
    @patch('engine.stockfish_client.chess.engine.SimpleEngine')
    def test_context_manager_cleanup(self, mock_engine_class, mock_which):
        """Verify context manager properly cleans up engine."""
        mock_engine = MagicMock()
        mock_engine_class.popen_uci.return_value = mock_engine
        
        with StockfishClient() as client:
            self.assertIsNotNone(client.engine)
        
        # After context exit, engine should be quit
        mock_engine.quit.assert_called_once()


class TestStockfishIntegration(unittest.TestCase):
    """Integration tests with real chess positions (using mocked engine)."""
    
    @patch('engine.stockfish_client.shutil.which', return_value="/usr/bin/stockfish")
    @patch('engine.stockfish_client.chess.engine.SimpleEngine')
    def test_fool_mate_detection(self, mock_engine_class, mock_which):
        """Test detection of Fool's Mate (f3 e6 g4 Qh5#)."""
        mock_engine = MagicMock()
        mock_engine_class.popen_uci.return_value = mock_engine
        
        # Mock: Fool's Mate is a loss for White
        mate_score = MagicMock()
        mate_score.is_mate.return_value = True
        mate_score.white.return_value = -1  # Negative means Black is winning (comparable int)
        mate_score.mate.return_value = -1  # Mate in 1 for Black (negative = opponent's mate)
        
        mock_engine.analyse.return_value = {
            "score": mate_score,
            "pv": [chess.Move.from_uci("h5f7")],
            "depth": 20,
            "time": 0.1,
        }
        
        client = StockfishClient()
        board = chess.Board()
        board.push_san("f3")
        board.push_san("e6")
        board.push_san("g4")
        
        # This position should be mate
        result = client.evaluate(board)
        
        self.assertTrue(result.is_mate)
        self.assertEqual(result.mate_in, -1)  # Negative = opponent (Black) has mate in 1
        self.assertTrue(result.score_cp < 0)  # Black is winning


if __name__ == "__main__":
    unittest.main()
