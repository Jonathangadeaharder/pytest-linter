# PYTEST-MNT-005 — MockOnlyVerifyRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-MNT-005` |
| **Name** | MockOnlyVerifyRule |
| **Severity** | Warning |
| **Category** | Maintenance |

## Message

> Test '{test}' only verifies mocks without checking state

## Rationale

Tests that only verify mock interactions but never check actual state are brittle — they confirm the code calls something but not that it produces correct results.

## Suggestion

Add state assertions to verify actual outcomes

## Examples

### ❌ Bad

```python
def test_send_email(mocker):
    send_welcome_email(user)
    mocker.assert_called_once()  # only mock check
```

### ✅ Good

```python
def test_send_email(mocker):
    result = send_welcome_email(user)
    mocker.assert_called_once()
    assert result.status == 'sent'  # state assertion
```
