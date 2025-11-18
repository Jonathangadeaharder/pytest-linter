"""Go language adapter implementation using regex-based parsing."""

from pathlib import Path
from typing import List, Optional, Any, Set
import re

from test_linter.core.adapters import LanguageAdapter, ParsedModule, ParseError
from test_linter.core.models import (
    TestFunction,
    TestAssertion,
    TestFixture,
    LanguageType,
    TestFramework,
)
from test_linter.core.parsing_utils import extract_brace_delimited_body


class GoAdapter(LanguageAdapter):
    """Language adapter for Go test files.

    Supports the standard testing package and testify framework.
    Uses regex-based parsing for test detection.
    """

    def __init__(self):
        super().__init__(LanguageType.GO)

    def can_handle_file(self, file_path: Path) -> bool:
        """Check if this is a Go file."""
        return file_path.suffix.lower() == ".go"

    def detect_framework(self, file_path: Path) -> Optional[TestFramework]:
        """Detect test framework by examining imports and function signatures.

        Args:
            file_path: Path to the Go file

        Returns:
            TestFramework.GO_TESTING or TESTIFY if detected, None otherwise
        """
        try:
            # Go test files must end with _test.go
            if not file_path.name.endswith("_test.go"):
                return None

            content = file_path.read_text(encoding="utf-8")

            # Check for testify
            if self._is_testify(content):
                return TestFramework.TESTIFY

            # Check for standard testing package
            if self._is_standard_testing(content):
                return TestFramework.GO_TESTING

            return None

        except Exception:
            return None

    def _is_testify(self, content: str) -> bool:
        """Check if file uses testify framework."""
        testify_patterns = [
            r"github\.com/stretchr/testify",
            r"assert\.",
            r"require\.",
            r"suite\.",
        ]
        return any(re.search(pattern, content) for pattern in testify_patterns)

    def _is_standard_testing(self, content: str) -> bool:
        """Check if file uses standard testing package."""
        # Look for test functions with *testing.T parameter
        test_function_pattern = r"func\s+Test\w+\s*\(\s*t\s+\*testing\.T\s*\)"
        return bool(re.search(test_function_pattern, content))

    def parse_file(self, file_path: Path) -> ParsedModule:
        """Parse a Go test file.

        Args:
            file_path: Path to the file

        Returns:
            ParsedModule with extracted test information

        Raises:
            ParseError: If parsing fails
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            framework = self.detect_framework(file_path) or TestFramework.GO_TESTING

            parsed = ParsedModule(
                file_path=str(file_path),
                language=self.language,
                framework=framework,
                raw_ast=content,  # Store content as "AST"
            )

            # Extract imports
            parsed.imports = self._extract_imports(content)

            # Check for network imports
            network_modules = {"net/http", "http", "net"}
            parsed.has_network_imports = any(
                imp in network_modules for imp in parsed.imports
            )

            # Extract test functions and fixtures
            parsed.test_functions = self._extract_test_functions(content, parsed)
            parsed.fixtures = self._extract_fixtures(content, parsed)

            return parsed

        except Exception as e:
            raise ParseError(f"Failed to parse {file_path}: {e}")

    def _extract_imports(self, content: str) -> List[str]:
        """Extract imports from the file."""
        imports = []

        # Single import: import "package"
        single_import_pattern = r'import\s+"([^"]+)"'
        imports.extend(re.findall(single_import_pattern, content))

        # Multi-line imports: import ( ... )
        multi_import_pattern = r"import\s+\((.*?)\)"
        for match in re.finditer(multi_import_pattern, content, re.DOTALL):
            import_block = match.group(1)
            # Extract quoted strings from import block
            imports.extend(re.findall(r'"([^"]+)"', import_block))

        return imports

    def _extract_test_functions(
        self, content: str, parsed_module: ParsedModule
    ) -> List[TestFunction]:
        """Extract test functions using regex."""
        test_functions = []

        # Pattern to match test functions: func TestXxx(t *testing.T) { ... }
        test_pattern = r"func\s+(Test\w+)\s*\(\s*(\w+)\s+\*testing\.T\s*\)\s*{"

        for match in re.finditer(test_pattern, content):
            test_name = match.group(1)
            param_name = match.group(2)  # Usually 't'

            # Find line number
            line_number = content[: match.start()].count("\n") + 1

            # Extract function body
            func_start = match.end() - 1  # Position of opening brace
            func_body = self._extract_function_body(content, func_start)

            test_func = TestFunction(
                name=test_name,
                file_path=parsed_module.file_path,
                line_number=line_number,
                framework=parsed_module.framework,
            )

            # Analyze test body
            if func_body:
                test_func.assertions = self._extract_assertions(
                    func_body, line_number, param_name
                )
                test_func.has_test_logic = self._has_conditional_logic(func_body)
                test_func.uses_time_sleep = self._uses_time_sleep(func_body)
                test_func.uses_file_io = self._uses_file_io(func_body)
                test_func.uses_network = self._uses_network(func_body)

                # Check for table-driven tests
                test_func.is_parametrized = self._is_table_driven_test(func_body)

                # Check for subtests
                has_subtests = bool(re.search(rf"{param_name}\.Run\(", func_body))
                if has_subtests:
                    test_func.metadata["has_subtests"] = True

            test_functions.append(test_func)

        return test_functions

    def _extract_fixtures(
        self, content: str, parsed_module: ParsedModule
    ) -> List[TestFixture]:
        """Extract fixtures/setup functions."""
        fixtures = []

        # TestMain is the main setup/teardown function
        main_pattern = r"func\s+(TestMain)\s*\(\s*m\s+\*testing\.M\s*\)\s*{"
        for match in re.finditer(main_pattern, content):
            line_number = content[: match.start()].count("\n") + 1

            fixture = TestFixture(
                name="TestMain",
                scope="session",  # TestMain runs once for the package
                file_path=parsed_module.file_path,
                line_number=line_number,
                is_auto=True,
            )
            fixtures.append(fixture)

        # Suite setup/teardown (testify)
        if parsed_module.framework == TestFramework.TESTIFY:
            suite_patterns = {
                r"func\s+\(\w+\s+\*\w+\)\s+(SetupTest)\s*\(": "function",
                r"func\s+\(\w+\s+\*\w+\)\s+(TearDownTest)\s*\(": "function",
                r"func\s+\(\w+\s+\*\w+\)\s+(SetupSuite)\s*\(": "class",
                r"func\s+\(\w+\s+\*\w+\)\s+(TearDownSuite)\s*\(": "class",
            }

            for pattern, scope in suite_patterns.items():
                for match in re.finditer(pattern, content):
                    line_number = content[: match.start()].count("\n") + 1
                    fixture_name = match.group(1)

                    fixture = TestFixture(
                        name=fixture_name,
                        scope=scope,
                        file_path=parsed_module.file_path,
                        line_number=line_number,
                        is_auto=True,
                    )
                    fixtures.append(fixture)

        return fixtures

    def _extract_function_body(self, content: str, start_pos: int) -> str:
        """Extract function body using string-aware brace matching.

        Handles Go's raw string literals (backticks) and regular strings.
        """
        return extract_brace_delimited_body(content, start_pos)

    def _extract_assertions(
        self, body: str, start_line: int, param_name: str
    ) -> List[TestAssertion]:
        """Extract assertions from test body."""
        assertions = []

        # Standard testing package assertions: t.Error, t.Fatal, etc.
        testing_patterns = [
            rf"{param_name}\.(Error|Errorf)\(",
            rf"{param_name}\.(Fatal|Fatalf)\(",
            rf"{param_name}\.(Fail|FailNow)\(",
        ]

        for pattern in testing_patterns:
            for match in re.finditer(pattern, body):
                assertion_type = match.group(1)
                line_offset = body[: match.start()].count("\n")

                assertions.append(
                    TestAssertion(
                        line_number=start_line + line_offset,
                        assertion_type=assertion_type,
                        expression=match.group(0),
                    )
                )

        # Testify assertions: assert.Equal, require.NoError, etc.
        testify_patterns = [
            r"assert\.(Equal|NotEqual|True|False|Nil|NotNil|NoError|Error)\(",
            r"require\.(Equal|NotEqual|True|False|Nil|NotNil|NoError|Error)\(",
        ]

        for pattern in testify_patterns:
            for match in re.finditer(pattern, body):
                assertion_type = match.group(1)
                line_offset = body[: match.start()].count("\n")

                assertions.append(
                    TestAssertion(
                        line_number=start_line + line_offset,
                        assertion_type=assertion_type,
                        expression=match.group(0),
                    )
                )

        return assertions

    def _has_conditional_logic(self, body: str) -> bool:
        """Check if body has conditional logic."""
        patterns = [
            r"\bif\s+",
            r"\bfor\s+",
            r"\bswitch\s+",
            r"\bselect\s+",
        ]
        # Exclude common test patterns like "if err != nil"
        has_conditional = any(re.search(pattern, body) for pattern in patterns)

        # Don't flag simple error checks as test logic
        if has_conditional:
            # Check if it's just error handling
            error_check_pattern = r"if\s+err\s*!=\s*nil"
            error_checks = len(re.findall(error_check_pattern, body))
            total_conditionals = sum(
                len(re.findall(pattern, body)) for pattern in patterns
            )

            # If all conditionals are just error checks, don't flag
            if total_conditionals > 0 and error_checks == total_conditionals:
                return False

        return has_conditional

    def _uses_time_sleep(self, body: str) -> bool:
        """Check if body uses time.Sleep."""
        patterns = [
            r"time\.Sleep\(",
            r"time\.After\(",
        ]
        return any(re.search(pattern, body) for pattern in patterns)

    def _uses_file_io(self, body: str) -> bool:
        """Check if body uses file I/O."""
        patterns = [
            r"os\.Open\(",
            r"os\.Create\(",
            r"os\.ReadFile\(",
            r"os\.WriteFile\(",
            r"ioutil\.ReadFile\(",
            r"ioutil\.WriteFile\(",
        ]
        return any(re.search(pattern, body) for pattern in patterns)

    def _uses_network(self, body: str) -> bool:
        """Check if body uses network calls."""
        patterns = [
            r"http\.Get\(",
            r"http\.Post\(",
            r"http\.NewRequest\(",
            r"net\.Dial\(",
        ]
        return any(re.search(pattern, body) for pattern in patterns)

    def _is_table_driven_test(self, body: str) -> bool:
        """Check if this is a table-driven test."""
        # Look for common table-driven test patterns
        patterns = [
            r"tests\s*:=\s*\[\]struct",
            r"testCases\s*:=\s*\[\]struct",
            r"for\s+_?,\s*tt\s*:=\s*range\s+tests",
            r"for\s+_?,\s*tc\s*:=\s*range\s+testCases",
        ]
        return any(re.search(pattern, body) for pattern in patterns)

    def extract_test_functions(self, parsed_module: ParsedModule) -> List[TestFunction]:
        """Extract test functions from parsed module."""
        return parsed_module.test_functions

    def extract_fixtures(self, parsed_module: ParsedModule) -> List[TestFixture]:
        """Extract fixtures from parsed module."""
        return parsed_module.fixtures

    def get_call_name(self, node: Any) -> Optional[str]:
        """Get qualified name of a function call."""
        if isinstance(node, str):
            # Extract function name from call expression
            match = re.search(r"([\w\.]+)\s*\(", node)
            if match:
                return match.group(1)
        return None

    def is_assertion(self, node: Any) -> bool:
        """Check if node is an assertion."""
        if isinstance(node, str):
            patterns = [
                r"t\.(Error|Fatal|Fail)",
                r"(assert|require)\.",
            ]
            return any(re.search(pattern, node) for pattern in patterns)
        return False

    def is_conditional(self, node: Any) -> bool:
        """Check if node is conditional logic."""
        if isinstance(node, str):
            return bool(re.search(r"\b(if|for|switch|select)\s+", node))
        return False

    def get_file_imports(self, parsed_module: ParsedModule) -> List[str]:
        """Get all imports from module."""
        return parsed_module.imports

    def supports_async(self) -> bool:
        """Go supports concurrent tests via goroutines."""
        return True

    def get_supported_frameworks(self) -> List[TestFramework]:
        """Get supported Go test frameworks."""
        return [TestFramework.GO_TESTING, TestFramework.TESTIFY]
