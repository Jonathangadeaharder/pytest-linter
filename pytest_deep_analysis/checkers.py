"""
Main checker implementation for pytest-deep-analysis.

This module implements the core linter logic organized into three categories:
1. Test Body Smells (ast-based, file-local)
2. Fixture Definition Smells (ast-based, file-local)
3. Fixture Interaction Smells (astroid-based, cross-file)

The checker uses a multi-pass architecture:
- Pass 1: Fixture Discovery & Graph Building
- Pass 2: Graph Validation & Test Analysis
"""

from typing import Optional, Dict, List, Set, Any, TYPE_CHECKING

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker

from pytest_deep_analysis.messages import MESSAGES
from pytest_deep_analysis.utils import (
    is_test_function,
    is_pytest_fixture,
    get_fixture_decorator_args,
    get_fixture_dependencies,
    is_in_comprehension,
    is_in_context_manager,
    is_magic_constant,
    get_call_qualname,
    compare_fixture_scopes,
)

if TYPE_CHECKING:
    from pylint.lint import PyLinter


class FixtureInfo:
    """Information about a discovered pytest fixture."""

    def __init__(
        self,
        name: str,
        scope: str,
        autouse: bool,
        dependencies: List[str],
        file_path: str,
        node: astroid.FunctionDef,
    ):
        self.name = name
        self.scope = scope
        self.autouse = autouse
        self.dependencies = dependencies
        self.file_path = file_path
        self.node = node
        self.used_by: Set[str] = set()  # Track which tests use this fixture


class PytestDeepAnalysisChecker(BaseChecker):
    """Pylint checker for deep, semantic pytest analysis.

    This checker implements high-value pytest linting rules that require
    cross-file semantic analysis using astroid's inference engine.
    """

    name = "pytest-deep-analysis"
    msgs = MESSAGES

    def __init__(self, linter: "PyLinter"):
        super().__init__(linter)
        # Fixture graph: maps fixture name to FixtureInfo
        self.fixture_graph: Dict[str, FixtureInfo] = {}
        # Track which tests use which fixtures
        self.test_fixture_usage: Dict[str, List[str]] = {}
        # Track if we're inside a test function for Category 1 checks
        self._in_test_function = False
        # Track pass completion
        self._pass1_complete = False

    # =========================================================================
    # Pass 1: Fixture Discovery
    # =========================================================================

    def visit_module(self, node: astroid.Module) -> None:
        """Visit a module to discover fixtures (Pass 1).

        Args:
            node: The module node
        """
        # Traverse all function definitions in this module
        for child in node.body:
            if isinstance(child, astroid.FunctionDef):
                self._process_potential_fixture(child)

    def _process_potential_fixture(self, node: astroid.FunctionDef) -> None:
        """Process a function that might be a pytest fixture.

        Args:
            node: The function definition node
        """
        if not is_pytest_fixture(node):
            return

        # Extract fixture metadata
        scope, autouse = get_fixture_decorator_args(node)
        dependencies = get_fixture_dependencies(node)
        file_path = node.root().file if node.root().file else "<unknown>"

        # Store in the fixture graph
        fixture_info = FixtureInfo(
            name=node.name,
            scope=scope,
            autouse=autouse,
            dependencies=dependencies,
            file_path=file_path,
            node=node,
        )
        self.fixture_graph[node.name] = fixture_info

        # Category 2: Check for autouse=True (PYTEST-FIX-001)
        if autouse:
            self.add_message(
                "pytest-fix-autouse",
                node=node,
                line=node.lineno,
            )

    # =========================================================================
    # Pass 2: Test and Fixture Analysis
    # =========================================================================

    def visit_functiondef(self, node: astroid.FunctionDef) -> None:
        """Visit a function definition for analysis (Pass 2).

        This handles both test functions (Category 1) and fixture interaction
        checks (Category 3).

        Args:
            node: The function definition node
        """
        if is_test_function(node):
            self._in_test_function = True
            self._check_test_function(node)
            # Continue visiting children for Category 1 checks

    def leave_functiondef(self, node: astroid.FunctionDef) -> None:
        """Leave a function definition.

        Args:
            node: The function definition node
        """
        if is_test_function(node):
            self._in_test_function = False

    def _check_test_function(self, node: astroid.FunctionDef) -> None:
        """Analyze a test function for fixture usage (Category 3).

        Args:
            node: The test function node
        """
        # Extract fixture dependencies from test signature
        if not node.args or not node.args.args:
            return

        test_name = f"{node.root().file}::{node.name}"
        fixtures_used = []

        for arg in node.args.args:
            if arg.name in {"self", "cls"}:
                continue

            fixtures_used.append(arg.name)

            # Track fixture usage for unused fixture detection
            if arg.name in self.fixture_graph:
                self.fixture_graph[arg.name].used_by.add(test_name)

            # Category 3: Check for shadowed fixtures (PYTEST-FIX-004)
            self._check_shadowed_fixture(arg, node)

        self.test_fixture_usage[test_name] = fixtures_used

    def _check_shadowed_fixture(
        self, arg: astroid.AssignName, test_node: astroid.FunctionDef
    ) -> None:
        """Check if a fixture is shadowed across conftest.py files.

        Args:
            arg: The fixture argument node
            test_node: The test function using the fixture
        """
        fixture_name = arg.name

        # Count how many definitions exist
        definitions = []
        for name, info in self.fixture_graph.items():
            if name == fixture_name:
                definitions.append(info)

        if len(definitions) > 1:
            # Fixture is shadowed
            files = [info.file_path for info in definitions]
            self.add_message(
                "pytest-fix-shadowed",
                node=test_node,
                line=arg.lineno,
                args=(fixture_name, files[0], files[1]),
            )

    # =========================================================================
    # Category 1: Test Body Smells (ast-based checks)
    # =========================================================================

    def visit_call(self, node: astroid.Call) -> None:
        """Visit a function call for Category 1 checks.

        Args:
            node: The call node
        """
        if not self._in_test_function:
            return

        qualname = get_call_qualname(node)
        if not qualname:
            return

        # PYTEST-FLK-001: Check for time.sleep()
        if qualname == "time.sleep" or qualname == "sleep":
            self.add_message(
                "pytest-flk-time-sleep",
                node=node,
                line=node.lineno,
            )

        # PYTEST-FLK-002: Check for open()
        if qualname == "open":
            self.add_message(
                "pytest-flk-io-open",
                node=node,
                line=node.lineno,
            )

        # PYTEST-FLK-004: Check for CWD-sensitive functions
        cwd_functions = {
            "os.getcwd",
            "os.chdir",
            "pathlib.Path.cwd",
            "Path.cwd",
            "getcwd",
            "chdir",
        }
        if qualname in cwd_functions:
            self.add_message(
                "pytest-flk-cwd-dependency",
                node=node,
                line=node.lineno,
            )

    def visit_import(self, node: astroid.Import) -> None:
        """Visit an import statement for Category 1 checks.

        Args:
            node: The import node
        """
        # PYTEST-FLK-003: Check for network module imports
        network_modules = {"requests", "socket", "httpx", "aiohttp", "urllib3"}

        for name, _ in node.names:
            if name in network_modules or name.split(".")[0] in network_modules:
                self.add_message(
                    "pytest-flk-network-import",
                    node=node,
                    line=node.lineno,
                )
                break

    def visit_importfrom(self, node: astroid.ImportFrom) -> None:
        """Visit a from...import statement for Category 1 checks.

        Args:
            node: The import node
        """
        # PYTEST-FLK-003: Check for network module imports
        network_modules = {"requests", "socket", "httpx", "aiohttp", "urllib3"}

        if node.modname:
            base_module = node.modname.split(".")[0]
            if base_module in network_modules:
                self.add_message(
                    "pytest-flk-network-import",
                    node=node,
                    line=node.lineno,
                )

    def visit_if(self, node: astroid.If) -> None:
        """Visit an if statement for Category 1 checks.

        Args:
            node: The if node
        """
        if not self._in_test_function:
            return

        # PYTEST-MNT-001: Check for conditional logic in tests
        # Skip if inside comprehension or context manager
        if is_in_comprehension(node) or is_in_context_manager(node, "raises"):
            return

        self.add_message(
            "pytest-mnt-test-logic",
            node=node,
            line=node.lineno,
        )

    def visit_for(self, node: astroid.For) -> None:
        """Visit a for loop for Category 1 checks.

        Args:
            node: The for node
        """
        if not self._in_test_function:
            return

        # PYTEST-MNT-001: Check for loops in tests
        # Skip if inside comprehension
        if is_in_comprehension(node):
            return

        self.add_message(
            "pytest-mnt-test-logic",
            node=node,
            line=node.lineno,
        )

    def visit_while(self, node: astroid.While) -> None:
        """Visit a while loop for Category 1 checks.

        Args:
            node: The while node
        """
        if not self._in_test_function:
            return

        # PYTEST-MNT-001: Check for loops in tests
        self.add_message(
            "pytest-mnt-test-logic",
            node=node,
            line=node.lineno,
        )

    def visit_assert(self, node: astroid.Assert) -> None:
        """Visit an assert statement for Category 1 checks.

        Args:
            node: The assert node
        """
        if not self._in_test_function:
            return

        # PYTEST-MNT-002: Check for magic constants in asserts
        self._check_magic_constants_in_assert(node)

        # PYTEST-MNT-003: Check for suboptimal asserts
        self._check_suboptimal_assert(node)

    def _check_magic_constants_in_assert(self, node: astroid.Assert) -> None:
        """Check for magic constants in assert statements.

        Args:
            node: The assert node
        """
        # Traverse the test expression looking for constants
        if isinstance(node.test, astroid.Compare):
            # In astroid, Compare has 'ops' attribute: list of (operator, operand) tuples
            for _operator, operand in node.test.ops:
                if isinstance(operand, astroid.Const):
                    if is_magic_constant(operand.value):
                        self.add_message(
                            "pytest-mnt-magic-assert",
                            node=node,
                            line=node.lineno,
                        )
                        return

    def _check_suboptimal_assert(self, node: astroid.Assert) -> None:
        """Check for suboptimal assert patterns.

        Args:
            node: The assert node
        """
        # Check if assert is wrapping a comparison
        # Pattern: assert (x == y) is True or assert assertTrue(x == y)
        if isinstance(node.test, astroid.Call):
            func = node.test.func
            # Check for assertTrue, assertFalse, etc.
            if isinstance(func, astroid.Attribute):
                if func.attrname in {"assertTrue", "assertFalse", "assertEqual"}:
                    # Check if argument is a comparison
                    if node.test.args:
                        arg = node.test.args[0]
                        if isinstance(arg, (astroid.Compare, astroid.BinOp)):
                            self.add_message(
                                "pytest-mnt-suboptimal-assert",
                                node=node,
                                line=node.lineno,
                            )

    # =========================================================================
    # Pass 2 Finalization: Fixture Graph Validation (Category 3)
    # =========================================================================

    def close(self) -> None:
        """Finalize checking after all files have been visited.

        This performs Category 3 checks that require the complete fixture graph.
        """
        if not self.fixture_graph:
            return

        # Category 3: Validate fixture scope dependencies (PYTEST-FIX-003)
        self._check_fixture_scope_dependencies()

        # Category 3: Check for unused fixtures (PYTEST-FIX-005)
        self._check_unused_fixtures()

        # Category 3: Check for stateful session fixtures (PYTEST-FIX-006)
        self._check_stateful_session_fixtures()

    def _check_fixture_scope_dependencies(self) -> None:
        """Check for invalid fixture scope dependencies.

        A fixture cannot depend on a fixture with a narrower scope.
        For example, a session fixture cannot depend on a function fixture.
        """
        for fixture_name, fixture_info in self.fixture_graph.items():
            my_scope = fixture_info.scope

            for dep_name in fixture_info.dependencies:
                if dep_name not in self.fixture_graph:
                    # Dependency is a built-in fixture or not found
                    continue

                dep_info = self.fixture_graph[dep_name]
                dep_scope = dep_info.scope

                # Check if my scope is broader than dependency scope
                if compare_fixture_scopes(my_scope, dep_scope) > 0:
                    self.add_message(
                        "pytest-fix-invalid-scope",
                        node=fixture_info.node,
                        line=fixture_info.node.lineno,
                        args=(fixture_name, my_scope, dep_name, dep_scope),
                    )

    def _check_unused_fixtures(self) -> None:
        """Check for fixtures that are defined but never used."""
        for fixture_name, fixture_info in self.fixture_graph.items():
            # Skip autouse fixtures (they're used implicitly)
            if fixture_info.autouse:
                continue

            # Check if any tests or other fixtures use this fixture
            is_used = len(fixture_info.used_by) > 0

            # Also check if other fixtures depend on it
            for other_fixture in self.fixture_graph.values():
                if fixture_name in other_fixture.dependencies:
                    is_used = True
                    break

            if not is_used:
                self.add_message(
                    "pytest-fix-unused",
                    node=fixture_info.node,
                    line=fixture_info.node.lineno,
                    args=(fixture_name,),
                )

    def _check_stateful_session_fixtures(self) -> None:
        """Check for session-scoped fixtures that return mutable objects.

        This is a simplified heuristic check. A full implementation would
        require deeper type inference.
        """
        for fixture_name, fixture_info in self.fixture_graph.items():
            if fixture_info.scope != "session":
                continue

            # Look for return statements in the fixture body
            for node in fixture_info.node.body:
                if isinstance(node, astroid.Return) and node.value:
                    # Check if returning a mutable type
                    if isinstance(
                        node.value,
                        (
                            astroid.List,
                            astroid.Dict,
                            astroid.Set,
                            astroid.Call,
                        ),
                    ):
                        # Check for common mutable return patterns
                        if isinstance(node.value, astroid.Call):
                            qualname = get_call_qualname(node.value)
                            mutable_constructors = {
                                "list",
                                "dict",
                                "set",
                                "[]",
                                "{}",
                            }
                            if qualname in mutable_constructors:
                                self.add_message(
                                    "pytest-fix-stateful-session",
                                    node=fixture_info.node,
                                    line=fixture_info.node.lineno,
                                    args=(fixture_name,),
                                )
                        else:
                            self.add_message(
                                "pytest-fix-stateful-session",
                                node=fixture_info.node,
                                line=fixture_info.node.lineno,
                                args=(fixture_name,),
                            )
