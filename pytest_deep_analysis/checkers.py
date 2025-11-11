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
from pytest_deep_analysis.config import get_config
from pytest_deep_analysis.xdist_support import (
    is_xdist_worker,
    get_worker_id,
    XdistCoordinator,
)
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
        # Track fixtures used in current test function
        self._current_test_fixtures: Set[str] = set()
        # Track pass completion
        self._pass1_complete = False
        # Load configuration from pyproject.toml
        self.config_obj = get_config()

    def add_message(
        self,
        msgid: str,
        line: Optional[int] = None,
        node: Optional[astroid.NodeNG] = None,
        args: Any = None,
        confidence: Any = None,
        col_offset: Optional[int] = None,
    ) -> None:
        """Override add_message to respect configuration.

        Args:
            msgid: Message ID or symbol
            line: Line number
            node: AST node
            args: Message arguments
            confidence: Confidence level
            col_offset: Column offset
        """
        # Check if rule is enabled in config
        if not self.config_obj.is_rule_enabled(msgid):
            return

        # Check if file should be ignored
        if node and hasattr(node.root(), "file"):
            file_path = node.root().file
            if file_path and self.config_obj.should_ignore_file(file_path):
                return

        # Call parent add_message
        super().add_message(
            msgid=msgid,
            line=line,
            node=node,
            args=args,
            confidence=confidence,
            col_offset=col_offset,
        )

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
            # Category 1: Check for parametrize misuse (W9015, W9016)
            self._check_parametrize_decorators(node)
            # Continue visiting children for Category 1 checks

    def leave_functiondef(self, node: astroid.FunctionDef) -> None:
        """Leave a function definition.

        Args:
            node: The function definition node
        """
        if is_test_function(node):
            self._in_test_function = False
            self._current_test_fixtures.clear()

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
            # Store for fixture mutation detection
            self._current_test_fixtures.add(arg.name)

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

    def _check_parametrize_decorators(self, node: astroid.FunctionDef) -> None:
        """Check for parametrize misuse and anti-patterns.

        Args:
            node: The test function node
        """
        if not node.decorators:
            return

        for decorator in node.decorators.nodes:
            # Check if this is a pytest.mark.parametrize decorator
            if not isinstance(decorator, astroid.Call):
                continue

            # Get the qualified name
            if isinstance(decorator.func, astroid.Attribute):
                # pytest.mark.parametrize
                if (
                    isinstance(decorator.func.expr, astroid.Attribute)
                    and decorator.func.expr.attrname == "mark"
                    and decorator.func.attrname == "parametrize"
                ):
                    self._validate_parametrize(decorator, node)
            elif isinstance(decorator.func, astroid.Name):
                # Direct parametrize import
                if decorator.func.name == "parametrize":
                    self._validate_parametrize(decorator, node)

    def _validate_parametrize(
        self, decorator: astroid.Call, test_node: astroid.FunctionDef
    ) -> None:
        """Validate a parametrize decorator for common issues.

        Args:
            decorator: The parametrize decorator call
            test_node: The test function being decorated
        """
        if not decorator.args or len(decorator.args) < 2:
            return

        # First arg is parameter names (string or list of strings)
        param_names_node = decorator.args[0]
        # Second arg is parameter values (list of tuples/values)
        param_values_node = decorator.args[1]

        # Extract parameter names
        param_names = []
        if isinstance(param_names_node, astroid.Const):
            # Single string like "a,b" or "a, b"
            param_names = [
                name.strip() for name in param_names_node.value.split(",")
            ]
        elif isinstance(param_names_node, (astroid.List, astroid.Tuple)):
            # List of strings like ["a", "b"]
            for elem in param_names_node.elts:
                if isinstance(elem, astroid.Const):
                    param_names.append(elem.value)

        # W9016: Check parameter count matches function signature
        if param_names and test_node.args and test_node.args.args:
            # Count non-self/cls parameters in test function
            test_params = [
                arg.name
                for arg in test_node.args.args
                if arg.name not in {"self", "cls"}
            ]

            # Check if parametrize names are in test signature
            # (allowing for fixtures as well)
            expected_count = len(param_names)
            # We need at least the parametrized params in the signature
            if not all(name in [p for p in test_params] for name in param_names):
                # Only warn if there's a clear mismatch we can detect
                pass  # This is complex to detect perfectly

        # W9015: Check for duplicate parameter values
        if isinstance(param_values_node, (astroid.List, astroid.Tuple)):
            # Collect all parameter value combinations
            seen_values = []
            duplicates = []

            for value_node in param_values_node.elts:
                # Convert node to a hashable representation
                value_repr = self._get_node_repr(value_node)
                if value_repr in seen_values:
                    duplicates.append(value_repr)
                else:
                    seen_values.append(value_repr)

            if duplicates:
                self.add_message(
                    "pytest-param-duplicate",
                    node=decorator,
                    line=decorator.lineno,
                    args=(", ".join(set(duplicates)),),
                )

    def _get_node_repr(self, node: astroid.NodeNG) -> str:
        """Get a string representation of an AST node for comparison.

        Args:
            node: The AST node

        Returns:
            String representation of the node
        """
        if isinstance(node, astroid.Const):
            return repr(node.value)
        elif isinstance(node, (astroid.Tuple, astroid.List)):
            return "(" + ", ".join(self._get_node_repr(e) for e in node.elts) + ")"
        else:
            # For more complex nodes, use as_string() which may not be perfect
            # but is better than nothing
            try:
                return node.as_string()
            except Exception:
                return str(id(node))

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

    def visit_assign(self, node: astroid.Assign) -> None:
        """Visit an assignment for Category 1 checks.

        Args:
            node: The assignment node
        """
        if not self._in_test_function:
            return

        # W9014: Check for fixture mutation in tests
        for target in node.targets:
            # Check for attribute assignment to fixtures: fixture.attr = value
            if isinstance(target, astroid.Attribute):
                if hasattr(target.expr, "name") and target.expr.name in self._current_test_fixtures:
                    self.add_message(
                        "pytest-fix-fixture-mutation",
                        node=node,
                        line=node.lineno,
                        args=(target.expr.name,),
                    )
            # Check for item assignment to fixtures: fixture[key] = value
            elif isinstance(target, astroid.Subscript):
                if hasattr(target.value, "name") and target.value.name in self._current_test_fixtures:
                    self.add_message(
                        "pytest-fix-fixture-mutation",
                        node=node,
                        line=node.lineno,
                        args=(target.value.name,),
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

        # If running under pytest-xdist, save worker results for merging
        if is_xdist_worker():
            worker_id = get_worker_id()
            if worker_id:
                coordinator = XdistCoordinator()
                coordinator.save_worker_results(
                    worker_id, self.fixture_graph, self.test_fixture_usage
                )
            # Don't run checks yet - wait for merge
            return

        # Category 3: Validate fixture scope dependencies (PYTEST-FIX-003)
        self._check_fixture_scope_dependencies()

        # Category 3: Check for unused fixtures (PYTEST-FIX-005)
        self._check_unused_fixtures()

        # Category 3: Check for stateful session fixtures (PYTEST-FIX-006)
        self._check_stateful_session_fixtures()

        # Category 3: Check for database commits without cleanup (E9036)
        if self.config_obj.check_db_commits:
            self._check_db_commits_without_cleanup()

        # Category 3: Check for fixture scope overuse (W9037)
        if self.config_obj.check_scope_narrowing:
            self._check_fixture_scope_narrowing()

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

    def _check_db_commits_without_cleanup(self) -> None:
        """Check for fixtures that perform database commits without proper cleanup.

        Detects fixtures that call commit() methods without corresponding
        rollback/cleanup logic, which can cause test pollution.
        """
        for fixture_name, fixture_info in self.fixture_graph.items():
            has_commit = False
            has_yield = False
            has_cleanup = False
            yield_index = -1

            # Analyze fixture body for commit calls and yield statements
            for i, node in enumerate(fixture_info.node.body):
                # Check for yield (indicates setup/teardown pattern)
                if isinstance(node, astroid.Expr) and isinstance(
                    node.value, astroid.Yield
                ):
                    has_yield = True
                    yield_index = i

                # Check for commit calls
                if self._node_contains_commit(node):
                    has_commit = True
                    # If commit is after yield, it's in cleanup section
                    if has_yield and i > yield_index:
                        has_cleanup = True

            # Also check for rollback calls after yield
            if has_yield and not has_cleanup:
                for i in range(yield_index + 1, len(fixture_info.node.body)):
                    if self._node_contains_rollback(fixture_info.node.body[i]):
                        has_cleanup = True
                        break

            # Warn if fixture has commit but no cleanup
            if has_commit and has_yield and not has_cleanup:
                self.add_message(
                    "pytest-fix-db-commit",
                    node=fixture_info.node,
                    line=fixture_info.node.lineno,
                    args=(fixture_name,),
                )

    def _node_contains_commit(self, node: astroid.NodeNG) -> bool:
        """Check if a node contains a database commit call."""
        if isinstance(node, astroid.Expr) and isinstance(node.value, astroid.Call):
            qualname = get_call_qualname(node.value)
            # Check for common commit patterns
            if qualname and "commit" in qualname.lower():
                return True
        # Recursively check child nodes
        for child in node.get_children():
            if self._node_contains_commit(child):
                return True
        return False

    def _node_contains_rollback(self, node: astroid.NodeNG) -> bool:
        """Check if a node contains a database rollback/cleanup call."""
        if isinstance(node, astroid.Expr) and isinstance(node.value, astroid.Call):
            qualname = get_call_qualname(node.value)
            # Check for common rollback patterns
            if qualname and any(
                keyword in qualname.lower()
                for keyword in ["rollback", "close", "cleanup", "teardown"]
            ):
                return True
        # Recursively check child nodes
        for child in node.get_children():
            if self._node_contains_rollback(child):
                return True
        return False

    def _check_fixture_scope_narrowing(self) -> None:
        """Check for fixtures that could use a narrower scope.

        Detects fixtures with broader scopes than necessary based on their
        actual usage patterns.
        """
        for fixture_name, fixture_info in self.fixture_graph.items():
            # Only check fixtures with broader scopes
            if fixture_info.scope not in ("session", "module"):
                continue

            # Skip if unused (already caught by unused fixture check)
            if not fixture_info.used_by:
                continue

            # Collect all files where this fixture is used
            used_files = set()
            used_classes = set()

            for usage in fixture_info.used_by:
                # Usage format: "file::test_name" or "file::Class::test_name"
                parts = usage.split("::")
                if len(parts) >= 1:
                    used_files.add(parts[0])
                if len(parts) >= 3:
                    used_classes.add(f"{parts[0]}::{parts[1]}")

            # Suggest narrowing scope based on usage patterns
            if fixture_info.scope == "session":
                if len(used_files) == 1:
                    self.add_message(
                        "pytest-fix-scope-overuse",
                        node=fixture_info.node,
                        line=fixture_info.node.lineno,
                        args=(fixture_name, "session", "module"),
                    )
            elif fixture_info.scope == "module":
                if len(used_classes) == 1:
                    self.add_message(
                        "pytest-fix-scope-overuse",
                        node=fixture_info.node,
                        line=fixture_info.node.lineno,
                        args=(fixture_name, "module", "class"),
                    )
                elif len(fixture_info.used_by) == 1:
                    self.add_message(
                        "pytest-fix-scope-overuse",
                        node=fixture_info.node,
                        line=fixture_info.node.lineno,
                        args=(fixture_name, "module", "function"),
                    )
