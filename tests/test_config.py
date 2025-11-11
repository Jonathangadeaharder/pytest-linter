"""
Tests for the configuration module.

These tests verify that the pyproject.toml configuration loading
and rule management work correctly.
"""

import tempfile
from pathlib import Path

import pytest

from pytest_deep_analysis.config import Config, reset_config


def test_config_defaults():
    """Test that default configuration values are set correctly."""
    config = Config()

    assert config.disabled_rules == set()
    assert config.ignore_patterns == []
    assert config.check_db_commits is True
    assert config.check_scope_narrowing is True
    assert config.check_fixture_mutations is True
    assert config.check_parametrize is True


def test_is_rule_enabled():
    """Test checking if a rule is enabled."""
    config = Config()

    # All rules enabled by default
    assert config.is_rule_enabled("pytest-fix-autouse") is True
    assert config.is_rule_enabled("pytest-fix-db-commit") is True

    # Disable a rule
    config.disabled_rules.add("pytest-fix-autouse")
    assert config.is_rule_enabled("pytest-fix-autouse") is False
    assert config.is_rule_enabled("pytest-fix-db-commit") is True


def test_should_ignore_file():
    """Test file pattern matching for ignoring files."""
    config = Config()
    config.ignore_patterns = ["**/migrations/*", "*/generated/*.py"]

    assert config.should_ignore_file("project/migrations/001_initial.py") is True
    assert config.should_ignore_file("app/generated/models.py") is True
    assert config.should_ignore_file("app/tests/test_models.py") is False
    assert config.should_ignore_file("regular_file.py") is False


def test_get_rule_option():
    """Test getting rule-specific options."""
    config = Config()
    config.rule_config = {
        "pytest-fix-autouse": {
            "severity": "error",
            "ignore_conftest": True,
        }
    }

    assert config.get_rule_option("pytest-fix-autouse", "severity") == "error"
    assert config.get_rule_option("pytest-fix-autouse", "ignore_conftest") is True
    assert config.get_rule_option("pytest-fix-autouse", "unknown", "default") == "default"
    assert config.get_rule_option("unknown-rule", "option") is None


def test_load_from_pyproject():
    """Test loading configuration from pyproject.toml."""
    # Create a temporary directory with a pyproject.toml
    with tempfile.TemporaryDirectory() as tmpdir:
        pyproject_path = Path(tmpdir) / "pyproject.toml"
        pyproject_path.write_text("""
[tool.pytest-deep-analysis]
disable = ["pytest-fix-autouse", "pytest-mnt-test-logic"]
ignore_patterns = ["**/migrations/*", "*/test_*.py"]

[tool.pytest-deep-analysis.features]
database_commits = false
scope_narrowing = true
fixture_mutations = true
parametrize_checks = false

[tool.pytest-deep-analysis.rules.pytest-fix-autouse]
severity = "error"
ignore_conftest = true
""")

        config = Config()
        config.load_from_pyproject(tmpdir)

        # Check disabled rules
        assert "pytest-fix-autouse" in config.disabled_rules
        assert "pytest-mnt-test-logic" in config.disabled_rules
        assert config.is_rule_enabled("pytest-fix-autouse") is False

        # Check ignore patterns
        assert "**/migrations/*" in config.ignore_patterns
        assert "*/test_*.py" in config.ignore_patterns

        # Check feature flags
        assert config.check_db_commits is False
        assert config.check_scope_narrowing is True
        assert config.check_fixture_mutations is True
        assert config.check_parametrize is False

        # Check rule options
        assert config.get_rule_option("pytest-fix-autouse", "severity") == "error"
        assert config.get_rule_option("pytest-fix-autouse", "ignore_conftest") is True


def test_find_pyproject_walks_up():
    """Test that _find_pyproject walks up the directory tree."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create nested directory structure
        project_root = Path(tmpdir)
        subdir = project_root / "src" / "app"
        subdir.mkdir(parents=True)

        # Create pyproject.toml at root
        pyproject = project_root / "pyproject.toml"
        pyproject.write_text("[tool.pytest-deep-analysis]\n")

        config = Config()
        # Start search from subdirectory
        found = config._find_pyproject(str(subdir))

        assert found is not None
        assert found == pyproject


def test_find_pyproject_not_found():
    """Test that _find_pyproject returns None when not found."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config()
        found = config._find_pyproject(tmpdir)
        assert found is None


def test_load_from_invalid_pyproject():
    """Test that loading from invalid pyproject.toml doesn't crash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        pyproject_path = Path(tmpdir) / "pyproject.toml"
        pyproject_path.write_text("invalid toml {{{")

        config = Config()
        # Should not raise an exception
        config.load_from_pyproject(tmpdir)

        # Should use defaults
        assert config.disabled_rules == set()


def test_reset_config():
    """Test that reset_config clears the global config."""
    from pytest_deep_analysis.config import get_config

    # Get initial config
    config1 = get_config()
    config1.disabled_rules.add("test-rule")

    # Reset and get new config
    reset_config()
    config2 = get_config()

    # Should be a fresh instance
    assert "test-rule" not in config2.disabled_rules
