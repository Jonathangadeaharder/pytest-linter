# Golden corpus: PYTEST-INF-004 MacOsCopyArtefactRule
# expect: PYTEST-INF-004
# expect: PYTEST-BDD-001
# expect: PYTEST-DBC-001
# expect: PYTEST-MNT-002

import shutil
from pathlib import Path


def test_uses_shutil_copy():
    shutil.copy("source.txt", "dest.txt")
    assert True


def test_uses_finder_artefact_filename():
    content = Path("data 2.txt").read_text()
    assert content
