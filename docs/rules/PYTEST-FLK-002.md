# PYTEST-FLK-002 — FileIoRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FLK-002` |
| **Name** | FileIoRule |
| **Severity** | Warning |
| **Category** | Flakiness |

## Message

> Test '{test}' uses file I/O without tmp_path/tmpdir fixture

## Rationale

Direct file I/O without temporary directory fixtures can leave residual files, cause path conflicts between tests, or fail in parallel execution.

## Suggestion

Use the tmp_path or tmpdir fixture for temporary files

## Examples

### ❌ Bad

```python
def test_save():
    with open('output.txt', 'w') as f:
        f.write('data')
```

### ✅ Good

```python
def test_save(tmp_path):
    out = tmp_path / 'output.txt'
    out.write_text('data')
```
