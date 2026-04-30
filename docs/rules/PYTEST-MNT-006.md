# PYTEST-MNT-006 — AssertionRouletteRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-MNT-006` |
| **Name** | AssertionRouletteRule |
| **Severity** | Warning |
| **Category** | Maintenance |

## Message

> Test '{test}' has {count} assertions (assertion roulette)

## Rationale

When a test has many assertions (>3), it's hard to tell which one failed and why. Smaller, focused tests provide clearer failure messages and better isolation.

## Suggestion

Split into smaller, focused tests

## Examples

### ❌ Bad

```python
def test_user_full():
    user = create_user('Alice')
    assert user.name == 'Alice'
    assert user.email == 'alice@example.com'
    assert user.age == 30
    assert user.active is True
    assert user.role == 'admin'
```

### ✅ Good

```python
def test_user_name():
    user = create_user('Alice')
    assert user.name == 'Alice'

def test_user_email():
    user = create_user('Alice')
    assert user.email == 'alice@example.com'
```
