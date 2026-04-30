# PYTEST-MNT-003 — SuboptimalAssertRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-MNT-003` |
| **Name** | SuboptimalAssertRule |
| **Severity** | Info |
| **Category** | Enhancement |

## Message

> Suboptimal assertion at line {line}: '{expr}'

## Rationale

Some assertion patterns produce unclear failure messages. For example, `assert len(items) > 0` doesn't show the actual count. Using `assert items` or `assert items == [...]` is clearer.

## Suggestion

Use a more direct assertion pattern

## Examples

### ❌ Bad

```python
def test_items():
    items = get_items()
    assert len(items) > 0
```

### ✅ Good

```python
def test_items():
    items = get_items()
    assert items  # shows actual list on failure
```
