"""
Automated tests for Category 2: Fixture Definition Smells.

Tests for rules:
- W9021: pytest-fix-autouse
"""

import pytest
from pylint.testutils import MessageTest

from tests.test_harness.base import PytestDeepAnalysisTestCase, msg


class TestAutouseFixture(PytestDeepAnalysisTestCase):
    """Tests for W9021: pytest-fix-autouse"""

    def test_autouse_true_fixture(self):
        """Should warn when autouse=True is used."""
        code = """
        import pytest

        @pytest.fixture(autouse=True)  # Line 4
        def auto_fixture():
            print("This runs automatically")
            yield
            print("Cleanup")
        """
        self.assert_adds_messages(code, msg("pytest-fix-autouse", line=4))

    def test_autouse_true_with_scope(self):
        """Should warn when autouse=True is used with scope."""
        code = """
        import pytest

        @pytest.fixture(scope="session", autouse=True)  # Line 4
        def session_auto_fixture():
            print("Session setup")
            yield
            print("Session teardown")
        """
        self.assert_adds_messages(code, msg("pytest-fix-autouse", line=4))

    def test_autouse_false(self):
        """Should NOT warn when autouse=False (default)."""
        code = """
        import pytest

        @pytest.fixture(autouse=False)
        def normal_fixture():
            return {"data": "value"}
        """
        self.assert_no_messages(code)

    def test_no_autouse_parameter(self):
        """Should NOT warn when autouse parameter is not specified."""
        code = """
        import pytest

        @pytest.fixture
        def normal_fixture():
            return {"data": "value"}
        """
        self.assert_no_messages(code)

    def test_autouse_with_scope_function(self):
        """Should warn for function-scoped autouse fixture."""
        code = """
        import pytest

        @pytest.fixture(scope="function", autouse=True)  # Line 4
        def function_auto():
            yield
        """
        self.assert_adds_messages(code, msg("pytest-fix-autouse", line=4))

    def test_autouse_with_scope_module(self):
        """Should warn for module-scoped autouse fixture."""
        code = """
        import pytest

        @pytest.fixture(scope="module", autouse=True)  # Line 4
        def module_auto():
            yield
        """
        self.assert_adds_messages(code, msg("pytest-fix-autouse", line=4))

    def test_regular_fixture_with_scope(self):
        """Should NOT warn for regular fixture with scope."""
        code = """
        import pytest

        @pytest.fixture(scope="session")
        def session_fixture():
            return {"connection": "established"}
        """
        self.assert_no_messages(code)

    def test_multiple_autouse_fixtures(self):
        """Should warn for each autouse fixture."""
        code = """
        import pytest

        @pytest.fixture(autouse=True)  # Line 4
        def auto1():
            yield

        @pytest.fixture(autouse=True)  # Line 8
        def auto2():
            yield

        @pytest.fixture  # No warning
        def normal():
            return "data"
        """
        self.assert_adds_messages(
            code,
            msg("pytest-fix-autouse", line=4),
            msg("pytest-fix-autouse", line=8),
        )
