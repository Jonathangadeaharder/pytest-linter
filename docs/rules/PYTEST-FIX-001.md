# PYTEST-FIX-001 — AutouseFixtureRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FIX-001` |
| **Name** | AutouseFixtureRule |
| **Severity** | Warning |
| **Category** | Fixture |

## Message

> Fixture '{fixture}' uses autouse=True

## Rationale

`autouse=True` fixtures run implicitly for every test, making dependencies invisible. This hurts readability and makes it hard to understand what setup a test relies on.

## Suggestion

Explicitly declare fixture dependencies instead

## Examples

### ❌ Bad

```python
@pytest.fixture(autouse=True)
def setup_db():
    db.create_tables()
```

### ✅ Good

```python
@pytest.fixture
def db_tables():
    db.create_tables()
    return db

def test_query(db_tables):
    assert db_tables.query('SELECT 1')
```
