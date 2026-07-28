# Golden corpus: PYTEST-MOC-001 PatchTargetingDefinitionModuleRule
# expect: PYTEST-MOC-001
# expect: PYTEST-MNT-004

from unittest.mock import patch

# Importing the definition module that the patch targets — this is what
# makes PYTEST-MOC-001 fire (the rule triggers when the patched definition
# module is imported into the test file).
import myapp.models
from myapp.service import create_user


@patch("myapp.models.User.save")
def test_patches_definition_module():
    create_user()
