# PYTEST-PARAM-003 — ParametrizeExplosionRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-PARAM-003` |
| **Name** | ParametrizeExplosionRule |
| **Severity** | Warning |
| **Category** | Maintenance |

## Message

> Test '{test}' has {count} parametrized cases — combinatorial explosion

## Rationale

When parametrize generates >20 test cases (especially with multiple `@pytest.mark.parametrize` decorators), the test suite becomes slow. Property-based testing covers edge cases more efficiently.

## Suggestion

Reduce test cases or use hypothesis

## Examples

### ❌ Bad

```python
@pytest.mark.parametrize('a', range(10))
@pytest.mark.parametrize('b', range(10))
def test_add(a, b):
    assert (a + b) >= a
```

### ✅ Good

```python
from hypothesis import given, strategies as st

@given(st.integers(), st.integers())
def test_add_commutative(a, b):
    assert a + b == b + a
```
