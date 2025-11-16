"""
Automated tests for Category 3: Fixture Interaction Smells.

Tests for rules:
- E9032: pytest-fix-invalid-scope
- W9033: pytest-fix-shadowed
- W9034: pytest-fix-unused
- E9035: pytest-fix-stateful-session

Note: E9031 (session-mutation) is not yet implemented.
"""

from tests.test_harness.base import PytestDeepAnalysisTestCase


class TestInvalidScopeDependency(PytestDeepAnalysisTestCase):
    """Tests for E9032: pytest-fix-invalid-scope"""

    def test_session_depends_on_function(self):
        """Should warn when session fixture depends on function fixture."""
        code = """
        import pytest

        @pytest.fixture(scope="function")
        def func_fixture():
            return {"data": "value"}

        @pytest.fixture(scope="session")  # Line 8
        def session_fixture(func_fixture):
            return {"session": func_fixture}
        """
        # Create a module and walk it to trigger close()
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        # Manually process and close to trigger validation
        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        # Check that we got the expected messages
        # This fixture violates multiple rules: invalid-scope, unused, stateful-session
        messages = self.linter.release_messages()
        msg_ids = {msg.msg_id for msg in messages}
        assert "pytest-fix-invalid-scope" in msg_ids
        assert "pytest-fix-unused" in msg_ids  # Never used by a test
        assert "pytest-fix-stateful-session" in msg_ids  # Returns dict

    def test_session_depends_on_module(self):
        """Should warn when session fixture depends on module fixture."""
        code = """
        import pytest

        @pytest.fixture(scope="module")
        def module_fixture():
            return {"module": "data"}

        @pytest.fixture(scope="session")  # Line 8
        def session_fixture(module_fixture):
            return {"session": module_fixture}
        """
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        messages = self.linter.release_messages()
        msg_ids = {msg.msg_id for msg in messages}
        assert "pytest-fix-invalid-scope" in msg_ids
        assert "pytest-fix-unused" in msg_ids  # Never used by a test
        assert "pytest-fix-stateful-session" in msg_ids  # Returns dict

    def test_module_depends_on_function(self):
        """Should warn when module fixture depends on function fixture."""
        code = """
        import pytest

        @pytest.fixture(scope="function")
        def func_fixture():
            return "data"

        @pytest.fixture(scope="module")  # Line 8
        def module_fixture(func_fixture):
            return func_fixture
        """
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        messages = self.linter.release_messages()
        msg_ids = {msg.msg_id for msg in messages}
        assert "pytest-fix-invalid-scope" in msg_ids
        assert "pytest-fix-unused" in msg_ids  # Never used by a test

    def test_function_depends_on_session(self):
        """Should NOT warn when function fixture depends on session (valid)."""
        code = """
        import pytest

        @pytest.fixture(scope="session")
        def session_fixture():
            return {"session": "data"}

        @pytest.fixture(scope="function")
        def func_fixture(session_fixture):
            return {"func": session_fixture}

        def test_something(func_fixture):
            assert func_fixture
        """
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        messages = self.linter.release_messages()
        # Filter for only invalid-scope messages
        scope_messages = [m for m in messages if m.msg_id == "pytest-fix-invalid-scope"]
        assert len(scope_messages) == 0

    def test_module_depends_on_session(self):
        """Should NOT warn when module fixture depends on session (valid)."""
        code = """
        import pytest

        @pytest.fixture(scope="session")
        def session_fixture():
            return "session"

        @pytest.fixture(scope="module")
        def module_fixture(session_fixture):
            return session_fixture
        """
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        messages = self.linter.release_messages()
        scope_messages = [m for m in messages if m.msg_id == "pytest-fix-invalid-scope"]
        assert len(scope_messages) == 0


class TestUnusedFixtures(PytestDeepAnalysisTestCase):
    """Tests for W9034: pytest-fix-unused"""

    def test_unused_fixture(self):
        """Should warn for fixtures that are never used."""
        code = """
        import pytest

        @pytest.fixture  # Line 4
        def unused_fixture():
            return "never used"

        def test_something():
            assert True
        """
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        messages = self.linter.release_messages()
        unused_messages = [m for m in messages if m.msg_id == "pytest-fix-unused"]
        assert len(unused_messages) == 1

    def test_used_fixture(self):
        """Should NOT warn for fixtures that are used."""
        code = """
        import pytest

        @pytest.fixture
        def used_fixture():
            return "data"

        def test_something(used_fixture):
            assert used_fixture == "data"
        """
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        messages = self.linter.release_messages()
        unused_messages = [m for m in messages if m.msg_id == "pytest-fix-unused"]
        assert len(unused_messages) == 0

    def test_autouse_not_unused(self):
        """Should NOT warn for autouse fixtures (they're implicitly used)."""
        code = """
        import pytest

        @pytest.fixture(autouse=True)
        def auto_fixture():
            yield
        """
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        messages = self.linter.release_messages()
        unused_messages = [m for m in messages if m.msg_id == "pytest-fix-unused"]
        assert len(unused_messages) == 0

    def test_fixture_used_by_other_fixture(self):
        """Should NOT warn for fixtures used by other fixtures."""
        code = """
        import pytest

        @pytest.fixture
        def base_fixture():
            return "base"

        @pytest.fixture
        def derived_fixture(base_fixture):
            return base_fixture + "_derived"

        def test_something(derived_fixture):
            assert derived_fixture
        """
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        messages = self.linter.release_messages()
        unused_messages = [m for m in messages if m.msg_id == "pytest-fix-unused"]
        assert len(unused_messages) == 0


class TestStatefulSessionFixtures(PytestDeepAnalysisTestCase):
    """Tests for E9035: pytest-fix-stateful-session"""

    def test_session_returns_list(self):
        """Should warn when session fixture returns a mutable list."""
        code = """
        import pytest

        @pytest.fixture(scope="session")  # Line 4
        def session_list():
            return []
        """
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        messages = self.linter.release_messages()
        stateful_messages = [
            m for m in messages if m.msg_id == "pytest-fix-stateful-session"
        ]
        assert len(stateful_messages) == 1

    def test_session_returns_dict(self):
        """Should warn when session fixture returns a mutable dict."""
        code = """
        import pytest

        @pytest.fixture(scope="session")  # Line 4
        def session_dict():
            return {}
        """
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        messages = self.linter.release_messages()
        stateful_messages = [
            m for m in messages if m.msg_id == "pytest-fix-stateful-session"
        ]
        assert len(stateful_messages) == 1

    def test_session_returns_set(self):
        """Should warn when session fixture returns a mutable set."""
        code = """
        import pytest

        @pytest.fixture(scope="session")  # Line 4
        def session_set():
            return set()
        """
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        messages = self.linter.release_messages()
        stateful_messages = [
            m for m in messages if m.msg_id == "pytest-fix-stateful-session"
        ]
        # Note: set() is a Call node, so it should be detected
        assert len(stateful_messages) >= 1

    def test_session_returns_tuple(self):
        """Should NOT warn when session fixture returns immutable tuple."""
        code = """
        import pytest

        @pytest.fixture(scope="session")
        def session_tuple():
            return (1, 2, 3)

        def test_something(session_tuple):
            assert session_tuple
        """
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        messages = self.linter.release_messages()
        stateful_messages = [
            m for m in messages if m.msg_id == "pytest-fix-stateful-session"
        ]
        assert len(stateful_messages) == 0

    def test_session_returns_string(self):
        """Should NOT warn when session fixture returns immutable string."""
        code = """
        import pytest

        @pytest.fixture(scope="session")
        def session_string():
            return "immutable"

        def test_something(session_string):
            assert session_string
        """
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        messages = self.linter.release_messages()
        stateful_messages = [
            m for m in messages if m.msg_id == "pytest-fix-stateful-session"
        ]
        assert len(stateful_messages) == 0

    def test_function_scope_returns_list(self):
        """Should NOT warn for function-scoped fixtures returning lists."""
        code = """
        import pytest

        @pytest.fixture(scope="function")
        def function_list():
            return []

        def test_something(function_list):
            assert function_list is not None
        """
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        messages = self.linter.release_messages()
        stateful_messages = [
            m for m in messages if m.msg_id == "pytest-fix-stateful-session"
        ]
        assert len(stateful_messages) == 0


class TestShadowedFixtures(PytestDeepAnalysisTestCase):
    """Tests for W9033: pytest-fix-shadowed

    Note: Full shadowing detection requires multi-file analysis.
    These tests check basic shadowing detection.
    """

    def test_shadowed_fixture_basic(self):
        """Should detect when the same fixture name is defined twice in same file."""
        code = """
        import pytest

        @pytest.fixture
        def my_fixture():
            return "first"

        @pytest.fixture
        def my_fixture():  # Line 8 - Shadows the first definition
            return "second"

        def test_something(my_fixture):
            assert my_fixture
        """
        import astroid

        node = astroid.parse(code, module_name="test.py")
        node.file = "test.py"

        self.checker.visit_module(node)
        self.walk(node)
        self.checker.close()

        messages = self.linter.release_messages()
        # With refactored fixture graph, we now detect same-file shadowing!
        shadowed_messages = [m for m in messages if m.msg_id == "pytest-fix-shadowed"]
        assert len(shadowed_messages) == 1
