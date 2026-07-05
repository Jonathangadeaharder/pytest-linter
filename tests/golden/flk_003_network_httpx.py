# Golden corpus: PYTEST-FLK-003 NetworkImportRule
# Fixture imports httpx (a network library) without a mock layer and without
# the network mark, so both PYTEST-FLK-003 (network import) and PYTEST-INF-001
# (no mark and no mock layer) should fire.
# expect: PYTEST-FLK-003
# expect: PYTEST-INF-001
# expect: PYTEST-BDD-001
# expect: PYTEST-DBC-001
# expect: PYTEST-MNT-002

import httpx


def test_httpx_import_flagged():
    assert True
