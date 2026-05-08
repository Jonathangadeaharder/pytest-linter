# Golden corpus: PYTEST-MOC-004 MockRatioBudgetRule
# expect: PYTEST-MOC-004
# expect: PYTEST-BDD-001
# expect: PYTEST-DBC-001
# expect: PYTEST-MNT-002

from unittest.mock import MagicMock, patch


@patch("myapp.service.fetch")
@patch("myapp.service.process")
@patch("myapp.service.validate")
@patch("myapp.service.save")
def test_over_mocked():
    mock_fetch = MagicMock()
    mock_process = MagicMock()
    mock_validate = MagicMock()
    mock_save = MagicMock()
    mock_fetch.return_value = "data"
    mock_process.return_value = "processed"
    mock_validate.return_value = True
    mock_save.return_value = None
    assert True
