"""
Message definitions for pytest-deep-analysis linter rules.

This module defines all linter messages following the taxonomy outlined in the design:
- Category 1: Test Body Smells (PYTEST-FLK-*, PYTEST-MNT-*)
- Category 2: Fixture Definition Smells (PYTEST-FIX-001)
- Category 3: Fixture Interaction Smells (PYTEST-FIX-002+)
"""

# Pylint message format: (message-id, message-symbol, message-text, help-text)
MESSAGES = {
    # =========================================================================
    # Category 1: Test Body Smells (ast-based)
    # =========================================================================
    # PYTEST-FLK: Flakiness checks
    "W9001": (
        "time.sleep() found in test function. Use explicit waits instead.",
        "pytest-flk-time-sleep",
        "Hard-coded waits with time.sleep() create slow, unreliable, and flaky tests. "
        "Instead, use explicit polling or wait conditions that check for the actual "
        "condition you're waiting for.",
    ),
    "W9002": (
        "open() found in test function. Use the 'tmp_path' fixture instead.",
        "pytest-flk-io-open",
        "Direct filesystem I/O with open() makes tests stateful and environment-dependent, "
        "leading to flakiness. Use pytest's built-in 'tmp_path' fixture, which provides "
        "a clean, isolated temporary directory for each test.",
    ),
    "W9003": (
        "Network module (e.g., 'requests', 'socket') imported in test file.",
        "pytest-flk-network-import",
        "Network-dependent tests are a form of integration test and are inherently flaky "
        "due to external dependencies. Consider mocking network calls or moving these "
        "tests to a separate integration test suite.",
    ),
    "W9004": (
        "CWD-sensitive function (e.g., 'os.getcwd()') found in test.",
        "pytest-flk-cwd-dependency",
        "Tests that rely on the current working directory are brittle and fail when run "
        "from different directories. Use absolute paths or the 'tmp_path' fixture instead.",
    ),
    "W9005": (
        "Mystery Guest: Test uses file I/O without a resource fixture (tmp_path, tmpdir).",
        "pytest-flk-mystery-guest",
        "This test calls open() or file operations without depending on pytest's resource "
        "fixtures (tmp_path, tmp_path_factory, tmpdir). This is the 'Mystery Guest' smell: "
        "an external resource of unclear origin. Tests should use tmp_path fixture to ensure "
        "isolation, cleanup, and clarity about what files are being used.",
    ),
    # PYTEST-MNT: Maintenance checks
    "W9011": (
        "Conditional logic (if/for/while) found in test function.",
        "pytest-mnt-test-logic",
        "Tests should follow the simple Arrange-Act-Assert pattern. The presence of "
        "conditional logic or loops indicates the test is either testing multiple code "
        "paths at once or has become a 'workflow test' with business logic embedded. "
        "This increases cognitive load and maintenance burden.",
    ),
    "W9012": (
        "Magic number or string used in assert statement.",
        "pytest-mnt-magic-assert",
        "Magic numbers and strings (hard-coded, unexplained values) make tests unreadable "
        "and brittle. Extract these values to well-named constants that explain their meaning.",
    ),
    "W9013": (
        "Suboptimal assert: use direct 'assert x == y' instead of 'assertTrue(x == y)'.",
        "pytest-mnt-suboptimal-assert",
        "Pytest's powerful introspection relies on direct assert statements. Using "
        "'assert x == y' produces rich diffs, while 'assertTrue(x == y)' or similar "
        "will only report 'assert False is True' without helpful context.",
    ),
    "E9014": (
        "Test function '%s' contains no assertions.",
        "pytest-test-no-assert",
        "Tests without assertions (H-3: Assertion-Free) cannot verify correctness and "
        "provide false confidence. Either add explicit assertions or mark as a smoke test "
        "if only checking for exceptions. This is a CRITICAL indicator of low-value tests.",
    ),
    "W9015": (
        "Test '%s' only verifies mock interactions without state assertions.",
        "pytest-mock-only-verify",
        "Tests that only verify mock calls (H-9: Interaction-Only) without checking state "
        "changes or return values provide weak guarantees. Interaction-based testing is "
        "brittle and tightly coupled to implementation details. Consider adding state assertions.",
    ),
    "W9016": (
        "Test '%s' lacks BDD traceability (missing @pytest.mark.scenario or Gherkin reference).",
        "pytest-bdd-missing-scenario",
        "Behavior-Driven Development requires explicit traceability from tests to scenarios. "
        "Consider using pytest-bdd with @pytest.mark.scenario or documenting the Gherkin "
        "feature file reference in the test docstring to maintain semantic alignment.",
    ),
    "W9017": (
        "Test '%s' uses @pytest.mark.parametrize but could benefit from property-based testing.",
        "pytest-no-property-test-hint",
        "Property-Based Testing (PBT) with Hypothesis generates diverse test cases and uncovers "
        "edge cases better than manual parametrization. For tests with >3 parameter sets or "
        "numeric/string inputs, consider using @hypothesis.given() to define invariants.",
    ),
    "W9018": (
        "Fixture '%s' has complex logic but lacks formal contracts (icontract decorators).",
        "pytest-no-contract-hint",
        "Design by Contract (DbC) makes preconditions and postconditions explicit and machine-verifiable. "
        "For fixtures with complex setup/teardown logic, consider using @icontract.require() and "
        "@icontract.ensure() decorators to formalize contracts instead of relying on informal docstrings.",
    ),
    # =========================================================================
    # Category 2: Fixture Definition Smells (ast-based)
    # =========================================================================
    "W9021": (
        "@pytest.fixture(autouse=True) detected. Avoid 'magic' fixtures.",
        "pytest-fix-autouse",
        "The autouse=True parameter is 'too much magic' and creates a 'mess' by hiding "
        "test dependencies. It breaks the explicit-is-better-than-implicit principle, "
        "making it impossible to know what setup a test is running without cross-referencing "
        "all conftest.py files. Make fixture dependencies explicit in test signatures.",
    ),
    # =========================================================================
    # Category 3: Fixture Interaction Smells (astroid-based)
    # =========================================================================
    "E9031": (
        "Session-scoped fixture '%s' mutates a global variable.",
        "pytest-fix-session-mutation",
        "Fixtures with session scope that mutate shared state can 'bleed' between tests, "
        "causing flakiness. Session-scoped fixtures should be immutable or reset their "
        "state after each test.",
    ),
    "E9032": (
        "Invalid scope dependency: Fixture '%s' (scope='%s') cannot depend on "
        "lower-scope fixture '%s' (scope='%s').",
        "pytest-fix-invalid-scope",
        "A fixture's scope must be less than or equal to all its dependencies. For example, "
        "a session-scoped fixture (created once) cannot depend on a function-scoped "
        "fixture (created for every test), as this is a logical impossibility.",
    ),
    "W9033": (
        "Shadowed fixture: Fixture '%s' is defined in '%s' and '%s'.",
        "pytest-fix-shadowed",
        "Pytest's conftest.py resolution order allows fixtures in subdirectories to "
        "'shadow' (override) fixtures from parent directories. While powerful, this is "
        "a massive source of confusion and 'it works on my machine' bugs.",
    ),
    "W9034": (
        "Unused fixture: Fixture '%s' is defined but not used by any test or fixture.",
        "pytest-fix-unused",
        "Dead code in test suites adds to the maintenance burden. Remove unused fixtures "
        "or document why they are being kept.",
    ),
    "E9035": (
        "Stateful session fixture: Session-scoped fixture '%s' returns a mutable object "
        "that may be mutated by function-scoped tests.",
        "pytest-fix-stateful-session",
        "A session-scoped, mutable object (like a shared database connection) that is "
        "altered by tests creates stateful dependencies and flakiness. Either use a "
        "narrower scope or ensure the fixture returns immutable objects.",
    ),
    "W9019": (
        "Test contains %d assertions without explanation (assertion roulette)",
        "pytest-mnt-assertion-roulette",
        "A test with many assertions (>3) without explanatory messages makes failures "
        "hard to debug. Consider splitting into multiple focused tests, adding assertion "
        "messages (assert x == y, 'expected y to equal x'), or using pytest.mark.parametrize "
        "for data-driven testing.",
    ),
    "W9020": (
        "Test uses raw try/except instead of pytest.raises()",
        "pytest-mnt-raw-exception-handling",
        "Using try/except in tests obscures intent and provides poor failure messages. "
        "Use 'with pytest.raises(ExpectedException):' to explicitly declare expected "
        "exceptions and get better test failure reporting.",
    ),
    # =========================================================================
    # New Enhancement Rules
    # =========================================================================
    "W9022": (
        "Fixture '%s' performs database commits without explicit cleanup/rollback.",
        "pytest-fix-db-commit-no-cleanup",
        "Fixtures that commit to a database without cleanup can cause test pollution "
        "and inter-test dependencies. Use transactions with rollback, or ensure explicit "
        "cleanup in a yield fixture's teardown section. Database state should be isolated "
        "per test to prevent flakiness.",
    ),
    "W9023": (
        "Test '%s' modifies fixture return value in-place (mutation detected).",
        "pytest-test-fixture-mutation",
        "Tests that mutate fixture return values in-place can cause state bleeding between "
        "tests when fixtures are cached at module/session scope. Either copy the fixture "
        "value before mutation, use function scope for the fixture, or make the fixture "
        "return a fresh instance each time.",
    ),
    "W9024": (
        "Fixture '%s' with scope='%s' is only used by tests in a single %s. Consider narrowing scope to '%s'.",
        "pytest-fix-overly-broad-scope",
        "Fixtures with broader scope than necessary waste resources and increase risk of "
        "state bleeding. If a session-scoped fixture is only used in one module, make it "
        "module-scoped. If a module-scoped fixture is only used in one test, make it "
        "function-scoped. Narrow scopes improve test isolation.",
    ),
    "W9025": (
        "Empty parametrize: @pytest.mark.parametrize with no parameters or single value.",
        "pytest-parametrize-empty",
        "Using @pytest.mark.parametrize with an empty list or single value adds complexity "
        "without benefit. Remove the decorator or add meaningful parameter variations.",
    ),
    "W9026": (
        "Duplicate parametrize values detected in '%s'.",
        "pytest-parametrize-duplicate",
        "Duplicate values in @pytest.mark.parametrize waste test execution time and provide "
        "no additional coverage. Remove duplicate entries to keep tests efficient.",
    ),
    "W9027": (
        "Nested parametrize decorators create cartesian product (%d combinations). Consider using pytest.param with indirect=True.",
        "pytest-parametrize-explosion",
        "Multiple @pytest.mark.parametrize decorators create a cartesian product of test cases. "
        "With many parameters, this leads to test explosion and slow execution. Consider "
        "using pytest.param with indirect=True or hypothesis for property-based testing.",
    ),
    "W9028": (
        "Parametrize without test variation: all parameter sets produce same assertion.",
        "pytest-parametrize-no-variation",
        "Parametrize decorators should test different behaviors or edge cases. If all "
        "parameter values lead to the same assertion, the parametrization adds no value. "
        "Either add assertions that vary by parameter or remove the decorator.",
    ),
    "W9029": (
        "Test '%s' may have issues with pytest-xdist parallel execution (shared state detected).",
        "pytest-xdist-shared-state",
        "Tests that access shared state (global variables, class attributes, files outside "
        "tmp_path) may fail or cause race conditions when run in parallel with pytest-xdist. "
        "Ensure proper isolation using fixtures and temporary directories.",
    ),
    "W9030": (
        "Fixture '%s' uses file I/O without tmp_path, which may conflict in parallel execution.",
        "pytest-xdist-fixture-io",
        "Fixtures that perform file I/O in fixed locations (not tmp_path) will conflict when "
        "tests run in parallel with pytest-xdist. Use tmp_path_factory for session-scoped "
        "fixtures or tmp_path for function-scoped fixtures to ensure isolation.",
    ),
}
