# PYTEST-FIX-009 — FixtureOverlyBroadScopeRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FIX-009` |
| **Name** | FixtureOverlyBroadScopeRule |
| **Severity** | Warning |
| **Category** | Fixture |

## Message

> Fixture '{fixture}' has scope '{scope}' but no expensive setup — consider using function scope for better isolation

## Rationale

Broad-scoped fixtures (module, session) are intended for expensive setup (DB connections, large fixtures). Without expensive setup, function scope provides better test isolation at negligible cost.

## Suggestion

Change fixture scope to 'function'

## Examples

### ❌ Bad

```python
@pytest.fixture(scope='module')
def simple_value():
    return 42
```

### ✅ Good

```python
@pytest.fixture
def simple_value():
    return 42
```
