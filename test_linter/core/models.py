"""Core data models for language-agnostic test representation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Set, Optional, Any, Dict


class LanguageType(Enum):
    """Supported programming languages."""
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    GO = "go"
    CPP = "cpp"
    JAVA = "java"
    RUST = "rust"
    CSHARP = "csharp"


class TestFramework(Enum):
    """Supported test frameworks by language."""
    # Python
    PYTEST = "pytest"
    UNITTEST = "unittest"

    # TypeScript/JavaScript
    JEST = "jest"
    MOCHA = "mocha"
    VITEST = "vitest"

    # Go
    GO_TESTING = "testing"
    TESTIFY = "testify"

    # C++
    GOOGLETEST = "googletest"
    CATCH2 = "catch2"
    BOOST_TEST = "boost_test"

    # Java
    JUNIT4 = "junit4"
    JUNIT5 = "junit5"
    TESTNG = "testng"

    # Rust
    RUST_BUILTIN = "rust_builtin"
    PROPTEST = "proptest"

    # C#
    NUNIT = "nunit"
    XUNIT = "xunit"
    MSTEST = "mstest"


class SmellCategory(Enum):
    """Categories of test smells."""
    FLAKINESS = "flakiness"  # Environment-dependent, non-deterministic tests
    MAINTENANCE = "maintenance"  # Hard to read/maintain tests
    FIXTURE = "fixture"  # Setup/teardown issues
    ENHANCEMENT = "enhancement"  # Opportunities for improvement


class SmellSeverity(Enum):
    """Severity levels for test smells."""
    ERROR = "error"  # Critical issues that must be fixed
    WARNING = "warning"  # Important issues that should be addressed
    INFO = "info"  # Suggestions for improvement


@dataclass
class TestAssertion:
    """Represents a single assertion in a test."""
    line_number: int
    assertion_type: str  # e.g., "equality", "exception", "mock_verify", "boolean"
    expression: str  # The assertion expression as string
    actual_value: Optional[str] = None  # What's being tested
    expected_value: Optional[str] = None  # What's expected
    raw_node: Any = None  # Language-specific AST node


@dataclass
class TestFixture:
    """Represents a test fixture/setup function (language-agnostic)."""
    name: str
    scope: str  # Normalized scope: "function", "class", "module", "session"
    file_path: str
    line_number: int
    dependencies: List[str] = field(default_factory=list)  # Other fixtures it depends on
    is_auto: bool = False  # Runs automatically without being called
    teardown_method: Optional[str] = None  # Associated cleanup function
    used_by: Set[str] = field(default_factory=set)  # Test IDs that use this fixture
    raw_node: Any = None  # Language-specific AST node

    # Language-specific metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestFunction:
    """Represents a test function (language-agnostic)."""
    name: str
    file_path: str
    line_number: int
    framework: TestFramework

    # Test structure
    assertions: List[TestAssertion] = field(default_factory=list)
    setup_dependencies: List[str] = field(default_factory=list)  # Fixtures/setups used
    has_test_logic: bool = False  # Contains if/for/while logic

    # Additional metadata
    is_parametrized: bool = False
    parameter_count: int = 0
    has_async: bool = False
    docstring: Optional[str] = None
    raw_node: Any = None  # Language-specific AST node

    # Execution context
    uses_file_io: bool = False
    uses_network: bool = False
    uses_time_sleep: bool = False
    uses_cwd: bool = False

    # Mock/stub tracking
    has_mock_verifications: bool = False
    has_state_assertions: bool = False

    # Language-specific metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestSmell:
    """Represents a detected test smell/anti-pattern."""
    rule_id: str  # e.g., "W9001", "TS-FLK-001"
    rule_name: str  # e.g., "pytest-flk-time-sleep", "time-sleep"
    category: SmellCategory
    severity: SmellSeverity
    message: str
    file_path: str
    line_number: int
    column: Optional[int] = None

    # Context
    test_name: Optional[str] = None
    fixture_name: Optional[str] = None

    # Suggestion/fix
    suggestion: Optional[str] = None
    auto_fixable: bool = False

    # Additional context
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FixtureScope:
    """Defines scope hierarchy for different test frameworks."""
    name: str
    level: int  # Higher number = broader scope

    @classmethod
    def get_scope_mapping(cls, framework: TestFramework) -> Dict[str, int]:
        """Get scope hierarchy mapping for a specific framework.

        Returns a dict mapping scope names to their hierarchy level.
        Higher numbers indicate broader scopes.
        """
        mappings = {
            # Python pytest
            TestFramework.PYTEST: {
                "function": 1,
                "class": 2,
                "module": 3,
                "package": 4,
                "session": 5,
            },
            # Python unittest
            TestFramework.UNITTEST: {
                "method": 1,
                "class": 2,
                "module": 3,
            },
            # JavaScript/TypeScript Jest/Mocha
            TestFramework.JEST: {
                "test": 1,
                "describe": 2,
                "file": 3,
                "global": 4,
            },
            TestFramework.MOCHA: {
                "test": 1,
                "describe": 2,
                "file": 3,
                "global": 4,
            },
            TestFramework.VITEST: {
                "test": 1,
                "describe": 2,
                "file": 3,
                "global": 4,
            },
            # Go
            TestFramework.GO_TESTING: {
                "subtest": 1,
                "test": 2,
                "package": 3,
                "main": 4,
            },
            TestFramework.TESTIFY: {
                "test": 1,
                "suite": 2,
                "package": 3,
            },
            # C++
            TestFramework.GOOGLETEST: {
                "test": 1,
                "fixture": 2,
                "suite": 3,
                "global": 4,
            },
            TestFramework.CATCH2: {
                "section": 1,
                "test_case": 2,
                "global": 3,
            },
            # Java
            TestFramework.JUNIT5: {
                "method": 1,
                "class": 2,
                "global": 3,
            },
            TestFramework.JUNIT4: {
                "method": 1,
                "class": 2,
            },
            TestFramework.TESTNG: {
                "method": 1,
                "class": 2,
                "suite": 3,
            },
            # Rust
            TestFramework.RUST_BUILTIN: {
                "test": 1,
                "module": 2,
            },
            # C#
            TestFramework.NUNIT: {
                "test": 1,
                "fixture": 2,
                "global": 3,
            },
            TestFramework.XUNIT: {
                "fact": 1,
                "class": 2,
                "collection": 3,
            },
            TestFramework.MSTEST: {
                "method": 1,
                "class": 2,
                "assembly": 3,
            },
        }
        return mappings.get(framework, {})

    @classmethod
    def normalize_scope(cls, scope: str, framework: TestFramework) -> str:
        """Normalize framework-specific scope to generic scope.

        Maps various framework-specific scope names to a common set:
        function, class, module, session
        """
        mapping = {
            # Pytest -> generic
            "function": "function",
            "class": "class",
            "module": "module",
            "package": "module",
            "session": "session",

            # Jest/Mocha -> generic
            "test": "function",
            "describe": "class",
            "file": "module",
            "global": "session",

            # Go -> generic
            "subtest": "function",
            "test": "function",
            "package": "module",
            "main": "session",

            # C++ -> generic
            "fixture": "class",
            "suite": "class",
            "test_case": "function",
            "section": "function",

            # Java -> generic
            "method": "function",

            # C# -> generic
            "fact": "function",
            "collection": "module",
            "assembly": "session",
        }
        return mapping.get(scope, scope)

    @classmethod
    def compare_scopes(cls, scope1: str, scope2: str, framework: TestFramework) -> int:
        """Compare two scopes within a framework.

        Returns:
            < 0 if scope1 is narrower than scope2
            0 if equal
            > 0 if scope1 is broader than scope2
        """
        mappings = cls.get_scope_mapping(framework)
        level1 = mappings.get(scope1, 0)
        level2 = mappings.get(scope2, 0)
        return level1 - level2
