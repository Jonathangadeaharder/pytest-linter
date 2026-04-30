# PYTEST-XDIST-002 — XdistFixtureIoRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-XDIST-002` |
| **Name** | XdistFixtureIoRule |
| **Severity** | Warning |
| **Category** | Flakiness |

## Message

> Session-scoped fixture '{fixture}' uses file I/O — may conflict with xdist workers

## Rationale

Session-scoped fixtures that perform file I/O can race with each other when tests run in parallel under xdist, causing file corruption or missing data.

## Suggestion

Use tmp_path_factory or make I/O paths unique per worker

## Examples

### ❌ Bad

```python
@pytest.fixture(scope='session')
def db_file():
    with open('test.db', 'w') as f:
        f.write('schema')
    return 'test.db'
```

### ✅ Good

```python
@pytest.fixture(scope='session')
def db_file(tmp_path_factory):
    db = tmp_path_factory.mktemp('db') / 'test.db'
    db.write_text('schema')
    return db
```
