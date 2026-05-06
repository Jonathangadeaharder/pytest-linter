# PYTEST-FIX-013 — AutouseCascadeDepthRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FIX-013` |
| **Name** | AutouseCascadeDepthRule |
| **Severity** | Warning |
| **Category** | Fixture |

## Message

> Autouse fixture '{fixture}' has dependency cascade depth of {depth} (> 3)

## Rationale

Deep fixture dependency chains with `autouse=True` create hidden, complex setup graphs that are hard to debug. When an autouse fixture depends on other fixtures that depend on more fixtures, understanding test setup requires tracing many levels.

## Suggestion

Reduce fixture dependency chain or remove autouse

## Examples

### ❌ Bad

```python
@pytest.fixture(autouse=True)
def base():
    return {'base': True}

@pytest.fixture(autouse=True)
def layer1(base):
    return {**base, 'l1': True}

@pytest.fixture(autouse=True)
def layer2(layer1):
    return {**layer1, 'l2': True}

@pytest.fixture(autouse=True)
def layer3(layer2):
    return {**layer2, 'l3': True}
```

### ✅ Good

```python
@pytest.fixture
def env():
    return {'base': True, 'l1': True, 'l2': True, 'l3': True}

def test_env(env):
    assert env['base']
```
