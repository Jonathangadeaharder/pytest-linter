# Golden corpus: PYTEST-INF-002 LiveSuiteUnmarkedRule
# expect: PYTEST-FLK-003
# expect: PYTEST-INF-001
# expect: PYTEST-INF-002
# expect: PYTEST-BDD-001
# expect: PYTEST-DBC-001

import requests


def test_live_unmarked():
    resp = requests.get("https://example.com")
    assert resp.status_code == 200
