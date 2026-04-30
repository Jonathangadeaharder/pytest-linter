# PYTEST-PARAM-002 — ParametrizeDuplicateRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-PARAM-002` |
| **Name** | ParametrizeDuplicateRule |
| **Severity** | Warning |
| **Category** | Maintenance |

## Message

> Parametrize in test '{test}' has duplicate values: {values}

## Rationale

Duplicate parametrize values waste test execution time and make the test suite slower without adding any verification value.

## Suggestion

Remove duplicate parametrize values

## Examples

### ❌ Bad

```python
@pytest.mark.parametrize('x', [1, 2, 3, 2, 1])
def test_positive(x):
    assert x > 0
```

### ✅ Good

```python
@pytest.mark.parametrize('x', [1, 2, 3])
def test_positive(x):
    assert x > 0
```
