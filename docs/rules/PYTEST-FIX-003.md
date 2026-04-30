# PYTEST-FIX-003 — InvalidScopeRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FIX-003` |
| **Name** | InvalidScopeRule |
| **Severity** | Error |
| **Category** | Fixture |

## Message

> Fixture '{fixture}' (scope={scope}) depends on '{dep}' (scope={dep_scope}) — fixture scope must not exceed dependency scope

## Rationale

A fixture with a broader scope than its dependency will fail because the dependency may be torn down before the dependent fixture is done. Scope hierarchy: function < class < module < package < session.

## Suggestion

Reduce scope of '{fixture}' to match or be narrower than '{dep}'

## Examples

### ❌ Bad

```python
@pytest.fixture(scope='function')
def config():
    return load_config()

@pytest.fixture(scope='session')
def db(config):
    return Database(config)
```

### ✅ Good

```python
@pytest.fixture(scope='session')
def config():
    return load_config()

@pytest.fixture(scope='session')
def db(config):
    return Database(config)
```
