"""
Configuration handling for pytest-deep-analysis.

This module provides functionality to read configuration from pyproject.toml
and apply it to linter rules.
"""

from typing import Any, Set, Optional
import sys
import logging
from pathlib import Path

# Use tomllib for Python 3.11+, tomli for earlier versions
if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore


class PytestDeepAnalysisConfig:
    """Configuration for pytest-deep-analysis linter."""

    def __init__(self, config_file: Optional[str] = None):
        """Initialize configuration.

        Args:
            config_file: Path to pyproject.toml file. If None, searches upward.
        """
        # Note: 0 and False are equal in sets, as are 1 and True. We include both
        # for clarity, but the set will automatically deduplicate them.
        self.magic_assert_allowlist: Set[Any] = {-1, 0, 1, None, ""}
        self.config_path: Optional[Path] = None

        # Rule configuration
        self.disabled_rules: Set[str] = set()

        # Thresholds for rules
        self.max_assertions = 3  # For W9019 assertion roulette
        self.max_parametrize_combinations = 20  # For W9027 parametrize explosion

        # Database operations to consider for commit detection
        self.db_commit_methods: Set[str] = {
            "commit",
            "save",
            "create",
            "update_or_create",
            "bulk_create",
            "bulk_update",
        }
        self.db_rollback_methods: Set[str] = {"rollback"}

        if config_file:
            self.config_path = Path(config_file)
        else:
            self.config_path = self._find_pyproject_toml()

        if self.config_path and self.config_path.exists():
            self._load_config()

    def _find_pyproject_toml(self) -> Optional[Path]:
        """Find pyproject.toml by searching upward from current directory.

        Returns:
            Path to pyproject.toml if found, None otherwise
        """
        current = Path.cwd()
        while True:
            pyproject = current / "pyproject.toml"
            if pyproject.exists():
                return pyproject

            # Stop at filesystem root
            if current.parent == current:
                return None
            current = current.parent

    def _load_list_config(
        self, tool_config: dict, key: str, target_set: Set[Any]
    ) -> None:
        """Load a list configuration value into a target set.

        Args:
            tool_config: Configuration dictionary
            key: Configuration key
            target_set: Target set to update
        """
        if key in tool_config:
            value = tool_config[key]
            if isinstance(value, list):
                target_set.update(value)

    def _load_int_threshold(self, tool_config: dict, key: str) -> Optional[int]:
        """Load an integer threshold configuration value.

        Args:
            tool_config: Configuration dictionary
            key: Configuration key

        Returns:
            Integer value if valid, None otherwise
        """
        if key in tool_config:
            value = tool_config[key]
            if isinstance(value, int) and value > 0:
                return value
        return None

    def _load_config(self) -> None:
        """Load configuration from pyproject.toml."""
        if not self.config_path or not self.config_path.exists():
            return

        if tomllib is None:
            # tomli not installed, use defaults
            return

        try:
            with open(self.config_path, "rb") as f:
                data = tomllib.load(f)

            # Look for [tool.pytest-deep-analysis] section
            tool_config = data.get("tool", {}).get("pytest-deep-analysis", {})

            # Load magic assert allowlist
            self._load_list_config(
                tool_config, "magic-assert-allowlist", self.magic_assert_allowlist
            )

            # Load disabled rules
            self._load_list_config(tool_config, "disable-rules", self.disabled_rules)

            # Load thresholds
            max_assertions = self._load_int_threshold(tool_config, "max-assertions")
            if max_assertions is not None:
                self.max_assertions = max_assertions

            max_combos = self._load_int_threshold(
                tool_config, "max-parametrize-combinations"
            )
            if max_combos is not None:
                self.max_parametrize_combinations = max_combos

            # Load database method lists
            if "db-commit-methods" in tool_config:
                commit_methods = tool_config["db-commit-methods"]
                if isinstance(commit_methods, list):
                    self.db_commit_methods = set(commit_methods)

            if "db-rollback-methods" in tool_config:
                rollback_methods = tool_config["db-rollback-methods"]
                if isinstance(rollback_methods, list):
                    self.db_rollback_methods = set(rollback_methods)

        except FileNotFoundError:
            # Config file not found, use defaults
            logging.debug(f"Config file not found: {self.config_path}")
        except (KeyError, ValueError, TypeError) as e:
            # Invalid config structure or values, use defaults
            logging.warning(f"Error parsing config from {self.config_path}: {e}")
        except Exception as e:
            # Unexpected error, use defaults but log it
            logging.error(
                f"Unexpected error loading config from {self.config_path}: {e}"
            )

    def is_magic_constant(self, value: Any) -> bool:
        """Check if a constant value is 'magic' considering configuration.

        Args:
            value: The constant value to check

        Returns:
            True if the value is a magic constant
        """
        if value in self.magic_assert_allowlist:
            return False

        # Empty collections are not magic
        if isinstance(value, (list, dict, tuple, set)) and not value:
            return False

        # Numeric or string constants are potentially magic
        if isinstance(value, (int, float, str)):
            return True

        return False

    def is_rule_disabled(self, rule_symbol: str) -> bool:
        """Check if a rule is disabled in configuration.

        Args:
            rule_symbol: The rule symbol (e.g., 'pytest-fix-db-commit-no-cleanup')

        Returns:
            True if the rule is disabled
        """
        return rule_symbol in self.disabled_rules


# Global config instance (will be initialized by the checker)
_config: Optional[PytestDeepAnalysisConfig] = None


def get_config() -> PytestDeepAnalysisConfig:
    """Get the global configuration instance.

    Returns:
        The global configuration instance
    """
    global _config
    if _config is None:
        _config = PytestDeepAnalysisConfig()
    return _config


def set_config(config: PytestDeepAnalysisConfig) -> None:
    """Set the global configuration instance.

    Args:
        config: The configuration instance to set
    """
    global _config
    _config = config
