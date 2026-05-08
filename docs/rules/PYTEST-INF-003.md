# PYTEST-INF-003 — NonIdiomaticMonkeyPatchRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-INF-003` |
| **Name** | NonIdiomaticMonkeyPatchRule |
| **Severity** | Info |
| **Category** | Enhancement |

## Message

> Test uses monkeypatch without context manager — changes may leak

## Rationale

Using `monkeypatch.setattr()` without a context manager means patches are only undone when the fixture is torn down. If a test fails midway, subsequent assertions or cleanup code may see the patched state. Using `monkeypatch.context()` ensures automatic cleanup.

## Suggestion

Use `with monkeypatch.context() as m:` for automatic cleanup

## Examples

### ❌ Bad

```python
def test_env(monkeypatch):
    monkeypatch.setattr("os.environ", {"TEST": "1"})
    # if assertion fails, os.environ stays patched until teardown
    assert os.environ["TEST"] == "1"
```

### ✅ Good

```python
def test_env(monkeypatch):
    with monkeypatch.context() as m:
        m.setattr("os.environ", {"TEST": "1"})
        assert os.environ["TEST"] == "1"
    # os.environ is restored even if assertion fails
```
