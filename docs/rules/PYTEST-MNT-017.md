# PYTEST-MNT-017 — TestNameLengthRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-MNT-017` |
| **Name** | TestNameLengthRule |
| **Severity** | Info |
| **Category** | Maintenance |

## Message

> Test name '{test}' exceeds 80 characters ({count} chars)

## Rationale

Overly long test names reduce readability in test reports, IDE test runners, and CI logs. Names > 80 characters usually contain implementation details that belong in the test body or parametrize parameters instead.

## Suggestion

Shorten the test name to be more concise

## Examples

### ❌ Bad

```python
def test_user_registration_with_valid_email_and_password_creates_account_and_sends_welcome_email_and_redirects_to_dashboard():
    ...
```

### ✅ Good

```python
@pytest.mark.parametrize('email,password', [
    ('valid@example.com', 'strongpass'),
])
def test_user_registration(email, password):
    ...
```
