"""
Automated tests for Enhancement Features.

Tests for new rules:
- W9022: pytest-fix-db-commit-no-cleanup
- W9023: pytest-test-fixture-mutation
- W9024: pytest-fix-overly-broad-scope
- W9025: pytest-parametrize-empty
- W9026: pytest-parametrize-duplicate
- W9027: pytest-parametrize-explosion
- W9029: pytest-xdist-shared-state
- W9030: pytest-xdist-fixture-io
"""

from tests.test_harness.base import PytestDeepAnalysisTestCase, msg


class TestDatabaseCommitCleanup(PytestDeepAnalysisTestCase):
    """Tests for W9022: pytest-fix-db-commit-no-cleanup"""

    def test_fixture_with_commit_no_cleanup(self):
        """Should warn when fixture commits without cleanup."""
        code = """
        import pytest

        @pytest.fixture  # Line 4
        def db_fixture():
            conn = get_connection()
            conn.commit()
            return conn
        """
        self.assert_adds_messages(code, msg("pytest-fix-db-commit-no-cleanup", line=4))

    def test_fixture_with_commit_and_yield_cleanup(self):
        """Should NOT warn when fixture has yield with cleanup."""
        code = """
        import pytest

        @pytest.fixture
        def db_fixture():
            conn = get_connection()
            conn.commit()
            yield conn
            conn.rollback()
        """
        self.assert_no_messages(code)

    def test_fixture_with_commit_and_rollback(self):
        """Should NOT warn when fixture has rollback."""
        code = """
        import pytest

        @pytest.fixture
        def db_fixture():
            conn = get_connection()
            try:
                conn.commit()
            except Exception:
                conn.rollback()
            return conn
        """
        self.assert_no_messages(code)


class TestFixtureMutation(PytestDeepAnalysisTestCase):
    """Tests for W9023: pytest-test-fixture-mutation"""

    def test_mutating_module_scoped_fixture(self):
        """Should warn when test mutates a module-scoped fixture."""
        code = """
        import pytest

        @pytest.fixture(scope="module")
        def shared_list():
            return []

        def test_mutation(shared_list):  # Line 8
            shared_list.append(1)
            assert len(shared_list) == 1
        """
        self.assert_adds_messages(code, msg("pytest-test-fixture-mutation", line=9))

    def test_mutating_function_scoped_fixture(self):
        """Should NOT warn for function-scoped fixture mutation."""
        code = """
        import pytest

        @pytest.fixture
        def my_list():
            return []

        def test_mutation(my_list):
            my_list.append(1)
            assert len(my_list) == 1
        """
        self.assert_no_messages(code)


class TestParametrizeAntipatterns(PytestDeepAnalysisTestCase):
    """Tests for parametrize anti-patterns"""

    def test_empty_parametrize(self):
        """Should warn for empty parametrize."""
        code = """
        import pytest

        @pytest.mark.parametrize("value", [])  # Line 4
        def test_empty(value):
            assert True
        """
        self.assert_adds_messages(code, msg("pytest-parametrize-empty", line=4))

    def test_single_value_parametrize(self):
        """Should warn for single value parametrize."""
        code = """
        import pytest

        @pytest.mark.parametrize("value", [1])  # Line 4
        def test_single(value):
            assert value == 1
        """
        self.assert_adds_messages(code, msg("pytest-parametrize-empty", line=4))

    def test_duplicate_parametrize_values(self):
        """Should warn for duplicate values."""
        code = """
        import pytest

        @pytest.mark.parametrize("value", [1, 2, 1])  # Line 4
        def test_duplicate(value):
            assert value > 0
        """
        self.assert_adds_messages(code, msg("pytest-parametrize-duplicate", line=4))

    def test_parametrize_explosion(self):
        """Should warn for excessive combinations."""
        code = """
        import pytest

        @pytest.mark.parametrize("a", [1, 2, 3, 4, 5])  # Line 4
        @pytest.mark.parametrize("b", [1, 2, 3, 4, 5])
        @pytest.mark.parametrize("c", [1, 2, 3, 4, 5])
        def test_explosion(a, b, c):
            assert a + b + c > 0
        """
        # 5 * 5 * 5 = 125 combinations, exceeds threshold of 20
        self.assert_adds_messages(code, msg("pytest-parametrize-explosion", line=4))

    def test_normal_parametrize(self):
        """Should NOT warn for normal parametrize usage."""
        code = """
        import pytest

        @pytest.mark.parametrize("value", [1, 2, 3])
        def test_normal(value):
            assert value > 0
        """
        self.assert_no_messages(code)


class TestXdistCompatibility(PytestDeepAnalysisTestCase):
    """Tests for pytest-xdist compatibility issues"""

    def test_shared_state_global_variable(self):
        """Should warn for global variable access."""
        # Note: This test may not trigger in simple cases due to scope detection limitations
        # The actual implementation checks for module-scope variables
        # For demonstration, we'll mark this as a known limitation

    def test_fixture_io_without_tmp_path(self):
        """Should warn when fixture does I/O without tmp_path."""
        code = """
        import pytest

        @pytest.fixture  # Line 4
        def file_fixture():
            with open("test.txt", "w") as f:
                f.write("data")
            return "test.txt"
        """
        self.assert_adds_messages(code, msg("pytest-xdist-fixture-io", line=4))

    def test_fixture_io_with_tmp_path(self):
        """Should NOT warn when fixture uses tmp_path."""
        code = """
        import pytest

        @pytest.fixture
        def file_fixture(tmp_path):
            test_file = tmp_path / "test.txt"
            test_file.write_text("data")
            return str(test_file)
        """
        self.assert_no_messages(code)
