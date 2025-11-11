"""
Test cases for new enhancements added to pytest-deep-analysis.

These tests demonstrate anti-patterns for the newly added features:
1. Database commits without cleanup
2. Test fixture state mutation
3. Fixture scope narrowing opportunities
4. Parametrize misuse and anti-patterns
"""

import pytest


# =========================================================================
# Test: Database Commits Without Cleanup (E9036)
# =========================================================================

@pytest.fixture(scope="session")
def db_session_bad():
    """BAD: Session fixture that commits without cleanup (E9036)."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE users (id INTEGER, name TEXT)")

    # Commit without cleanup
    conn.commit()

    yield conn

    # Missing rollback or cleanup here!


@pytest.fixture(scope="function")
def db_session_good():
    """GOOD: Function fixture with proper cleanup."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE users (id INTEGER, name TEXT)")
    conn.commit()

    yield conn

    # Proper cleanup
    conn.rollback()
    conn.close()


# =========================================================================
# Test: Fixture Mutation (W9014)
# =========================================================================

@pytest.fixture
def user_dict():
    """Fixture returning a mutable dictionary."""
    return {"name": "Alice", "age": 30, "roles": []}


@pytest.fixture
def user_list():
    """Fixture returning a mutable list."""
    return ["Alice", "Bob", "Charlie"]


def test_mutates_fixture_attribute(user_dict):
    """BAD: Modifying fixture attribute in-place (W9014)."""
    user_dict["age"] = 31  # Should trigger warning
    assert user_dict["age"] == 31


def test_mutates_fixture_list_item(user_list):
    """BAD: Modifying fixture list item in-place (W9014)."""
    user_list[0] = "Dave"  # Should trigger warning
    assert user_list[0] == "Dave"


def test_appends_to_fixture(user_dict):
    """BAD: Appending to fixture list in-place (W9014)."""
    user_dict["roles"].append("admin")  # Should trigger warning
    assert "admin" in user_dict["roles"]


def test_uses_fixture_without_mutation(user_dict):
    """GOOD: Reading fixture without modification."""
    assert user_dict["name"] == "Alice"
    assert user_dict["age"] == 30


# =========================================================================
# Test: Fixture Scope Narrowing (W9037)
# =========================================================================

@pytest.fixture(scope="session")
def session_fixture_used_once():
    """BAD: Session fixture only used in one test (W9037)."""
    return "session_data"


@pytest.fixture(scope="module")
def module_fixture_used_once():
    """BAD: Module fixture only used in one test (W9037)."""
    return "module_data"


def test_uses_session_fixture_once(session_fixture_used_once):
    """Test that uses a session fixture (should suggest narrowing scope)."""
    assert session_fixture_used_once == "session_data"


def test_uses_module_fixture_once(module_fixture_used_once):
    """Test that uses a module fixture (should suggest narrowing scope)."""
    assert module_fixture_used_once == "module_data"


# =========================================================================
# Test: Parametrize Misuse - Duplicate Values (W9015)
# =========================================================================

@pytest.mark.parametrize("value", [1, 2, 3, 2, 4])  # Should trigger warning - duplicate "2"
def test_with_duplicate_params(value):
    """BAD: Parametrize with duplicate values (W9015)."""
    assert value > 0


@pytest.mark.parametrize("x,y", [(1, 2), (3, 4), (1, 2)])  # Should trigger warning - duplicate (1,2)
def test_with_duplicate_tuple_params(x, y):
    """BAD: Parametrize with duplicate tuples (W9015)."""
    assert x + y > 0


@pytest.mark.parametrize("name,age", [
    ("Alice", 30),
    ("Bob", 25),
    ("Alice", 30),  # Duplicate
])
def test_with_duplicate_named_params(name, age):
    """BAD: Parametrize with duplicate named parameter combinations (W9015)."""
    assert len(name) > 0
    assert age > 0


# =========================================================================
# Test: Good Parametrize Usage (should not trigger warnings)
# =========================================================================

@pytest.mark.parametrize("value", [1, 2, 3, 4, 5])
def test_with_unique_params(value):
    """GOOD: Parametrize with unique values."""
    assert value > 0


@pytest.mark.parametrize("x,y,expected", [
    (1, 2, 3),
    (2, 3, 5),
    (5, 5, 10),
])
def test_addition_parametrized(x, y, expected):
    """GOOD: Parametrize with unique combinations."""
    assert x + y == expected


@pytest.mark.parametrize("case", [
    {"input": "hello", "expected": "HELLO"},
    {"input": "world", "expected": "WORLD"},
    {"input": "python", "expected": "PYTHON"},
])
def test_with_dict_params(case):
    """GOOD: Parametrize with dict values."""
    assert case["input"].upper() == case["expected"]


# =========================================================================
# Test: Multiple Fixtures (for scope analysis)
# =========================================================================

@pytest.fixture(scope="module")
def shared_config():
    """Module fixture used by multiple tests."""
    return {"setting1": "value1", "setting2": "value2"}


def test_config_setting1(shared_config):
    """Test using shared config."""
    assert shared_config["setting1"] == "value1"


def test_config_setting2(shared_config):
    """Test using shared config."""
    assert shared_config["setting2"] == "value2"


# =========================================================================
# Helper functions (not tests)
# =========================================================================

def calculate_value():
    """Helper function."""
    return 15


def get_results():
    """Helper function."""
    return [1, 2, 3, 4, 5]


def try_operation():
    """Helper function."""
    return True


def get_response():
    """Helper function."""
    class Response:
        status_code = 200
        data = {"count": 10}
    return Response()


def get_user():
    """Helper function."""
    class User:
        role = "user"
    return User()
