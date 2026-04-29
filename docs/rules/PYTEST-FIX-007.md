# PYTEST-FIX-007 — FixtureMutationRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FIX-007` |
| **Name** | FixtureMutationRule |
| **Severity** | Warning |
| **Category** | Fixture |

## Message

> Test '{test}' mutates fixture '{fixture}' which may affect other tests

## Rationale

When a test mutates a fixture's return value (especially shared-scope fixtures), subsequent tests may see the modified state, leading to order-dependent failures.

## Suggestion

Create a fresh copy of the fixture value before modifying it

## Examples

### ❌ Bad

```python
@pytest.fixture
def config():
    return {'debug': True}

def test_a(config):
    config['debug'] = False
    assert not config['debug']
```

### ✅ Good

```python
@pytest.fixture
def config():
    return {'debug': True}

def test_a(config):
    test_config = config.copy()
    test_config['debug'] = False
    assert not test_config['debug']
```
