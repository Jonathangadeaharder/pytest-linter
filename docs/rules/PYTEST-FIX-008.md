# PYTEST-FIX-008 — FixtureDbCommitNoCleanupRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FIX-008` |
| **Name** | FixtureDbCommitNoCleanupRule |
| **Severity** | Warning |
| **Category** | Fixture |

## Message

> Fixture '{fixture}' commits to DB without rollback or cleanup (no yield)

## Rationale

Database fixtures that commit without cleanup leave residual data that can contaminate subsequent test runs, causing mysterious failures.

## Suggestion

Use yield to provide cleanup or wrap in a transaction

## Examples

### ❌ Bad

```python
@pytest.fixture
def db_record():
    record = db.insert({'name': 'test'})
    db.commit()
    return record
```

### ✅ Good

```python
@pytest.fixture
def db_record():
    record = db.insert({'name': 'test'})
    db.commit()
    yield record
    db.delete(record)
    db.commit()
```
