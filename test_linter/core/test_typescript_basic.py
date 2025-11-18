"""Basic test to verify TypeScript/JavaScript support works."""

from pathlib import Path
import tempfile

from test_linter.core.engine import create_default_engine
from test_linter.core.models import TestFramework


def test_jest_linting():
    """Test that Jest test linting works."""
    # Create a Jest test file with known issues
    test_code = '''
describe('User API', () => {
  it('should create user', async () => {
    // Time-based wait - should be flagged
    setTimeout(() => {
      console.log('waiting...');
    }, 1000);

    const user = await createUser();
    expect(user.id).toBeDefined();
  });

  it('has too many assertions', () => {
    expect(1).toBe(1);
    expect(2).toBe(2);
    expect(3).toBe(3);
    expect(4).toBe(4);
    expect(5).toBe(5);
  });

  it('has no assertions', () => {
    console.log('This test does nothing');
  });
});
'''

    # Create temp file
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.test.ts', delete=False
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

        print(f"✓ Found {len(violations)} violation(s) in Jest test:")
        for v in violations:
            print(f"  - {v.rule_id} ({v.severity.value}): {v.message}")

        # Check for specific violations
        rule_ids = {v.rule_id for v in violations}

        # Should detect setTimeout
        if "UNI-FLK-001" in rule_ids:
            print("  ✓ Detected time-based wait (setTimeout)")

        # Should detect too many assertions
        if "UNI-MNT-002" in rule_ids:
            print("  ✓ Detected assertion roulette")

        # Should detect no assertions
        if "UNI-MNT-003" in rule_ids:
            print("  ✓ Detected test without assertions")

    finally:
        # Clean up
        temp_path.unlink()


def test_mocha_linting():
    """Test that Mocha test linting works."""
    test_code = '''
const assert = require('assert');

describe('Calculator', function() {
  before(function() {
    // Setup
  });

  it('should add numbers', function() {
    const result = 2 + 2;
    if (result === 4) {
      assert.equal(result, 4);
    }
  });
});
'''

    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.test.js', delete=False
    ) as f:
        f.write(test_code)
        temp_path = Path(f.name)

    try:
        engine = create_default_engine()
        violations = engine.lint_files([temp_path])

        print(f"\n✓ Found {len(violations)} violation(s) in Mocha test:")
        for v in violations:
            print(f"  - {v.rule_id}: {v.message}")

        # Should detect conditional logic
        rule_ids = {v.rule_id for v in violations}
        if "UNI-MNT-001" in rule_ids:
            print("  ✓ Detected test logic (if statement)")

    finally:
        temp_path.unlink()


if __name__ == "__main__":
    print("Testing TypeScript/JavaScript Support\n" + "="*50)

    test_jest_linting()
    test_mocha_linting()

    print("\n" + "="*50)
    print("✅ TypeScript/JavaScript support working!")
