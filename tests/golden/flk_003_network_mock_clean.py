# Golden corpus: PYTEST-FLK-003 with mock layer — should be suppressed
# expect: PYTEST-BDD-001
# expect: PYTEST-DBC-001
# expect: PYTEST-MNT-002

import httpx
import respx


def test_uses_httpx_with_mock():
    assert True
