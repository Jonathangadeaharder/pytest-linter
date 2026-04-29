# PYTEST-FIX-004 — ShadowedFixtureRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FIX-004` |
| **Name** | ShadowedFixtureRule |
| **Severity** | Warning |
| **Category** | Fixture |

## Message

> Fixture '{fixture}' is defined in {count} different modules (shadowed)

## Rationale

When the same fixture name is defined in multiple files, pytest's resolution order can lead to surprising behavior. Tests may use a different fixture than expected depending on file location.

## Suggestion

Rename or consolidate fixture definitions

## Examples

### ❌ Bad

```python
# conftest.py
@pytest.fixture
def user():
    return User('default')

# tests/conftest.py
@pytest.fixture
def user():
    return User('test')
```

### ✅ Good

```python
# conftest.py
@pytest.fixture
def default_user():
    return User('default')

# tests/conftest.py
@pytest.fixture
def test_user():
    return User('test')
```
