# PYTEST-MNT-004 — NoAssertionRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-MNT-004` |
| **Name** | NoAssertionRule |
| **Severity** | Error |
| **Category** | Maintenance |

## Message

> Test '{test}' has no assertions

## Rationale

A test without assertions can never fail, making it useless as a verification tool. Every test should assert at least one expected behavior.

## Suggestion

Add assertions to verify expected behavior

## Examples

### ❌ Bad

```python
def test_process():
    result = process(data)
    # no assertion
```

### ✅ Good

```python
def test_process():
    result = process(data)
    assert result.status == 'success'
```
