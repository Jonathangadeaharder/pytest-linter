"""
Base test infrastructure for pytest-deep-analysis linter tests.

This module provides utilities for testing the linter using pylint.testutils.
"""

from typing import List, Tuple, Optional, Set
import textwrap
import tempfile
import os
from pathlib import Path

import astroid
from pylint.testutils import CheckerTestCase, MessageTest
from pylint.lint import PyLinter

from pytest_deep_analysis.checkers import PytestDeepAnalysisChecker


class PytestDeepAnalysisTestCase(CheckerTestCase):
    """Base test case for pytest-deep-analysis checker tests.

    This class provides utilities to:
    - Run the linter on code snippets or files
    - Assert that specific messages are generated
    - Verify line numbers and message arguments
    """

    CHECKER_CLASS = PytestDeepAnalysisChecker

    def assert_adds_messages(
        self,
        code: str,
        *expected_messages: MessageTest,
        filename: str = "test.py"
    ) -> None:
        """Assert that the given code produces the expected messages.

        Args:
            code: Python code to lint
            *expected_messages: Expected MessageTest instances
            filename: Name for the temporary file (default: test.py)
        """
        # Dedent the code to make test cases more readable
        code = textwrap.dedent(code)

        # Parse the code into an AST
        node = astroid.parse(code, module_name=filename)

        # Run the checker and collect messages
        self.checker.visit_module(node)
        self.walk(node)

        # Get actual messages
        actual_messages = self.linter.release_messages()

        # Compare messages (only msg_id and line)
        expected_set = {(msg.msg_id, msg.line) for msg in expected_messages}
        actual_set = {(msg.msg_id, msg.line) for msg in actual_messages}

        if expected_set != actual_set:
            missing = expected_set - actual_set
            unexpected = actual_set - expected_set

            error_parts = []
            if missing:
                error_parts.append(f"Missing messages: {sorted(missing)}")
            if unexpected:
                error_parts.append(f"Unexpected messages: {sorted(unexpected)}")

            raise AssertionError("\n".join(error_parts))

    def assert_no_messages(self, code: str, filename: str = "test.py") -> None:
        """Assert that the given code produces no messages.

        Args:
            code: Python code to lint
            filename: Name for the temporary file (default: test.py)
        """
        self.assert_adds_messages(code, filename=filename)

    def assert_file_adds_messages(
        self,
        file_path: str,
        *expected_messages: MessageTest
    ) -> None:
        """Assert that linting a file produces the expected messages.

        Args:
            file_path: Path to the file to lint
            *expected_messages: Expected MessageTest instances
        """
        with open(file_path, 'r') as f:
            code = f.read()

        node = astroid.parse(code, module_name=file_path)
        node.file = file_path  # Set the file path for fixture discovery

        with self.assertAddsMessages(*expected_messages):
            self.checker.visit_module(node)
            self.walk(node)
            # Call close() to trigger fixture graph validation
            self.checker.close()


class MultiFileTestCase:
    """Test case for multi-file analysis (Category 3 fixture checks).

    This class allows testing fixture interactions across multiple conftest.py
    and test files.
    """

    def __init__(self):
        """Initialize the multi-file test case."""
        self.temp_dir: Optional[Path] = None
        self.linter: Optional[PyLinter] = None

    def setup_files(self, file_structure: dict) -> Path:
        """Create a temporary directory structure with test files.

        Args:
            file_structure: Dict mapping file paths to file contents
                Example: {
                    "conftest.py": "import pytest\n...",
                    "test_foo.py": "def test_foo(): ...",
                    "subdir/conftest.py": "...",
                }

        Returns:
            Path to the temporary directory
        """
        self.temp_dir = Path(tempfile.mkdtemp())

        for file_path, content in file_structure.items():
            full_path = self.temp_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(textwrap.dedent(content))

        return self.temp_dir

    def run_linter(self, *file_paths: str) -> List[Tuple[str, int, str]]:
        """Run the linter on the specified files.

        Args:
            *file_paths: Paths relative to temp_dir to lint

        Returns:
            List of (message_id, line_number, message_symbol) tuples
        """
        from pylint.lint import Run
        from io import StringIO
        import sys

        if not self.temp_dir:
            raise ValueError("Must call setup_files() first")

        # Build absolute paths
        abs_paths = [str(self.temp_dir / path) for path in file_paths]

        # Capture pylint output
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()

        messages = []

        try:
            # Run pylint with our plugin
            args = [
                "--load-plugins=pytest_deep_analysis",
                "--disable=all",
                "--enable=pytest-deep-analysis",
                "--reports=n",
                "--score=n",
            ] + abs_paths

            run = Run(args, exit=False)

            # Extract messages from the linter
            for msg in run.linter.reporter.messages:
                messages.append((msg.msg_id, msg.line, msg.symbol))

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        return messages

    def assert_messages(
        self,
        expected: List[Tuple[str, str, int]],
        files: List[str]
    ) -> None:
        """Assert that linting produces the expected messages.

        Args:
            expected: List of (file_path, message_symbol, line_number) tuples
            files: Files to lint
        """
        actual_messages = self.run_linter(*files)

        # Convert expected to set for comparison
        expected_set = {(msg_symbol, line) for _, msg_symbol, line in expected}
        actual_set = {(symbol, line) for _, line, symbol in actual_messages}

        missing = expected_set - actual_set
        unexpected = actual_set - expected_set

        if missing or unexpected:
            error_msg = []
            if missing:
                error_msg.append(f"Missing messages: {missing}")
            if unexpected:
                error_msg.append(f"Unexpected messages: {unexpected}")
            raise AssertionError("\n".join(error_msg))

    def cleanup(self) -> None:
        """Clean up temporary directory."""
        if self.temp_dir:
            import shutil
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None


def msg(
    message_id: str,
    line: Optional[int] = None,
    node: Optional[str] = None,
    args: Optional[tuple] = None,
    **kwargs
) -> MessageTest:
    """Helper to create MessageTest instances with less boilerplate.

    Args:
        message_id: The message ID (e.g., "pytest-flk-time-sleep")
        line: The line number where the message should appear
        node: Optional node type (e.g., "call")
        args: Optional message arguments
        **kwargs: Additional MessageTest arguments

    Returns:
        MessageTest instance
    """
    # Build kwargs dict to only include non-None values
    msg_kwargs = {}
    if line is not None:
        msg_kwargs["line"] = line
    if node is not None:
        msg_kwargs["node"] = node
    if args is not None:
        msg_kwargs["args"] = args
    msg_kwargs.update(kwargs)

    return MessageTest(
        msg_id=message_id,
        **msg_kwargs
    )
