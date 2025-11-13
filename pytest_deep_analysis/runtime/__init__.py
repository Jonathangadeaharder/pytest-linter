"""
Runtime semantic validation plugin for pytest-deep-analysis.

This module provides runtime validation capabilities that complement the
static linter checks, enabling deep semantic analysis that's impossible
to perform statically:

- BDD: Verify Gherkin steps actually execute (trace-to-spec mapping)
- PBT: Analyze Hypothesis strategy coverage and shrinking behavior
- DbC: Track icontract precondition/postcondition enforcement
- Semantic Coverage: Detect tests that pass but verify nothing meaningful
- Requirements Traceability: Generate actual Requirements Traceability Matrix (RTM)

Usage:
    # Enable runtime validation
    pytest --semantic-validate

    # Generate detailed report
    pytest --semantic-validate --semantic-report=html

    # BDD scenario validation only
    pytest --semantic-validate --semantic-checks=bdd
"""

__version__ = "0.2.0"

from pytest_deep_analysis.runtime.plugin import (
    SemanticValidationPlugin,
    pytest_configure,
    pytest_collection_modifyitems,
    pytest_runtest_setup,
    pytest_runtest_call,
    pytest_runtest_teardown,
    pytest_sessionfinish,
)

__all__ = [
    "SemanticValidationPlugin",
    "pytest_configure",
    "pytest_collection_modifyitems",
    "pytest_runtest_setup",
    "pytest_runtest_call",
    "pytest_runtest_teardown",
    "pytest_sessionfinish",
]
