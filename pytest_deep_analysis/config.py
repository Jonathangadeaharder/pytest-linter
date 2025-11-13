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
            if "magic-assert-allowlist" in tool_config:
                allowlist = tool_config["magic-assert-allowlist"]
                if isinstance(allowlist, list):
                    # Add configured values to the default allowlist
                    self.magic_assert_allowlist.update(allowlist)

        except FileNotFoundError:
            # Config file not found, use defaults
            logging.debug(f"Config file not found: {self.config_path}")
        except (KeyError, ValueError, TypeError) as e:
            # Invalid config structure or values, use defaults
            logging.warning(f"Error parsing config from {self.config_path}: {e}")
        except Exception as e:
            # Unexpected error, use defaults but log it
            logging.error(f"Unexpected error loading config from {self.config_path}: {e}")

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
