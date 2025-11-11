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
}
