# Golden corpus: PYTEST-VAL-001 InlineSchemaRedeclaredRule
# expect: PYTEST-VAL-001
# expect: PYTEST-BDD-001
# expect: PYTEST-DBC-001


def test_create_order():
    order = {"customer_id": 1, "items": ["book"], "total": 29.99}
    assert order["total"] == 29.99


def test_update_order():
    order = {"customer_id": 1, "items": ["book"], "total": 29.99}
    order["total"] = 39.99
    assert order["total"] == 39.99
