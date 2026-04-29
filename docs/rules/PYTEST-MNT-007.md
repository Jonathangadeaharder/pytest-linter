# PYTEST-MNT-007 — RawExceptionHandlingRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-MNT-007` |
| **Name** | RawExceptionHandlingRule |
| **Severity** | Warning |
| **Category** | Maintenance |

## Message

> Test '{test}' uses try/except instead of pytest.raises

## Rationale

`pytest.raises()` provides clearer intent, better failure messages, and integrates with pytest's reporting. Raw `try/except` is verbose and error-prone.

## Suggestion

Use pytest.raises() for exception testing

## Examples

### ❌ Bad

```python
def test_divide_by_zero():
    try:
        divide(1, 0)
    except ZeroDivisionError:
        pass
```

### ✅ Good

```python
def test_divide_by_zero():
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)
```
