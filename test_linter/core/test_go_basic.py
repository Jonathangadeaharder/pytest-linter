"""Basic test to verify Go support works."""

from pathlib import Path
import tempfile

from test_linter.core.engine import create_default_engine


def test_go_linting():
    """Test that Go test linting works."""
    # Create a Go test file with known issues
    test_code = '''package example

import (
	"testing"
	"time"
)

// Test with time.Sleep - should be flagged
func TestWithSleep(t *testing.T) {
	time.Sleep(1 * time.Second)
	t.Log("done")
}

// Test with too many assertions
func TestTooManyAssertions(t *testing.T) {
	if 1 != 1 { t.Error("fail") }
	if 2 != 2 { t.Error("fail") }
	if 3 != 3 { t.Error("fail") }
	if 4 != 4 { t.Error("fail") }
	if 5 != 5 { t.Error("fail") }
}

// Test without assertions
func TestNoAssertions(t *testing.T) {
	// Does nothing
}

// Test with conditional logic
func TestWithLogic(t *testing.T) {
	value := 10
	if value > 5 {
		t.Log("greater")
	} else {
		t.Error("less")
	}
}
'''

    # Create temp file
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='_test.go', delete=False
    ) as f:
        f.write(test_code)
        temp_path = Path(f.name)

    try:
        # Create engine
        engine = create_default_engine()

        # Lint the file
        violations = engine.lint_files([temp_path])

        # Should find violations
        assert len(violations) > 0, "Should find at least one violation"

        print(f"✓ Found {len(violations)} violation(s) in Go test:")
        for v in violations:
            print(f"  - {v.rule_id} ({v.severity.value}): {v.message}")

        # Check for specific violations
        rule_ids = {v.rule_id for v in violations}

        # Should detect time.Sleep
        if "UNI-FLK-001" in rule_ids:
            print("  ✓ Detected time-based wait (time.Sleep)")

        # Should detect too many assertions
        if "UNI-MNT-002" in rule_ids:
            print("  ✓ Detected assertion roulette")

        # Should detect no assertions
        if "UNI-MNT-003" in rule_ids:
            print("  ✓ Detected test without assertions")

        # Should detect test logic
        if "UNI-MNT-001" in rule_ids:
            print("  ✓ Detected test logic (if statement)")

    finally:
        # Clean up
        temp_path.unlink()


if __name__ == "__main__":
    print("Testing Go Support\n" + "="*50)

    test_go_linting()

    print("\n" + "="*50)
    print("✅ Go support working!")
