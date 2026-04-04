"""
tests/test_spinner.py

Tests for the Spinner animated-progress class (main.py).

The Spinner is a context manager that runs a background daemon thread
with a braille animation and elapsed-time counter.

Covers:
- Context manager protocol (__enter__ / __exit__)
- Thread lifecycle (starts on enter, stops on exit)
- Public attributes
- No-crash on rapid enter/exit
"""

import time
import unittest
from unittest.mock import patch
from io import StringIO

# conftest.py sets CAISSA_TEST_MODE=1 before collection, so main.py
# skips its stdout replacement and setup_logging() at import time.
from main import Spinner


class TestSpinnerAttributes(unittest.TestCase):
    """Tests for Spinner initialisation and public attributes."""

    def test_default_message(self):
        """Default message should be 'Working'."""
        s = Spinner()
        self.assertEqual(s._msg, "Working")

    def test_custom_message(self):
        """Custom message should be stored."""
        s = Spinner("Loading models")
        self.assertEqual(s._msg, "Loading models")

    def test_default_interval(self):
        """Default interval should be 0.1 s."""
        s = Spinner()
        self.assertAlmostEqual(s._interval, 0.1)

    def test_frames_non_empty(self):
        """There should be at least one animation frame."""
        self.assertGreater(len(Spinner._FRAMES), 0)


class TestSpinnerContextManager(unittest.TestCase):
    """Tests for the context-manager lifecycle."""

    def test_enter_returns_self(self):
        """__enter__ should return the Spinner instance."""
        s = Spinner("test")
        with patch("sys.stdout", new_callable=StringIO):
            with s as ctx:
                self.assertIs(ctx, s)

    def test_thread_starts_on_enter(self):
        """A daemon thread should be running inside the with block."""
        s = Spinner("test", interval=0.05)
        with patch("sys.stdout", new_callable=StringIO):
            with s:
                self.assertIsNotNone(s._thread)
                self.assertTrue(s._thread.is_alive())

    def test_thread_stops_on_exit(self):
        """Thread should be stopped after the with block exits."""
        s = Spinner("test", interval=0.05)
        with patch("sys.stdout", new_callable=StringIO):
            with s:
                pass
        # Give the thread a moment to finish
        time.sleep(0.15)
        self.assertTrue(s._stop.is_set())
        self.assertFalse(s._thread.is_alive())

    def test_elapsed_time_tracked(self):
        """_start_time should be set to a positive float."""
        s = Spinner("test", interval=0.05)
        with patch("sys.stdout", new_callable=StringIO):
            with s:
                self.assertGreater(s._start_time, 0)

    def test_rapid_enter_exit(self):
        """Rapid creation and exit should not raise."""
        with patch("sys.stdout", new_callable=StringIO):
            for _ in range(10):
                with Spinner("fast", interval=0.01):
                    pass

    def test_exception_inside_with(self):
        """Spinner should clean up even when the body raises."""
        s = Spinner("test", interval=0.05)
        with patch("sys.stdout", new_callable=StringIO):
            try:
                with s:
                    raise ValueError("boom")
            except ValueError:
                pass
        time.sleep(0.15)
        self.assertTrue(s._stop.is_set())
        self.assertFalse(s._thread.is_alive())


class TestSpinnerOutput(unittest.TestCase):
    """Tests verifying that the spinner writes output to stdout."""

    def test_writes_message(self):
        """The spinner should write its message to stdout."""
        captured = StringIO()
        with patch("sys.stdout", captured):
            with Spinner("Loading", interval=0.05):
                time.sleep(0.2)  # Allow a few frames to render

        output = captured.getvalue()
        self.assertIn("Loading", output)

    def test_clears_line_on_exit(self):
        """The spinner should write a clear-line escape on exit."""
        captured = StringIO()
        with patch("sys.stdout", captured):
            with Spinner("test", interval=0.05):
                time.sleep(0.1)

        output = captured.getvalue()
        # \r\033[K is the line-clear sequence
        self.assertIn("\r\033[K", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
