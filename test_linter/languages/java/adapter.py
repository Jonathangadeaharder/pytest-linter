"""Java language adapter implementation using regex-based parsing."""

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


class JavaAdapter(LanguageAdapter):
    """Language adapter for Java test files.

    Supports JUnit 4, JUnit 5, and TestNG frameworks.
    Uses regex-based parsing for test detection.
    """

    def __init__(self):
        super().__init__(LanguageType.JAVA)

    def can_handle_file(self, file_path: Path) -> bool:
        """Check if this is a Java file."""
        return file_path.suffix.lower() == ".java"

    def detect_framework(self, file_path: Path) -> Optional[TestFramework]:
        """Detect test framework by examining imports and annotations.

        Args:
            file_path: Path to the Java file

        Returns:
            TestFramework.JUNIT4, JUNIT5, or TESTNG if detected
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # JUnit 5 detection (org.junit.jupiter)
            if self._is_junit5(content):
                return TestFramework.JUNIT5

            # TestNG detection
            if self._is_testng(content):
                return TestFramework.TESTNG

            # JUnit 4 detection (org.junit)
            if self._is_junit4(content):
                return TestFramework.JUNIT4

            return None

        except Exception:
            return None

    def _is_junit5(self, content: str) -> bool:
        """Check if file uses JUnit 5."""
        junit5_patterns = [
            r'import\s+org\.junit\.jupiter',
            r'@Test',  # With jupiter import
            r'@BeforeEach',
            r'@AfterEach',
            r'@BeforeAll',
            r'@AfterAll',
        ]
        has_jupiter = bool(re.search(r'org\.junit\.jupiter', content))
        has_test_annotation = bool(re.search(r'@Test', content))
        return has_jupiter or (has_test_annotation and 'org.junit' in content and 'jupiter' in content)

    def _is_testng(self, content: str) -> bool:
        """Check if file uses TestNG."""
        testng_patterns = [
            r'import\s+org\.testng',
            r'@Test\s*\(',  # TestNG uses @Test with parameters
        ]
        return any(re.search(pattern, content) for pattern in testng_patterns)

    def _is_junit4(self, content: str) -> bool:
        """Check if file uses JUnit 4."""
        junit4_patterns = [
            r'import\s+org\.junit\.',
            r'@Test',
            r'@Before\b',
            r'@After\b',
            r'@BeforeClass',
            r'@AfterClass',
        ]
        has_junit_import = bool(re.search(r'import\s+org\.junit\.', content))
        has_test = bool(re.search(r'@Test', content))
        return has_junit_import and has_test and 'jupiter' not in content

    def parse_file(self, file_path: Path) -> ParsedModule:
        """Parse a Java test file.

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
            network_modules = {"java.net", "HttpClient", "okhttp"}
            parsed.has_network_imports = any(
                imp in network_modules for imp in parsed.imports
            )

            # Extract test functions and fixtures
            parsed.test_functions = self._extract_test_functions(content, parsed)
            parsed.fixtures = self._extract_fixtures(content, parsed)

            return parsed

        except ParseError:
            raise
        except Exception as e:
            raise ParseError(f"Failed to parse {file_path}: {e}")

    def _extract_imports(self, content: str) -> List[str]:
        """Extract imports from the file."""
        imports = []

        # import package.Class;
        # import static package.Class.method;
        import_pattern = r'import\s+(?:static\s+)?([\w.]+)'
        imports.extend(re.findall(import_pattern, content))

        return imports

    def _extract_test_functions(
        self, content: str, parsed_module: ParsedModule
    ) -> List[TestFunction]:
        """Extract test functions (methods with @Test annotation)."""
        test_functions = []

        # Find all @Test annotated methods
        # Pattern: @Test ... public/private/protected void testName() { ... }
        test_pattern = r'@Test[^\n]*\n\s*(?:public|private|protected)?\s+void\s+(\w+)\s*\([^)]*\)\s*(?:throws[^{]*)?\{'

        for match in re.finditer(test_pattern, content):
            test_name = match.group(1)
            line_number = content[:match.start()].count('\n') + 1

            # Find the opening brace
            brace_pos = match.end() - 1
            func_body = self._extract_function_body(content, brace_pos)

            test_func = TestFunction(
                name=test_name,
                file_path=parsed_module.file_path,
                line_number=line_number,
                framework=parsed_module.framework,
            )

            if func_body:
                test_func.assertions = self._extract_assertions(
                    func_body, line_number, parsed_module.framework
                )
                test_func.has_test_logic = self._has_conditional_logic(func_body)
                test_func.uses_time_sleep = self._uses_time_sleep(func_body)
                test_func.uses_file_io = self._uses_file_io(func_body)
                test_func.uses_network = self._uses_network(func_body)

            test_functions.append(test_func)

        return test_functions

    def _extract_fixtures(
        self, content: str, parsed_module: ParsedModule
    ) -> List[TestFixture]:
        """Extract fixtures/setup methods."""
        fixtures = []

        if parsed_module.framework == TestFramework.JUNIT5:
            fixture_patterns = {
                r'@BeforeEach\s+(?:public|private|protected)?\s+void\s+(\w+)': "function",
                r'@AfterEach\s+(?:public|private|protected)?\s+void\s+(\w+)': "function",
                r'@BeforeAll\s+(?:public|private|protected)?\s+static\s+void\s+(\w+)': "class",
                r'@AfterAll\s+(?:public|private|protected)?\s+static\s+void\s+(\w+)': "class",
            }
        elif parsed_module.framework == TestFramework.JUNIT4:
            fixture_patterns = {
                r'@Before\s+(?:public|private|protected)?\s+void\s+(\w+)': "function",
                r'@After\s+(?:public|private|protected)?\s+void\s+(\w+)': "function",
                r'@BeforeClass\s+(?:public|private|protected)?\s+static\s+void\s+(\w+)': "class",
                r'@AfterClass\s+(?:public|private|protected)?\s+static\s+void\s+(\w+)': "class",
            }
        elif parsed_module.framework == TestFramework.TESTNG:
            fixture_patterns = {
                r'@BeforeMethod\s+(?:public|private|protected)?\s+void\s+(\w+)': "function",
                r'@AfterMethod\s+(?:public|private|protected)?\s+void\s+(\w+)': "function",
                r'@BeforeClass\s+(?:public|private|protected)?\s+void\s+(\w+)': "class",
                r'@AfterClass\s+(?:public|private|protected)?\s+void\s+(\w+)': "class",
            }
        else:
            fixture_patterns = {}

        for pattern, scope in fixture_patterns.items():
            for match in re.finditer(pattern, content):
                fixture_name = match.group(1)
                line_number = content[:match.start()].count('\n') + 1

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
        """Extract method body by matching braces."""
        if start_pos >= len(content) or content[start_pos] != '{':
            return ""

        depth = 0
        in_string = False
        in_char = False
        escape_next = False

        for i in range(start_pos, len(content)):
            char = content[i]

            if escape_next:
                escape_next = False
                continue

            if char == '\\':
                escape_next = True
                continue

            if char == '"' and not in_char:
                in_string = not in_string
                continue

            if char == "'" and not in_string:
                in_char = not in_char
                continue

            if not in_string and not in_char:
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        return content[start_pos:i+1]

        return ""

    def _extract_assertions(
        self, body: str, start_line: int, framework: TestFramework
    ) -> List[TestAssertion]:
        """Extract assertions from test body."""
        assertions = []

        # JUnit assertions
        junit_patterns = [
            r'\bassertEquals\s*\(',
            r'\bassertNotEquals\s*\(',
            r'\bassertTrue\s*\(',
            r'\bassertFalse\s*\(',
            r'\bassertNull\s*\(',
            r'\bassertNotNull\s*\(',
            r'\bassertSame\s*\(',
            r'\bassertNotSame\s*\(',
            r'\bassertArrayEquals\s*\(',
            r'\bassertThrows\s*\(',
            r'\bfail\s*\(',
        ]

        # TestNG assertions
        testng_patterns = [
            r'\bAssert\.assertEquals\s*\(',
            r'\bAssert\.assertTrue\s*\(',
            r'\bAssert\.assertFalse\s*\(',
            r'\bAssert\.assertNull\s*\(',
            r'\bAssert\.assertNotNull\s*\(',
        ]

        patterns = junit_patterns if framework in (TestFramework.JUNIT4, TestFramework.JUNIT5) else testng_patterns

        for pattern in patterns:
            for match in re.finditer(pattern, body):
                assertion_type = match.group(0).split('(')[0].strip()
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
            r'\bif\s*\(',
            r'\bfor\s*\(',
            r'\bwhile\s*\(',
            r'\bswitch\s*\(',
        ]
        return any(re.search(pattern, body) for pattern in patterns)

    def _uses_time_sleep(self, body: str) -> bool:
        """Check if body uses Thread.sleep."""
        patterns = [
            r'Thread\.sleep\s*\(',
            r'TimeUnit\.\w+\.sleep\s*\(',
        ]
        return any(re.search(pattern, body) for pattern in patterns)

    def _uses_file_io(self, body: str) -> bool:
        """Check if body uses file I/O."""
        patterns = [
            r'\bnew\s+File\s*\(',
            r'\bnew\s+FileReader\s*\(',
            r'\bnew\s+FileWriter\s*\(',
            r'\bnew\s+FileInputStream\s*\(',
            r'\bnew\s+FileOutputStream\s*\(',
            r'Files\.\w+\s*\(',
        ]
        return any(re.search(pattern, body) for pattern in patterns)

    def _uses_network(self, body: str) -> bool:
        """Check if body uses network calls."""
        patterns = [
            r'\bnew\s+URL\s*\(',
            r'HttpClient',
            r'HttpURLConnection',
            r'\.get\s*\(',
            r'\.post\s*\(',
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
            match = re.search(r'([\w.]+)\s*\(', node)
            if match:
                return match.group(1)
        return None

    def is_assertion(self, node: Any) -> bool:
        """Check if node is an assertion."""
        if isinstance(node, str):
            return bool(re.search(r'\b(assert|Assert\.|fail)\s*\(', node))
        return False

    def is_conditional(self, node: Any) -> bool:
        """Check if node is conditional logic."""
        if isinstance(node, str):
            return bool(re.search(r'\b(if|for|while|switch)\s*\(', node))
        return False

    def get_file_imports(self, parsed_module: ParsedModule) -> List[str]:
        """Get all imports from module."""
        return parsed_module.imports

    def supports_async(self) -> bool:
        """Java supports async tests (CompletableFuture, etc)."""
        return True

    def get_supported_frameworks(self) -> List[TestFramework]:
        """Get supported Java test frameworks."""
        return [
            TestFramework.JUNIT4,
            TestFramework.JUNIT5,
            TestFramework.TESTNG,
        ]
