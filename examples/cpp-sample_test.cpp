#include <gtest/gtest.h>
#include <thread>
#include <chrono>
#include <fstream>

// Good: Simple test with one assertion
TEST(MathTest, Addition) {
    int result = 2 + 2;
    EXPECT_EQ(4, result);
}

// BAD: Test with sleep
TEST(FlakinesTest, WithSleep) {
    // Time-based wait - should be flagged
    std::this_thread::sleep_for(std::chrono::seconds(1));
    EXPECT_TRUE(true);
}

// BAD: Test with too many assertions
TEST(AssertionTest, TooMany) {
    EXPECT_EQ(1, 1);
    EXPECT_EQ(2, 2);
    EXPECT_EQ(3, 3);
    EXPECT_EQ(4, 4);
    EXPECT_EQ(5, 5);
}

// BAD: Test without assertions
TEST(EmptyTest, NoAssertions) {
    // This test does nothing
    int x = 2 + 2;
}

// BAD: Test with conditional logic
TEST(LogicTest, WithConditional) {
    int value = 10;
    if (value > 5) {
        EXPECT_GT(value, 5);
    } else {
        EXPECT_LT(value, 5);
    }
}

// BAD: Test with file I/O
TEST(FileTest, WithIO) {
    // Mystery Guest - file I/O without proper setup
    std::ifstream file("test.txt");
    EXPECT_TRUE(file.is_open());
}

// Test fixture example
class MyTestFixture : public ::testing::Test {
 protected:
    void SetUp() override {
        // Setup code
    }

    void TearDown() override {
        // Cleanup code
    }
};

// Using fixture
TEST_F(MyTestFixture, UsingFixture) {
    EXPECT_TRUE(true);
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
