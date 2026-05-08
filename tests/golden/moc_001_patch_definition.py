# Golden corpus: PYTEST-MOC-001 PatchTargetingDefinitionModuleRule
# expect: PYTEST-MOC-001
# expect: PYTEST-BDD-001
# expect: PYTEST-MNT-004

from myapp.models import User
from myapp.service import create_user
from unittest.mock import patch


@patch("myapp.models.User.save")
def test_patches_definition_module():
    create_user()
