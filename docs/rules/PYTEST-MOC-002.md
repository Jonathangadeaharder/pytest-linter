# PYTEST-MOC-002 — MagicMockOnAsyncRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-MOC-002` |
| **Name** | MagicMockOnAsyncRule |
| **Severity** | Error |
| **Category** | Maintenance |

## Message

> Async test uses MagicMock instead of AsyncMock

## Rationale

Using `MagicMock` for async functions returns non-awaitable coroutines, causing `TypeError` or silent failures. `unittest.mock.AsyncMock` properly supports `await` and async iteration.

## Suggestion

Use `unittest.mock.AsyncMock` for async functions

## Examples

### ❌ Bad

```python
from unittest.mock import MagicMock

async def test_fetch():
    mock = MagicMock()
    result = await mock()  # TypeError
```

### ✅ Good

```python
from unittest.mock import AsyncMock

async def test_fetch():
    mock = AsyncMock()
    result = await mock()
```
