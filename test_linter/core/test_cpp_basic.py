"""Basic test to verify C++ support works."""

from pathlib import Path
import tempfile

from test_linter.core.engine import create_default_engine


def test_cpp_googletest_linting():
    """Test that GoogleTest linting works."""
    test_code = '''#include <gtest/gtest.h>
#include <thread>
#include <chrono>

TEST(FlakinesTest, WithSleep) {
    std::this_thread::sleep_for(std::chrono::seconds(1));
    EXPECT_TRUE(true);
}

TEST(AssertionTest, TooMany) {
    EXPECT_EQ(1, 1);
    EXPECT_EQ(2, 2);
    EXPECT_EQ(3, 3);
    EXPECT_EQ(4, 4);
    EXPECT_EQ(5, 5);
}

TEST(EmptyTest, NoAssertions) {
    int x = 2 + 2;
}

TEST(LogicTest, WithConditional) {
    int value = 10;
    if (value > 5) {
        EXPECT_GT(value, 5);
    }
}
'''

    with tempfile.NamedTemporaryFile(
        mode='w', suffix='_test.cpp', delete=False
    ) as f:
        f.write(test_code)
        temp_path = Path(f.name)

    try:
        engine = create_default_engine()
        violations = engine.lint_files([temp_path])

        assert len(violations) > 0, "Should find at least one violation"

        print(f"✓ Found {len(violations)} violation(s) in GoogleTest:")
        for v in violations:
            print(f"  - {v.rule_id} ({v.severity.value}): {v.message}")

        rule_ids = {v.rule_id for v in violations}

        if "UNI-FLK-001" in rule_ids:
            print("  ✓ Detected time-based wait (std::this_thread::sleep_for)")
        if "UNI-MNT-002" in rule_ids:
            print("  ✓ Detected assertion roulette")
        if "UNI-MNT-003" in rule_ids:
            print("  ✓ Detected test without assertions")
        if "UNI-MNT-001" in rule_ids:
            print("  ✓ Detected test logic")

    finally:
        temp_path.unlink()


if __name__ == "__main__":
    print("Testing C++ Support\n" + "="*50)
    test_cpp_googletest_linting()
    print("\n" + "="*50)
    print("✅ C++ support working!")
