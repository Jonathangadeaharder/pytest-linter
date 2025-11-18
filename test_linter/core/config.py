"""Configuration system for test-linter supporting multiple languages."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore

from test_linter.core.models import LanguageType, SmellSeverity


@dataclass
class LanguageConfig:
    """Configuration for a specific language."""
    enabled: bool = True
    framework: Optional[str] = None
    disabled_rules: Set[str] = field(default_factory=set)
    max_assertions: int = 3
    max_parametrize_combinations: int = 20

    # Language-specific settings
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleConfig:
    """Configuration for individual rules."""
    severity: Optional[SmellSeverity] = None
    enabled: bool = True
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestLinterConfig:
    """Main configuration for test-linter."""

    # General settings
    languages: List[LanguageType] = field(default_factory=list)
    auto_detect_language: bool = True
    output_format: str = "terminal"  # terminal, json, html
    output_file: Optional[str] = None

    # Rule settings
    max_assertions: int = 3
    max_parametrize_combinations: int = 20
    disabled_rules: Set[str] = field(default_factory=set)
    rule_overrides: Dict[str, RuleConfig] = field(default_factory=dict)

    # Language-specific configurations
    python: LanguageConfig = field(default_factory=LanguageConfig)
    typescript: LanguageConfig = field(default_factory=LanguageConfig)
    javascript: LanguageConfig = field(default_factory=LanguageConfig)
    go: LanguageConfig = field(default_factory=LanguageConfig)
    cpp: LanguageConfig = field(default_factory=LanguageConfig)
    java: LanguageConfig = field(default_factory=LanguageConfig)
    rust: LanguageConfig = field(default_factory=LanguageConfig)
    csharp: LanguageConfig = field(default_factory=LanguageConfig)

    # Python-specific (backward compatibility)
    magic_assert_allowlist: Set[Any] = field(default_factory=set)
    db_commit_methods: Set[str] = field(
        default_factory=lambda: {"commit", "save", "create", "execute"}
    )
    db_rollback_methods: Set[str] = field(
        default_factory=lambda: {"rollback", "abort"}
    )

    # Advanced settings
    cross_file_analysis: bool = True
    parallel_processing: bool = True
    cache_enabled: bool = True

    def get_language_config(self, language: LanguageType) -> LanguageConfig:
        """Get configuration for a specific language."""
        lang_configs = {
            LanguageType.PYTHON: self.python,
            LanguageType.TYPESCRIPT: self.typescript,
            LanguageType.JAVASCRIPT: self.javascript,
            LanguageType.GO: self.go,
            LanguageType.CPP: self.cpp,
            LanguageType.JAVA: self.java,
            LanguageType.RUST: self.rust,
            LanguageType.CSHARP: self.csharp,
        }
        return lang_configs.get(language, LanguageConfig())

    def is_rule_enabled(self, rule_id: str, language: Optional[LanguageType] = None) -> bool:
        """Check if a rule is enabled.

        Args:
            rule_id: The rule ID
            language: Optional language to check language-specific disabling

        Returns:
            True if rule is enabled
        """
        # Check global disabled rules
        if rule_id in self.disabled_rules:
            return False

        # Check rule overrides
        if rule_id in self.rule_overrides:
            if not self.rule_overrides[rule_id].enabled:
                return False

        # Check language-specific disabled rules
        if language:
            lang_config = self.get_language_config(language)
            if rule_id in lang_config.disabled_rules:
                return False

        return True

    def get_rule_severity(self, rule_id: str) -> Optional[SmellSeverity]:
        """Get severity override for a rule."""
        if rule_id in self.rule_overrides:
            return self.rule_overrides[rule_id].severity
        return None


class ConfigLoader:
    """Loads configuration from various sources."""

    @staticmethod
    def load_from_file(config_file: Path) -> TestLinterConfig:
        """Load configuration from a TOML file.

        Args:
            config_file: Path to the config file (pyproject.toml or test-linter.toml)

        Returns:
            Loaded configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If TOML parsing fails
        """
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        if tomllib is None:
            raise ImportError(
                "tomli/tomllib not available. Install tomli for Python < 3.11"
            )

        with open(config_file, "rb") as f:
            data = tomllib.load(f)

        # Look for config in [tool.test-linter] section
        config_data = data.get("tool", {}).get("test-linter", {})

        return ConfigLoader._parse_config_dict(config_data)

    @staticmethod
    def load_from_pyproject(project_dir: Path) -> TestLinterConfig:
        """Load configuration from pyproject.toml in project directory.

        Args:
            project_dir: Project directory containing pyproject.toml

        Returns:
            Loaded configuration or default if not found
        """
        pyproject = project_dir / "pyproject.toml"
        if pyproject.exists():
            try:
                return ConfigLoader.load_from_file(pyproject)
            except Exception:
                pass

        return TestLinterConfig()

    @staticmethod
    def _parse_config_dict(data: Dict[str, Any]) -> TestLinterConfig:
        """Parse configuration dictionary into TestLinterConfig.

        Args:
            data: Configuration dictionary

        Returns:
            Parsed configuration
        """
        config = TestLinterConfig()

        # General settings
        if "languages" in data:
            config.languages = [
                LanguageType(lang) for lang in data["languages"]
            ]

        if "auto-detect-language" in data:
            config.auto_detect_language = data["auto-detect-language"]

        if "output-format" in data:
            config.output_format = data["output-format"]

        if "output-file" in data:
            config.output_file = data["output-file"]

        # Rule settings
        if "max-assertions" in data:
            config.max_assertions = data["max-assertions"]

        if "max-parametrize-combinations" in data:
            config.max_parametrize_combinations = data["max-parametrize-combinations"]

        if "disabled-rules" in data:
            config.disabled_rules = set(data["disabled-rules"])

        # Python-specific (backward compatibility)
        if "magic-assert-allowlist" in data:
            config.magic_assert_allowlist = set(data["magic-assert-allowlist"])

        if "db-commit-methods" in data:
            config.db_commit_methods = set(data["db-commit-methods"])

        if "db-rollback-methods" in data:
            config.db_rollback_methods = set(data["db-rollback-methods"])

        # Advanced settings
        if "cross-file-analysis" in data:
            config.cross_file_analysis = data["cross-file-analysis"]

        if "parallel-processing" in data:
            config.parallel_processing = data["parallel-processing"]

        if "cache-enabled" in data:
            config.cache_enabled = data["cache-enabled"]

        # Language-specific configurations
        for lang in ["python", "typescript", "javascript", "go", "cpp", "java", "rust", "csharp"]:
            if lang in data:
                lang_config = ConfigLoader._parse_language_config(data[lang])
                setattr(config, lang.replace("-", "_"), lang_config)

        # Rule overrides
        if "rules" in data:
            for rule_id, rule_data in data["rules"].items():
                config.rule_overrides[rule_id] = ConfigLoader._parse_rule_config(rule_data)

        return config

    @staticmethod
    def _parse_language_config(data: Dict[str, Any]) -> LanguageConfig:
        """Parse language-specific configuration."""
        config = LanguageConfig()

        if "enabled" in data:
            config.enabled = data["enabled"]

        if "framework" in data:
            config.framework = data["framework"]

        if "disabled-rules" in data:
            config.disabled_rules = set(data["disabled-rules"])

        if "max-assertions" in data:
            config.max_assertions = data["max-assertions"]

        if "max-parametrize-combinations" in data:
            config.max_parametrize_combinations = data["max-parametrize-combinations"]

        # Copy all other settings
        for key, value in data.items():
            if key not in ("enabled", "framework", "disabled-rules", "max-assertions", "max-parametrize-combinations"):
                config.settings[key] = value

        return config

    @staticmethod
    def _parse_rule_config(data: Any) -> RuleConfig:
        """Parse rule configuration."""
        config = RuleConfig()

        if isinstance(data, str):
            # Simple string format: "error", "warning", "info", "off"
            if data == "off":
                config.enabled = False
            else:
                try:
                    config.severity = SmellSeverity(data)
                except ValueError:
                    pass

        elif isinstance(data, dict):
            if "severity" in data:
                try:
                    config.severity = SmellSeverity(data["severity"])
                except ValueError:
                    pass

            if "enabled" in data:
                config.enabled = data["enabled"]

            if "options" in data:
                config.options = data["options"]

        return config


def get_default_config() -> TestLinterConfig:
    """Get default configuration.

    Returns:
        Default TestLinterConfig
    """
    return TestLinterConfig()


def find_config_file(start_dir: Path) -> Optional[Path]:
    """Find configuration file by searching up the directory tree.

    Args:
        start_dir: Directory to start searching from

    Returns:
        Path to config file or None if not found
    """
    current = start_dir.resolve()

    # Search up to root
    while True:
        # Check for pyproject.toml
        pyproject = current / "pyproject.toml"
        if pyproject.exists():
            # Check if it has test-linter config
            if tomllib:
                try:
                    with open(pyproject, "rb") as f:
                        data = tomllib.load(f)
                    if "tool" in data and "test-linter" in data["tool"]:
                        return pyproject
                except Exception:
                    pass

        # Check for standalone test-linter.toml
        config_file = current / "test-linter.toml"
        if config_file.exists():
            return config_file

        # Move up one directory
        parent = current.parent
        if parent == current:
            # Reached root
            break
        current = parent

    return None


def load_config(config_file: Optional[Path] = None, start_dir: Optional[Path] = None) -> TestLinterConfig:
    """Load configuration from file or use defaults.

    Args:
        config_file: Explicit config file path
        start_dir: Directory to start searching for config

    Returns:
        Loaded or default configuration
    """
    if config_file:
        return ConfigLoader.load_from_file(config_file)

    if start_dir:
        found_config = find_config_file(start_dir)
        if found_config:
            return ConfigLoader.load_from_file(found_config)

    return get_default_config()
