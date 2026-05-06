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

While pytest runs teardown code after `yield` even if a test fails, using `try/finally` is essential for fixtures that acquire multiple resources. It ensures that if an error occurs during the setup of one resource, previously acquired resources are still cleaned up.

## Suggestion

Wrap yield in try/finally to ensure cleanup runs even on failure

## Examples

### ❌ Bad

```python
@pytest.fixture
def db_connection():
    conn = create_connection()
    yield conn
    conn.close()  # may be skipped if setup fails before yield
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
