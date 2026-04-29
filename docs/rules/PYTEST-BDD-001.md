# PYTEST-BDD-001 — BddMissingScenarioRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-BDD-001` |
| **Name** | BddMissingScenarioRule |
| **Severity** | Info |
| **Category** | Enhancement |

## Message

> Test '{test}' lacks a Gherkin-style docstring scenario

## Rationale

Tests with Gherkin-style docstrings (Given/When/Then) serve as living documentation and make test intent clear without reading implementation details.

## Suggestion

Add a docstring with Given/When/Then structure

## Examples

### ❌ Bad

```python
def test_login():
    user = login('admin', 'pass')
    assert user.authenticated
```

### ✅ Good

```python
def test_login():
    """Given a valid user
    When logging in
    Then the user is authenticated"""
    user = login('admin', 'pass')
    assert user.authenticated
```
