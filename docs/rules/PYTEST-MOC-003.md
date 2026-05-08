# PYTEST-MOC-003 — PatchInitBypassRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-MOC-003` |
| **Name** | PatchInitBypassRule |
| **Severity** | Warning |
| **Category** | Maintenance |

## Message

> Test patches __init__ — bypasses constructor validation

## Rationale

Patching `__init__` bypasses constructor validation, invariants, and required setup. This creates objects in an invalid state and tests behavior that cannot occur in production.

## Suggestion

Patch the class itself or use a factory fixture instead

## Examples

### ❌ Bad

```python
from unittest.mock import patch

@patch("myapp.models.User.__init__", return_value=None)
def test_user():
    user = User()
```

### ✅ Good

```python
from unittest.mock import patch

@patch("myapp.models.User")
def test_user(MockUser):
    user = MockUser.return_value
```
