# PYTEST-MNT-015 — DuplicateTestBodiesRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-MNT-015` |
| **Name** | DuplicateTestBodiesRule |
| **Severity** | Info |
| **Category** | Maintenance |

## Message

> Test '{test}' has identical body to {count} other test(s): {peers} (shared body hash)

## Rationale

Duplicate test bodies provide no additional verification value and increase maintenance burden. Either the tests are redundant (remove them) or they should test different scenarios (differentiate them).

## Suggestion

Consolidate or differentiate the test bodies

## Examples

### ❌ Bad

```python
def test_add_positive():
    result = add(2, 3)
    assert result == 5

def test_add_positive_two():
    result = add(2, 3)
    assert result == 5
```

### ✅ Good

```python
def test_add_positive():
    result = add(2, 3)
    assert result == 5

def test_add_negative():
    result = add(-1, -2)
    assert result == -3
```
