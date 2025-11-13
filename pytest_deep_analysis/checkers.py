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
        self._current_test_node: Optional[astroid.FunctionDef] = None
        self._test_has_assertions: bool = False
        self._test_has_state_assertions: bool = False
        self._test_has_mock_verifications: bool = False
        # Semantic feedback loop: Track which tests need semantic validation
        self._semantic_validation_tasks: Dict[str, List[str]] = {}
        # Semantic feedback loop Phase 2: Load validation cache from runtime
        self._validation_cache: Dict[str, Dict[str, Any]] = self._load_validation_cache()

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
            return cache_data.get("tests_with_semantic_validation", {})
        except Exception:
            # Fail silently if cache is corrupted
            return {}

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
            self._current_test_node = node
            self._test_has_assertions = False
            self._test_has_state_assertions = False
            self._test_has_mock_verifications = False
            self._assertion_count = 0
            self._check_test_function(node)
            # Continue visiting children for Category 1 checks

    def leave_functiondef(self, node: astroid.FunctionDef) -> None:
        """Leave a function definition.

        Args:
            node: The function definition node
        """
        if is_test_function(node):
            # Check for semantic quality issues before leaving
            self._check_test_semantic_quality(node)

            # W9019: Check for assertion roulette (too many assertions)
            self._check_assertion_roulette(node)

            self._in_test_function = False
            self._current_test_node = None

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
                for fixture_info in self.fixture_graph[arg.name]:
                    fixture_info.used_by.add(test_name)

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
                args=(fixture_name, files[0], files[-1] if len(unique_files) > 1 else files[0]),
            )

    def _check_test_semantic_quality(self, node: astroid.FunctionDef) -> None:
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
        file_path = node.root().file if node.root().file else "<unknown>"
        test_id = f"{file_path}::{node.name}"
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

    def _has_pytest_raises(self, node: astroid.FunctionDef) -> bool:
        """Check if test uses pytest.raises context manager.

        Args:
            node: The test function node

        Returns:
            True if pytest.raises is used
        """
        for with_node in node.nodes_of_class(astroid.With):
            for item in with_node.items:
                context_expr = item[0]
                if isinstance(context_expr, astroid.Call):
                    qualname = get_call_qualname(context_expr)
                    if qualname in {"pytest.raises", "raises"}:
                        return True
        return False

    def _has_bdd_traceability(self, node: astroid.FunctionDef) -> bool:
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
                if isinstance(decorator, astroid.Attribute):
                    qualname = decorator.as_string()
                elif isinstance(decorator, astroid.Call):
                    if isinstance(decorator.func, astroid.Attribute):
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

    def _should_suggest_pbt(self, node: astroid.FunctionDef) -> bool:
        """Check if test should use property-based testing.

        Args:
            node: The test function node

        Returns:
            True if PBT would be beneficial
        """
        # Check for @pytest.mark.parametrize with many parameters
        if node.decorators:
            for decorator in node.decorators.nodes:
                if isinstance(decorator, astroid.Call):
                    qualname = ""
                    if isinstance(decorator.func, astroid.Attribute):
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
                            if isinstance(param_values, astroid.List):
                                if len(param_values.elts) > 3:
                                    return True

        return False

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

        # Track mock verification calls (for W9015)
        mock_verify_methods = {
            "assert_called", "assert_called_once", "assert_called_with",
            "assert_called_once_with", "assert_any_call", "assert_has_calls",
            "assert_not_called"
        }
        if any(qualname.endswith(f".{method}") for method in mock_verify_methods):
            self._test_has_mock_verifications = True

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

        # Track that this test has assertions (for E9014)
        self._test_has_assertions = True
        self._test_has_state_assertions = True  # Most asserts are state checks
        self._assertion_count += 1

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

    def _check_assertion_roulette(self, node: astroid.FunctionDef) -> None:
        """Check for assertion roulette (W9019): too many assertions without explanation.

        Args:
            node: The test function node
        """
        threshold = 3

        # Skip if test is parametrized (multiple assertions are justified)
        if node.decorators:
            for decorator in node.decorators.nodes:
                # Check for @pytest.mark.parametrize
                if isinstance(decorator, astroid.Call):
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

    def visit_try(self, node: astroid.Try) -> None:
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

    def _track_semantic_validation_task(
        self, node: astroid.FunctionDef, validation_type: str
    ) -> None:
        """Track that a test needs semantic validation (feedback loop Phase 1).

        Args:
            node: The test function node
            validation_type: Type of validation needed ("bdd", "pbt", "dbc")
        """
        # Build test identifier: file_path::test_name
        file_path = node.root().file if node.root().file else "<unknown>"
        test_id = f"{file_path}::{node.name}"

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
            from pathlib import Path

            task_file = Path(".pytest_deep_analysis_tasks.json")
            try:
                task_file.write_text(json.dumps(self._semantic_validation_tasks, indent=2))
            except Exception:
                # Fail silently if we can't write the task file
                pass

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
                for node in fixture_info.node.nodes_of_class(astroid.Return):
                    if node.value and self._is_mutable_return(node.value):
                        self.add_message(
                            "pytest-fix-stateful-session",
                            node=fixture_info.node,
                            line=fixture_info.node.lineno,
                            args=(fixture_name,),
                        )
                        break  # Only report once per fixture

    def _is_mutable_return(self, value_node: astroid.NodeNG) -> bool:
        """Check if a return value is mutable using type inference.

        Args:
            value_node: The value being returned

        Returns:
            True if the value is likely mutable
        """
        # Direct mutable literals - these are definitely mutable
        if isinstance(value_node, (astroid.List, astroid.Dict, astroid.Set)):
            return True

        # Call nodes - use inference for better accuracy
        if isinstance(value_node, astroid.Call):
            # First try qualified name check (fast path)
            qualname = get_call_qualname(value_node)
            if qualname in {"list", "dict", "set"}:
                return True

            # Try astroid's inference engine for better detection
            try:
                for inferred in value_node.infer():
                    if inferred is astroid.Uninferable:
                        continue
                    # Check if inferred type is a mutable collection instance
                    if hasattr(inferred, "pytype"):
                        pytype = inferred.pytype()
                        if pytype in ("builtins.list", "builtins.dict", "builtins.set"):
                            return True
            except (astroid.InferenceError, AttributeError, StopIteration):
                # Inference failed, not considered mutable
                pass

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

    def _has_contract_decorators(self, node: astroid.FunctionDef) -> bool:
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

    def _is_complex_fixture(self, node: astroid.FunctionDef) -> bool:
        """Check if fixture is complex enough to warrant contracts.

        Args:
            node: The fixture function node

        Returns:
            True if fixture is complex
        """
        # Count statements (excluding docstring)
        body = node.body
        if body and isinstance(body[0], astroid.Expr) and isinstance(body[0].value, astroid.Const):
            # Skip docstring
            body = body[1:]

        statement_count = len(body)

        # Complex if >3 statements
        if statement_count > 3:
            return True

        # Check for database/network keywords in code
        complexity_indicators = {
            "connection", "cursor", "execute", "commit", "rollback",
            "session", "transaction", "database", "db",
            "request", "response", "http", "api"
        }

        code_str = node.as_string().lower()
        if any(indicator in code_str for indicator in complexity_indicators):
            return True

        # Check for yield (resource management fixtures)
        for _yield_node in node.nodes_of_class(astroid.Yield):
            return True

        return False
