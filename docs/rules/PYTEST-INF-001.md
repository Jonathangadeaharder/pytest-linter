# PYTEST-INF-001 — NetworkBanMissingRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-INF-001` |
| **Name** | NetworkBanMissingRule |
| **Severity** | Warning |
| **Category** | Flakiness |

## Message

> File imports network libraries without @pytest.mark.network or mock layer

## Rationale

Test files that import network libraries without explicit opt-in via `@pytest.mark.network` or a mock layer (respx, responses, etc.) may accidentally make live network calls. Explicit marking enables CI filtering and prevents flaky tests.

## Suggestion

Add `@pytest.mark.network` or use a mock layer (respx, responses, etc.)

## Examples

### ❌ Bad

```python
import requests

def test_api():
    resp = requests.get("https://api.example.com")
    assert resp.status_code == 200
```

### ✅ Good

```python
import requests
import responses

@responses.activate
def test_api():
    responses.add(responses.GET, "https://api.example.com", status=200)
    resp = requests.get("https://api.example.com")
    assert resp.status_code == 200
```
