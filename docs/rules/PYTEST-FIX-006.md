# PYTEST-FIX-006 — StatefulSessionFixtureRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FIX-006` |
| **Name** | StatefulSessionFixtureRule |
| **Severity** | Warning |
| **Category** | Fixture |

## Message

> Session-scoped fixture '{fixture}' returns mutable state

## Rationale

Session-scoped fixtures that return mutable objects (lists, dicts) can accumulate state across tests, causing order-dependent failures.

## Suggestion

Return immutable data or use a factory pattern

## Examples

### ❌ Bad

```python
@pytest.fixture(scope='session')
def cache():
    return {}
```

### ✅ Good

```python
@pytest.fixture(scope='session')
def cache_factory():
    def _cache():
        return {}
    return _cache

def test_a(cache_factory):
    c = cache_factory()
    c['key'] = 'value'
```
