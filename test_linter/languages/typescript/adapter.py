"""TypeScript/JavaScript language adapter implementation using tree-sitter."""

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

try:
    from tree_sitter import Language, Parser, Node
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    Language = None
    Parser = None
    Node = None


class TypeScriptAdapter(LanguageAdapter):
    """Language adapter for TypeScript/JavaScript test files.

    Supports Jest, Mocha, and Vitest test frameworks.
    Uses tree-sitter for robust AST parsing when available,
    falls back to regex-based detection otherwise.
    """

    def __init__(self, language: LanguageType = LanguageType.TYPESCRIPT):
        super().__init__(language)
        self._parser = None
        self._ts_language = None

        if TREE_SITTER_AVAILABLE:
            self._init_parser()

    def _init_parser(self):
        """Initialize tree-sitter parser if available."""
        try:
            # Try to load pre-built language libraries
            # In production, these would be built during installation
            # For now, we'll use fallback regex parsing
            pass
        except Exception:
            pass

    def can_handle_file(self, file_path: Path) -> bool:
        """Check if this is a TypeScript/JavaScript file."""
        suffix = file_path.suffix.lower()
        return suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}

    def detect_framework(self, file_path: Path) -> Optional[TestFramework]:
        """Detect test framework by examining imports and function calls.

        Args:
            file_path: Path to the TypeScript/JavaScript file

        Returns:
            TestFramework.JEST, MOCHA, or VITEST if detected, None otherwise
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # Jest detection
            if self._is_jest(content):
                return TestFramework.JEST

            # Vitest detection (similar to Jest but uses 'vitest')
            if self._is_vitest(content):
                return TestFramework.VITEST

            # Mocha detection
            if self._is_mocha(content):
                return TestFramework.MOCHA

            # Check for test functions (generic detection)
            if self._has_test_functions(content):
                # Default to Jest as most common
                return TestFramework.JEST

            return None

        except Exception:
            return None

    def _is_jest(self, content: str) -> bool:
        """Check if file uses Jest."""
        jest_patterns = [
            r"from\s+['\"]@?jest",
            r"require\(['\"]@?jest",
            r"\bdescribe\(",
            r"\bit\(",
            r"\btest\(",
            r"\bexpect\(",
            r"jest\.mock\(",
            r"@jest/globals",
        ]
        return any(re.search(pattern, content) for pattern in jest_patterns)

    def _is_vitest(self, content: str) -> bool:
        """Check if file uses Vitest."""
        vitest_patterns = [
            r"from\s+['\"]vitest",
            r"import.*from\s+['\"]vitest",
            r"vitest\.config",
        ]
        return any(re.search(pattern, content) for pattern in vitest_patterns)

    def _is_mocha(self, content: str) -> bool:
        """Check if file uses Mocha."""
        mocha_patterns = [
            r"from\s+['\"]mocha",
            r"require\(['\"]mocha",
            r"\bbefore\(",
            r"\bafter\(",
            r"\bbeforeEach\(",
            r"\bafterEach\(",
            r"import.*\{.*describe.*\}.*from.*['\"]mocha",
        ]
        # Mocha often uses describe/it without explicit import
        has_mocha_imports = any(re.search(pattern, content) for pattern in mocha_patterns)
        has_describe_it = re.search(r"\bdescribe\(", content) and re.search(r"\bit\(", content)

        return has_mocha_imports or (has_describe_it and not self._is_jest(content))

    def _has_test_functions(self, content: str) -> bool:
        """Check if file has test functions."""
        test_patterns = [
            r"\btest\(",
            r"\bit\(",
            r"\bdescribe\(",
        ]
        return any(re.search(pattern, content) for pattern in test_patterns)

    def parse_file(self, file_path: Path) -> ParsedModule:
        """Parse a TypeScript/JavaScript test file.

        Args:
            file_path: Path to the file

        Returns:
            ParsedModule with extracted test information

        Raises:
            ParseError: If parsing fails
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            framework = self.detect_framework(file_path) or TestFramework.JEST

            parsed = ParsedModule(
                file_path=str(file_path),
                language=self.language,
                framework=framework,
                raw_ast=content,  # Store content as "AST" for now
            )

            # Extract imports
            parsed.imports = self._extract_imports(content)

            # Check for network imports
            network_modules = {"axios", "fetch", "http", "https", "net", "request"}
            parsed.has_network_imports = any(
                imp in network_modules for imp in parsed.imports
            )

            # Extract test functions and fixtures
            parsed.test_functions = self._extract_test_functions_regex(content, parsed)
            parsed.fixtures = self._extract_fixtures_regex(content, parsed)

            return parsed

        except Exception as e:
            raise ParseError(f"Failed to parse {file_path}: {e}")

    def _extract_imports(self, content: str) -> List[str]:
        """Extract imports from the file."""
        imports = []

        # ES6 imports: import ... from 'module'
        import_pattern = r"import\s+(?:.*\s+from\s+)?['\"]([^'\"]+)['\"]"
        imports.extend(re.findall(import_pattern, content))

        # CommonJS: require('module')
        require_pattern = r"require\(['\"]([^'\"]+)['\"]\)"
        imports.extend(re.findall(require_pattern, content))

        return imports

    def _extract_test_functions_regex(
        self, content: str, parsed_module: ParsedModule
    ) -> List[TestFunction]:
        """Extract test functions using regex (fallback method)."""
        test_functions = []

        # Pattern to match test functions: test('name', ...), it('name', ...), etc.
        patterns = [
            r"(test|it)\s*\(\s*['\"]([^'\"]+)['\"]",
            r"(test|it)\.(?:each|skip|only)\s*\([^)]*\)\s*\(\s*['\"]([^'\"]+)['\"]",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, content):
                test_type = match.group(1)
                test_name = match.group(2) if len(match.groups()) >= 2 else "unknown"

                # Find line number
                line_number = content[:match.start()].count('\n') + 1

                # Extract the test body (simplified - just look for the closing brace)
                test_start = match.end()
                test_body = self._extract_function_body(content, test_start)

                test_func = TestFunction(
                    name=test_name,
                    file_path=parsed_module.file_path,
                    line_number=line_number,
                    framework=parsed_module.framework,
                )

                # Analyze test body
                if test_body:
                    test_func.assertions = self._extract_assertions(test_body, line_number)
                    test_func.has_test_logic = self._has_conditional_logic(test_body)
                    test_func.uses_time_sleep = self._uses_time_sleep(test_body)
                    test_func.uses_file_io = self._uses_file_io(test_body)
                    test_func.uses_network = self._uses_network(test_body)
                    test_func.has_async = "async" in content[max(0, match.start() - 20):match.start()]
                    test_func.setup_dependencies = self._extract_fixtures_used(test_body)

                test_functions.append(test_func)

        return test_functions

    def _extract_fixtures_regex(
        self, content: str, parsed_module: ParsedModule
    ) -> List[TestFixture]:
        """Extract fixtures/setup functions."""
        fixtures = []

        # Jest/Mocha setup patterns
        setup_patterns = {
            "beforeEach": "function",
            "beforeAll": "class",
            "afterEach": "function",
            "afterAll": "class",
            "before": "class",
            "after": "class",
        }

        for setup_func, scope in setup_patterns.items():
            pattern = rf"\b{setup_func}\s*\("
            for match in re.finditer(pattern, content):
                line_number = content[:match.start()].count('\n') + 1

                fixture = TestFixture(
                    name=setup_func,
                    scope=scope,
                    file_path=parsed_module.file_path,
                    line_number=line_number,
                    is_auto=True,  # beforeEach/afterEach run automatically
                )
                fixtures.append(fixture)

        return fixtures

    def _extract_function_body(self, content: str, start_pos: int) -> str:
        """Extract function body by matching braces."""
        # Find the opening brace
        brace_start = content.find('{', start_pos)
        if brace_start == -1:
            return ""

        # Match braces
        depth = 0
        for i in range(brace_start, len(content)):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    return content[brace_start:i+1]

        return ""

    def _extract_assertions(self, body: str, start_line: int) -> List[TestAssertion]:
        """Extract assertions from test body."""
        assertions = []

        # Jest/Vitest assertions: expect(...).toBe(...), etc.
        expect_pattern = r"expect\([^)]+\)\.(\w+)\("
        for match in re.finditer(expect_pattern, body):
            assertion_type = match.group(1)
            line_offset = body[:match.start()].count('\n')

            assertions.append(TestAssertion(
                line_number=start_line + line_offset,
                assertion_type=assertion_type,
                expression=match.group(0),
            ))

        # Mocha assertions: assert.equal(...), etc.
        assert_pattern = r"assert\.(\w+)\("
        for match in re.finditer(assert_pattern, body):
            assertion_type = match.group(1)
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
            r"\bif\s*\(",
            r"\bfor\s*\(",
            r"\bwhile\s*\(",
            r"\bswitch\s*\(",
        ]
        return any(re.search(pattern, body) for pattern in patterns)

    def _uses_time_sleep(self, body: str) -> bool:
        """Check if body uses setTimeout/setInterval."""
        patterns = [
            r"\bsetTimeout\s*\(",
            r"\bsetInterval\s*\(",
        ]
        return any(re.search(pattern, body) for pattern in patterns)

    def _uses_file_io(self, body: str) -> bool:
        """Check if body uses file I/O."""
        patterns = [
            r"\bfs\.\w+",
            r"\breadFile",
            r"\bwriteFile",
            r"\bopen\(",
        ]
        return any(re.search(pattern, body) for pattern in patterns)

    def _uses_network(self, body: str) -> bool:
        """Check if body uses network calls."""
        patterns = [
            r"\bfetch\s*\(",
            r"\baxios\.",
            r"\bhttp\.",
            r"\bhttps\.",
        ]
        return any(re.search(pattern, body) for pattern in patterns)

    def _extract_fixtures_used(self, body: str) -> List[str]:
        """Extract fixture names used in test."""
        # This is simplified - would need proper parsing for accurate results
        return []

    def extract_test_functions(self, parsed_module: ParsedModule) -> List[TestFunction]:
        """Extract test functions from parsed module."""
        return parsed_module.test_functions

    def extract_fixtures(self, parsed_module: ParsedModule) -> List[TestFixture]:
        """Extract fixtures from parsed module."""
        return parsed_module.fixtures

    def get_call_name(self, node: Any) -> Optional[str]:
        """Get qualified name of a function call."""
        # For regex-based parsing, this would be called with string snippets
        if isinstance(node, str):
            # Extract function name from call expression
            match = re.search(r'(\w+(?:\.\w+)*)\s*\(', node)
            if match:
                return match.group(1)
        return None

    def is_assertion(self, node: Any) -> bool:
        """Check if node is an assertion."""
        if isinstance(node, str):
            return bool(re.search(r'\b(expect|assert)\s*\(', node))
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
        """TypeScript/JavaScript supports async tests."""
        return True

    def get_supported_frameworks(self) -> List[TestFramework]:
        """Get supported JavaScript/TypeScript test frameworks."""
        return [TestFramework.JEST, TestFramework.MOCHA, TestFramework.VITEST]
