"""
Test file in subdirectory that demonstrates fixture shadowing.
"""


def test_using_shadowed_fixture(used_fixture):
    """This test uses the shadowed fixture from local conftest.

    The linter should warn about fixture shadowing (PYTEST-FIX-004).
    """
    assert "shadowed" in used_fixture


def test_using_local_fixture(local_fixture):
    """This test uses a fixture only defined locally."""
    assert local_fixture["local"] is True
