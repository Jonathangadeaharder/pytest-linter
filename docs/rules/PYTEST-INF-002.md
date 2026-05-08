# PYTEST-INF-002 — LiveSuiteUnmarkedRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-INF-002` |
| **Name** | LiveSuiteUnmarkedRule |
| **Severity** | Warning |
| **Category** | Flakiness |

## Message

> File has live network calls without @pytest.mark.live

## Rationale

Tests that make live network calls should be marked with `@pytest.mark.live` so they can be selectively included/excluded in CI pipelines. Unmarked live tests run in every CI job, causing flaky failures and slow builds.

## Suggestion

Mark live network tests with `@pytest.mark.live` for selective CI filtering

## Examples

### ❌ Bad

```python
import requests

def test_live_api():
    resp = requests.get("https://api.example.com")
    assert resp.status_code == 200
```

### ✅ Good

```python
import pytest
import requests

@pytest.mark.live
def test_live_api():
    resp = requests.get("https://api.example.com")
    assert resp.status_code == 200
```
