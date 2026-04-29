# pytest-linter

Fast, tree-sitter-powered test smell detector for **pytest** (Python), written in Rust.

## Why pytest-linter?

- **Fast**: Tree-sitter AST parsing — no regex, no Python runtime overhead
- **Comprehensive**: 39 rules covering flakiness, maintenance, and fixture smells
- **Zero config**: Works out of the box with sensible defaults
- **Multiple formats**: Terminal (colored), JSON, and SARIF output
- **CI-friendly**: Exit code 1 on Error-severity violations

## Quick Example

```bash
pytest-linter tests/
```

Output:

```text
tests/test_api.py:12 PYTEST-FLK-001 [warning] Test 'test_timeout' uses time.sleep which causes flaky tests
  → Use pytest's time mocking or wait for a condition instead

tests/test_models.py:45 PYTEST-MNT-004 [error] Test 'test_create' has no assertions
  → Add assertions to verify expected behavior
```

## Features

| Feature | Description |
|---------|-------------|
| AST-based analysis | Tree-sitter parsing, no false positives from string matching |
| 39 rules | Flakiness, maintenance, fixture, BDD, PBT, and parametrize checks |
| JSON output | `--format json` for integration with other tools |
| SARIF output | `--format sarif` for GitHub Code Scanning |
| Configurable | `pyproject.toml` configuration support |
| Pre-commit hook | Ready-to-use pre-commit integration |

## Installation

<!-- markdownlint-disable MD046 -->

=== "Prebuilt Binary (Recommended)"

    Download from [GitHub Releases](https://github.com/Jonathangadeaharder/pytest-linter/releases).

=== "pip"

    ```bash
    pip install pytest-linter
    ```

=== "Homebrew"

    ```bash
    brew install Jonathangadeaharder/tap/pytest-linter
    ```

=== "Cargo"

    ```bash
    cargo install pytest-linter
    ```

<!-- markdownlint-enable MD046 -->

## Next Steps

- [Getting Started Guide](getting-started.md)
- [All Rules](rules/index.md)
- [Comparison with other tools](comparison.md)
- [Migration Guide](migration.md)
