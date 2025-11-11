"""
Configuration management for pytest-deep-analysis.

This module handles loading and parsing configuration from pyproject.toml,
allowing users to customize linter behavior, enable/disable rules, and
set rule-specific options.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

try:
    import tomli as tomllib
except ImportError:
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        tomllib = None  # type: ignore


class Config:
    """Configuration for pytest-deep-analysis linter."""

    def __init__(self):
        """Initialize with default configuration."""
        # Rules that are disabled by default
        self.disabled_rules: Set[str] = set()
        # File patterns to ignore
        self.ignore_patterns: List[str] = []
        # Rule-specific configuration
        self.rule_config: Dict[str, Dict[str, Any]] = {}
        # Whether to check for database commits
        self.check_db_commits: bool = True
        # Whether to check for fixture scope narrowing
        self.check_scope_narrowing: bool = True
        # Whether to check for fixture mutations
        self.check_fixture_mutations: bool = True
        # Whether to check for parametrize issues
        self.check_parametrize: bool = True

    def load_from_pyproject(self, start_path: Optional[str] = None) -> None:
        """Load configuration from pyproject.toml.

        Searches for pyproject.toml starting from start_path and moving up
        the directory tree.

        Args:
            start_path: Directory to start searching from. Defaults to cwd.
        """
        if tomllib is None:
            # No TOML library available, use defaults
            return

        pyproject_path = self._find_pyproject(start_path)
        if not pyproject_path:
            return

        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)
        except Exception:
            # Failed to load, use defaults
            return

        # Extract pytest-deep-analysis configuration
        config = data.get("tool", {}).get("pytest-deep-analysis", {})
        if not config:
            return

        # Load disabled rules
        disabled = config.get("disable", [])
        if isinstance(disabled, list):
            self.disabled_rules.update(disabled)

        # Load ignore patterns
        ignore = config.get("ignore_patterns", [])
        if isinstance(ignore, list):
            self.ignore_patterns.extend(ignore)

        # Load feature flags
        features = config.get("features", {})
        if isinstance(features, dict):
            self.check_db_commits = features.get("database_commits", True)
            self.check_scope_narrowing = features.get("scope_narrowing", True)
            self.check_fixture_mutations = features.get("fixture_mutations", True)
            self.check_parametrize = features.get("parametrize_checks", True)

        # Load rule-specific configuration
        rules = config.get("rules", {})
        if isinstance(rules, dict):
            self.rule_config = rules

    def _find_pyproject(self, start_path: Optional[str] = None) -> Optional[Path]:
        """Find pyproject.toml by walking up the directory tree.

        Args:
            start_path: Directory to start searching from

        Returns:
            Path to pyproject.toml if found, None otherwise
        """
        if start_path is None:
            start_path = os.getcwd()

        current = Path(start_path).resolve()

        # Walk up the directory tree
        while True:
            pyproject = current / "pyproject.toml"
            if pyproject.exists():
                return pyproject

            # Move to parent directory
            parent = current.parent
            if parent == current:
                # Reached root, not found
                return None
            current = parent

    def is_rule_enabled(self, rule_name: str) -> bool:
        """Check if a rule is enabled.

        Args:
            rule_name: The rule symbol (e.g., "pytest-fix-autouse")

        Returns:
            True if the rule is enabled, False otherwise
        """
        return rule_name not in self.disabled_rules

    def should_ignore_file(self, file_path: str) -> bool:
        """Check if a file should be ignored based on patterns.

        Args:
            file_path: Path to the file

        Returns:
            True if the file should be ignored, False otherwise
        """
        from fnmatch import fnmatch

        for pattern in self.ignore_patterns:
            if fnmatch(file_path, pattern):
                return True
        return False

    def get_rule_option(self, rule_name: str, option: str, default: Any = None) -> Any:
        """Get a rule-specific configuration option.

        Args:
            rule_name: The rule symbol
            option: The option name
            default: Default value if option not set

        Returns:
            The option value or default
        """
        return self.rule_config.get(rule_name, {}).get(option, default)


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance.

    Returns:
        The global Config instance
    """
    global _config
    if _config is None:
        _config = Config()
        _config.load_from_pyproject()
    return _config


def reset_config() -> None:
    """Reset the global configuration (mainly for testing)."""
    global _config
    _config = None
