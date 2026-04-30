# PYTEST-FLK-004 — CwdDependencyRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FLK-004` |
| **Name** | CwdDependencyRule |
| **Severity** | Warning |
| **Category** | Flakiness |

## Message

> Test '{test}' depends on the current working directory

## Rationale

Tests that depend on `os.getcwd()` or relative paths are sensitive to execution order and working directory, leading to failures when run from different locations or in parallel.

## Suggestion

Use absolute paths or tmp_path fixture instead

## Examples

### ❌ Bad

```python
def test_load():
    data = open('data/config.json').read()
    assert data
```

### ✅ Good

```python
from pathlib import Path

def test_load(tmp_path):
    config = tmp_path / 'config.json'
    config.write_text('{}')
    data = config.read_text()
    assert data
```
