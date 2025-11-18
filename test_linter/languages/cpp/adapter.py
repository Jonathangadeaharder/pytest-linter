"""C++ language adapter implementation using regex-based parsing."""

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


class CppAdapter(LanguageAdapter):
    """Language adapter for C++ test files.

    Supports GoogleTest, Catch2, and Boost.Test frameworks.
    Uses regex-based parsing for test detection.
    """

    def __init__(self):
        super().__init__(LanguageType.CPP)

    def can_handle_file(self, file_path: Path) -> bool:
        """Check if this is a C++ file."""
        suffix = file_path.suffix.lower()
        return suffix in {".cpp", ".cc", ".cxx", ".hpp", ".h"}

    def detect_framework(self, file_path: Path) -> Optional[TestFramework]:
        """Detect test framework by examining includes and macros.

        Args:
            file_path: Path to the C++ file

        Returns:
            TestFramework.GOOGLETEST, CATCH2, or BOOST_TEST if detected
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # GoogleTest detection
            if self._is_googletest(content):
                return TestFramework.GOOGLETEST

            # Catch2 detection
            if self._is_catch2(content):
                return TestFramework.CATCH2

            # Boost.Test detection
            if self._is_boost_test(content):
                return TestFramework.BOOST_TEST

            return None

        except Exception:
            return None

    def _is_googletest(self, content: str) -> bool:
        """Check if file uses GoogleTest."""
        gtest_patterns = [
            r'#include\s+[<"]gtest/gtest\.h[>"]',
            r'\bTEST\s*\(',
            r'\bTEST_F\s*\(',
            r'\bASSERT_',
            r'\bEXPECT_',
        ]
        return any(re.search(pattern, content) for pattern in gtest_patterns)

    def _is_catch2(self, content: str) -> bool:
        """Check if file uses Catch2."""
        catch_patterns = [
            r'#include\s+[<"]catch2?/catch\.hpp[>"]',
            r'\bTEST_CASE\s*\(',
            r'\bSECTION\s*\(',
            r'\bREQUIRE\s*\(',
            r'\bCHECK\s*\(',
        ]
        return any(re.search(pattern, content) for pattern in catch_patterns)

    def _is_boost_test(self, content: str) -> bool:
        """Check if file uses Boost.Test."""
        boost_patterns = [
            r'#include\s+<boost/test/',
            r'\bBOOST_AUTO_TEST_CASE\s*\(',
            r'\bBOOST_TEST\s*\(',
            r'\bBOOST_CHECK',
            r'\bBOOST_REQUIRE',
        ]
        return any(re.search(pattern, content) for pattern in boost_patterns)

    def parse_file(self, file_path: Path) -> ParsedModule:
        """Parse a C++ test file.

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
                # Not a test file
                raise ParseError(f"No test framework detected in {file_path}")

            parsed = ParsedModule(
                file_path=str(file_path),
                language=self.language,
                framework=framework,
                raw_ast=content,
            )

            # Extract imports (includes)
            parsed.imports = self._extract_imports(content)

            # Check for network imports
            network_modules = {"curl", "boost/asio", "socket"}
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
        """Extract includes from the file."""
        imports = []

        # #include <header> or #include "header"
        include_pattern = r'#include\s+[<"]([^>"]+)[>"]'
        imports.extend(re.findall(include_pattern, content))

        return imports

    def _extract_test_functions(
        self, content: str, parsed_module: ParsedModule
    ) -> List[TestFunction]:
        """Extract test functions based on framework."""
        if parsed_module.framework == TestFramework.GOOGLETEST:
            return self._extract_googletest_tests(content, parsed_module)
        elif parsed_module.framework == TestFramework.CATCH2:
            return self._extract_catch2_tests(content, parsed_module)
        elif parsed_module.framework == TestFramework.BOOST_TEST:
            return self._extract_boost_tests(content, parsed_module)
        return []

    def _extract_googletest_tests(
        self, content: str, parsed_module: ParsedModule
    ) -> List[TestFunction]:
        """Extract GoogleTest tests."""
        test_functions = []

        # TEST(TestSuite, TestName) { ... }
        test_pattern = r'\bTEST\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)\s*{'
        for match in re.finditer(test_pattern, content):
            suite_name = match.group(1)
            test_name = match.group(2)
            full_name = f"{suite_name}.{test_name}"

            line_number = content[:match.start()].count('\n') + 1
            func_body = self._extract_function_body(content, match.end() - 1)

            test_func = self._create_test_function(
                full_name, line_number, func_body, parsed_module
            )
            test_functions.append(test_func)

        # TEST_F(FixtureName, TestName) { ... }
        test_f_pattern = r'\bTEST_F\s*\(\s*(\w+)\s*,\s*(\w+)\s*\)\s*{'
        for match in re.finditer(test_f_pattern, content):
            fixture_name = match.group(1)
            test_name = match.group(2)
            full_name = f"{fixture_name}.{test_name}"

            line_number = content[:match.start()].count('\n') + 1
            func_body = self._extract_function_body(content, match.end() - 1)

            test_func = self._create_test_function(
                full_name, line_number, func_body, parsed_module
            )
            test_func.setup_dependencies = [fixture_name]
            test_functions.append(test_func)

        return test_functions

    def _extract_catch2_tests(
        self, content: str, parsed_module: ParsedModule
    ) -> List[TestFunction]:
        """Extract Catch2 tests."""
        test_functions = []

        # TEST_CASE("test name", "[tag]") { ... }
        test_pattern = r'\bTEST_CASE\s*\(\s*"([^"]+)"'
        for match in re.finditer(test_pattern, content):
            test_name = match.group(1)

            line_number = content[:match.start()].count('\n') + 1
            # Find the opening brace
            brace_pos = content.find('{', match.end())
            if brace_pos != -1:
                func_body = self._extract_function_body(content, brace_pos)
                test_func = self._create_test_function(
                    test_name, line_number, func_body, parsed_module
                )
                test_functions.append(test_func)

        return test_functions

    def _extract_boost_tests(
        self, content: str, parsed_module: ParsedModule
    ) -> List[TestFunction]:
        """Extract Boost.Test tests."""
        test_functions = []

        # BOOST_AUTO_TEST_CASE(test_name) { ... }
        test_pattern = r'\bBOOST_AUTO_TEST_CASE\s*\(\s*(\w+)\s*\)\s*{'
        for match in re.finditer(test_pattern, content):
            test_name = match.group(1)

            line_number = content[:match.start()].count('\n') + 1
            func_body = self._extract_function_body(content, match.end() - 1)

            test_func = self._create_test_function(
                test_name, line_number, func_body, parsed_module
            )
            test_functions.append(test_func)

        return test_functions

    def _create_test_function(
        self, name: str, line_number: int, body: str, parsed_module: ParsedModule
    ) -> TestFunction:
        """Create TestFunction from extracted data."""
        test_func = TestFunction(
            name=name,
            file_path=parsed_module.file_path,
            line_number=line_number,
            framework=parsed_module.framework,
        )

        if body:
            test_func.assertions = self._extract_assertions(
                body, line_number, parsed_module.framework
            )
            test_func.has_test_logic = self._has_conditional_logic(body)
            test_func.uses_time_sleep = self._uses_time_sleep(body)
            test_func.uses_file_io = self._uses_file_io(body)
            test_func.uses_network = self._uses_network(body)

        return test_func

    def _extract_fixtures(
        self, content: str, parsed_module: ParsedModule
    ) -> List[TestFixture]:
        """Extract fixtures/setup functions."""
        fixtures = []

        if parsed_module.framework == TestFramework.GOOGLETEST:
            # class MyTest : public ::testing::Test {
            #   protected:
            #     void SetUp() override { ... }
            #     void TearDown() override { ... }
            # };
            fixture_pattern = r'class\s+(\w+)\s*:\s*public\s+::?testing::Test'
            for match in re.finditer(fixture_pattern, content):
                fixture_name = match.group(1)
                line_number = content[:match.start()].count('\n') + 1

                fixture = TestFixture(
                    name=fixture_name,
                    scope="class",
                    file_path=parsed_module.file_path,
                    line_number=line_number,
                    is_auto=False,
                )
                fixtures.append(fixture)

        elif parsed_module.framework == TestFramework.BOOST_TEST:
            # BOOST_AUTO_TEST_SUITE(suite_name)
            suite_pattern = r'\bBOOST_AUTO_TEST_SUITE\s*\(\s*(\w+)\s*\)'
            for match in re.finditer(suite_pattern, content):
                suite_name = match.group(1)
                line_number = content[:match.start()].count('\n') + 1

                fixture = TestFixture(
                    name=suite_name,
                    scope="class",
                    file_path=parsed_module.file_path,
                    line_number=line_number,
                    is_auto=True,
                )
                fixtures.append(fixture)

        return fixtures

    def _extract_function_body(self, content: str, start_pos: int) -> str:
        """Extract function body by matching braces."""
        if start_pos >= len(content) or content[start_pos] != '{':
            return ""

        depth = 0
        in_string = False
        escape_next = False

        for i in range(start_pos, len(content)):
            char = content[i]

            # Handle strings
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue

            if not in_string:
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

        if framework == TestFramework.GOOGLETEST:
            # ASSERT_*, EXPECT_*
            patterns = [
                r'\b(ASSERT|EXPECT)_(TRUE|FALSE|EQ|NE|LT|LE|GT|GE|STREQ|STRNE)\s*\(',
            ]
        elif framework == TestFramework.CATCH2:
            # REQUIRE, CHECK
            patterns = [
                r'\b(REQUIRE|CHECK)(_FALSE|_THROWS|_NOTHROW)?\s*\(',
            ]
        elif framework == TestFramework.BOOST_TEST:
            # BOOST_TEST, BOOST_CHECK, BOOST_REQUIRE
            patterns = [
                r'\bBOOST_(TEST|CHECK|REQUIRE)(_EQUAL|_NE|_LT|_LE|_GT|_GE)?\s*\(',
            ]
        else:
            patterns = []

        for pattern in patterns:
            for match in re.finditer(pattern, body):
                assertion_type = match.group(0).split('(')[0]
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
        """Check if body uses sleep functions."""
        patterns = [
            r'std::this_thread::sleep_for\s*\(',
            r'std::this_thread::sleep_until\s*\(',
            r'\bsleep\s*\(',
            r'\busleep\s*\(',
            r'Sleep\s*\(',  # Windows
        ]
        return any(re.search(pattern, body) for pattern in patterns)

    def _uses_file_io(self, body: str) -> bool:
        """Check if body uses file I/O."""
        patterns = [
            r'std::ifstream',
            r'std::ofstream',
            r'std::fstream',
            r'\bfopen\s*\(',
            r'\bopen\s*\(',
        ]
        return any(re.search(pattern, body) for pattern in patterns)

    def _uses_network(self, body: str) -> bool:
        """Check if body uses network calls."""
        patterns = [
            r'curl_',
            r'boost::asio',
            r'\bsocket\s*\(',
            r'\bconnect\s*\(',
            r'\bbind\s*\(',
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
            match = re.search(r'([\w:]+)\s*\(', node)
            if match:
                return match.group(1)
        return None

    def is_assertion(self, node: Any) -> bool:
        """Check if node is an assertion."""
        if isinstance(node, str):
            patterns = [
                r'\b(ASSERT|EXPECT|REQUIRE|CHECK|BOOST_TEST|BOOST_CHECK|BOOST_REQUIRE)_',
            ]
            return any(re.search(pattern, node) for pattern in patterns)
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
        """C++ supports async tests (though not common)."""
        return False

    def get_supported_frameworks(self) -> List[TestFramework]:
        """Get supported C++ test frameworks."""
        return [
            TestFramework.GOOGLETEST,
            TestFramework.CATCH2,
            TestFramework.BOOST_TEST,
        ]
