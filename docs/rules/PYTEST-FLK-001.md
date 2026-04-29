# PYTEST-FLK-001 — TimeSleepRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FLK-001` |
| **Name** | TimeSleepRule |
| **Severity** | Warning |
| **Category** | Flakiness |

## Message

> Test '{test}' uses time.sleep which causes flaky tests

## Rationale

`time.sleep()` introduces implicit timing dependencies that vary across machines and CI environments. Tests become flaky because they rely on wall-clock time rather than synchronization.

## Suggestion

Use pytest's time mocking or wait for a condition instead

## Examples

### ❌ Bad

```python
def test_retry():
    time.sleep(5)  # waits an arbitrary duration
    assert service.is_ready()
```

### ✅ Good

```python
def test_retry():
    with pytest.mock.patch('time.sleep'):
        service.trigger()
    assert service.is_ready()
```
