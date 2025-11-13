"""
Main pytest plugin for runtime semantic validation.

This plugin hooks into pytest's execution lifecycle to collect runtime
data and perform semantic validations that cannot be done statically.
"""

from typing import Optional, List, Dict, Any, Set
import sys
import inspect
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from _pytest.config import Config
from _pytest.nodes import Item
from _pytest.reports import TestReport

from pytest_deep_analysis.runtime.collectors import ExecutionTraceCollector
from pytest_deep_analysis.runtime.bdd_validator import BDDValidator
from pytest_deep_analysis.runtime.pbt_analyzer import PBTAnalyzer
from pytest_deep_analysis.runtime.dbc_tracker import DbCTracker
from pytest_deep_analysis.runtime.semantic_reporter import SemanticReporter


@dataclass
class TestExecutionContext:
    """Context for a single test execution."""
    test_id: str
    test_name: str
    test_file: str
    test_function: Any

    # Execution traces
    function_calls: List[Dict[str, Any]] = field(default_factory=list)
    assertions_executed: List[Dict[str, Any]] = field(default_factory=list)
    exceptions_raised: List[Exception] = field(default_factory=list)

    # BDD-specific
    gherkin_steps: Optional[List[str]] = None
    scenario_reference: Optional[str] = None

    # PBT-specific
    hypothesis_examples_tried: int = 0
    hypothesis_falsifying_example: Optional[Any] = None

    # DbC-specific
    contracts_checked: List[str] = field(default_factory=list)
    contract_violations: List[str] = field(default_factory=list)

    # Result
    passed: bool = False
    semantic_issues: List[str] = field(default_factory=list)


class SemanticValidationPlugin:
    """
    Pytest plugin for runtime semantic validation.

    This plugin collects execution traces and validates semantic properties
    that cannot be verified statically:

    1. BDD Validation: Gherkin steps actually execute
    2. PBT Analysis: Hypothesis coverage and shrinking
    3. DbC Tracking: Contract enforcement and violations
    4. Semantic Coverage: Tests that pass but verify nothing
    """

    def __init__(self, config: Config):
        self.config = config
        self.enabled = config.getoption("--semantic-validate", default=False)
        self.checks = config.getoption("--semantic-checks", default="all")
        self.report_format = config.getoption("--semantic-report", default="terminal")

        # Validators
        self.bdd_validator = BDDValidator()
        self.pbt_analyzer = PBTAnalyzer()
        self.dbc_tracker = DbCTracker()
        self.trace_collector = ExecutionTraceCollector()

        # Test execution contexts
        self.test_contexts: Dict[str, TestExecutionContext] = {}
        self.current_context: Optional[TestExecutionContext] = None

        # Global semantic issues
        self.global_issues: List[str] = []

        # Semantic feedback loop: Load validation tasks from static linter
        self.validation_tasks = self._load_validation_tasks()
        # Semantic feedback loop: Track validation results
        self.validation_results: Dict[str, Dict[str, Any]] = {}

    def _load_validation_tasks(self) -> Dict[str, List[str]]:
        """Load validation tasks from static linter (Phase 1)."""
        import json
        from pathlib import Path

        task_file = Path(".pytest_deep_analysis_tasks.json")
        if not task_file.exists():
            return {}

        try:
            return json.loads(task_file.read_text())
        except Exception:
            return {}

    def should_check(self, check_type: str) -> bool:
        """Check if a specific validation type is enabled."""
        if not self.enabled:
            return False
        return self.checks == "all" or check_type in self.checks.split(",")

    def create_test_context(self, item: Item) -> TestExecutionContext:
        """Create execution context for a test item."""
        test_id = item.nodeid
        test_name = item.name
        test_file = str(item.fspath)
        test_function = item.obj

        context = TestExecutionContext(
            test_id=test_id,
            test_name=test_name,
            test_file=test_file,
            test_function=test_function
        )

        # Extract BDD markers
        if self.should_check("bdd"):
            scenario_marker = item.get_closest_marker("scenario")
            if scenario_marker:
                context.scenario_reference = str(scenario_marker.args)

            # Extract Gherkin from docstring
            if test_function.__doc__:
                context.gherkin_steps = self._extract_gherkin_steps(test_function.__doc__)

        return context

    def _extract_gherkin_steps(self, docstring: str) -> List[str]:
        """Extract Gherkin steps from docstring."""
        steps = []
        for line in docstring.split('\n'):
            line = line.strip()
            if line.startswith(('Given ', 'When ', 'Then ', 'And ', 'But ')):
                steps.append(line)
        return steps if steps else None

    def start_test_execution(self, item: Item):
        """Called before test execution starts."""
        self.current_context = self.create_test_context(item)
        self.test_contexts[item.nodeid] = self.current_context

        # Start trace collection
        if self.should_check("bdd") or self.should_check("coverage"):
            self.trace_collector.start_trace(self.current_context)

    def end_test_execution(self, item: Item, outcome: str):
        """Called after test execution completes."""
        if not self.current_context:
            return

        self.current_context.passed = (outcome == "passed")

        # Stop trace collection
        self.trace_collector.stop_trace()

        # Run semantic validations
        self._validate_test_semantics(self.current_context)

        self.current_context = None

    def _validate_test_semantics(self, context: TestExecutionContext):
        """Run all enabled semantic validations on test context."""

        # Semantic feedback loop Phase 2: Check if this test needs validation
        test_id = context.test_id
        needs_validation = self.validation_tasks.get(test_id, [])

        if test_id not in self.validation_results:
            self.validation_results[test_id] = {}

        # 1. BDD Validation: Gherkin steps actually executed
        if self.should_check("bdd") and context.gherkin_steps:
            bdd_issues = self.bdd_validator.validate_scenario_execution(
                context.gherkin_steps,
                context.function_calls
            )
            context.semantic_issues.extend(bdd_issues)

            # Semantic feedback loop: Record BDD validation result
            if "bdd" in needs_validation:
                self.validation_results[test_id]["bdd"] = {
                    "validated": len(bdd_issues) == 0 and context.passed,
                    "timestamp": self._get_timestamp(),
                }

        # 2. PBT Analysis: Check Hypothesis coverage
        if self.should_check("pbt") and context.hypothesis_examples_tried > 0:
            pbt_issues = self.pbt_analyzer.analyze_coverage(context)
            context.semantic_issues.extend(pbt_issues)

            # Semantic feedback loop: Record PBT validation result
            if "pbt" in needs_validation:
                self.validation_results[test_id]["pbt"] = {
                    "validated": len(pbt_issues) == 0 and context.passed,
                    "timestamp": self._get_timestamp(),
                }

        # 3. DbC Tracking: Contract enforcement
        if self.should_check("dbc") and context.contracts_checked:
            dbc_issues = self.dbc_tracker.analyze_contracts(context)
            context.semantic_issues.extend(dbc_issues)

        # 4. Semantic Coverage: Test passed but verified nothing
        if self.should_check("coverage"):
            if context.passed and not context.assertions_executed:
                if not context.exceptions_raised:  # No pytest.raises
                    context.semantic_issues.append(
                        "SEMANTIC-COVERAGE: Test passed but executed no assertions "
                        "(possible false positive)"
                    )

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()

    def _write_validation_cache(self):
        """Write validation cache for static linter (Phase 2)."""
        import json
        from pathlib import Path

        cache_data = {
            "tests_with_semantic_validation": self.validation_results,
            "timestamp": self._get_timestamp(),
        }

        cache_file = Path(".pytest_deep_analysis_cache.json")
        try:
            cache_file.write_text(json.dumps(cache_data, indent=2))
        except Exception:
            # Fail silently if we can't write the cache
            pass

    def generate_report(self):
        """Generate semantic validation report."""
        reporter = SemanticReporter(
            test_contexts=self.test_contexts,
            global_issues=self.global_issues,
            format=self.report_format
        )
        reporter.generate()

        # Semantic feedback loop Phase 2: Write validation cache
        self._write_validation_cache()


# Pytest plugin hooks
_plugin_instance: Optional[SemanticValidationPlugin] = None


def pytest_addoption(parser):
    """Add command-line options for semantic validation."""
    group = parser.getgroup("semantic", "Runtime semantic validation")

    group.addoption(
        "--semantic-validate",
        action="store_true",
        default=False,
        help="Enable runtime semantic validation"
    )

    group.addoption(
        "--semantic-checks",
        action="store",
        default="all",
        help="Comma-separated list of checks: bdd,pbt,dbc,coverage (default: all)"
    )

    group.addoption(
        "--semantic-report",
        action="store",
        default="terminal",
        choices=["terminal", "html", "json"],
        help="Report format (default: terminal)"
    )


def pytest_configure(config: Config):
    """Initialize the semantic validation plugin."""
    global _plugin_instance

    if config.getoption("--semantic-validate", default=False):
        _plugin_instance = SemanticValidationPlugin(config)
        config.pluginmanager.register(_plugin_instance, "semantic_validation")

        # Register markers
        config.addinivalue_line(
            "markers",
            "scenario(feature, scenario): Mark test with BDD scenario reference"
        )
        config.addinivalue_line(
            "markers",
            "property(description): Mark test as property-based test"
        )


def pytest_collection_modifyitems(config: Config, items: List[Item]):
    """Analyze collected test items."""
    if not _plugin_instance or not _plugin_instance.enabled:
        return

    # Pre-analyze test collection for reporting
    for item in items:
        # Check for missing BDD markers (complement static check)
        if _plugin_instance.should_check("bdd"):
            if not item.get_closest_marker("scenario"):
                if hasattr(item.obj, "__doc__") and item.obj.__doc__:
                    if not any(kw in item.obj.__doc__.lower()
                             for kw in ["given", "when", "then", "scenario"]):
                        _plugin_instance.global_issues.append(
                            f"BDD-MISSING: {item.nodeid} lacks scenario marker or Gherkin docstring"
                        )


def pytest_runtest_setup(item: Item):
    """Hook called before test execution."""
    if _plugin_instance and _plugin_instance.enabled:
        _plugin_instance.start_test_execution(item)


def pytest_runtest_call(item: Item):
    """Hook called during test execution."""
    # Execution tracing happens automatically via sys.settrace
    pass


def pytest_runtest_teardown(item: Item, nextitem):
    """Hook called after test execution."""
    # Finalization happens in pytest_runtest_makereport once the real outcome is known.
    pass


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: Item, call):
    """Capture test outcome for semantic analysis."""
    outcome = yield
    report: TestReport = outcome.get_result()

    if _plugin_instance and _plugin_instance.enabled:
        if report.when == "call":
            # Stop trace collection and finalize the test context after the call phase
            if _plugin_instance.current_context:
                _plugin_instance.end_test_execution(item, report.outcome)


def pytest_sessionfinish(session, exitstatus):
    """Generate final semantic validation report."""
    if _plugin_instance and _plugin_instance.enabled:
        _plugin_instance.generate_report()
