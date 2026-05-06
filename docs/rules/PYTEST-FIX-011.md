# PYTEST-FIX-011 — YieldWithoutTryFinallyRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FIX-011` |
| **Name** | YieldWithoutTryFinallyRule |
| **Severity** | Warning |
| **Category** | Fixture |

## Message

> Fixture '{fixture}' uses yield without try/finally cleanup

## Rationale

A `yield` fixture without `try/finally` will skip teardown code if the test raises an exception. This leaves resources (DB connections, temp files, mocks) in a dirty state for subsequent tests.

## Suggestion

Wrap yield in try/finally to ensure cleanup runs even on failure

## Examples

### ❌ Bad

```python
@pytest.fixture
def db_connection():
    conn = create_connection()
    yield conn
    conn.close()  # skipped if test raises
```

### ✅ Good

```python
@pytest.fixture
def db_connection():
    conn = create_connection()
    try:
        yield conn
    finally:
        conn.close()  # always runs
```
