"""
Automated tests for Category 1: Test Body Smells (Maintenance checks).

Tests for rules:
- W9011: pytest-mnt-test-logic
- W9012: pytest-mnt-magic-assert
- W9013: pytest-mnt-suboptimal-assert
"""

import pytest
from pylint.testutils import MessageTest

from tests.test_harness.base import PytestDeepAnalysisTestCase, msg


class TestLogicInTests(PytestDeepAnalysisTestCase):
    """Tests for W9011: pytest-mnt-test-logic"""

    def test_if_statement_in_test(self):
        """Should warn when if statement is used in a test."""
        code = """
        def test_with_conditional():
            result = calculate()
            if result > 10:  # Line 4 - test logic
                assert result < 100  # Line 5 - 100 is magic
            else:
                assert result >= 0  # 0 is not magic
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-test-logic", line=4),
            msg("pytest-mnt-magic-assert", line=5)
        )

    def test_for_loop_in_test(self):
        """Should warn when for loop is used in a test."""
        code = """
        def test_with_loop():
            items = get_items()
            for item in items:  # Line 4
                assert item is not None
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-test-logic", line=4)
        )

    def test_while_loop_in_test(self):
        """Should warn when while loop is used in a test."""
        code = """
        def test_with_while():
            counter = 0
            while counter < 10:  # Line 4 - test logic
                counter += 1
            assert counter == 10  # Line 6 - 10 is magic
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-test-logic", line=4),
            msg("pytest-mnt-magic-assert", line=6)
        )

    def test_list_comprehension_allowed(self):
        """Should NOT warn for list comprehensions (they're idiomatic)."""
        code = """
        def test_with_comprehension():
            items = [1, 2, 3, 4, 5]
            filtered = [x for x in items if x > 2]  # Comprehension OK
            assert len(filtered) == 3  # Line 5 - 3 is magic
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-magic-assert", line=5)  # 3 is a magic number
        )

    def test_dict_comprehension_allowed(self):
        """Should NOT warn for dict comprehensions."""
        code = """
        def test_with_dict_comp():
            data = {"a": 1, "b": 2, "c": 3}
            doubled = {k: v * 2 for k, v in data.items()}  # Comprehension OK
            assert doubled["a"] == 2  # Line 5 - 2 is magic
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-magic-assert", line=5)  # 2 is a magic number
        )

    def test_if_in_pytest_raises_allowed(self):
        """Should NOT warn for logic inside pytest.raises context."""
        code = """
        import pytest

        def test_with_raises():
            with pytest.raises(ValueError):
                if True:  # This is OK inside pytest.raises
                    raise ValueError("test")
            assert True
        """
        self.assert_no_messages(code)

    def test_logic_outside_test(self):
        """Should NOT warn for logic outside test functions."""
        code = """
        def helper_function():
            if True:  # Logic in helper is OK
                return "yes"
            return "no"

        def test_something():
            assert helper_function() == "yes"  # Line 8 - "yes" is magic
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-magic-assert", line=8)  # "yes" is a magic string
        )


class TestMagicConstants(PytestDeepAnalysisTestCase):
    """Tests for W9012: pytest-mnt-magic-assert"""

    def test_magic_number_in_assert(self):
        """Should warn for magic numbers in assertions."""
        code = """
        def test_status_code():
            response = get_response()
            assert response.status_code == 250  # Line 4
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-magic-assert", line=4)
        )

    def test_magic_string_in_assert(self):
        """Should warn for magic strings in assertions."""
        code = """
        def test_user_role():
            user = get_user()
            assert user.role == "super_admin_level_3"  # Line 4
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-magic-assert", line=4)
        )

    def test_non_magic_zero(self):
        """Should NOT warn for 0 (not considered magic)."""
        code = """
        def test_count():
            result = get_count()
            assert result > 0
        """
        self.assert_no_messages(code)

    def test_non_magic_one(self):
        """Should NOT warn for 1 (not considered magic)."""
        code = """
        def test_length():
            items = get_items()
            assert len(items) >= 1
        """
        self.assert_no_messages(code)

    def test_non_magic_negative_one(self):
        """Should NOT warn for -1 (not considered magic)."""
        code = """
        def test_index():
            result = find_item()
            assert result != -1
        """
        self.assert_no_messages(code)

    def test_non_magic_true(self):
        """Should NOT warn for True (not considered magic)."""
        code = """
        def test_flag():
            result = is_enabled()
            assert result is True
        """
        self.assert_no_messages(code)

    def test_non_magic_false(self):
        """Should NOT warn for False (not considered magic)."""
        code = """
        def test_disabled():
            result = is_disabled()
            assert result is False
        """
        self.assert_no_messages(code)

    def test_non_magic_none(self):
        """Should NOT warn for None (not considered magic)."""
        code = """
        def test_optional():
            result = get_optional()
            assert result is not None
        """
        self.assert_no_messages(code)

    def test_non_magic_empty_string(self):
        """Should NOT warn for empty string (not considered magic)."""
        code = """
        def test_string():
            result = get_string()
            assert result != ""
        """
        self.assert_no_messages(code)

    def test_named_constant(self):
        """Should NOT warn when using named constants."""
        code = """
        def test_with_constant():
            EXPECTED_STATUS = 200
            response = get_response()
            assert response.status == EXPECTED_STATUS
        """
        self.assert_no_messages(code)


class TestSuboptimalAssert(PytestDeepAnalysisTestCase):
    """Tests for W9013: pytest-mnt-suboptimal-assert"""

    def test_assert_true_with_comparison(self):
        """Should warn for assertTrue with comparison."""
        code = """
        def test_bad_assert(self):
            result = calculate()
            assert self.assertTrue(result == 42)  # Line 4
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-suboptimal-assert", line=4)
            # Note: 42 inside assertTrue() argument is not caught by magic-assert
            # checker (it only looks at direct assert comparisons)
        )

    def test_assert_false_with_comparison(self):
        """Should warn for assertFalse with comparison."""
        code = """
        def test_bad_assert_false(self):
            result = calculate()
            assert self.assertFalse(result != 42)  # Line 4
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-suboptimal-assert", line=4)
            # Note: 42 inside assertFalse() argument is not caught by magic-assert
            # checker (it only looks at direct assert comparisons)
        )

    def test_assert_equal_with_comparison(self):
        """Should warn for assertEqual with comparison."""
        code = """
        def test_bad_assert_equal(self):
            result = calculate()
            assert self.assertEqual(result > 10, True)  # Line 4
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-suboptimal-assert", line=4)
            # True is not magic
        )

    def test_direct_assert(self):
        """Should NOT warn for direct pytest-style assertions."""
        code = """
        def test_good_assert():
            result = calculate()
            assert result == 42  # Line 4 - 42 is magic though!
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-magic-assert", line=4)  # 42 is a magic number
        )

    def test_assert_with_boolean(self):
        """Should NOT warn for simple boolean assertions."""
        code = """
        def test_boolean():
            result = is_valid()
            assert result
        """
        self.assert_no_messages(code)


class TestMultipleMaintenanceIssues(PytestDeepAnalysisTestCase):
    """Tests for multiple maintenance issues in one file."""

    def test_all_maintenance_warnings(self):
        """Should detect all maintenance issues."""
        code = """
        def test_many_problems(self):
            result = calculate()
            if result > 10:  # Line 4 - test logic
                assert result == 250  # Line 5 - magic number
            assert self.assertTrue(result != 0)  # Line 6 - suboptimal assert
        """
        self.assert_adds_messages(
            code,
            msg("pytest-mnt-test-logic", line=4),
            msg("pytest-mnt-magic-assert", line=5),
            msg("pytest-mnt-suboptimal-assert", line=6),
        )
