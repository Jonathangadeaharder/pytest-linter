# Golden corpus: patterns from hypothesis test suite
# Each `# expect: RULE-ID` marks a line where the linter should report that rule.

import pytest


# --- PBT-001: property-based test hint (>3 parametrize cases) ---
@pytest.mark.parametrize("x", [1, 2, 3, 4])  # expect: PYTEST-PBT-001
def test_lots_of_vals(x):
    assert x > 0


# --- PARAM-001: single parametrize case ---
@pytest.mark.parametrize("x", [42])  # expect: PYTEST-PARAM-001
def test_single_case(x):
    assert x == 42


# --- PARAM-002: duplicate parametrize values ---
@pytest.mark.parametrize("x", [1, 2, 2, 3])  # expect: PYTEST-PARAM-002
def test_dup(x):  # expect: PYTEST-MNT-015
    assert x > 0


# --- MNT-002: magic assert ---
def test_magic():
    assert True  # expect: PYTEST-MNT-002


# --- MNT-003: suboptimal assert ---
def test_suboptimal():
    assert len(items) == 3  # expect: PYTEST-MNT-003


# --- FLK-002: file I/O without tmp_path ---
def test_file_io():
    f = open("data.txt")  # expect: PYTEST-FLK-002
    content = f.read()
    f.close()
    assert content


# --- FLK-005: mystery guest ---
# Same file I/O pattern triggers mystery guest too
# expect: PYTEST-FLK-005


# --- BDD-001: no Gherkin docstring ---
def test_plain():  # expect: PYTEST-BDD-001
    assert True


# --- DBC-001: happy-path only ---
def test_happy_only():  # expect: PYTEST-DBC-001
    assert 1 + 1 == 2


# --- Clean: parametrize with good count ---
@pytest.mark.parametrize("x", [1, 2, 3])
def test_good_param(x):
    assert x > 0
