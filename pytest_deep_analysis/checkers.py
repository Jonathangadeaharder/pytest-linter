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

from astroid import nodes, Uninferable, InferenceError
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
    has_parametrize_decorator,
    get_parametrize_decorators,
    is_mutation_operation,
    has_database_operations,
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
        node: nodes.FunctionDef,
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
        # Fixture graph: maps fixture name to LIST of FixtureInfo (supports shadowing)
        self.fixture_graph: Dict[str, List[FixtureInfo]] = {}
        # Track which tests use which fixtures
        self.test_fixture_usage: Dict[str, List[str]] = {}
        # Track if we're inside a test function for Category 1 checks
        self._in_test_function = False
        # Track pass completion
        self._pass1_complete = False
        # Track processed fixture nodes to avoid duplicates
        self._processed_fixtures: Set[int] = set()
        # Track current test function for assertion counting
        self._current_test_node: Optional[nodes.FunctionDef] = None
        self._test_has_assertions: bool = False
        self._test_has_state_assertions: bool = False
        self._test_has_mock_verifications: bool = False
        self._assertion_count: int = 0
        # Semantic feedback loop: Track which tests need semantic validation
        self._semantic_validation_tasks: Dict[str, List[str]] = {}
        # Semantic feedback loop Phase 2: Load validation cache from runtime
        self._validation_cache: Dict[str, Dict[str, Any]] = (
            self._load_validation_cache()
        )
        # Cache project root for test ID normalization
        self._project_root: Optional[str] = None
        # Track fixture usage patterns for scope optimization
        self.fixture_usage_locations: Dict[str, Set[str]] = {}  # fixture_name -> set of file paths
        # Track fixture parameters accessed in tests
        self._test_fixture_params: Dict[str, Set[str]] = {}  # test_name -> fixture names used
        # Track global/class variable access for xdist checking
        self._has_shared_state_access: bool = False

    def _get_project_root(self) -> str:
        """Get the project root directory (cwd where pylint was invoked)."""
        if self._project_root is None:
            import os

            self._project_root = os.getcwd()
        return self._project_root

    def _get_test_id(self, node: nodes.FunctionDef) -> str:
        """Get test ID in pytest nodeid format (relative path from project root).

        Args:
            node: The test function node

        Returns:
            Test ID string like "tests/test_api.py::test_user_creation"
        """
        import os
        from pathlib import Path

        file_path = node.root().file if node.root().file else "<unknown>"
        if file_path == "<unknown>":
            return f"{file_path}::{node.name}"

        # Convert absolute path to relative path from project root
        try:
            rel_path = os.path.relpath(file_path, self._get_project_root())
            # Normalize to forward slashes (pytest nodeid format uses / even on Windows)
            rel_path = rel_path.replace(os.sep, "/")
            return f"{rel_path}::{node.name}"
        except ValueError:
            # If paths are on different drives (Windows), use absolute
            # Still normalize to forward slashes
            normalized_path = file_path.replace(os.sep, "/")
            return f"{normalized_path}::{node.name}"

    def _load_validation_cache(self) -> Dict[str, Dict[str, Any]]:
        """Load the validation cache written by the runtime plugin (Phase 2).

        Returns:
            Dictionary mapping test IDs to their validation status
        """
        import json
        from pathlib import Path

        cache_file = Path(".pytest_deep_analysis_cache.json")
        if not cache_file.exists():
            return {}

        try:
            cache_data = json.loads(cache_file.read_text())
            if isinstance(cache_data, dict):
                validation_data = cache_data.get("tests_with_semantic_validation", {})
                return validation_data if isinstance(validation_data, dict) else {}
            return {}
        except (IOError, OSError, json.JSONDecodeError) as e:
            # Log warning but continue - cache is optional
            import sys

            print(f"Warning: Failed to load validation cache: {e}", file=sys.stderr)
            return {}

    # =========================================================================
    # Pass 1: Fixture Discovery
    # =========================================================================

    def visit_module(self, node: nodes.Module) -> None:
        """Visit a module to discover fixtures (Pass 1).

        Args:
            node: The module node
        """
        # Traverse all function definitions in this module
        for child in node.body:
            if isinstance(child, nodes.FunctionDef):
                self._process_potential_fixture(child)

    def _process_potential_fixture(self, node: nodes.FunctionDef) -> None:
        """Process a function that might be a pytest fixture.

        Args:
            node: The function definition node
        """
        if not is_pytest_fixture(node):
            return

        # Avoid processing the same fixture node twice
        node_id = id(node)
        if node_id in self._processed_fixtures:
            return
        self._processed_fixtures.add(node_id)

        # Extract fixture metadata
        scope, autouse = get_fixture_decorator_args(node)
        dependencies = get_fixture_dependencies(node)
        file_path = node.root().file if node.root().file else "<unknown>"

        # Store in the fixture graph (supports multiple definitions per name)
        fixture_info = FixtureInfo(
            name=node.name,
            scope=scope,
            autouse=autouse,
            dependencies=dependencies,
            file_path=file_path,
            node=node,
        )
        if node.name not in self.fixture_graph:
            self.fixture_graph[node.name] = []
        self.fixture_graph[node.name].append(fixture_info)

        # Category 2: Check for autouse=True (PYTEST-FIX-001)
        if autouse:
            self.add_message(
                "pytest-fix-autouse",
                node=node,
                line=node.lineno,
            )

        # W9022: Check for database commits without cleanup
        self._check_fixture_db_commits(node)

    # =========================================================================
    # Pass 2: Test and Fixture Analysis
    # =========================================================================

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Visit a function definition for analysis (Pass 2).

        This handles both test functions (Category 1) and fixture interaction
        checks (Category 3).

        Args:
            node: The function definition node
        """
        if is_test_function(node):
            self._in_test_function = True
            self._current_test_node = node
            self._test_has_assertions = False
            self._test_has_state_assertions = False
            self._test_has_mock_verifications = False
            self._assertion_count = 0
            self._has_shared_state_access = False
            self._check_test_function(node)
            # Check parametrize decorators for anti-patterns
            self._check_parametrize_antipatterns(node)
            # Continue visiting children for Category 1 checks

    def leave_functiondef(self, node: nodes.FunctionDef) -> None:
        """Leave a function definition.

        Args:
            node: The function definition node
        """
        if is_test_function(node):
            # Check for semantic quality issues before leaving
            self._check_test_semantic_quality(node)

            # W9019: Check for assertion roulette (too many assertions)
            self._check_assertion_roulette(node)

            # W9029: Check for pytest-xdist compatibility issues
            if self._has_shared_state_access:
                self.add_message(
                    "pytest-xdist-shared-state",
                    node=node,
                    line=node.lineno,
                    args=(node.name,),
                )

            self._in_test_function = False
            self._current_test_node = None

    def _check_test_function(self, node: nodes.FunctionDef) -> None:
        """Analyze a test function for fixture usage (Category 3).

        Args:
            node: The test function node
        """
        # Extract fixture dependencies from test signature
        if not node.args or not node.args.args:
            return

        test_name = f"{node.root().file}::{node.name}"
        test_file = node.root().file if node.root().file else "<unknown>"
        fixtures_used = []

        for arg in node.args.args:
            if arg.name in {"self", "cls"}:
                continue

            fixtures_used.append(arg.name)

            # Track fixture usage for unused fixture detection
            if arg.name in self.fixture_graph:
                for fixture_info in self.fixture_graph[arg.name]:
                    fixture_info.used_by.add(test_name)

            # Track fixture usage locations for scope optimization
            if arg.name not in self.fixture_usage_locations:
                self.fixture_usage_locations[arg.name] = set()
            self.fixture_usage_locations[arg.name].add(test_file)

            # Category 3: Check for shadowed fixtures (PYTEST-FIX-004)
            self._check_shadowed_fixture(arg, node)

        self.test_fixture_usage[test_name] = fixtures_used
        self._test_fixture_params[test_name] = set(fixtures_used)

    def _check_shadowed_fixture(
        self, arg: nodes.AssignName, test_node: nodes.FunctionDef
    ) -> None:
        """Check if a fixture is shadowed across conftest.py files.

        Args:
            arg: The fixture argument node
            test_node: The test function using the fixture
        """
        fixture_name = arg.name

        # Get all definitions for this fixture name
        if fixture_name not in self.fixture_graph:
            return

        definitions = self.fixture_graph[fixture_name]

        if len(definitions) > 1:
            # Fixture is shadowed - multiple definitions exist
            files = [info.file_path for info in definitions]
            # Get unique file paths
            unique_files = list(dict.fromkeys(files))  # Preserve order

            # Warn about shadowing even in same file (redefinition)
            # or across different files (conftest shadowing)
            self.add_message(
                "pytest-fix-shadowed",
                node=test_node,
                line=arg.lineno,
                args=(
                    fixture_name,
                    files[0],
                    files[-1] if len(unique_files) > 1 else files[0],
                ),
            )

    def _check_test_semantic_quality(self, node: nodes.FunctionDef) -> None:
        """Check test function for semantic quality issues (BDD/PBT/DbC alignment).

        This implements the new semantic checks:
        - E9014: Assertion-free tests (H-3)
        - W9015: Mock-only verification (H-9)
        - W9016: BDD traceability
        - W9017: PBT hints

        Args:
            node: The test function node
        """
        test_name = node.name

        # E9014: Check for assertion-free tests (CRITICAL)
        # Skip if test is expected to raise (pytest.raises context manager)
        has_pytest_raises = self._has_pytest_raises(node)
        if not self._test_has_assertions and not has_pytest_raises:
            self.add_message(
                "pytest-test-no-assert",
                node=node,
                line=node.lineno,
                args=(test_name,),
            )

        # W9015: Check for interaction-only tests (mock verify without state checks)
        if self._test_has_mock_verifications and not self._test_has_state_assertions:
            self.add_message(
                "pytest-mock-only-verify",
                node=node,
                line=node.lineno,
                args=(test_name,),
            )

        # Build test ID for cache lookup (semantic feedback loop Phase 2)
        test_id = self._get_test_id(node)
        test_cache = self._validation_cache.get(test_id, {})

        # W9016: Check for BDD traceability
        if not self._has_bdd_traceability(node):
            # Semantic feedback loop Phase 2: Check if runtime validated this test
            bdd_validated = test_cache.get("bdd", {}).get("validated", False)
            if not bdd_validated:
                self.add_message(
                    "pytest-bdd-missing-scenario",
                    node=node,
                    line=node.lineno,
                    args=(test_name,),
                )
                # Semantic feedback loop Phase 1: Track that this test needs validation
                self._track_semantic_validation_task(node, "bdd")

        # W9017: Check if parametrize could be PBT
        if self._should_suggest_pbt(node):
            # Semantic feedback loop Phase 2: Check if runtime validated this test
            pbt_validated = test_cache.get("pbt", {}).get("validated", False)
            if not pbt_validated:
                self.add_message(
                    "pytest-no-property-test-hint",
                    node=node,
                    line=node.lineno,
                    args=(test_name,),
                )
                # Semantic feedback loop Phase 1: Track that this test needs validation
                self._track_semantic_validation_task(node, "pbt")

    def _has_pytest_raises(self, node: nodes.FunctionDef) -> bool:
        """Check if test uses pytest.raises context manager.

        Args:
            node: The test function node

        Returns:
            True if pytest.raises is used
        """
        for with_node in node.nodes_of_class(nodes.With):
            for item in with_node.items:
                context_expr = item[0]
                if isinstance(context_expr, nodes.Call):
                    qualname = get_call_qualname(context_expr)
                    if qualname in {"pytest.raises", "raises"}:
                        return True
        return False

    def _has_bdd_traceability(self, node: nodes.FunctionDef) -> bool:
        """Check if test has BDD traceability markers.

        Args:
            node: The test function node

        Returns:
            True if test has BDD traceability
        """
        # Check for @pytest.mark.scenario decorator
        if node.decorators:
            for decorator in node.decorators.nodes:
                qualname = ""
                if isinstance(decorator, nodes.Attribute):
                    qualname = decorator.as_string()
                elif isinstance(decorator, nodes.Call):
                    if isinstance(decorator.func, nodes.Attribute):
                        qualname = decorator.func.as_string()

                if "scenario" in qualname or "feature" in qualname:
                    return True

        # Check for Gherkin references in docstring
        if node.doc_node:
            docstring = node.doc_node.value.lower()
            gherkin_keywords = ["given", "when", "then", "scenario:", "feature:"]
            if any(keyword in docstring for keyword in gherkin_keywords):
                return True

        return False

    def _should_suggest_pbt(self, node: nodes.FunctionDef) -> bool:
        """Check if test should use property-based testing.

        Args:
            node: The test function node

        Returns:
            True if PBT would be beneficial
        """
        # Check for @pytest.mark.parametrize with many parameters
        if node.decorators:
            for decorator in node.decorators.nodes:
                if isinstance(decorator, nodes.Call):
                    qualname = ""
                    if isinstance(decorator.func, nodes.Attribute):
                        qualname = decorator.func.as_string()

                    if "parametrize" in qualname:
                        # Check if already using hypothesis
                        for dec in node.decorators.nodes:
                            dec_str = dec.as_string()
                            if "hypothesis" in dec_str or "given" in dec_str:
                                return False  # Already using PBT

                        # Check number of parameter sets
                        if len(decorator.args) >= 2:
                            param_values = decorator.args[1]
                            # If it's a list with >3 items, suggest PBT
                            if isinstance(param_values, nodes.List):
                                if len(param_values.elts) > 3:
                                    return True

        return False

    # =========================================================================
    # Category 1: Test Body Smells (ast-based checks)
    # =========================================================================

    def visit_call(self, node: nodes.Call) -> None:
        """Visit a function call for Category 1 checks.

        Args:
            node: The call node
        """
        if not self._in_test_function:
            return

        qualname = get_call_qualname(node)
        if not qualname:
            return

        # Track mock verification calls (for W9015)
        mock_verify_methods = {
            "assert_called",
            "assert_called_once",
            "assert_called_with",
            "assert_called_once_with",
            "assert_any_call",
            "assert_has_calls",
            "assert_not_called",
        }
        if any(qualname.endswith(f".{method}") for method in mock_verify_methods):
            self._test_has_mock_verifications = True

        # W9023: Check for fixture mutation (mutating method calls)
        if is_mutation_operation(node):
            self._check_fixture_mutation(node)

        # PYTEST-FLK-001: Check for time.sleep()
        if qualname == "time.sleep" or qualname == "sleep":
            self.add_message(
                "pytest-flk-time-sleep",
                node=node,
                line=node.lineno,
            )

        # PYTEST-FLK-002/W9005: Check for open() and Mystery Guest pattern
        if qualname == "open":
            # Enhanced check: Determine if this is a "Mystery Guest"
            # A Mystery Guest is file I/O without a resource fixture dependency
            has_resource_fixture = False

            if self._current_test_node:
                # Get fixture dependencies of the current test
                test_fixtures = set(get_fixture_dependencies(self._current_test_node))

                # Known pytest resource fixtures
                resource_fixtures = {
                    "tmp_path",
                    "tmp_path_factory",
                    "tmpdir",
                    "tmpdir_factory",
                }

                # Check if test uses any resource fixture
                has_resource_fixture = bool(test_fixtures & resource_fixtures)

            if not has_resource_fixture:
                # Mystery Guest: File I/O without clear resource management
                self.add_message(
                    "pytest-flk-mystery-guest",
                    node=node,
                    line=node.lineno,
                )
            else:
                # Has resource fixture, still flag but less severe
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

    def visit_import(self, node: nodes.Import) -> None:
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

    def visit_importfrom(self, node: nodes.ImportFrom) -> None:
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

    def visit_if(self, node: nodes.If) -> None:
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

    def visit_for(self, node: nodes.For) -> None:
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

    def visit_while(self, node: nodes.While) -> None:
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

    def visit_assert(self, node: nodes.Assert) -> None:
        """Visit an assert statement for Category 1 checks.

        Args:
            node: The assert node
        """
        if not self._in_test_function:
            return

        # Track that this test has assertions (for E9014)
        self._test_has_assertions = True
        self._test_has_state_assertions = True  # Most asserts are state checks
        self._assertion_count += 1

        # PYTEST-MNT-002: Check for magic constants in asserts
        self._check_magic_constants_in_assert(node)

        # PYTEST-MNT-003: Check for suboptimal asserts
        self._check_suboptimal_assert(node)

    def _check_magic_constants_in_assert(self, node: nodes.Assert) -> None:
        """Check for magic constants in assert statements.

        Args:
            node: The assert node
        """
        # Traverse the test expression looking for constants
        if isinstance(node.test, nodes.Compare):
            # In astroid, Compare has 'ops' attribute: list of (operator, operand) tuples
            for _operator, operand in node.test.ops:
                if isinstance(operand, nodes.Const):
                    if is_magic_constant(operand.value):
                        self.add_message(
                            "pytest-mnt-magic-assert",
                            node=node,
                            line=node.lineno,
                        )
                        return

    def _check_suboptimal_assert(self, node: nodes.Assert) -> None:
        """Check for suboptimal assert patterns.

        Args:
            node: The assert node
        """
        # Check if assert is wrapping a comparison
        # Pattern: assert (x == y) is True or assert assertTrue(x == y)
        if isinstance(node.test, nodes.Call):
            func = node.test.func
            # Check for assertTrue, assertFalse, etc.
            if isinstance(func, nodes.Attribute):
                if func.attrname in {"assertTrue", "assertFalse", "assertEqual"}:
                    # Check if argument is a comparison
                    if node.test.args:
                        arg = node.test.args[0]
                        if isinstance(arg, (nodes.Compare, nodes.BinOp)):
                            self.add_message(
                                "pytest-mnt-suboptimal-assert",
                                node=node,
                                line=node.lineno,
                            )

    def _check_assertion_roulette(self, node: nodes.FunctionDef) -> None:
        """Check for assertion roulette (W9019): too many assertions without explanation.

        Args:
            node: The test function node
        """
        threshold = 3

        # Skip if test is parametrized (multiple assertions are justified)
        if node.decorators:
            for decorator in node.decorators.nodes:
                # Check for @pytest.mark.parametrize
                if isinstance(decorator, nodes.Call):
                    if get_call_qualname(decorator) in {
                        "pytest.mark.parametrize",
                        "parametrize",
                    }:
                        return

        # Check assertion count
        if self._assertion_count > threshold:
            self.add_message(
                "pytest-mnt-assertion-roulette",
                node=node,
                line=node.lineno,
                args=(self._assertion_count,),
            )

    def visit_try(self, node: nodes.Try) -> None:
        """Check for raw exception handling (W9020) in tests.

        Args:
            node: The try/except node
        """
        if not self._in_test_function:
            return

        # Only flag if there are exception handlers
        if not node.handlers:
            return

        # Check if this try/except is inside a pytest.raises context
        # If so, it's acceptable (testing exception attributes)
        if is_in_context_manager(node, "raises"):
            return

        # Raw try/except in a test is a smell
        self.add_message(
            "pytest-mnt-raw-exception-handling",
            node=node,
            line=node.lineno,
        )

    def visit_assign(self, node: nodes.Assign) -> None:
        """Check for fixture mutations and shared state assignments.

        Args:
            node: The assignment node
        """
        if not self._in_test_function:
            return

        # W9023: Check for fixture mutation via assignment
        if is_mutation_operation(node):
            self._check_fixture_mutation(node)

        # W9029: Check for global/class variable assignment (shared state)
        for target in node.targets:
            if isinstance(target, nodes.Name):
                # Check if it's a global variable
                if self._is_global_or_class_variable(target):
                    self._has_shared_state_access = True
            elif isinstance(target, nodes.Attribute):
                # Check if it's a class attribute
                if self._is_class_attribute_access(target):
                    self._has_shared_state_access = True

    def visit_augassign(self, node: nodes.AugAssign) -> None:
        """Check for fixture mutations via augmented assignment.

        Args:
            node: The augmented assignment node
        """
        if not self._in_test_function:
            return

        # W9023: Check for fixture mutation
        if is_mutation_operation(node):
            self._check_fixture_mutation(node)

    def visit_name(self, node: nodes.Name) -> None:
        """Check for global variable access (shared state).

        Args:
            node: The name node
        """
        if not self._in_test_function:
            return
        
        # Skip names in decorators - they're not part of the test body
        parent = node.parent
        while parent:
            if isinstance(parent, nodes.Decorators):
                return
            if isinstance(parent, nodes.FunctionDef):
                break
            parent = parent.parent

        # W9029: Check for global variable access
        if self._is_global_or_class_variable(node):
            self._has_shared_state_access = True

    def _track_semantic_validation_task(
        self, node: nodes.FunctionDef, validation_type: str
    ) -> None:
        """Track that a test needs semantic validation (feedback loop Phase 1).

        Args:
            node: The test function node
            validation_type: Type of validation needed ("bdd", "pbt", "dbc")
        """
        # Build test identifier in pytest nodeid format
        test_id = self._get_test_id(node)

        # Add validation type to this test's task list
        if test_id not in self._semantic_validation_tasks:
            self._semantic_validation_tasks[test_id] = []

        if validation_type not in self._semantic_validation_tasks[test_id]:
            self._semantic_validation_tasks[test_id].append(validation_type)

    # =========================================================================
    # Pass 2 Finalization: Fixture Graph Validation (Category 3)
    # =========================================================================

    def close(self) -> None:
        """Finalize checking after all files have been visited.

        This performs Category 3 checks that require the complete fixture graph.
        """
        # Semantic feedback loop Phase 1: Write task file for runtime plugin
        # This tells the runtime plugin which tests need validation
        # This runs regardless of whether there's a fixture graph
        if self._semantic_validation_tasks:
            import json
            import sys
            from pathlib import Path

            task_file = Path(".pytest_deep_analysis_tasks.json")
            try:
                task_file.write_text(
                    json.dumps(self._semantic_validation_tasks, indent=2)
                )
            except (IOError, OSError) as e:
                # Log warning but continue - task file is optional
                print(
                    f"Warning: Failed to write validation task file: {e}",
                    file=sys.stderr,
                )

        # Early return if no fixture graph available
        if not self.fixture_graph:
            return

        # Category 3: Validate fixture scope dependencies (PYTEST-FIX-003)
        self._check_fixture_scope_dependencies()

        # Category 3: Check for unused fixtures (PYTEST-FIX-005)
        self._check_unused_fixtures()

        # Category 3: Check for stateful session fixtures (PYTEST-FIX-006)
        self._check_stateful_session_fixtures()

        # W9018: Check for complex fixtures without contracts (DbC)
        self._check_fixtures_without_contracts()

        # W9024: Check for overly broad fixture scopes
        self._check_overly_broad_scopes()

        # W9030: Check for xdist fixture I/O issues
        self._check_xdist_fixture_io()

    def _check_fixture_scope_dependencies(self) -> None:
        """Check for invalid fixture scope dependencies.

        A fixture cannot depend on a fixture with a narrower scope.
        For example, a session fixture cannot depend on a function fixture.
        """
        for fixture_name, fixture_infos in self.fixture_graph.items():
            for fixture_info in fixture_infos:
                my_scope = fixture_info.scope

                for dep_name in fixture_info.dependencies:
                    if dep_name not in self.fixture_graph:
                        # Dependency is a built-in fixture or not found
                        continue

                    # Check against first definition (pytest uses first found)
                    dep_info = self.fixture_graph[dep_name][0]
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
        for fixture_name, fixture_infos in self.fixture_graph.items():
            for fixture_info in fixture_infos:
                # Skip autouse fixtures (they're used implicitly)
                if fixture_info.autouse:
                    continue

                # Check if any tests or other fixtures use this fixture
                is_used = len(fixture_info.used_by) > 0

                # Also check if other fixtures depend on it
                for other_fixture_list in self.fixture_graph.values():
                    for other_fixture in other_fixture_list:
                        if fixture_name in other_fixture.dependencies:
                            is_used = True
                            break
                    if is_used:
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

        Uses astroid's type inference for more accurate detection.
        """
        for fixture_name, fixture_infos in self.fixture_graph.items():
            for fixture_info in fixture_infos:
                if fixture_info.scope != "session":
                    continue

                # Look for return statements in the fixture body (recursively)
                for node in fixture_info.node.nodes_of_class(nodes.Return):
                    if node.value and self._is_mutable_return(node.value):
                        self.add_message(
                            "pytest-fix-stateful-session",
                            node=fixture_info.node,
                            line=fixture_info.node.lineno,
                            args=(fixture_name,),
                        )
                        break  # Only report once per fixture

    def _infer_mutable_type(self, value_node: nodes.NodeNG) -> bool:
        """Use astroid inference to check if value is a mutable type.

        Args:
            value_node: The value node

        Returns:
            True if inferred to be mutable
        """
        try:
            for inferred in value_node.infer():
                if inferred is Uninferable:
                    continue
                if hasattr(inferred, "pytype"):
                    pytype = inferred.pytype()
                    if pytype in ("builtins.list", "builtins.dict", "builtins.set"):
                        return True
        except (InferenceError, AttributeError, StopIteration):
            pass
        return False

    def _is_mutable_return(self, value_node: nodes.NodeNG) -> bool:
        """Check if a return value is mutable using type inference.

        Args:
            value_node: The value being returned

        Returns:
            True if the value is likely mutable
        """
        # Direct mutable literals - these are definitely mutable
        if isinstance(value_node, (nodes.List, nodes.Dict, nodes.Set)):
            return True

        # Call nodes - use inference for better accuracy
        if isinstance(value_node, nodes.Call):
            qualname = get_call_qualname(value_node)
            if qualname in {"list", "dict", "set"}:
                return True

            # Try astroid's inference engine for better detection
            if self._infer_mutable_type(value_node):
                return True

        return False

    def _check_fixtures_without_contracts(self) -> None:
        """Check for complex fixtures without formal contracts (DbC).

        W9018: Suggests icontract decorators for fixtures with:
        - Multiple statements (complex logic)
        - Database/network operations
        - Resource management (yield fixtures)
        """
        for fixture_name, fixture_infos in self.fixture_graph.items():
            for fixture_info in fixture_infos:
                # Check if fixture already has contract decorators
                if self._has_contract_decorators(fixture_info.node):
                    continue

                # Check if fixture is complex enough to warrant contracts
                if self._is_complex_fixture(fixture_info.node):
                    self.add_message(
                        "pytest-no-contract-hint",
                        node=fixture_info.node,
                        line=fixture_info.node.lineno,
                        args=(fixture_name,),
                    )

    def _has_contract_decorators(self, node: nodes.FunctionDef) -> bool:
        """Check if function has icontract decorators.

        Args:
            node: The function node

        Returns:
            True if icontract decorators are present
        """
        if not node.decorators:
            return False

        for decorator in node.decorators.nodes:
            dec_str = decorator.as_string()
            if "icontract" in dec_str or "require" in dec_str or "ensure" in dec_str:
                return True

        return False

    def _is_complex_fixture(self, node: nodes.FunctionDef) -> bool:
        """Check if fixture is complex enough to warrant contracts.

        Args:
            node: The fixture function node

        Returns:
            True if fixture is complex
        """
        # Count statements (excluding docstring)
        body = node.body
        if (
            body
            and isinstance(body[0], nodes.Expr)
            and isinstance(body[0].value, nodes.Const)
        ):
            # Skip docstring
            body = body[1:]

        statement_count = len(body)

        # Complex if >3 statements
        if statement_count > 3:
            return True

        # Check for database/network keywords in code
        complexity_indicators = {
            "connection",
            "cursor",
            "execute",
            "commit",
            "rollback",
            "session",
            "transaction",
            "database",
            "db",
            "request",
            "response",
            "http",
            "api",
        }

        code_str = node.as_string().lower()
        if any(indicator in code_str for indicator in complexity_indicators):
            return True

        # Check for yield (resource management fixtures)
        for _yield_node in node.nodes_of_class(nodes.Yield):
            return True

        return False

    # =========================================================================
    # New Enhancement Methods
    # =========================================================================

    def _check_fixture_db_commits(self, node: nodes.FunctionDef) -> None:
        """Check if fixture performs database commits without cleanup.

        W9022: Detects database operations without explicit rollback or cleanup.

        Args:
            node: The fixture function node
        """
        from pytest_deep_analysis.config import get_config
        config = get_config()

        has_commit = False
        has_rollback = False
        has_yield_cleanup = False

        # Check if fixture has yield (for cleanup section)
        for yield_node in node.nodes_of_class(nodes.Yield):
            # Check if there's code after yield (cleanup section)
            yield_parent = yield_node.parent
            if isinstance(yield_parent, nodes.Expr):
                # Find the yield statement index
                if hasattr(node, 'body'):
                    try:
                        yield_idx = node.body.index(yield_parent)
                        # Check if there's cleanup code after yield
                        if yield_idx < len(node.body) - 1:
                            has_yield_cleanup = True
                    except ValueError:
                        # The yield statement's parent is not found in the function body.
                        # This can happen in rare cases; we ignore and do not set has_yield_cleanup.
                        pass

        # Check for database operations using configured method lists
        for call_node in node.nodes_of_class(nodes.Call):
            if has_database_operations(call_node):
                qualname = get_call_qualname(call_node)
                if qualname:
                    method_name = qualname.split('.')[-1]
                    if method_name in config.db_commit_methods:
                        has_commit = True
                    elif method_name in config.db_rollback_methods:
                        has_rollback = True

        # Warn if has commit but no rollback and no yield cleanup
        if has_commit and not has_rollback and not has_yield_cleanup:
            self.add_message(
                "pytest-fix-db-commit-no-cleanup",
                node=node,
                line=node.lineno,
                args=(node.name,),
            )

    def _check_fixture_mutation(self, node: nodes.NodeNG) -> None:
        """Check if test mutates a fixture value in-place.

        W9023: Detects mutations of fixture return values.

        Args:
            node: The mutation node (call, assign, or augassign)
        """
        if not self._current_test_node:
            return

        # Get the target being mutated
        target = None
        if isinstance(node, nodes.Call):
            # Mutating method call like fixture.append()
            if isinstance(node.func, nodes.Attribute):
                target = node.func.expr
        elif isinstance(node, nodes.Assign):
            # Direct assignment like fixture[0] = val
            for assign_target in node.targets:
                if isinstance(assign_target, (nodes.Attribute, nodes.Subscript)):
                    if isinstance(assign_target, nodes.Subscript):
                        target = assign_target.value
                    elif isinstance(assign_target, nodes.Attribute):
                        target = assign_target.expr
                    break
        elif isinstance(node, nodes.AugAssign):
            # Augmented assignment like fixture += [1]
            if isinstance(node.target, nodes.Name):
                target = node.target

        # Check if target is a fixture parameter
        if target and isinstance(target, nodes.Name):
            test_name = f"{self._current_test_node.root().file}::{self._current_test_node.name}"
            if test_name in self._test_fixture_params:
                if target.name in self._test_fixture_params[test_name]:
                    # Check if the fixture has broader scope than function
                    if target.name in self.fixture_graph:
                        for fixture_info in self.fixture_graph[target.name]:
                            if fixture_info.scope != "function":
                                self.add_message(
                                    "pytest-test-fixture-mutation",
                                    node=node,
                                    line=node.lineno,
                                    args=(self._current_test_node.name,),
                                )
                                return

    def _is_global_or_class_variable(self, node: nodes.Name) -> bool:
        """Check if a name node refers to a global or class variable.

        Args:
            node: The name node

        Returns:
            True if it's a global or class variable
        """
        # Try to find the definition
        try:
            # Look up the scope
            scope = node.scope()
            if scope:
                # Check if defined in module scope (global)
                if isinstance(scope, nodes.Module):
                    return True
                # Check if defined in class scope
                if isinstance(scope, nodes.ClassDef):
                    return True
        except (AttributeError, KeyError):
            # If scope lookup fails, assume not global/class variable and return False.
            pass

        return False

    def _is_class_attribute_access(self, node: nodes.Attribute) -> bool:
        """Check if an attribute access is to a class attribute.

        Args:
            node: The attribute node

        Returns:
            True if it's a class attribute access
        """
        # Check if expr is a class name or self/cls
        if isinstance(node.expr, nodes.Name):
            if node.expr.name in {'self', 'cls'}:
                return True
            # Try to determine if it's a class
            try:
                for inferred in node.expr.infer():
                    if isinstance(inferred, nodes.ClassDef):
                        return True
            except (InferenceError, AttributeError, StopIteration):
                pass

        return False

    def _check_parametrize_antipatterns(self, node: nodes.FunctionDef) -> None:
        """Check for parametrize anti-patterns.

        Checks for:
        - W9025: Empty or single-value parametrize
        - W9026: Duplicate parameter values
        - W9027: Excessive parameter combinations

        Args:
            node: The test function node
        """
        from pytest_deep_analysis.config import get_config
        config = get_config()

        parametrize_decorators = get_parametrize_decorators(node)

        if not parametrize_decorators:
            return

        # W9027: Check for explosion (multiple parametrize decorators)
        if len(parametrize_decorators) > 1:
            # Calculate total combinations
            total_combinations = 1
            for decorator in parametrize_decorators:
                # Try to extract parameter count
                if decorator.args and len(decorator.args) >= 2:
                    values_arg = decorator.args[1]
                    if isinstance(values_arg, (nodes.List, nodes.Tuple)):
                        total_combinations *= len(values_arg.elts)

            if total_combinations > config.max_parametrize_combinations:
                self.add_message(
                    "pytest-parametrize-explosion",
                    node=node,
                    line=parametrize_decorators[0].lineno,
                    args=(total_combinations,),
                )

        # Check each parametrize decorator
        for decorator in parametrize_decorators:
            if not decorator.args or len(decorator.args) < 2:
                continue

            param_names = decorator.args[0]
            param_values = decorator.args[1]

            # W9025: Check for empty or single value
            if isinstance(param_values, (nodes.List, nodes.Tuple)):
                if len(param_values.elts) == 0:
                    self.add_message(
                        "pytest-parametrize-empty",
                        node=node,
                        line=decorator.lineno,
                    )
                elif len(param_values.elts) == 1:
                    self.add_message(
                        "pytest-parametrize-empty",
                        node=node,
                        line=decorator.lineno,
                    )

                # W9026: Check for duplicates
                values_strs = []
                for val in param_values.elts:
                    val_str = val.as_string()
                    if val_str in values_strs:
                        # Get param name for message
                        param_name = param_names.as_string() if hasattr(param_names, 'as_string') else 'parameters'
                        self.add_message(
                            "pytest-parametrize-duplicate",
                            node=node,
                            line=decorator.lineno,
                            args=(param_name,),
                        )
                        break
                    values_strs.append(val_str)

    def _check_overly_broad_scopes(self) -> None:
        """Check for fixtures with overly broad scopes.

        W9024: Detects fixtures that could be narrowed in scope.
        """
        for fixture_name, fixture_infos in self.fixture_graph.items():
            for fixture_info in fixture_infos:
                # Skip function-scoped fixtures (already narrowest)
                if fixture_info.scope == "function":
                    continue

                # Get usage locations
                usage_locations = self.fixture_usage_locations.get(fixture_name, set())

                if not usage_locations:
                    continue

                # Determine appropriate scope based on usage
                suggested_scope = None
                scope_context = None

                if fixture_info.scope == "session":
                    # Check if only used in one module
                    if len(usage_locations) == 1:
                        suggested_scope = "module"
                        scope_context = "module"
                    # Could also check for class-level usage, but that's more complex

                elif fixture_info.scope == "module":
                    # Check if only used by one test
                    test_count = len(fixture_info.used_by)
                    if test_count == 1:
                        suggested_scope = "function"
                        scope_context = "test"

                elif fixture_info.scope == "class":
                    # Check if only used by one test
                    test_count = len(fixture_info.used_by)
                    if test_count == 1:
                        suggested_scope = "function"
                        scope_context = "test"

                if suggested_scope:
                    self.add_message(
                        "pytest-fix-overly-broad-scope",
                        node=fixture_info.node,
                        line=fixture_info.node.lineno,
                        args=(fixture_name, fixture_info.scope, scope_context, suggested_scope),
                    )

    def _check_xdist_fixture_io(self) -> None:
        """Check for fixtures that perform I/O without tmp_path.

        W9030: Detects fixtures that may conflict in parallel execution.
        """
        for fixture_name, fixture_infos in self.fixture_graph.items():
            for fixture_info in fixture_infos:
                # Check if fixture uses file I/O
                has_file_io = False
                has_tmp_path = False

                # Check for file operations in fixture
                for call_node in fixture_info.node.nodes_of_class(nodes.Call):
                    qualname = get_call_qualname(call_node)
                    if qualname:
                        # File I/O operations
                        if qualname in {'open', 'Path', 'pathlib.Path'}:
                            has_file_io = True
                        # Check for operations on file-like objects
                        method_name = qualname.split('.')[-1]
                        if method_name in {'read', 'write', 'mkdir', 'touch', 'unlink'}:
                            has_file_io = True

                # Check if fixture depends on tmp_path or tmp_path_factory
                tmp_path_fixtures = {'tmp_path', 'tmp_path_factory', 'tmpdir', 'tmpdir_factory'}
                if any(dep in tmp_path_fixtures for dep in fixture_info.dependencies):
                    has_tmp_path = True

                # Warn if has file I/O but no tmp_path
                if has_file_io and not has_tmp_path:
                    self.add_message(
                        "pytest-xdist-fixture-io",
                        node=fixture_info.node,
                        line=fixture_info.node.lineno,
                        args=(fixture_name,),
                    )
