"""
conftest.py for test_prebrief package.

Prevents PrebriefConfig from loading .env files during tests so that
mock.patch.dict(os.environ, {}, clear=True) works correctly.
"""
import pytest


@pytest.fixture(autouse=True)
def disable_prebrief_dotenv_loading():
    """Prevent _load_env from overriding mocked os.environ in tests."""
    import sys
    import importlib

    # Import the module under test
    if "scripts.run_prebrief" not in sys.modules:
        import scripts.run_prebrief  # noqa: F401

    from scripts.run_prebrief import PrebriefConfig
    PrebriefConfig._testing = True
    yield
    PrebriefConfig._testing = False
