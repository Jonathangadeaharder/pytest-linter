# Golden corpus: PYTEST-INF-001 NetworkBanMissingRule
# expect: PYTEST-FLK-003
# expect: PYTEST-INF-001
# expect: PYTEST-INF-002

import requests


def test_live_call():
    resp = requests.get("https://example.com")
    assert resp.status_code == 200
