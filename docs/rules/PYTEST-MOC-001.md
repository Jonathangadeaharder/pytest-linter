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

Patching the module where a class/function is defined instead of where it is consumed causes subtle issues. If a consumer module (e.g., `myapp.service`) imports the target before the patch is applied, the patch won't take effect because the consumer holds a cached reference. The correct pattern is to patch the consumer module's reference.

## Suggestion

Patch where the target is used, not where it is defined

## Examples

### ❌ Bad

```python
# myapp/service.py does: from myapp.models import User
from myapp.service import create_user
from unittest.mock import patch

@patch("myapp.models.User.save")  # patches definition — won't affect myapp.service's cached reference
def test_save():
    create_user()  # still calls the real User.save
```

### ✅ Good

```python
# myapp/service.py does: from myapp.models import User
from myapp.service import create_user
from unittest.mock import patch

@patch("myapp.service.User.save")  # patches consumer — intercepts the cached reference
def test_save():
    create_user()  # calls the mocked User.save
```
