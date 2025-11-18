"""Universal test smell detection rules.

This module contains language-agnostic test smell detection rules
that work across all supported languages.
"""

from typing import List, Optional, Set, Dict, Any

from test_linter.core.models import (
    TestFunction,
    TestFixture,
    SmellCategory,
    SmellSeverity,
    LanguageType,
    TestFramework,
)
from test_linter.core.rules import UniversalRule, RuleViolation
from test_linter.core.adapters import ParsedModule


class TimeSleepRule(UniversalRule):
    """Detects time-based waits (sleep calls) in tests.

    Time-based waits create slow, unreliable, and flaky tests.
    Instead, tests should use explicit polling or wait conditions.
    """

    # Language-specific sleep function names
    SLEEP_FUNCTIONS: Dict[LanguageType, Set[str]] = {
        LanguageType.PYTHON: {"time.sleep", "sleep"},
        LanguageType.TYPESCRIPT: {"setTimeout", "setInterval"},
        LanguageType.JAVASCRIPT: {"setTimeout", "setInterval"},
        LanguageType.GO: {"time.Sleep", "Sleep"},
        LanguageType.CPP: {
            "std::this_thread::sleep_for",
            "std::this_thread::sleep_until",
            "sleep",
            "usleep",
        },
        LanguageType.JAVA: {"Thread.sleep", "sleep"},
        LanguageType.RUST: {"thread::sleep", "sleep"},
        LanguageType.CSHARP: {"Thread.Sleep", "Task.Delay"},
    }

    def __init__(self):
        super().__init__(
            rule_id="UNI-FLK-001",
            name="time-sleep",
            category=SmellCategory.FLAKINESS,
            severity=SmellSeverity.WARNING,
            description="Time-based waits (sleep) found in test. Use explicit waits instead.",
        )

    def check(
        self,
        parsed_module: ParsedModule,
        all_modules: Optional[List[ParsedModule]] = None,
    ) -> List[RuleViolation]:
        violations = []
        sleep_funcs = self.SLEEP_FUNCTIONS.get(parsed_module.language, set())

        for test_func in parsed_module.test_functions:
            if test_func.uses_time_sleep:
                violations.append(
                    RuleViolation(
                        rule_id=self.rule_id,
                        rule_name=self.name,
                        message=f"Time-based wait found in test '{test_func.name}'. "
                        f"Use explicit waits instead.",
                        file_path=test_func.file_path,
                        line_number=test_func.line_number,
                        severity=self.severity,
                        category=self.category,
                        suggestion="Replace time-based waits with polling or wait conditions "
                        "that check for the actual condition.",
                        context={"test_name": test_func.name},
                    )
                )

        return violations


class MysteryGuestRule(UniversalRule):
    """Detects file I/O without proper test fixtures.

    Tests that use file I/O without setup fixtures are harder to
    understand and maintain. They should use temporary directories
    or mock file operations.
    """

    def __init__(self):
        super().__init__(
            rule_id="UNI-FLK-002",
            name="mystery-guest",
            category=SmellCategory.FLAKINESS,
            severity=SmellSeverity.WARNING,
            description="Test uses file I/O without a resource fixture.",
        )

    def check(
        self,
        parsed_module: ParsedModule,
        all_modules: Optional[List[ParsedModule]] = None,
    ) -> List[RuleViolation]:
        violations = []

        for test_func in parsed_module.test_functions:
            if test_func.uses_file_io:
                # Check if test has a temporary directory fixture
                has_temp_fixture = self._has_temp_fixture(
                    test_func, parsed_module.framework
                )

                if not has_temp_fixture:
                    violations.append(
                        RuleViolation(
                            rule_id=self.rule_id,
                            rule_name=self.name,
                            message=f"Test '{test_func.name}' uses file I/O without "
                            f"a resource fixture (Mystery Guest).",
                            file_path=test_func.file_path,
                            line_number=test_func.line_number,
                            severity=self.severity,
                            category=self.category,
                            suggestion="Use a temporary directory fixture to ensure "
                            "test isolation and clarity.",
                            context={"test_name": test_func.name},
                        )
                    )

        return violations

    def _has_temp_fixture(
        self, test_func: TestFunction, framework: TestFramework
    ) -> bool:
        """Check if test uses a temporary directory fixture."""
        temp_fixture_names = {
            TestFramework.PYTEST: {"tmp_path", "tmp_path_factory", "tmpdir"},
            TestFramework.UNITTEST: {"tempfile", "TemporaryDirectory"},
            TestFramework.JEST: {"tmp", "tmpdir"},
            TestFramework.MOCHA: {"tmp", "tmpdir"},
            # Add more as needed
        }
        expected_fixtures = temp_fixture_names.get(framework, set())
        return any(
            fixture in expected_fixtures for fixture in test_func.setup_dependencies
        )


class TestLogicRule(UniversalRule):
    """Detects conditional logic (if/for/while) in tests.

    Tests should follow the simple Arrange-Act-Assert pattern.
    Conditional logic increases complexity and maintenance burden.
    """

    def __init__(self):
        super().__init__(
            rule_id="UNI-MNT-001",
            name="test-logic",
            category=SmellCategory.MAINTENANCE,
            severity=SmellSeverity.WARNING,
            description="Conditional logic (if/for/while) found in test.",
        )

    def check(
        self,
        parsed_module: ParsedModule,
        all_modules: Optional[List[ParsedModule]] = None,
    ) -> List[RuleViolation]:
        violations = []

        for test_func in parsed_module.test_functions:
            if test_func.has_test_logic:
                violations.append(
                    RuleViolation(
                        rule_id=self.rule_id,
                        rule_name=self.name,
                        message=f"Test '{test_func.name}' contains conditional logic. "
                        f"Tests should follow Arrange-Act-Assert pattern.",
                        file_path=test_func.file_path,
                        line_number=test_func.line_number,
                        severity=self.severity,
                        category=self.category,
                        suggestion="Split complex tests into multiple simple tests, "
                        "or use parametrized tests for different scenarios.",
                        context={"test_name": test_func.name},
                    )
                )

        return violations


class AssertionRouletteRule(UniversalRule):
    """Detects tests with too many assertions.

    Tests with many assertions are hard to understand and debug.
    When they fail, it's unclear which assertion failed without
    reading the error message carefully.
    """

    def __init__(self, max_assertions: int = 3):
        super().__init__(
            rule_id="UNI-MNT-002",
            name="assertion-roulette",
            category=SmellCategory.MAINTENANCE,
            severity=SmellSeverity.INFO,
            description="Test contains too many assertions.",
        )
        self.max_assertions = max_assertions

    def check(
        self,
        parsed_module: ParsedModule,
        all_modules: Optional[List[ParsedModule]] = None,
    ) -> List[RuleViolation]:
        violations = []

        for test_func in parsed_module.test_functions:
            assertion_count = len(test_func.assertions)
            if assertion_count > self.max_assertions:
                violations.append(
                    RuleViolation(
                        rule_id=self.rule_id,
                        rule_name=self.name,
                        message=f"Test '{test_func.name}' has {assertion_count} assertions "
                        f"(max: {self.max_assertions}). Consider splitting into multiple tests.",
                        file_path=test_func.file_path,
                        line_number=test_func.line_number,
                        severity=self.severity,
                        category=self.category,
                        suggestion=f"Split test into {assertion_count // self.max_assertions + 1} "
                        f"smaller tests, each verifying one specific behavior.",
                        context={
                            "test_name": test_func.name,
                            "assertion_count": assertion_count,
                        },
                    )
                )

        return violations


class NoAssertionRule(UniversalRule):
    """Detects tests with no assertions.

    Tests without assertions cannot verify correctness and provide
    false confidence.
    """

    def __init__(self):
        super().__init__(
            rule_id="UNI-MNT-003",
            name="no-assertion",
            category=SmellCategory.MAINTENANCE,
            severity=SmellSeverity.ERROR,
            description="Test contains no assertions.",
        )

    def check(
        self,
        parsed_module: ParsedModule,
        all_modules: Optional[List[ParsedModule]] = None,
    ) -> List[RuleViolation]:
        violations = []

        for test_func in parsed_module.test_functions:
            if len(test_func.assertions) == 0 and not test_func.has_mock_verifications:
                violations.append(
                    RuleViolation(
                        rule_id=self.rule_id,
                        rule_name=self.name,
                        message=f"Test '{test_func.name}' contains no assertions.",
                        file_path=test_func.file_path,
                        line_number=test_func.line_number,
                        severity=self.severity,
                        category=self.category,
                        suggestion="Add explicit assertions or mark as a smoke test "
                        "if only checking for exceptions.",
                        context={"test_name": test_func.name},
                    )
                )

        return violations


class NetworkDependencyRule(UniversalRule):
    """Detects network-dependent tests.

    Network-dependent tests are inherently flaky due to external
    dependencies and should be mocked or moved to integration tests.
    """

    # Language-specific network modules/packages
    NETWORK_MODULES: Dict[LanguageType, Set[str]] = {
        LanguageType.PYTHON: {"requests", "urllib", "httpx", "aiohttp", "socket"},
        LanguageType.TYPESCRIPT: {"axios", "fetch", "http", "https", "net"},
        LanguageType.JAVASCRIPT: {"axios", "fetch", "http", "https", "net"},
        LanguageType.GO: {"net/http", "http"},
        LanguageType.CPP: {"curl", "boost::asio"},
        LanguageType.JAVA: {"java.net", "HttpClient", "okhttp"},
        LanguageType.RUST: {"reqwest", "hyper", "ureq"},
        LanguageType.CSHARP: {"HttpClient", "WebClient", "System.Net"},
    }

    def __init__(self):
        super().__init__(
            rule_id="UNI-FLK-003",
            name="network-dependency",
            category=SmellCategory.FLAKINESS,
            severity=SmellSeverity.WARNING,
            description="Network module imported in test file.",
        )

    def check(
        self,
        parsed_module: ParsedModule,
        all_modules: Optional[List[ParsedModule]] = None,
    ) -> List[RuleViolation]:
        violations = []

        if parsed_module.has_network_imports:
            network_modules = self.NETWORK_MODULES.get(parsed_module.language, set())
            imports = set(parsed_module.imports)
            network_imports = imports.intersection(network_modules)

            if network_imports:
                violations.append(
                    RuleViolation(
                        rule_id=self.rule_id,
                        rule_name=self.name,
                        message=f"Network modules imported: {', '.join(network_imports)}. "
                        f"Consider mocking or moving to integration tests.",
                        file_path=parsed_module.file_path,
                        line_number=1,
                        severity=self.severity,
                        category=self.category,
                        suggestion="Mock network calls or move these tests to a separate "
                        "integration test suite.",
                        context={"network_imports": list(network_imports)},
                    )
                )

        return violations


class FixtureScopeMismatchRule(UniversalRule):
    """Detects fixture scope mismatches.

    A fixture with a narrower scope cannot depend on a fixture
    with a broader scope (e.g., function-scoped fixture depending
    on session-scoped fixture is OK, but not vice versa).
    """

    def __init__(self):
        super().__init__(
            rule_id="UNI-FIX-001",
            name="fixture-scope-mismatch",
            category=SmellCategory.FIXTURE,
            severity=SmellSeverity.ERROR,
            description="Fixture scope mismatch detected.",
        )

    def check(
        self,
        parsed_module: ParsedModule,
        all_modules: Optional[List[ParsedModule]] = None,
    ) -> List[RuleViolation]:
        violations = []

        # Build fixture map for cross-file analysis
        fixture_map: Dict[str, TestFixture] = {}
        if all_modules:
            for module in all_modules:
                for fixture in module.fixtures:
                    fixture_map[fixture.name] = fixture
        else:
            for fixture in parsed_module.fixtures:
                fixture_map[fixture.name] = fixture

        # Check each fixture's dependencies
        for fixture in parsed_module.fixtures:
            for dep_name in fixture.dependencies:
                if dep_name not in fixture_map:
                    continue

                dep_fixture = fixture_map[dep_name]

                # Compare scopes using framework-specific comparison
                from test_linter.core.models import FixtureScope

                scope_diff = FixtureScope.compare_scopes(
                    fixture.scope, dep_fixture.scope, parsed_module.framework
                )

                # Error if fixture has broader scope than dependency
                if scope_diff > 0:
                    violations.append(
                        RuleViolation(
                            rule_id=self.rule_id,
                            rule_name=self.name,
                            message=f"Fixture '{fixture.name}' (scope: {fixture.scope}) "
                            f"depends on '{dep_name}' (scope: {dep_fixture.scope}). "
                            f"Broader-scoped fixture cannot depend on narrower-scoped one.",
                            file_path=fixture.file_path,
                            line_number=fixture.line_number,
                            severity=self.severity,
                            category=self.category,
                            suggestion=f"Change '{fixture.name}' scope to '{dep_fixture.scope}' "
                            f"or lower, or change '{dep_name}' scope to '{fixture.scope}' "
                            f"or higher.",
                            context={
                                "fixture_name": fixture.name,
                                "fixture_scope": fixture.scope,
                                "dependency_name": dep_name,
                                "dependency_scope": dep_fixture.scope,
                            },
                        )
                    )

        return violations


def get_universal_rules(max_assertions: int = 3) -> List[UniversalRule]:
    """Get all universal test smell detection rules.

    Args:
        max_assertions: Maximum allowed assertions per test

    Returns:
        List of all universal rules
    """
    return [
        TimeSleepRule(),
        MysteryGuestRule(),
        TestLogicRule(),
        AssertionRouletteRule(max_assertions),
        NoAssertionRule(),
        NetworkDependencyRule(),
        FixtureScopeMismatchRule(),
    ]
