# PYTEST-DBC-001 — NoContractHintRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-DBC-001` |
| **Name** | NoContractHintRule |
| **Severity** | Info |
| **Category** | Enhancement |

## Message

> Test '{test}' only tests the happy path — consider adding error/edge case coverage

## Rationale

Design-by-contract testing suggests covering both happy paths and error/edge cases. Tests that only assert positive outcomes miss important failure modes.

## Suggestion

Add tests for error conditions using pytest.raises

## Examples

### ❌ Bad

```python
def test_parse():
    result = parse('valid json')
    assert result.success
```

### ✅ Good

```python
def test_parse_valid():
    result = parse('valid json')
    assert result.success

def test_parse_invalid():
    with pytest.raises(ParseError):
        parse('invalid json')
```
