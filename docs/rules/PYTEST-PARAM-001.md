# PYTEST-PARAM-001 — ParametrizeEmptyRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-PARAM-001` |
| **Name** | ParametrizeEmptyRule |
| **Severity** | Warning |
| **Category** | Maintenance |

## Message

> Test '{test}' is parametrized with only {count} case(s)

## Rationale

A parametrize with 0 or 1 cases is either dead code or adds unnecessary complexity. Either add meaningful cases or remove the parametrize decorator.

## Suggestion

Add more test cases or remove parametrize

## Examples

### ❌ Bad

```python
@pytest.mark.parametrize('x', [1])
def test_double(x):
    assert x * 2 == 2
```

### ✅ Good

```python
@pytest.mark.parametrize('x,expected', [(1, 2), (2, 4), (0, 0), (-1, -2)])
def test_double(x, expected):
    assert x * 2 == expected
```
