# PYTEST-MOC-001 — PatchTargetingDefinitionModuleRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-MOC-001` |
| **Name** | PatchTargetingDefinitionModuleRule |
| **Severity** | Warning |
| **Category** | Maintenance |

## Message

> Test patches definition module — patch the consumer instead

## Rationale

Patching the module where a class/function is defined (the definition module) instead of where it is consumed causes subtle issues. If another module imports the target before the patch is applied, the patch won't take effect. The correct pattern is to patch the consumer module's reference.

## Suggestion

Patch where the target is used, not where it is defined

## Examples

### ❌ Bad

```python
from myapp.models import User
from unittest.mock import patch

@patch("myapp.models.User.save")
def test_save():
    user = User()
    user.save()
```

### ✅ Good

```python
from myapp.service import User
from unittest.mock import patch

@patch("myapp.service.User.save")
def test_save():
    user = User()
    user.save()
```
