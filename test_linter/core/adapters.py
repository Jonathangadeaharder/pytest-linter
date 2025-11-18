"""Language adapter interface for parsing and analyzing test code."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

from test_linter.core.models import (
    TestFunction,
    TestFixture,
    LanguageType,
    TestFramework,
)


@dataclass
class ParsedModule:
    """Represents a parsed test file/module."""
    file_path: str
    language: LanguageType
    framework: TestFramework

    # Extracted elements
    test_functions: List[TestFunction] = field(default_factory=list)
    fixtures: List[TestFixture] = field(default_factory=list)

    # Module-level metadata
    imports: List[str] = field(default_factory=list)
    has_network_imports: bool = False

    # Raw AST (language-specific)
    raw_ast: Any = None

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class LanguageAdapter(ABC):
    """Abstract base class for language-specific test code analysis.

    Each language adapter is responsible for:
    1. Parsing test files into an AST
    2. Detecting test framework(s) used
    3. Extracting test functions and fixtures
    4. Providing language-specific AST navigation utilities
    """

    def __init__(self, language: LanguageType):
        self.language = language

    @abstractmethod
    def can_handle_file(self, file_path: Path) -> bool:
        """Check if this adapter can handle the given file.

        Args:
            file_path: Path to the file to check

        Returns:
            True if this adapter can parse the file
        """
        pass

    @abstractmethod
    def detect_framework(self, file_path: Path) -> Optional[TestFramework]:
        """Detect which test framework is used in the file.

        Args:
            file_path: Path to the test file

        Returns:
            Detected test framework or None if not a test file
        """
        pass

    @abstractmethod
    def parse_file(self, file_path: Path) -> ParsedModule:
        """Parse a test file and extract all relevant information.

        Args:
            file_path: Path to the test file

        Returns:
            ParsedModule containing extracted test elements

        Raises:
            ParseError: If the file cannot be parsed
        """
        pass

    @abstractmethod
    def extract_test_functions(self, parsed_module: ParsedModule) -> List[TestFunction]:
        """Extract all test functions from a parsed module.

        Args:
            parsed_module: The parsed module

        Returns:
            List of TestFunction objects
        """
        pass

    @abstractmethod
    def extract_fixtures(self, parsed_module: ParsedModule) -> List[TestFixture]:
        """Extract all fixtures/setup functions from a parsed module.

        Args:
            parsed_module: The parsed module

        Returns:
            List of TestFixture objects
        """
        pass

    @abstractmethod
    def get_call_name(self, node: Any) -> Optional[str]:
        """Get the qualified name of a function call from an AST node.

        Args:
            node: Language-specific AST call node

        Returns:
            Qualified name (e.g., "time.sleep", "setTimeout") or None
        """
        pass

    @abstractmethod
    def is_assertion(self, node: Any) -> bool:
        """Check if an AST node represents an assertion.

        Args:
            node: Language-specific AST node

        Returns:
            True if the node is an assertion
        """
        pass

    @abstractmethod
    def is_conditional(self, node: Any) -> bool:
        """Check if an AST node represents conditional logic (if/for/while).

        Args:
            node: Language-specific AST node

        Returns:
            True if the node is conditional logic
        """
        pass

    @abstractmethod
    def get_file_imports(self, parsed_module: ParsedModule) -> List[str]:
        """Get all imports from a parsed module.

        Args:
            parsed_module: The parsed module

        Returns:
            List of import names/modules
        """
        pass

    def supports_async(self) -> bool:
        """Check if this language/framework supports async tests.

        Returns:
            True if async tests are supported
        """
        return False

    def get_supported_frameworks(self) -> List[TestFramework]:
        """Get list of test frameworks supported by this adapter.

        Returns:
            List of supported TestFramework enums
        """
        return []


class ParseError(Exception):
    """Raised when a file cannot be parsed."""
    pass


class AdapterRegistry:
    """Registry for managing language adapters."""

    def __init__(self):
        self._adapters: Dict[LanguageType, LanguageAdapter] = {}

    def register(self, adapter: LanguageAdapter) -> None:
        """Register a language adapter.

        Args:
            adapter: The adapter to register
        """
        self._adapters[adapter.language] = adapter

    def get_adapter(self, language: LanguageType) -> Optional[LanguageAdapter]:
        """Get adapter for a specific language.

        Args:
            language: The language type

        Returns:
            The adapter or None if not registered
        """
        return self._adapters.get(language)

    def detect_language(self, file_path: Path) -> Optional[LanguageType]:
        """Detect language from file extension.

        Args:
            file_path: Path to the file

        Returns:
            Detected language or None
        """
        extension_map = {
            ".py": LanguageType.PYTHON,
            ".ts": LanguageType.TYPESCRIPT,
            ".tsx": LanguageType.TYPESCRIPT,
            ".js": LanguageType.JAVASCRIPT,
            ".jsx": LanguageType.JAVASCRIPT,
            ".go": LanguageType.GO,
            ".cpp": LanguageType.CPP,
            ".cc": LanguageType.CPP,
            ".cxx": LanguageType.CPP,
            ".hpp": LanguageType.CPP,
            ".h": LanguageType.CPP,
            ".java": LanguageType.JAVA,
            ".rs": LanguageType.RUST,
            ".cs": LanguageType.CSHARP,
        }
        suffix = file_path.suffix.lower()
        return extension_map.get(suffix)

    def get_adapter_for_file(self, file_path: Path) -> Optional[LanguageAdapter]:
        """Get the appropriate adapter for a file.

        Args:
            file_path: Path to the file

        Returns:
            The adapter or None if no suitable adapter found
        """
        for adapter in self._adapters.values():
            if adapter.can_handle_file(file_path):
                return adapter
        return None

    def get_all_adapters(self) -> List[LanguageAdapter]:
        """Get all registered adapters.

        Returns:
            List of all adapters
        """
        return list(self._adapters.values())
