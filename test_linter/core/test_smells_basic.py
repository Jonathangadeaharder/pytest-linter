"""Basic test to verify the multi-language architecture works."""

from pathlib import Path
import tempfile

from test_linter.core.engine import create_default_engine
from test_linter.core.models import LanguageType, TestFramework


def test_basic_python_linting():
    """Test that basic Python linting works with the new architecture."""
    # Create a test file with a known issue
    test_code = '''
import time

def test_example():
    """Test with time.sleep - should be flagged."""
    time.sleep(1)
    assert True
'''

    # Create temp file
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='_test.py', delete=False
    ) as f:
        f.write(test_code)
        temp_path = Path(f.name)

    try:
        # Create engine
        engine = create_default_engine()

        # Lint the file
        violations = engine.lint_files([temp_path])

        # Should find at least the time-sleep violation
        assert len(violations) > 0, "Should find at least one violation"

        # Check for time-sleep rule
        time_sleep_violations = [
            v for v in violations if v.rule_id == "UNI-FLK-001"
        ]
        assert (
            len(time_sleep_violations) > 0
        ), "Should find time-sleep violation"

        print(f"✓ Found {len(violations)} violation(s)")
        for v in violations:
            print(f"  - {v.rule_id}: {v.message}")

    finally:
        # Clean up
        temp_path.unlink()


if __name__ == "__main__":
    test_basic_python_linting()
    print("\n✅ Basic architecture test passed!")
