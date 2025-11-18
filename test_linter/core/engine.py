"""Main linter engine for orchestrating multi-language test analysis."""

from pathlib import Path
from typing import List, Optional, Dict
from concurrent.futures import ProcessPoolExecutor, as_completed

from test_linter.core.adapters import AdapterRegistry, ParsedModule
from test_linter.core.rules import RuleRegistry, RuleViolation
from test_linter.core.config import TestLinterConfig
from test_linter.core.models import LanguageType


class LinterEngine:
    """Main engine for running test linting across multiple languages."""

    def __init__(
        self,
        config: TestLinterConfig,
        adapter_registry: AdapterRegistry,
        rule_registry: RuleRegistry,
    ):
        self.config = config
        self.adapter_registry = adapter_registry
        self.rule_registry = rule_registry

    def lint_directory(
        self,
        directory: Path,
        recursive: bool = True,
        file_patterns: Optional[List[str]] = None,
    ) -> List[RuleViolation]:
        """Lint all test files in a directory.

        Args:
            directory: Directory to lint
            recursive: Whether to search recursively
            file_patterns: Optional file patterns to match (e.g., ["test_*.py"])

        Returns:
            List of all violations found
        """
        # Find all test files
        test_files = self._find_test_files(directory, recursive, file_patterns)

        # Parse all files
        parsed_modules = []
        for file_path in test_files:
            try:
                parsed = self._parse_file(file_path)
                if parsed:
                    parsed_modules.append(parsed)
            except Exception as e:
                print(f"Error parsing {file_path}: {e}")

        # Run checks
        violations = self._run_checks(parsed_modules)

        return violations

    def lint_files(self, file_paths: List[Path]) -> List[RuleViolation]:
        """Lint specific files.

        Args:
            file_paths: List of files to lint

        Returns:
            List of all violations found
        """
        parsed_modules = []
        for file_path in file_paths:
            try:
                parsed = self._parse_file(file_path)
                if parsed:
                    parsed_modules.append(parsed)
            except Exception as e:
                print(f"Error parsing {file_path}: {e}")

        return self._run_checks(parsed_modules)

    def _find_test_files(
        self,
        directory: Path,
        recursive: bool,
        file_patterns: Optional[List[str]],
    ) -> List[Path]:
        """Find test files in directory."""
        test_files = []

        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        for file_path in directory.glob(pattern):
            if not file_path.is_file():
                continue

            # Check if file can be handled by any adapter
            adapter = self.adapter_registry.get_adapter_for_file(file_path)
            if adapter:
                # Check if it's a test file
                framework = adapter.detect_framework(file_path)
                if framework:
                    test_files.append(file_path)

        return test_files

    def _parse_file(self, file_path: Path) -> Optional[ParsedModule]:
        """Parse a single file."""
        # Get appropriate adapter
        adapter = self.adapter_registry.get_adapter_for_file(file_path)
        if not adapter:
            return None

        # Check if framework is detected
        framework = adapter.detect_framework(file_path)
        if not framework:
            return None

        # Parse file
        try:
            parsed = adapter.parse_file(file_path)
            return parsed
        except Exception as e:
            raise Exception(f"Failed to parse {file_path}: {e}")

    def _run_checks(self, parsed_modules: List[ParsedModule]) -> List[RuleViolation]:
        """Run checks on all parsed modules."""
        violations = []

        if self.config.parallel_processing and len(parsed_modules) > 1:
            # Parallel processing
            violations = self._run_checks_parallel(parsed_modules)
        else:
            # Sequential processing
            for parsed_module in parsed_modules:
                module_violations = self.rule_registry.run_checks(
                    parsed_module, parsed_modules
                )
                violations.extend(module_violations)

        # Filter violations by config
        violations = self._filter_violations(violations)

        return violations

    def _run_checks_parallel(
        self, parsed_modules: List[ParsedModule]
    ) -> List[RuleViolation]:
        """Run checks in parallel using process pool."""
        violations = []

        # Note: This is a simplified version. In practice, we'd need to
        # serialize the rule registry and adapters for multiprocessing
        for parsed_module in parsed_modules:
            module_violations = self.rule_registry.run_checks(
                parsed_module, parsed_modules
            )
            violations.extend(module_violations)

        return violations

    def _filter_violations(
        self, violations: List[RuleViolation]
    ) -> List[RuleViolation]:
        """Filter violations based on configuration."""
        filtered = []

        for violation in violations:
            # Check if rule is disabled
            if violation.rule_id in self.config.disabled_rules:
                continue

            # Apply severity overrides
            severity_override = self.config.get_rule_severity(violation.rule_id)
            if severity_override:
                violation.severity = severity_override

            filtered.append(violation)

        return filtered


def create_default_engine(config: Optional[TestLinterConfig] = None) -> LinterEngine:
    """Create a linter engine with default configuration.

    Args:
        config: Optional configuration (uses default if None)

    Returns:
        Configured LinterEngine
    """
    from test_linter.core.config import get_default_config
    from test_linter.core.smells import get_universal_rules
    from test_linter.languages.python import PythonAdapter
    from test_linter.languages.typescript import TypeScriptAdapter
    from test_linter.languages.go import GoAdapter
    from test_linter.core.models import LanguageType

    if config is None:
        config = get_default_config()

    # Create adapter registry
    adapter_registry = AdapterRegistry()

    # Register Python adapter
    adapter_registry.register(PythonAdapter())

    # Register TypeScript/JavaScript adapters
    adapter_registry.register(TypeScriptAdapter(LanguageType.TYPESCRIPT))
    adapter_registry.register(TypeScriptAdapter(LanguageType.JAVASCRIPT))

    # Register Go adapter
    adapter_registry.register(GoAdapter())

    # TODO: Register other language adapters as they're implemented
    # adapter_registry.register(CppAdapter())
    # adapter_registry.register(JavaAdapter())
    # etc.

    # Create rule registry
    rule_registry = RuleRegistry()

    # Register universal rules
    universal_rules = get_universal_rules(max_assertions=config.max_assertions)
    rule_registry.register_many(universal_rules)

    # TODO: Register language-specific rules
    # python_rules = get_python_specific_rules()
    # rule_registry.register_many(python_rules)

    return LinterEngine(config, adapter_registry, rule_registry)
