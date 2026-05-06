# PYTEST-FLK-011 — DatetimeInAssertionRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FLK-011` |
| **Name** | DatetimeInAssertionRule |
| **Severity** | Warning |
| **Category** | Flakiness |

## Message

> Test '{test}' uses datetime functions near assertions — tests relying on real time are flaky

## Rationale

Assertions involving `datetime.now()`, `datetime.today()`, or similar functions produce different values on each run. These tests fail when run around midnight, across timezones, or under load.

## Suggestion

Use freezegun or time mocking to make assertions deterministic

## Examples

### ❌ Bad

```python
from datetime import datetime

def test_created_at():
    obj = create_record()
    assert obj.created_at == datetime.now()
```

### ✅ Good

```python
from freezegun import freeze_time
from datetime import datetime

@freeze_time('2025-01-01 12:00:00')
def test_created_at():
    obj = create_record()
    assert obj.created_at == datetime(2025, 1, 1, 12, 0, 0)
```
