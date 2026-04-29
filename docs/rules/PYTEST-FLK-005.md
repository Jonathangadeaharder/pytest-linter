# PYTEST-FLK-005 — MysteryGuestRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FLK-005` |
| **Name** | MysteryGuestRule |
| **Severity** | Warning |
| **Category** | Flakiness |

## Message

> Test '{test}' may be a Mystery Guest — uses file I/O without temp fixtures

## Rationale

A Mystery Guest is a test that uses external data (files, databases) that isn't visible in the test itself. This makes tests hard to understand and debug.

## Suggestion

Use tmp_path fixture and make test data explicit

## Examples

### ❌ Bad

```python
def test_parse():
    with open('fixtures/data.csv') as f:
        result = parse(f)
    assert result
```

### ✅ Good

```python
def test_parse(tmp_path):
    csv = tmp_path / 'data.csv'
    csv.write_text('a,b\n1,2')
    result = parse(csv.read_text())
    assert result
```
