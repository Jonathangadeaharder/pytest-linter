# PYTEST-FLK-003 — NetworkImportRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FLK-003` |
| **Name** | NetworkImportRule |
| **Severity** | Warning |
| **Category** | Flakiness |

## Message

> File imports network libraries which may cause flaky tests

## Rationale

Importing `requests`, `socket`, `httpx`, `aiohttp`, or `urllib` indicates potential network dependencies. Network calls are inherently non-deterministic and cause flaky tests.

## Suggestion

Mock network calls or use pytest-localserver

## Examples

### ❌ Bad

```python
import requests
import httpx

def test_api():
    resp = requests.get('https://api.example.com')
    assert resp.status_code == 200
```

### ✅ Good

```python
from unittest.mock import patch

def test_api():
    with patch('requests.get') as mock_get:
        mock_get.return_value.status_code = 200
        resp = requests.get('https://api.example.com')
        assert resp.status_code == 200
```
