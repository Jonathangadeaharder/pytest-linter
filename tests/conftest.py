"""
Conftest file with fixture definitions for testing Category 2 and 3 rules.
"""

import pytest


# ============================================================================
# Category 2: Fixture Definition Smells
# ============================================================================


@pytest.fixture(autouse=True)
def bad_autouse_fixture():
    """BAD: Using autouse=True (PYTEST-FIX-001)."""
    print("This fixture runs automatically for all tests")
    yield
    print("Cleanup")


# ============================================================================
# Category 3: Fixture Interaction Smells
# ============================================================================


@pytest.fixture(scope="session")
def session_db_connection():
    """GOOD: Session-scoped database connection."""
    connection = {"host": "localhost", "connected": True}
    yield connection
    connection["connected"] = False


@pytest.fixture(scope="function")
def function_scoped_user():
    """GOOD: Function-scoped user fixture."""
    return {"id": 1, "name": "Test User"}


@pytest.fixture(scope="session")
def bad_session_fixture(function_scoped_user):
    """BAD: Session fixture depending on function fixture (PYTEST-FIX-003)."""
    # This is invalid: session scope cannot depend on function scope
    return {"user": function_scoped_user, "session_id": "abc123"}


@pytest.fixture(scope="session")
def bad_mutable_session_fixture():
    """BAD: Session fixture returning mutable object (PYTEST-FIX-006)."""
    # Returning a mutable list that could be modified by tests
    return []


@pytest.fixture(scope="session")
def bad_mutable_dict_session_fixture():
    """BAD: Session fixture returning mutable dict (PYTEST-FIX-006)."""
    # Returning a mutable dict that could be modified by tests
    return {}


@pytest.fixture
def unused_fixture():
    """BAD: This fixture is never used (PYTEST-FIX-005)."""
    return {"data": "never used"}


@pytest.fixture
def another_unused_fixture():
    """BAD: Another unused fixture (PYTEST-FIX-005)."""
    return "also never used"


# ============================================================================
# GOOD: Properly designed fixtures
# ============================================================================


@pytest.fixture(scope="session")
def good_session_config():
    """GOOD: Session-scoped immutable config."""
    return ("localhost", 5432, "testdb")  # Immutable tuple


@pytest.fixture(scope="module")
def good_module_cache(good_session_config):
    """GOOD: Module fixture depending on session fixture (valid scope)."""
    host, port, db = good_session_config
    return {"connection_string": f"{host}:{port}/{db}"}


@pytest.fixture
def good_function_fixture(good_module_cache):
    """GOOD: Function fixture depending on module fixture (valid scope)."""
    return {"cache": good_module_cache, "timestamp": "2024-01-01"}


@pytest.fixture
def used_fixture():
    """GOOD: This fixture is used by tests."""
    return {"important": "data"}


@pytest.fixture
def db_transaction(session_db_connection):
    """GOOD: Function-scoped transaction using session connection."""
    # Start transaction
    transaction = {"connection": session_db_connection, "id": "txn_123"}
    yield transaction
    # Rollback transaction (keeps session connection clean)
    transaction["id"] = None
