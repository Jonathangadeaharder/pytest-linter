# PYTEST-VAL-001 — InlineSchemaRedeclaredRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-VAL-001` |
| **Name** | InlineSchemaRedeclaredRule |
| **Severity** | Info |
| **Category** | Enhancement |

## Message

> Inline schema redeclared across tests — extract to a fixture

## Rationale

When the same inline dict/list literal appears in multiple tests, changes to the schema require updating every test. Extracting shared test data into a fixture or conftest centralizes the definition and reduces maintenance burden.

## Suggestion

Extract shared test data into a fixture or conftest

## Examples

### ❌ Bad

```python
def test_create():
    order = {"customer_id": 1, "items": ["book"], "total": 29.99}
    assert create_order(order)["status"] == "ok"

def test_update():
    order = {"customer_id": 1, "items": ["book"], "total": 29.99}
    order["total"] = 39.99
    assert update_order(order)["status"] == "ok"
```

### ✅ Good

```python
@pytest.fixture
def base_order():
    return {"customer_id": 1, "items": ["book"], "total": 29.99}

def test_create(base_order):
    assert create_order(base_order)["status"] == "ok"

def test_update(base_order):
    order = {**base_order, "total": 39.99}
    assert update_order(order)["status"] == "ok"
```
