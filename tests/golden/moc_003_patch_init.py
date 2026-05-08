# Golden corpus: PYTEST-MOC-003 PatchInitBypassRule
# expect: PYTEST-MOC-003
# expect: PYTEST-BDD-001
# expect: PYTEST-MNT-004

from unittest.mock import patch


@patch("myapp.models.User.__init__")
def test_patches_init():
    pass
