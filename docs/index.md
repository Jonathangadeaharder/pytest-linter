# pytest-linter

Fast, tree-sitter-powered test smell detector for **pytest** (Python).

## Quick Start

```bash
# Install
cargo install --path .

# Run
pytest-linter /path/to/tests

# JSON output
pytest-linter --format json /path/to/tests

# Incremental mode (only changed files)
pytest-linter --incremental /path/to/tests

# Baseline mode
pytest-linter --baseline violations.json /path/to/tests
pytest-linter --check-baseline violations.json /path/to/tests
```

## Rules

pytest-linter includes **30 rules** across three categories:

### Flakiness (9 rules)
| Rule | Description | Severity |
|------|-------------|----------|
| PYTEST-FLK-001 | time.sleep in test | Warning |
| PYTEST-FLK-002 | File I/O without tmp_path | Warning |
| PYTEST-FLK-003 | Network library imports | Warning |
| PYTEST-FLK-004 | CWD dependency | Warning |
| PYTEST-FLK-005 | Mystery guest (file I/O) | Warning |
| PYTEST-FLK-008 | Random without fixed seed | Warning |
| PYTEST-FLK-009 | Subprocess without timeout | Warning |
| PYTEST-XDIST-001 | Session fixture mutable state | Warning |
| PYTEST-XDIST-002 | Session fixture file I/O | Warning |

### Maintenance (12 rules)
| Rule | Description | Severity |
|------|-------------|----------|
| PYTEST-MNT-001 | Conditional logic in test | Warning |
| PYTEST-MNT-002 | Magic assertion | Warning |
| PYTEST-MNT-003 | Suboptimal assertion | Info |
| PYTEST-MNT-004 | No assertions | Error |
| PYTEST-MNT-005 | Mock-only verification | Warning |
| PYTEST-MNT-006 | Assertion roulette | Warning |
| PYTEST-MNT-007 | Raw exception handling | Warning |
| PYTEST-BDD-001 | Missing BDD scenario | Info |
| PYTEST-PBT-001 | Property test hint | Info |
| PYTEST-PARAM-001 | Empty parametrize | Warning |
| PYTEST-PARAM-002 | Duplicate parametrize | Warning |
| PYTEST-PARAM-003 | Parametrize explosion | Warning |

### Fixtures (9 rules)
| Rule | Description | Severity |
|------|-------------|----------|
| PYTEST-FIX-001 | Autouse fixture | Warning |
| PYTEST-FIX-003 | Invalid scope | Error |
| PYTEST-FIX-004 | Shadowed fixture | Warning |
| PYTEST-FIX-005 | Unused fixture | Warning |
| PYTEST-FIX-006 | Stateful session fixture | Warning |
| PYTEST-FIX-007 | Fixture mutation | Warning |
| PYTEST-FIX-008 | DB commit without cleanup | Warning |
| PYTEST-FIX-009 | Overly broad scope | Warning |
| PYTEST-DBC-001 | Happy-path only hint | Info |

## Configuration

Add to your `pyproject.toml`:

```toml
[tool.pytest-linter]
format = "json"

[tool.pytest-linter.rules.PYTEST-FLK-001]
enabled = false

[tool.pytest-linter.rules.PYTEST-MNT-004]
severity = "warning"
```

## Suppression

Suppress specific rules inline:

```python
def test_something():  # noqa: PYTEST-FLK-001
    time.sleep(1)
    assert True
```

Suppress all rules:
```python
def test_something():  # noqa
    pass
```

## Output Formats

- `terminal` - Colored terminal output (default)
- `json` - JSON array of violations
- `sarif` - SARIF 2.1.0 format for GitHub code scanning
