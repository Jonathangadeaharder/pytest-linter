"""VB.NET language adapter implementation."""

from pathlib import Path
from typing import List, Optional, Any
import re

from test_linter.core.adapters import LanguageAdapter, ParsedModule, ParseError
from test_linter.core.models import (
    TestFunction, TestAssertion, TestFixture,
    LanguageType, TestFramework,
)


class VBNetAdapter(LanguageAdapter):
    """Language adapter for VB.NET test files.

    Supports NUnit, xUnit, and MSTest frameworks with VB.NET syntax.
    """

    def __init__(self):
        super().__init__(LanguageType.VBNET)

    def can_handle_file(self, file_path: Path) -> bool:
        """Check if this is a VB.NET file."""
        return file_path.suffix.lower() == ".vb"

    def detect_framework(self, file_path: Path) -> Optional[TestFramework]:
        """Detect test framework from imports and attributes.

        Args:
            file_path: Path to the VB.NET file

        Returns:
            TestFramework if detected, None otherwise
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # Check for NUnit (uses <Test>, <TestFixture>)
            if self._is_nunit(content):
                return TestFramework.NUNIT

            # Check for xUnit (uses <Fact>, <Theory>)
            if self._is_xunit(content):
                return TestFramework.XUNIT

            # Check for MSTest (uses <TestMethod>, <TestClass>)
            if self._is_mstest(content):
                return TestFramework.MSTEST

            return None
        except Exception:
            return None

    def _is_nunit(self, content: str) -> bool:
        """Check if file uses NUnit framework."""
        patterns = [
            r'Imports\s+NUnit\.Framework',
            r'<Test>',
            r'<TestFixture>',
        ]
        return any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns)

    def _is_xunit(self, content: str) -> bool:
        """Check if file uses xUnit framework."""
        patterns = [
            r'Imports\s+Xunit',
            r'<Fact>',
            r'<Theory>',
        ]
        return any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns)

    def _is_mstest(self, content: str) -> bool:
        """Check if file uses MSTest framework."""
        patterns = [
            r'Imports\s+Microsoft\.VisualStudio\.TestTools',
            r'<TestMethod>',
            r'<TestClass>',
        ]
        return any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns)

    def parse_file(self, file_path: Path) -> ParsedModule:
        """Parse a VB.NET test file.

        Args:
            file_path: Path to the file

        Returns:
            ParsedModule with extracted test information

        Raises:
            ParseError: If parsing fails
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            framework = self.detect_framework(file_path)

            if not framework:
                raise ParseError(f"No test framework detected in {file_path}")

            parsed = ParsedModule(
                file_path=str(file_path),
                language=self.language,
                framework=framework,
                raw_ast=content,
            )

            # Extract imports
            parsed.imports = self._extract_imports(content)

            # Check for network imports
            network_modules = {"System.Net", "System.Net.Http"}
            parsed.has_network_imports = any(
                imp in network_modules for imp in parsed.imports
            )

            # Extract test functions
            parsed.test_functions = self._extract_test_functions(content, parsed)

            return parsed

        except Exception as e:
            raise ParseError(f"Failed to parse {file_path}: {e}")

    def _extract_imports(self, content: str) -> List[str]:
        """Extract imports from the file."""
        imports = []

        # Match: Imports System.IO
        import_pattern = r'Imports\s+([\w.]+)'
        imports.extend(re.findall(import_pattern, content, re.IGNORECASE))

        return imports

    def _extract_test_functions(
        self, content: str, parsed_module: ParsedModule
    ) -> List[TestFunction]:
        """Extract test functions using regex."""
        test_functions = []

        # Patterns for different frameworks
        # VB.NET uses <Attribute> syntax and Sub/Function keywords
        patterns = {
            TestFramework.NUNIT: r'<Test>\s*\n\s*Public\s+(Sub|Function)\s+(\w+)\s*\(',
            TestFramework.XUNIT: r'<Fact>\s*\n\s*Public\s+(Sub|Function)\s+(\w+)\s*\(',
            TestFramework.MSTEST: r'<TestMethod>\s*\n\s*Public\s+(Sub|Function)\s+(\w+)\s*\(',
        }

        pattern = patterns.get(parsed_module.framework, patterns[TestFramework.NUNIT])

        for match in re.finditer(pattern, content, re.IGNORECASE):
            method_type = match.group(1)  # Sub or Function
            test_name = match.group(2)
            line_number = content[:match.start()].count('\n') + 1

            # Extract function body
            func_body = self._extract_function_body(content, match.end(), method_type)

            test_func = TestFunction(
                name=test_name,
                file_path=parsed_module.file_path,
                line_number=line_number,
                framework=parsed_module.framework,
            )

            # Analyze test body
            if func_body:
                test_func.assertions = self._extract_assertions(func_body, line_number)
                test_func.has_test_logic = self._has_conditional_logic(func_body)
                test_func.uses_time_sleep = self._uses_time_sleep(func_body)
                test_func.uses_file_io = self._uses_file_io(func_body)
                test_func.uses_network = self._uses_network(func_body)

                # Check for async
                test_func.is_async = bool(re.search(r'\bAsync\b', func_body, re.IGNORECASE))

            test_functions.append(test_func)

        return test_functions

    def _extract_function_body(self, content: str, start_pos: int, method_type: str) -> str:
        """Extract function body for VB.NET (no braces, uses End Sub/End Function)."""
        # VB.NET functions end with "End Sub" or "End Function"
        end_pattern = rf'\bEnd\s+{method_type}\b'

        # Find the end of the function
        match = re.search(end_pattern, content[start_pos:], re.IGNORECASE)
        if match:
            return content[start_pos:start_pos + match.end()]

        return ""

    def _extract_assertions(
        self, body: str, start_line: int
    ) -> List[TestAssertion]:
        """Extract assertions from test body."""
        assertions = []

        # NUnit/MSTest assertions: Assert.AreEqual, Assert.IsTrue, etc.
        assertion_patterns = [
            r'Assert\.(AreEqual|AreNotEqual|IsTrue|IsFalse|IsNull|IsNotNull|AreSame|AreNotSame)',
            r'Assert\.That',
        ]

        for pattern in assertion_patterns:
            for match in re.finditer(pattern, body, re.IGNORECASE):
                assertion_type = match.group(1) if match.lastindex else "Assert"
                line_offset = body[:match.start()].count('\n')

                assertions.append(TestAssertion(
                    line_number=start_line + line_offset,
                    assertion_type=assertion_type,
                    expression=match.group(0),
                ))

        return assertions

    def _has_conditional_logic(self, body: str) -> bool:
        """Check if body has conditional logic."""
        patterns = [
            r'\bIf\s+',
            r'\bFor\s+',
            r'\bWhile\s+',
            r'\bSelect\s+Case\s+',
        ]
        return any(re.search(pattern, body, re.IGNORECASE) for pattern in patterns)

    def _uses_time_sleep(self, body: str) -> bool:
        """Check if body uses Thread.Sleep or Task.Delay."""
        patterns = [
            r'Thread\.Sleep',
            r'Task\.Delay',
        ]
        return any(re.search(pattern, body, re.IGNORECASE) for pattern in patterns)

    def _uses_file_io(self, body: str) -> bool:
        """Check if body uses file I/O."""
        patterns = [
            r'File\.',
            r'FileStream',
            r'StreamReader',
            r'StreamWriter',
            r'System\.IO\.',
        ]
        return any(re.search(pattern, body, re.IGNORECASE) for pattern in patterns)

    def _uses_network(self, body: str) -> bool:
        """Check if body uses network calls."""
        patterns = [
            r'HttpClient',
            r'WebClient',
            r'HttpWebRequest',
            r'WebRequest',
        ]
        return any(re.search(pattern, body, re.IGNORECASE) for pattern in patterns)

    def extract_test_functions(self, parsed_module: ParsedModule) -> List[TestFunction]:
        """Extract test functions from parsed module."""
        return parsed_module.test_functions

    def extract_fixtures(self, parsed_module: ParsedModule) -> List[TestFixture]:
        """Extract fixtures from parsed module."""
        # VB.NET fixtures work similarly to C#
        fixtures = []
        content = parsed_module.raw_ast

        fixture_patterns = {
            # NUnit
            r'<SetUp>': "function",
            r'<TearDown>': "function",
            r'<OneTimeSetUp>': "class",
            r'<OneTimeTearDown>': "class",
            # MSTest
            r'<TestInitialize>': "function",
            r'<TestCleanup>': "function",
            r'<ClassInitialize>': "class",
            r'<ClassCleanup>': "class",
        }

        for pattern, scope in fixture_patterns.items():
            for match in re.finditer(pattern, content, re.IGNORECASE):
                line_number = content[:match.start()].count('\n') + 1

                fixture = TestFixture(
                    name=pattern.strip('<>'),
                    scope=scope,
                    file_path=parsed_module.file_path,
                    line_number=line_number,
                    is_auto=True,
                )
                fixtures.append(fixture)

        return fixtures

    def get_call_name(self, node: Any) -> Optional[str]:
        """Get qualified name of a function call."""
        if isinstance(node, str):
            # Extract function name from call expression
            match = re.search(r'([\w.]+)\s*\(', node)
            if match:
                return match.group(1)
        return None

    def is_assertion(self, node: Any) -> bool:
        """Check if node is an assertion."""
        if isinstance(node, str):
            return bool(re.search(r'Assert\.', node, re.IGNORECASE))
        return False

    def is_conditional(self, node: Any) -> bool:
        """Check if node is conditional logic."""
        if isinstance(node, str):
            patterns = [r'\bIf\s+', r'\bFor\s+', r'\bWhile\s+', r'\bSelect\s+']
            return any(re.search(pattern, node, re.IGNORECASE) for pattern in patterns)
        return False

    def get_file_imports(self, parsed_module: ParsedModule) -> List[str]:
        """Get all imports from module."""
        return parsed_module.imports

    def supports_async(self) -> bool:
        """VB.NET supports async/await."""
        return True

    def get_supported_frameworks(self) -> List[TestFramework]:
        """Get supported VB.NET test frameworks."""
        return [TestFramework.NUNIT, TestFramework.XUNIT, TestFramework.MSTEST]
