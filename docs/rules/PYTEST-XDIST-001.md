# PYTEST-XDIST-001 — XdistSharedStateRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-XDIST-001` |
| **Name** | XdistSharedStateRule |
| **Severity** | Warning |
| **Category** | Flakiness |

## Message

> Session-scoped fixture '{fixture}' returns mutable state that is modified by test '{test}' — unsafe for xdist

## Rationale

When using `pytest-xdist` for parallel test execution, session-scoped fixtures with mutable state can be corrupted by concurrent test modifications, causing flaky failures.

## Suggestion

Use function scope or return immutable values

## Examples

### ❌ Bad

```python
@pytest.fixture(scope='session')
def shared_list():
    return []

def test_a(shared_list):
    shared_list.append(1)
    assert len(shared_list) == 1
```

### ✅ Good

```python
@pytest.fixture
def fresh_list():
    return []

def test_a(fresh_list):
    fresh_list.append(1)
    assert len(fresh_list) == 1
```
