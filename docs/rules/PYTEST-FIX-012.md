# PYTEST-FIX-012 — FixtureNameShadowsBuiltinRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FIX-012` |
| **Name** | FixtureNameShadowsBuiltinRule |
| **Severity** | Warning |
| **Category** | Fixture |

## Message

> Fixture '{fixture}' shadows a Python builtin or pytest hook

## Rationale

Fixture names that shadow Python builtins (`list`, `dict`, `id`, `type`, `open`) or pytest hooks (`tmp_path`, `capsys`, `request`) cause confusing errors and make the test harder to understand.

## Suggestion

Rename the fixture to avoid shadowing built-in names

## Examples

### ❌ Bad

```python
@pytest.fixture
def list():
    return [1, 2, 3]
```

### ✅ Good

```python
@pytest.fixture
def item_list():
    return [1, 2, 3]
```
