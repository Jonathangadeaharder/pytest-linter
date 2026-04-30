# PYTEST-MNT-002 — MagicAssertRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-MNT-002` |
| **Name** | MagicAssertRule |
| **Severity** | Warning |
| **Category** | Maintenance |

## Message

> Magic assertion at line {line}: '{expr}' — this always passes/fails

## Rationale

Magic assertions are assertions that always pass or always fail regardless of the code under test, providing no real verification. Examples include `assert True` or `assert False`.

## Suggestion

Replace with a meaningful comparison

## Examples

### ❌ Bad

```python
def test_status():
    result = get_status()
    assert True  # always passes
```

### ✅ Good

```python
def test_status():
    result = get_status()
    assert result == 'ok'
```
