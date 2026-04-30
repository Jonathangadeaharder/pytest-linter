# PYTEST-PBT-001 — PropertyTestHintRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-PBT-001` |
| **Name** | PropertyTestHintRule |
| **Severity** | Info |
| **Category** | Enhancement |

## Message

> Test '{test}' has {count} parametrized cases — consider property-based testing

## Rationale

When a parametrize decorator has many cases (>3), property-based testing with Hypothesis can cover more edge cases with less boilerplate and find bugs manual cases miss.

## Suggestion

Consider using hypothesis for property-based testing

## Examples

### ❌ Bad

```python
@pytest.mark.parametrize('val', [1, 2, 3, 4, 5, 6, 7, 8])
def test_abs(val):
    assert abs(val) >= 0
```

### ✅ Good

```python
from hypothesis import given, strategies as st

@given(st.integers())
def test_abs(val):
    assert abs(val) >= 0
```
