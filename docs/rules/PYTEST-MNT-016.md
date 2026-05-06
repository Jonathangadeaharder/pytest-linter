# PYTEST-MNT-016 — SleepWithValueRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-MNT-016` |
| **Name** | SleepWithValueRule |
| **Severity** | Warning |
| **Category** | Maintenance |

## Message

> Test '{test}' uses time.sleep() with value > 0.1s — slows test suite

## Rationale

Using `time.sleep()` with values > 0.1s unnecessarily slows the test suite. In large projects, even small sleeps compound. Use mocking, `pytest-asyncio` waits, or reduce the sleep to the minimum needed.

## Suggestion

Use mocking, async waits, or reduce sleep duration

## Examples

### ❌ Bad

```python
import time

def test_debounce():
    trigger_event()
    time.sleep(2)
    assert is_debounced()
```

### ✅ Good

```python
import time
from unittest.mock import patch

def test_debounce():
    with patch('time.sleep'):
        trigger_event()
    assert is_debounced()
```
