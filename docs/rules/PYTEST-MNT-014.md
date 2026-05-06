# PYTEST-MNT-014 — ConditionalLogicInTestRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-MNT-014` |
| **Name** | ConditionalLogicInTestRule |
| **Severity** | Warning |
| **Category** | Maintenance |

## Message

> Parametrized test '{test}' contains conditional logic (if/elif/else/for/while) — use separate parameter cases instead of branching

## Rationale

Conditional logic inside parametrized tests defeats the purpose of parametrization. Each branch should be a separate parameter case for clearer failure isolation and better test reporting.

## Suggestion

Split into separate tests or use pytest.mark.parametrize

## Examples

### ❌ Bad

```python
@pytest.mark.parametrize('role', ['admin', 'user'])
def test_access(role):
    if role == 'admin':
        assert has_admin_access()
    else:
        assert not has_admin_access()
```

### ✅ Good

```python
@pytest.mark.parametrize('role,expected', [
    ('admin', True),
    ('user', False),
])
def test_access(role, expected):
    assert has_admin_access(role) == expected
```
