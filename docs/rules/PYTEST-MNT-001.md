# PYTEST-MNT-001 — TestLogicRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-MNT-001` |
| **Name** | TestLogicRule |
| **Severity** | Warning |
| **Category** | Maintenance |

## Message

> Test '{test}' contains conditional logic (if statements)

## Rationale

Conditional logic in tests makes them harder to understand and debug. Each branch should be a separate test case so failures are isolated and traceable.

## Suggestion

Split into separate tests or use parametrize

## Examples

### ❌ Bad

```python
def test_user():
    if user.is_admin:
        assert dashboard.shows_admin_panel()
    else:
        assert not dashboard.shows_admin_panel()
```

### ✅ Good

```python
@pytest.mark.parametrize('role,expected', [
    ('admin', True),
    ('user', False),
])
def test_admin_panel(role, expected):
    user = create_user(role)
    assert dashboard.shows_admin_panel(user) == expected
```
