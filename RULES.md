# Test Linter Rules Reference

Comprehensive documentation of all test smell detection rules across 7 programming languages.

## Table of Contents

- [Universal Rules Overview](#universal-rules-overview)
- [UNI-FLK-001: Time-Based Waits](#uni-flk-001-time-based-waits)
- [UNI-FLK-002: Mystery Guest](#uni-flk-002-mystery-guest)
- [UNI-FLK-003: Network Dependencies](#uni-flk-003-network-dependencies)
- [UNI-MNT-001: Test Logic](#uni-mnt-001-test-logic)
- [UNI-MNT-002: Assertion Roulette](#uni-mnt-002-assertion-roulette)
- [UNI-MNT-003: No Assertions](#uni-mnt-003-no-assertions)
- [UNI-FIX-001: Fixture Scope Mismatch](#uni-fix-001-fixture-scope-mismatch)
- [Configuration](#configuration)

---

## Universal Rules Overview

All rules work consistently across all 7 supported languages:

| Rule ID | Category | Severity | Description |
|---------|----------|----------|-------------|
| UNI-FLK-001 | Flakiness | Warning | Time-based waits (sleep functions) |
| UNI-FLK-002 | Flakiness | Warning | File I/O without resource fixtures |
| UNI-FLK-003 | Flakiness | Warning | Network imports/dependencies |
| UNI-MNT-001 | Maintenance | Warning | Conditional logic in tests |
| UNI-MNT-002 | Maintenance | Warning | Too many assertions (>3 default) |
| UNI-MNT-003 | Maintenance | Error | Tests without assertions |
| UNI-FIX-001 | Fixture | Error | Invalid fixture scope dependencies |

---

## UNI-FLK-001: Time-Based Waits

### Description
Detects time-based wait functions (sleep, setTimeout, etc.) that make tests flaky and unnecessarily slow.

### Category
Flakiness

### Severity
Warning

### Why This Matters
- **Flakiness**: Time-based waits are timing-dependent and unreliable
- **Slow tests**: Fixed waits add unnecessary time even when operations complete quickly
- **Maintenance**: Hard to tune (too short = flaky, too long = slow)

### Detected Patterns by Language

| Language | Sleep Functions |
|----------|-----------------|
| Python | `time.sleep`, `sleep` |
| TypeScript/JavaScript | `setTimeout`, `setInterval` |
| Go | `time.Sleep`, `Sleep` |
| C++ | `std::this_thread::sleep_for`, `sleep`, `usleep` |
| Java | `Thread.sleep` |
| Rust | `thread::sleep`, `std::thread::sleep` |
| C# | `Thread.Sleep`, `Task.Delay` |

### Examples

#### ❌ Bad: Python (pytest)
```python
def test_async_operation():
    trigger_async_task()
    time.sleep(5)  # Flaky! What if task takes 5.1 seconds?
    assert task_completed()
```

#### ✅ Good: Python (pytest)
```python
def test_async_operation():
    trigger_async_task()
    # Poll with timeout
    for _ in range(50):  # 5 second timeout
        if task_completed():
            break
        time.sleep(0.1)
    else:
        pytest.fail("Task did not complete in time")
    assert task_completed()
```

#### ❌ Bad: TypeScript (Jest)
```typescript
test('async operation', async () => {
    triggerTask();
    await new Promise(resolve => setTimeout(resolve, 1000));  // Flaky!
    expect(isCompleted()).toBe(true);
});
```

#### ✅ Good: TypeScript (Jest)
```typescript
test('async operation', async () => {
    triggerTask();
    // Use jest's waitFor or proper async/await
    await waitFor(() => expect(isCompleted()).toBe(true), {
        timeout: 5000
    });
});
```

#### ❌ Bad: Go (testing)
```go
func TestAsyncOperation(t *testing.T) {
    triggerTask()
    time.Sleep(1 * time.Second)  // Flaky!
    assert.True(t, taskCompleted())
}
```

#### ✅ Good: Go (testing)
```go
func TestAsyncOperation(t *testing.T) {
    triggerTask()
    // Use channels or context with timeout
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    if err := waitForCompletion(ctx); err != nil {
        t.Fatal("Task did not complete:", err)
    }
    assert.True(t, taskCompleted())
}
```

#### ❌ Bad: C++ (GoogleTest)
```cpp
TEST(AsyncTest, Operation) {
    trigger_task();
    std::this_thread::sleep_for(std::chrono::seconds(1));  // Flaky!
    EXPECT_TRUE(task_completed());
}
```

#### ✅ Good: C++ (GoogleTest)
```cpp
TEST(AsyncTest, Operation) {
    trigger_task();
    // Use condition variable or future
    std::future<void> result = std::async(std::launch::async, wait_for_task);
    auto status = result.wait_for(std::chrono::seconds(5));
    ASSERT_EQ(status, std::future_status::ready);
    EXPECT_TRUE(task_completed());
}
```

### Exceptions
- Sleep in test setup/teardown (outside test body) is generally acceptable
- Deliberate delays for rate limiting tests (should be commented)
- Integration tests that genuinely need to wait for external systems (consider mocking instead)

---

## UNI-FLK-002: Mystery Guest

### Description
Detects file I/O operations without using temporary file fixtures, making tests depend on external file state.

### Category
Flakiness

### Severity
Warning

### Why This Matters
- **Flakiness**: Tests depend on external file system state
- **Isolation**: Tests can interfere with each other
- **Cleanup**: Files may be left behind after test failures
- **Parallelization**: Can't run tests in parallel safely

### Detected Patterns by Language

| Language | File I/O Functions |
|----------|-------------------|
| Python | `open()`, `Path.open()`, `Path.read_text()` |
| TypeScript/JavaScript | `fs.readFile`, `fs.writeFile`, `fs.readFileSync` |
| Go | `os.Open`, `os.Create`, `ioutil.ReadFile` |
| C++ | `std::ifstream`, `std::ofstream`, `fopen` |
| Java | `FileInputStream`, `FileOutputStream`, `Files.readAllBytes` |
| Rust | `File::open`, `fs::read`, `fs::write` |
| C# | `File.Open`, `File.ReadAllText`, `StreamReader` |

### Examples

#### ❌ Bad: Python (pytest)
```python
def test_config_parsing():
    # Depends on actual file!
    with open('config.json') as f:
        config = json.load(f)
    assert config['debug'] is False
```

#### ✅ Good: Python (pytest)
```python
def test_config_parsing(tmp_path):
    # Use pytest's tmp_path fixture
    config_file = tmp_path / "config.json"
    config_file.write_text('{"debug": false}')

    with open(config_file) as f:
        config = json.load(f)
    assert config['debug'] is False
```

#### ❌ Bad: TypeScript (Jest)
```typescript
test('reads config', () => {
    const config = fs.readFileSync('config.json', 'utf-8');
    expect(JSON.parse(config).debug).toBe(false);
});
```

#### ✅ Good: TypeScript (Jest)
```typescript
test('reads config', () => {
    // Use in-memory mock or temp directory
    jest.mock('fs');
    const fs = require('fs');
    fs.readFileSync.mockReturnValue('{"debug": false}');

    const config = fs.readFileSync('config.json', 'utf-8');
    expect(JSON.parse(config).debug).toBe(false);
});
```

#### ❌ Bad: Go (testing)
```go
func TestConfigParsing(t *testing.T) {
    data, _ := os.ReadFile("config.json")  // Mystery Guest!
    var config Config
    json.Unmarshal(data, &config)
    assert.False(t, config.Debug)
}
```

#### ✅ Good: Go (testing)
```go
func TestConfigParsing(t *testing.T) {
    // Use t.TempDir() for temporary files
    tmpDir := t.TempDir()
    configPath := filepath.Join(tmpDir, "config.json")
    os.WriteFile(configPath, []byte(`{"debug": false}`), 0644)

    data, _ := os.ReadFile(configPath)
    var config Config
    json.Unmarshal(data, &config)
    assert.False(t, config.Debug)
}
```

### Exceptions
- Reading test fixtures/data from `testdata/` directory (Go convention)
- Reading immutable reference data
- Tests explicitly testing file I/O functionality

---

## UNI-FLK-003: Network Dependencies

### Description
Detects imports of network libraries, indicating tests may depend on external network services.

### Category
Flakiness

### Severity
Warning

### Why This Matters
- **Flakiness**: External services may be unavailable
- **Slow**: Network calls add latency
- **Cost**: May hit rate limits or incur charges
- **Isolation**: Tests should be self-contained

### Detected Patterns by Language

| Language | Network Imports |
|----------|-----------------|
| Python | `requests`, `urllib`, `httpx`, `aiohttp` |
| TypeScript/JavaScript | `http`, `https`, `axios`, `fetch`, `node-fetch` |
| Go | `net/http`, `http`, `net` |
| C++ | `<curl/curl.h>`, `<boost/asio.hpp>` |
| Java | `java.net.http`, `HttpClient`, `HttpURLConnection` |
| Rust | `reqwest`, `hyper`, `ureq` |
| C# | `System.Net.Http`, `HttpClient`, `WebClient` |

### Examples

#### ❌ Bad: Python (pytest)
```python
import requests

def test_api_endpoint():
    response = requests.get('https://api.example.com/users')  # Flaky!
    assert response.status_code == 200
```

#### ✅ Good: Python (pytest)
```python
from unittest.mock import Mock, patch

def test_api_endpoint():
    with patch('requests.get') as mock_get:
        mock_get.return_value = Mock(status_code=200)
        response = requests.get('https://api.example.com/users')
        assert response.status_code == 200
```

#### ❌ Bad: TypeScript (Jest)
```typescript
import axios from 'axios';

test('fetches users', async () => {
    const response = await axios.get('https://api.example.com/users');
    expect(response.status).toBe(200);
});
```

#### ✅ Good: TypeScript (Jest)
```typescript
import axios from 'axios';

jest.mock('axios');

test('fetches users', async () => {
    (axios.get as jest.Mock).mockResolvedValue({ status: 200, data: [] });
    const response = await axios.get('https://api.example.com/users');
    expect(response.status).toBe(200);
});
```

#### ❌ Bad: Java (JUnit 5)
```java
import java.net.http.HttpClient;

@Test
void testApiEndpoint() throws Exception {
    HttpClient client = HttpClient.newHttpClient();
    // Network call!
    HttpResponse<String> response = client.send(request, BodyHandlers.ofString());
    assertEquals(200, response.statusCode());
}
```

#### ✅ Good: Java (JUnit 5)
```java
@Test
void testApiEndpoint() {
    // Use MockWebServer or WireMock
    HttpClient mockClient = mock(HttpClient.class);
    when(mockClient.send(any(), any())).thenReturn(
        HttpResponse.of(200, "[]")
    );

    HttpResponse<String> response = mockClient.send(request, BodyHandlers.ofString());
    assertEquals(200, response.statusCode());
}
```

### Exceptions
- Integration tests explicitly testing network behavior
- Tests using localhost servers (e.g., WireMock, TestContainers)
- End-to-end tests (should be clearly marked)

---

## UNI-MNT-001: Test Logic

### Description
Detects conditional logic (if, for, while) in test bodies, making tests harder to understand and maintain.

### Category
Maintenance

### Severity
Warning

### Why This Matters
- **Clarity**: Tests should follow Arrange-Act-Assert pattern
- **Debugging**: Conditional logic makes failures harder to diagnose
- **Coverage**: Logic in tests may need its own tests
- **Complexity**: Tests should be simple and obvious

### Detected Patterns by Language

| Language | Conditional Keywords |
|----------|---------------------|
| Python | `if`, `for`, `while`, `match` |
| TypeScript/JavaScript | `if`, `for`, `while`, `switch` |
| Go | `if`, `for`, `switch`, `select` |
| C++ | `if`, `for`, `while`, `switch` |
| Java | `if`, `for`, `while`, `switch` |
| Rust | `if`, `for`, `while`, `match` |
| C# | `if`, `for`, `while`, `switch` |

### Examples

#### ❌ Bad: Python (pytest)
```python
def test_user_permissions():
    user = get_user()
    if user.is_admin:  # Test logic!
        assert user.can_delete
    else:
        assert not user.can_delete
```

#### ✅ Good: Python (pytest)
```python
def test_admin_can_delete():
    user = create_admin_user()
    assert user.can_delete

def test_regular_user_cannot_delete():
    user = create_regular_user()
    assert not user.can_delete
```

#### ❌ Bad: TypeScript (Jest)
```typescript
test('user permissions', () => {
    const user = getUser();
    if (user.isAdmin) {  // Test logic!
        expect(user.canDelete).toBe(true);
    } else {
        expect(user.canDelete).toBe(false);
    }
});
```

#### ✅ Good: TypeScript (Jest)
```typescript
test('admin can delete', () => {
    const user = createAdminUser();
    expect(user.canDelete).toBe(true);
});

test('regular user cannot delete', () => {
    const user = createRegularUser();
    expect(user.canDelete).toBe(false);
});
```

#### ❌ Bad: Go (testing)
```go
func TestUserPermissions(t *testing.T) {
    user := GetUser()
    if user.IsAdmin {  // Test logic!
        assert.True(t, user.CanDelete)
    } else {
        assert.False(t, user.CanDelete)
    }
}
```

#### ✅ Good: Go (testing)
```go
func TestAdminCanDelete(t *testing.T) {
    user := CreateAdminUser()
    assert.True(t, user.CanDelete)
}

func TestRegularUserCannotDelete(t *testing.T) {
    user := CreateRegularUser()
    assert.False(t, user.CanDelete)
}
```

### Special Cases

#### Go: Error Handling Exception
Go's idiomatic error handling (`if err != nil`) is **NOT** flagged:

```go
func TestFunction(t *testing.T) {
    result, err := DoSomething()
    if err != nil {  // OK! This is standard Go error handling
        t.Fatal(err)
    }
    assert.Equal(t, expected, result)
}
```

### Exceptions
- Error handling (e.g., Go's `if err != nil`)
- Setup loops that prepare test data (should be in fixtures/helpers)
- Parametrized tests (use framework's parametrize feature instead)

---

## UNI-MNT-002: Assertion Roulette

### Description
Detects tests with too many assertions (default: >3), making it hard to identify which assertion failed.

### Category
Maintenance

### Severity
Warning

### Why This Matters
- **Debugging**: When a test fails, unclear which assertion failed
- **Focus**: Each test should verify one behavior
- **Maintenance**: Large tests are harder to update
- **SRP**: Tests should have Single Responsibility

### Configuration
```toml
[tool.test-linter]
max-assertions = 3  # Adjust threshold (default: 3)
```

### Examples

#### ❌ Bad: Python (pytest)
```python
def test_user_creation():
    user = create_user("Alice", "alice@example.com")
    assert user.id == 1         # Assertion 1
    assert user.name == "Alice" # Assertion 2
    assert user.email == "alice@example.com"  # Assertion 3
    assert user.active is True  # Assertion 4 - Too many!
    assert user.created_at is not None  # Assertion 5
```

#### ✅ Good: Python (pytest)
```python
def test_user_creation():
    user = create_user("Alice", "alice@example.com")
    # Use object comparison or structured assertions
    assert user == User(
        id=1,
        name="Alice",
        email="alice@example.com",
        active=True
    )
    assert user.created_at is not None  # Separate concern

# OR split into focused tests:
def test_user_has_correct_name():
    user = create_user("Alice", "alice@example.com")
    assert user.name == "Alice"

def test_user_is_active_by_default():
    user = create_user("Alice", "alice@example.com")
    assert user.active is True
```

#### ❌ Bad: TypeScript (Jest)
```typescript
test('user creation', () => {
    const user = createUser('Alice', 'alice@example.com');
    expect(user.id).toBe(1);           // Assertion 1
    expect(user.name).toBe('Alice');   // Assertion 2
    expect(user.email).toBe('alice@example.com');  // Assertion 3
    expect(user.active).toBe(true);    // Assertion 4 - Too many!
});
```

#### ✅ Good: TypeScript (Jest)
```typescript
test('user creation', () => {
    const user = createUser('Alice', 'alice@example.com');
    // Use toMatchObject for structured comparison
    expect(user).toMatchObject({
        id: 1,
        name: 'Alice',
        email: 'alice@example.com',
        active: true
    });
});
```

### Exceptions
- Object equality checks (e.g., `expect(obj).toMatchObject({...})`)
- Parametrized tests with multiple assertions per case
- Builder pattern validations
- Complex object state verification (consider splitting)

---

## UNI-MNT-003: No Assertions

### Description
Detects tests that contain no assertions, making them effectively useless.

### Category
Maintenance

### Severity
Error

### Why This Matters
- **Useless**: Tests without assertions don't verify anything
- **False confidence**: Test passes even if code is broken
- **Maintenance**: Wastes CI time and developer attention
- **Smoke tests**: If intentional, should be clearly marked

### Examples

#### ❌ Bad: Python (pytest)
```python
def test_calculation():
    result = calculate(2, 2)  # No assertion!
    # Test always passes
```

#### ✅ Good: Python (pytest)
```python
def test_calculation():
    result = calculate(2, 2)
    assert result == 4  # Explicit verification
```

#### ❌ Bad: TypeScript (Jest)
```typescript
test('calculation', () => {
    const result = calculate(2, 2);  // No assertion!
});
```

#### ✅ Good: TypeScript (Jest)
```typescript
test('calculation', () => {
    const result = calculate(2, 2);
    expect(result).toBe(4);
});
```

#### ❌ Bad: C++ (GoogleTest)
```cpp
TEST(CalculationTest, Add) {
    int result = add(2, 2);  // No assertion!
}
```

#### ✅ Good: C++ (GoogleTest)
```cpp
TEST(CalculationTest, Add) {
    int result = add(2, 2);
    EXPECT_EQ(result, 4);
}
```

### Exceptions
- Smoke tests that just verify code doesn't crash (should be marked with comment)
- Tests that verify side effects (e.g., mock verification in some frameworks)
- Setup/teardown methods (not actual tests)

### Special Case: Mock Verification
Some frameworks have implicit assertions via mock verification:

```python
def test_api_called(mocker):
    mock_api = mocker.Mock()
    call_api(mock_api)
    mock_api.assert_called_once()  # This IS an assertion
```

---

## UNI-FIX-001: Fixture Scope Mismatch

### Description
Detects invalid fixture scope dependencies (e.g., session-scoped fixture depending on function-scoped fixture).

### Category
Fixture

### Severity
Error

### Why This Matters
- **Runtime errors**: Invalid scope dependencies cause test failures
- **Shared state**: Broader fixtures should not depend on narrower ones
- **Predictability**: Scope hierarchy violations break test isolation

### Scope Hierarchy
```
session (broadest)
  ↑
module
  ↑
class
  ↑
function (narrowest)
```

**Rule**: Broader scope fixtures CANNOT depend on narrower scope fixtures.

### Detected Patterns by Language/Framework

| Framework | Fixture Mechanisms |
|-----------|-------------------|
| pytest | `@pytest.fixture(scope=...)` |
| Jest | `beforeAll`, `beforeEach`, etc. |
| Mocha | `before`, `beforeEach`, etc. |
| Go testing | `TestMain`, suite methods |
| GoogleTest | Test fixtures, `SetUpTestSuite` |
| JUnit | `@BeforeAll`, `@BeforeEach` |
| NUnit | `[OneTimeSetUp]`, `[SetUp]` |
| xUnit | `IClassFixture<T>`, constructor |
| Rust | Module-level setup |

### Examples

#### ❌ Bad: Python (pytest)
```python
@pytest.fixture(scope="function")
def temp_user():
    return User("temp")

@pytest.fixture(scope="session")
def user_session(temp_user):  # ERROR! Session depends on function
    return {"user": temp_user}
```

#### ✅ Good: Python (pytest)
```python
@pytest.fixture(scope="session")
def user_session():
    return {"user": User("session")}

@pytest.fixture(scope="function")
def temp_user(user_session):  # OK! Function can depend on session
    return User("temp", session=user_session)
```

#### ❌ Bad: TypeScript (Jest)
```typescript
let tempData: any;

beforeEach(() => {
    tempData = createData();  // Function scope
});

beforeAll(() => {
    // ERROR! Suite setup depends on test setup
    globalData = processData(tempData);
});
```

#### ✅ Good: TypeScript (Jest)
```typescript
let globalData: any;

beforeAll(() => {
    globalData = createData();  // Suite scope
});

beforeEach(() => {
    // OK! Test setup can use suite data
    tempData = processData(globalData);
});
```

#### ❌ Bad: Go (testify)
```go
type MySuite struct {
    suite.Suite
    funcData string
}

func (s *MySuite) SetupTest() {
    s.funcData = "test data"  // Function scope
}

func (s *MySuite) SetupSuite() {
    // ERROR! Suite setup depends on test setup
    s.suiteData = s.funcData
}
```

#### ✅ Good: Go (testify)
```go
type MySuite struct {
    suite.Suite
    suiteData string
}

func (s *MySuite) SetupSuite() {
    s.suiteData = "suite data"  // Suite scope
}

func (s *MySuite) SetupTest() {
    // OK! Test setup can use suite data
    s.funcData = s.suiteData + "-test"
}
```

### Exceptions
- Fixtures with same scope can depend on each other
- Narrower fixtures depending on broader fixtures (always OK)

---

## Configuration

### Global Configuration

```toml
[tool.test-linter]
# Languages to lint
languages = ["python", "typescript", "go", "cpp", "java", "rust", "csharp"]

# Assertion threshold for UNI-MNT-002
max-assertions = 3

# Disabled rules
disabled-rules = ["UNI-FLK-001", "UNI-MNT-001"]

# Parallel processing
parallel-processing = true
```

### Language-Specific Configuration

```toml
[tool.test-linter.python]
enabled = true
framework = "pytest"
max-assertions = 5  # Override for Python

[tool.test-linter.typescript]
enabled = true
disabled-rules = ["UNI-FLK-003"]  # Allow network in TS tests
```

### Rule Severity Overrides

```toml
[tool.test-linter.rules]
UNI-FLK-001 = "error"   # Upgrade time-sleep to error
UNI-MNT-002 = "off"     # Disable assertion roulette
UNI-MNT-001 = "info"    # Downgrade test-logic to info
```

### Inline Suppression

#### Python
```python
# test-linter: disable=UNI-FLK-001
def test_with_sleep():
    time.sleep(1)  # Won't be flagged
```

#### TypeScript
```typescript
// test-linter: disable=UNI-FLK-001
test('with timeout', () => {
    setTimeout(() => {}, 1000);  // Won't be flagged
});
```

#### Go
```go
// test-linter: disable=UNI-FLK-001
func TestWithSleep(t *testing.T) {
    time.Sleep(1 * time.Second)  // Won't be flagged
}
```

---

## Best Practices

### 1. Start with Default Rules
Begin with all rules enabled and adjust based on your project's needs.

### 2. Use Language-Specific Overrides
Different languages may have different conventions:
```toml
[tool.test-linter.go]
max-assertions = 5  # Table-driven tests may need more

[tool.test-linter.python]
max-assertions = 3  # Stricter for Python
```

### 3. Document Suppressions
When disabling rules, document why:
```python
# test-linter: disable=UNI-FLK-001
# Intentional sleep to test rate limiting
def test_rate_limit():
    time.sleep(1)
```

### 4. Review Violations Regularly
Run in CI and review violations during code review.

### 5. Educate Team
Share this documentation with your team to build shared understanding.

---

## Future Rules (Potential)

Ideas for language-specific rules to be added:

### Python-Specific
- `PY-FIX-001`: Fixture shadowing detection
- `PY-FIX-002`: Stateful session fixtures
- `PY-PAR-001`: Parametrize anti-patterns

### TypeScript-Specific
- `TS-ASYNC-001`: Missing await on async operations
- `TS-MOCK-001`: Unmocked external dependencies

### Go-Specific
- `GO-GOROUTINE-001`: Unjoined goroutines in tests
- `GO-TABLE-001`: Table-driven test best practices

---

## Contributing

To propose new rules:
1. Open an issue with rule proposal
2. Provide examples from multiple languages
3. Explain why the pattern is problematic
4. Suggest remediation

---

**Built with care for the testing community** 🧪
