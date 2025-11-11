"""
Test cases for Category 3: Fixture Interaction Smells.

These tests demonstrate fixture usage patterns.
"""


def test_using_good_fixtures(used_fixture, db_transaction):
    """GOOD: Using well-designed fixtures."""
    assert used_fixture["important"] == "data"
    assert db_transaction["id"] == "txn_123"


def test_using_session_fixture(session_db_connection):
    """GOOD: Using a session-scoped fixture."""
    assert session_db_connection["connected"] is True


def test_using_function_fixture(function_scoped_user):
    """GOOD: Using a function-scoped fixture."""
    assert function_scoped_user["name"] == "Test User"


def test_using_nested_fixtures(good_function_fixture):
    """GOOD: Using fixtures with proper scope dependencies."""
    assert "cache" in good_function_fixture


def test_simple_assertion():
    """GOOD: Simple test without fixtures."""
    assert 1 + 1 == 2


# Note: The bad_session_fixture and unused fixtures will trigger warnings
# when the linter analyzes the conftest.py file, not when analyzing these tests.
