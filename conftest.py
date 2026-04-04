"""
conftest.py

Root-level pytest configuration for the Caissa Chess Engine test suite.

Ensures:
- Project root is on sys.path (so ``log_manager``, ``config_manager``
  are importable from any test).
- ``--run-live`` flag is registered for live API tests.
- Logging setup does not pollute test output with log directory creation
  unless explicitly requested.
"""

import sys
import os
import pytest

# ── Ensure project root is importable ────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ── Pytest hooks ─────────────────────────────────────────────────────────────

def pytest_addoption(parser):
    """Register custom CLI flags."""
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run live API tests that require valid API keys.",
    )


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "live: mark test as requiring live API access (use --run-live to run).",
    )
    config.addinivalue_line(
        "markers",
        "asyncio: mark test as async test.",
    )


def pytest_collection_modifyitems(config, items):
    """Skip live tests unless --run-live is provided."""
    if config.getoption("--run-live"):
        return

    skip_live = pytest.mark.skip(reason="need --run-live option to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


# ── Async test support ─────────────────────────────────────────────────────
# If pytest-asyncio is installed, use it. Otherwise provide basic event loop.

try:
    import pytest_asyncio
    # pytest-asyncio will handle async tests
except ImportError:
    import asyncio
    
    @pytest.fixture
    def event_loop():
        """Create event loop for async tests."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()


# ── Silence log_manager auto-setup during tests ─────────────────────────────
# Prevent setup_logging() from creating real log directories during unit tests.
# Tests that need logging should call setup_logging() explicitly with a temp dir.

os.environ.setdefault("CAISSA_TEST_MODE", "1")
