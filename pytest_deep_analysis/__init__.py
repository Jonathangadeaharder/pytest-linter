"""
pytest-deep-analysis: A Pylint plugin for deep, semantic pytest linting.

This plugin provides high-value, semantics-aware analysis of pytest code,
targeting the most complex pain points in the pytest ecosystem:
- Test flakiness caused by environment dependencies
- Maintenance overhead from test complexity
- Fixture interaction issues and scope misalignment

Architecture:
- Built as a Pylint plugin to leverage astroid's powerful inference engine
- Implements cross-file, project-wide semantic analysis
- Designed to complement fast linters like Ruff in a hybrid toolchain

Usage:
    pylint --disable=all --enable=pytest-deep-analysis path/to/tests/
"""

from typing import TYPE_CHECKING

from pytest_deep_analysis.checkers import PytestDeepAnalysisChecker

if TYPE_CHECKING:
    from pylint.lint import PyLinter


def register(linter: "PyLinter") -> None:
    """Register the pytest-deep-analysis checker with Pylint.

    This function is called by Pylint when loading the plugin.

    Args:
        linter: The Pylint linter instance
    """
    linter.register_checker(PytestDeepAnalysisChecker(linter))


__version__ = "0.1.0"
__all__ = ["register", "PytestDeepAnalysisChecker"]
