"""Rust language adapter implementation."""

from pathlib import Path
from typing import List, Optional, Any
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


class RustAdapter(LanguageAdapter):
    """Language adapter for Rust test files."""

    def __init__(self):
        super().__init__(LanguageType.RUST)

    def can_handle_file(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".rs"

    def detect_framework(self, file_path: Path) -> Optional[TestFramework]:
        try:
            content = file_path.read_text(encoding="utf-8")
            if re.search(r"#\[test\]|#\[cfg\(test\)\]", content):
                return TestFramework.RUST_BUILTIN
            return None
        except:
            return None

    def parse_file(self, file_path: Path) -> ParsedModule:
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
        parsed.imports = re.findall(r"use\s+([\w:]+)", content)
        parsed.test_functions = self._extract_tests(content, parsed)
        return parsed

    def _extract_tests(self, content: str, pm: ParsedModule) -> List[TestFunction]:
        tests = []
        pattern = r"#\[test\]\s*(?:async\s+)?fn\s+(\w+)\s*\("
        for m in re.finditer(pattern, content):
            line = content[: m.start()].count("\n") + 1
            body = self._extract_body(content, m.end())
            tf = TestFunction(m.group(1), pm.file_path, line, pm.framework)
            tf.assertions = [
                TestAssertion(line, "assert", e)
                for e in re.findall(r"assert[_!]", body)
            ]
            tf.has_test_logic = bool(re.search(r"\b(if|for|while)\s", body))
            tf.uses_time_sleep = bool(re.search(r"thread::sleep|sleep\(", body))
            tf.uses_file_io = bool(re.search(r"File::|fs::", body))
            tests.append(tf)
        return tests

    def _extract_body(self, content: str, pos: int) -> str:
        """Extract function body using string-aware brace matching.

        Handles Rust's raw strings (r#"..."#) and regular strings.
        """
        return extract_brace_delimited_body(content, pos)

    def extract_test_functions(self, pm: ParsedModule) -> List[TestFunction]:
        return pm.test_functions

    def extract_fixtures(self, pm: ParsedModule) -> List[TestFixture]:
        return []

    def get_call_name(self, node: Any) -> Optional[str]:
        if isinstance(node, str):
            m = re.search(r"([\w:]+)\s*\(", node)
            return m.group(1) if m else None
        return None

    def is_assertion(self, node: Any) -> bool:
        return (
            bool(re.search(r"assert[_!]", str(node)))
            if isinstance(node, str)
            else False
        )

    def is_conditional(self, node: Any) -> bool:
        return (
            bool(re.search(r"\b(if|for|while)\s", str(node)))
            if isinstance(node, str)
            else False
        )

    def get_file_imports(self, pm: ParsedModule) -> List[str]:
        return pm.imports

    def supports_async(self) -> bool:
        return True

    def get_supported_frameworks(self) -> List[TestFramework]:
        return [TestFramework.RUST_BUILTIN]
