# PYTEST-MOC-004 — MockRatioBudgetRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-MOC-004` |
| **Name** | MockRatioBudgetRule |
| **Severity** | Info |
| **Category** | Enhancement |

## Message

> Test has mock-to-assertion ratio exceeding 3:1 — over budget

## Rationale

Tests with excessive mocking relative to assertions test the mocking framework rather than production code. A high mock-to-assertion ratio indicates the test verifies mock interactions instead of real behavior.

## Suggestion

Reduce mock count or add more state assertions

## Examples

### ❌ Bad

```python
@patch("service.fetch")
@patch("service.process")
@patch("service.validate")
@patch("service.save")
def test_pipeline(mock_save, mock_validate, mock_process, mock_fetch):
    mock_fetch.return_value = "data"
    mock_process.return_value = "processed"
    mock_validate.return_value = True
    mock_save.return_value = None
    assert True  # only 1 assertion for 4 mocks
```

### ✅ Good

```python
def test_pipeline(integration_db):
    result = pipeline.run(fetch=True)
    assert result.status == "saved"
    assert integration_db.count("records") == 1
```
