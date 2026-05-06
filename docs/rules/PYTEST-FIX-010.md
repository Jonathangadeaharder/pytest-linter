# PYTEST-FIX-010 — ModuleScopeFixtureMutatedRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FIX-010` |
| **Name** | ModuleScopeFixtureMutatedRule |
| **Severity** | Error |
| **Category** | Fixture |

## Message

> Test '{test}' mutates module/session-scoped fixture '{fixture}' — causes cross-test contamination

## Rationale

Mutating a module or session-scoped fixture causes state to leak between tests. Test B sees the state left by test A, creating order-dependent failures that are hard to debug.

## Suggestion

Use function-scoped fixture or copy the value before mutation

## Examples

### ❌ Bad

```python
@pytest.fixture(scope='module')
def config():
    return {'debug': True}

def test_a(config):
    config['debug'] = False

def test_b(config):
    # config['debug'] is now False — contaminated by test_a
```

### ✅ Good

```python
@pytest.fixture(scope='module')
def config():
    return {'debug': True}

def test_a(config):
    test_cfg = config.copy()
    test_cfg['debug'] = False
    assert not test_cfg['debug']
```
