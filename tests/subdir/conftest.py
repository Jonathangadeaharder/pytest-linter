"""
Subdirectory conftest that shadows fixtures from parent.
"""

import pytest


@pytest.fixture
def used_fixture():
    """BAD: Shadows the used_fixture from parent conftest (PYTEST-FIX-004)."""
    return {"shadowed": "data"}


@pytest.fixture
def local_fixture():
    """GOOD: A fixture only defined in this subdirectory."""
    return {"local": True}
