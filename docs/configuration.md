# Configuration

pytest-linter is configured via `pyproject.toml` under the `[tool.pytest-linter]` section.

## Basic Options

```toml
[tool.pytest-linter]
# Output format: terminal, json, sarif
format = "terminal"

# Write output to a file (empty string = stdout)
output = ""

# Select specific rules to enable (empty = all)
# Each rule is a table key with optional severity/enable overrides
[tool.pytest-linter.rules]
PYTEST-FLK-001 = {}
PYTEST-MNT-004 = {}
```

## Per-Rule Overrides

Override severity or disable individual rules:

```toml
[[tool.pytest-linter.overrides]]
path = "tests/integration/**"
rules = { PYTEST-FLK-001 = { severity = "info" } }

[[tool.pytest-linter.overrides]]
path = "tests/unit/**"
rules = { PYTEST-MNT-003 = { enabled = false } }
```

## Suppression

Suppress specific rules inline using `noqa` comments:

```python
def test_something():  # noqa: PYTEST-FLK-001
    time.sleep(1)
    assert True
```

Suppress multiple rules on one line:

```python
def test_something():  # noqa: PYTEST-FLK-001, PYTEST-MNT-004
    time.sleep(1)
```

## Pre-commit Integration

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/Jonathangadeaharder/pytest-linter
    rev: v0.1.0
    hooks:
      - id: pytest-linter
```

## CI Integration

### GitHub Actions

```yaml
- name: Lint tests
  run: |
    curl -sL https://github.com/Jonathangadeaharder/pytest-linter/releases/latest/download/pytest-linter-x86_64-unknown-linux-gnu.tar.gz | tar xz
    ./pytest-linter --format sarif --output pytest-linter.sarif tests/
```

### GitLab CI

```yaml
lint-tests:
  script:
    - curl -sL https://github.com/Jonathangadeaharder/pytest-linter/releases/latest/download/pytest-linter-x86_64-unknown-linux-gnu.tar.gz | tar xz
    - ./pytest-linter tests/
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No Error-severity violations found |
| 1 | One or more Error-severity violations found |
