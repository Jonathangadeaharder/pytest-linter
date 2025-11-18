import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.*;
import java.io.File;

class JavaSampleTest {

    @BeforeEach
    void setUp() {
        // Setup code
    }

    @AfterEach
    void tearDown() {
        // Cleanup code
    }

    // Good: Simple test with one assertion
    @Test
    void testAddition() {
        int result = 2 + 2;
        assertEquals(4, result);
    }

    // BAD: Test with Thread.sleep
    @Test
    void testWithSleep() throws InterruptedException {
        // Time-based wait - should be flagged
        Thread.sleep(1000);
        assertTrue(true);
    }

    // BAD: Test with too many assertions
    @Test
    void testTooManyAssertions() {
        assertEquals(1, 1);
        assertEquals(2, 2);
        assertEquals(3, 3);
        assertEquals(4, 4);
        assertEquals(5, 5);
    }

    // BAD: Test without assertions
    @Test
    void testNoAssertions() {
        // This test does nothing
        int x = 2 + 2;
    }

    // BAD: Test with conditional logic
    @Test
    void testWithLogic() {
        int value = 10;
        if (value > 5) {
            assertTrue(value > 5);
        } else {
            assertTrue(value <= 5);
        }
    }

    // BAD: Test with file I/O
    @Test
    void testFileIO() {
        // Mystery Guest - file I/O without proper setup
        File file = new File("test.txt");
        assertTrue(file.exists());
    }
}
