"""
Test cases for Category 1: Test Body Smells (Maintenance checks).

These tests demonstrate anti-patterns that the linter should catch.
"""


def test_with_conditional_logic():
    """BAD: Using conditional logic in a test (PYTEST-MNT-001)."""
    result = calculate_value()

    if result > 10:  # Should trigger warning
        assert result < 100
    else:
        assert result >= 0


def test_with_for_loop():
    """BAD: Using a for loop in a test (PYTEST-MNT-001)."""
    results = get_results()

    for item in results:  # Should trigger warning
        assert item is not None


def test_with_while_loop():
    """BAD: Using a while loop in a test (PYTEST-MNT-001)."""
    counter = 0
    result = None

    while counter < 10:  # Should trigger warning
        result = try_operation()
        if result:
            break
        counter += 1

    assert result is not None


def test_with_magic_numbers():
    """BAD: Using magic numbers in asserts (PYTEST-MNT-002)."""
    response = get_response()
    assert response.status_code == 250  # Should trigger warning
    assert response.data["count"] == 42  # Should trigger warning


def test_with_magic_strings():
    """BAD: Using magic strings in asserts (PYTEST-MNT-002)."""
    user = get_user()
    assert user.role == "super_admin_level_3"  # Should trigger warning


def test_with_suboptimal_assert():
    """BAD: Using assertTrue with comparison (PYTEST-MNT-003)."""
    result = calculate()
    # This should trigger warning - using unittest-style assert
    assert assertTrue(result == 42)


# ============================================================================
# GOOD: Examples that should NOT trigger warnings
# ============================================================================


def test_with_list_comprehension():
    """GOOD: List comprehensions are acceptable."""
    items = get_items()
    # This should NOT trigger warning - comprehensions are idiomatic
    filtered = [item for item in items if item.is_valid]
    assert len(filtered) > 0


def test_with_pytest_raises():
    """GOOD: Logic inside pytest.raises context is acceptable."""
    import pytest

    with pytest.raises(ValueError) as exc_info:
        if True:  # This should NOT trigger warning
            raise ValueError("test")

    assert "test" in str(exc_info.value)


def test_with_named_constants():
    """GOOD: Using named constants instead of magic numbers."""
    EXPECTED_STATUS_CODE = 200
    MAX_RETRY_COUNT = 42

    response = get_response()
    assert response.status_code == EXPECTED_STATUS_CODE
    assert response.retries < MAX_RETRY_COUNT


def test_with_direct_assert():
    """GOOD: Using direct pytest assert."""
    result = calculate()
    assert result == 42  # Direct assert with comparison


def test_with_non_magic_values():
    """GOOD: Common non-magic values."""
    result = get_result()
    assert result > 0  # 0, 1, -1 are not considered magic
    assert result != -1
    assert len(result.items) >= 1


# Helper functions
def calculate_value():
    return 15


def get_results():
    return [1, 2, 3]


def try_operation():
    return True


def get_response():
    class Response:
        status_code = 200
        data = {"count": 10}

    return Response()


def get_user():
    class User:
        role = "admin"

    return User()


def calculate():
    return 42


def assertTrue(condition):
    """Mock assertTrue for demonstration."""
    return condition


def get_items():
    class Item:
        is_valid = True

    return [Item(), Item()]


def get_result():
    class Result:
        items = [1, 2, 3]

    return Result()
