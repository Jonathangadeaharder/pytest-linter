# PYTEST-FIX-005 — UnusedFixtureRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FIX-005` |
| **Name** | UnusedFixtureRule |
| **Severity** | Warning |
| **Category** | Fixture |

## Message

> Fixture '{fixture}' is not used by any test or fixture

## Rationale

Unused fixtures add dead code to the test suite, making it harder to maintain. They may also perform unnecessary setup/teardown work.

## Suggestion

Remove the unused fixture or reference it explicitly from tests/other fixtures

## Examples

### ❌ Bad

```python
@pytest.fixture
def legacy_db():
    # no test uses this
    return Database('legacy')
```

### ✅ Good

```python
# Remove the fixture entirely, or add:
def test_legacy(legacy_db):
    assert legacy_db.is_connected()
```
