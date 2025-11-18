"""Python language adapter implementation using astroid."""

from pathlib import Path
from typing import List, Optional, Any, Set
import astroid
from astroid import nodes

from test_linter.core.adapters import LanguageAdapter, ParsedModule, ParseError
from test_linter.core.models import (
    TestFunction,
    TestAssertion,
    TestFixture,
    LanguageType,
    TestFramework,
)


class PythonAdapter(LanguageAdapter):
    """Language adapter for Python test files."""

    def __init__(self):
        super().__init__(LanguageType.PYTHON)

    def can_handle_file(self, file_path: Path) -> bool:
        """Check if this is a Python file."""
        return file_path.suffix.lower() == ".py"

    def detect_framework(self, file_path: Path) -> Optional[TestFramework]:
        """Detect test framework by examining imports and decorators.

        Args:
            file_path: Path to the Python file

        Returns:
            TestFramework.PYTEST if pytest is detected
            TestFramework.UNITTEST if unittest is detected
            None if not a test file
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Quick heuristics
            if "import pytest" in content or "from pytest" in content:
                return TestFramework.PYTEST
            if "@pytest" in content:
                return TestFramework.PYTEST
            if "import unittest" in content or "from unittest" in content:
                return TestFramework.UNITTEST
            if "class Test" in content and "unittest.TestCase" in content:
                return TestFramework.UNITTEST

            # Parse AST for more reliable detection
            try:
                module = astroid.parse(content, path=str(file_path))

                # Check imports
                for node in module.body:
                    if isinstance(node, (nodes.Import, nodes.ImportFrom)):
                        if hasattr(node, "modname") and node.modname:
                            if "pytest" in node.modname:
                                return TestFramework.PYTEST
                            if "unittest" in node.modname:
                                return TestFramework.UNITTEST

                # Check for test functions (pytest style)
                for node in module.nodes_of_class(nodes.FunctionDef):
                    if node.name.startswith("test_"):
                        return TestFramework.PYTEST

                # Check for unittest.TestCase classes
                for node in module.nodes_of_class(nodes.ClassDef):
                    if any(
                        base.as_string() == "unittest.TestCase"
                        for base in node.bases
                        if hasattr(base, "as_string")
                    ):
                        return TestFramework.UNITTEST

            except Exception:
                pass

            return None

        except Exception:
            return None

    def parse_file(self, file_path: Path) -> ParsedModule:
        """Parse a Python test file using astroid.

        Args:
            file_path: Path to the file

        Returns:
            ParsedModule with extracted test information

        Raises:
            ParseError: If parsing fails
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            module = astroid.parse(content, path=str(file_path))
            framework = self.detect_framework(file_path) or TestFramework.PYTEST

            parsed = ParsedModule(
                file_path=str(file_path),
                language=self.language,
                framework=framework,
                raw_ast=module,
            )

            # Extract imports
            parsed.imports = self.get_file_imports(parsed)

            # Check for network imports
            network_modules = {"requests", "urllib", "httpx", "aiohttp", "socket"}
            parsed.has_network_imports = any(
                imp in network_modules for imp in parsed.imports
            )

            # Extract test functions and fixtures
            parsed.test_functions = self.extract_test_functions(parsed)
            parsed.fixtures = self.extract_fixtures(parsed)

            return parsed

        except Exception as e:
            raise ParseError(f"Failed to parse {file_path}: {e}")

    def extract_test_functions(self, parsed_module: ParsedModule) -> List[TestFunction]:
        """Extract test functions from parsed Python module."""
        test_functions = []
        module = parsed_module.raw_ast

        for node in module.nodes_of_class(nodes.FunctionDef):
            if not self._is_test_function(node):
                continue

            test_func = self._create_test_function(node, parsed_module)
            test_functions.append(test_func)

        return test_functions

    def extract_fixtures(self, parsed_module: ParsedModule) -> List[TestFixture]:
        """Extract pytest fixtures from parsed module."""
        fixtures = []
        module = parsed_module.raw_ast

        if parsed_module.framework != TestFramework.PYTEST:
            return fixtures  # Only pytest has fixtures in this sense

        for node in module.nodes_of_class(nodes.FunctionDef):
            if not self._is_pytest_fixture(node):
                continue

            fixture = self._create_fixture(node, parsed_module)
            fixtures.append(fixture)

        return fixtures

    def get_call_name(self, node: Any) -> Optional[str]:
        """Get qualified name of a function call."""
        if not isinstance(node, nodes.Call):
            return None

        try:
            if isinstance(node.func, nodes.Attribute):
                # e.g., time.sleep()
                return node.func.as_string()
            elif isinstance(node.func, nodes.Name):
                # e.g., sleep()
                return node.func.name
        except Exception:
            pass

        return None

    def is_assertion(self, node: Any) -> bool:
        """Check if node is an assertion."""
        if isinstance(node, nodes.Assert):
            return True

        # Check for unittest-style assertions
        if isinstance(node, nodes.Call):
            call_name = self.get_call_name(node)
            if call_name and call_name.startswith("assert"):
                return True

        return False

    def is_conditional(self, node: Any) -> bool:
        """Check if node is conditional logic."""
        return isinstance(node, (nodes.If, nodes.For, nodes.While))

    def get_file_imports(self, parsed_module: ParsedModule) -> List[str]:
        """Extract all imports from module."""
        imports = []
        module = parsed_module.raw_ast

        for node in module.body:
            if isinstance(node, nodes.Import):
                for name, _ in node.names:
                    imports.append(name)
            elif isinstance(node, nodes.ImportFrom):
                if node.modname:
                    imports.append(node.modname)

        return imports

    def supports_async(self) -> bool:
        """Python supports async tests."""
        return True

    def get_supported_frameworks(self) -> List[TestFramework]:
        """Get supported Python test frameworks."""
        return [TestFramework.PYTEST, TestFramework.UNITTEST]

    # Private helper methods

    def _is_test_function(self, node: nodes.FunctionDef) -> bool:
        """Check if function is a test."""
        return node.name.startswith("test_")

    def _is_pytest_fixture(self, node: nodes.FunctionDef) -> bool:
        """Check if function is a pytest fixture."""
        if not node.decorators:
            return False

        for decorator in node.decorators.nodes:
            try:
                if isinstance(decorator, nodes.Call):
                    if hasattr(decorator.func, "name") and decorator.func.name == "fixture":
                        return True
                    if hasattr(decorator.func, "attrname") and decorator.func.attrname == "fixture":
                        return True
                elif isinstance(decorator, (nodes.Name, nodes.Attribute)):
                    name = decorator.as_string()
                    if "fixture" in name:
                        return True
            except Exception:
                continue

        return False

    def _create_test_function(
        self, node: nodes.FunctionDef, parsed_module: ParsedModule
    ) -> TestFunction:
        """Create TestFunction from AST node."""
        test_func = TestFunction(
            name=node.name,
            file_path=parsed_module.file_path,
            line_number=node.lineno,
            framework=parsed_module.framework,
            raw_node=node,
        )

        # Extract assertions
        test_func.assertions = self._extract_assertions(node)

        # Check for test logic
        test_func.has_test_logic = self._has_conditional_logic(node)

        # Extract fixture dependencies
        test_func.setup_dependencies = self._get_fixture_dependencies(node)

        # Check for async
        test_func.has_async = isinstance(node, nodes.AsyncFunctionDef)

        # Check for parametrize
        test_func.is_parametrized = self._has_parametrize_decorator(node)

        # Detect usage patterns
        test_func.uses_time_sleep = self._uses_time_sleep(node)
        test_func.uses_file_io = self._uses_file_io(node)
        test_func.uses_network = self._uses_network(node)
        test_func.uses_cwd = self._uses_cwd(node)

        # Mock analysis
        test_func.has_mock_verifications = self._has_mock_verifications(node)
        test_func.has_state_assertions = len(test_func.assertions) > 0

        # Docstring
        test_func.docstring = node.doc_node.value if node.doc_node else None

        return test_func

    def _create_fixture(
        self, node: nodes.FunctionDef, parsed_module: ParsedModule
    ) -> TestFixture:
        """Create TestFixture from AST node."""
        scope, autouse = self._get_fixture_metadata(node)

        fixture = TestFixture(
            name=node.name,
            scope=scope,
            file_path=parsed_module.file_path,
            line_number=node.lineno,
            dependencies=self._get_fixture_dependencies(node),
            is_auto=autouse,
            raw_node=node,
        )

        return fixture

    def _extract_assertions(self, node: nodes.FunctionDef) -> List[TestAssertion]:
        """Extract assertions from test function."""
        assertions = []

        for child in node.nodes_of_class(nodes.Assert):
            assertion_type = "equality"  # Default
            expression = child.as_string() if hasattr(child, "as_string") else ""

            assertions.append(
                TestAssertion(
                    line_number=child.lineno,
                    assertion_type=assertion_type,
                    expression=expression,
                    raw_node=child,
                )
            )

        return assertions

    def _has_conditional_logic(self, node: nodes.FunctionDef) -> bool:
        """Check if function has conditional logic."""
        for child in node.nodes_of_class((nodes.If, nodes.For, nodes.While)):
            return True
        return False

    def _get_fixture_dependencies(self, node: nodes.FunctionDef) -> List[str]:
        """Get fixture dependencies from function arguments."""
        dependencies = []
        if node.args and node.args.args:
            for arg in node.args.args:
                if arg.name not in ("self", "cls"):
                    dependencies.append(arg.name)
        return dependencies

    def _get_fixture_metadata(self, node: nodes.FunctionDef) -> tuple[str, bool]:
        """Extract scope and autouse from fixture decorator."""
        scope = "function"  # Default
        autouse = False

        if not node.decorators:
            return scope, autouse

        for decorator in node.decorators.nodes:
            try:
                if isinstance(decorator, nodes.Call):
                    # Check for scope keyword argument
                    if decorator.keywords:
                        for keyword in decorator.keywords:
                            if keyword.arg == "scope":
                                if hasattr(keyword.value, "value"):
                                    scope = keyword.value.value
                            elif keyword.arg == "autouse":
                                if hasattr(keyword.value, "value"):
                                    autouse = keyword.value.value
            except Exception:
                continue

        return scope, autouse

    def _has_parametrize_decorator(self, node: nodes.FunctionDef) -> bool:
        """Check if function has parametrize decorator."""
        if not node.decorators:
            return False

        for decorator in node.decorators.nodes:
            try:
                if isinstance(decorator, nodes.Call):
                    if hasattr(decorator.func, "attrname"):
                        if decorator.func.attrname == "parametrize":
                            return True
            except Exception:
                continue

        return False

    def _uses_time_sleep(self, node: nodes.FunctionDef) -> bool:
        """Check if function uses time.sleep."""
        for call in node.nodes_of_class(nodes.Call):
            call_name = self.get_call_name(call)
            if call_name in ("time.sleep", "sleep"):
                return True
        return False

    def _uses_file_io(self, node: nodes.FunctionDef) -> bool:
        """Check if function uses file I/O."""
        for call in node.nodes_of_class(nodes.Call):
            call_name = self.get_call_name(call)
            if call_name in ("open", "Path.open", "file.open"):
                return True
        return False

    def _uses_network(self, node: nodes.FunctionDef) -> bool:
        """Check if function uses network calls."""
        for call in node.nodes_of_class(nodes.Call):
            call_name = self.get_call_name(call)
            if call_name and any(
                net in call_name for net in ("requests.", "urllib.", "httpx.")
            ):
                return True
        return False

    def _uses_cwd(self, node: nodes.FunctionDef) -> bool:
        """Check if function uses CWD-dependent operations."""
        for call in node.nodes_of_class(nodes.Call):
            call_name = self.get_call_name(call)
            if call_name in ("os.getcwd", "getcwd", "os.chdir", "chdir"):
                return True
        return False

    def _has_mock_verifications(self, node: nodes.FunctionDef) -> bool:
        """Check if function has mock verifications."""
        for call in node.nodes_of_class(nodes.Call):
            call_name = self.get_call_name(call)
            if call_name and ("assert_called" in call_name or "assert_" in call_name):
                return True
        return False
