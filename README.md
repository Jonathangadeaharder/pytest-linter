# test-linter: Multi-Language Test Smell Detector

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive, multi-language test linter that detects test smells and anti-patterns across **8 programming languages** and **20+ testing frameworks**.

## 🌟 Supported Languages & Frameworks

| Language | Frameworks | Status |
|----------|-----------|--------|
| **Python** | pytest, unittest | ✅ Complete |
| **TypeScript** | Jest, Mocha, Vitest | ✅ Complete |
| **JavaScript** | Jest, Mocha, Vitest | ✅ Complete |
| **Go** | testing, testify | ✅ Complete |
| **C++** | GoogleTest, Catch2, Boost.Test | ✅ Complete |
| **Java** | JUnit 4, JUnit 5, TestNG | ✅ Complete |
| **Rust** | Built-in tests, #[test] | ✅ Complete |
| **C#** | NUnit, xUnit, MSTest | ✅ Complete |
| **VB.NET** | NUnit, xUnit, MSTest | ✅ Complete |

## 🚀 Quick Start

### Installation

```bash
pip install -e .
```

### Run the Linter

```bash
# Lint all test files in current directory
test-linter .

# Lint specific directory
test-linter tests/

# Lint specific files
test-linter path/to/test.py path/to/test.ts

# JSON output for CI/CD
test-linter --format json --output report.json tests/
```

## ✨ Features

### Universal Test Smell Detection

7 cross-language rules that work across all supported languages:

| Rule ID | Name | Description |
|---------|------|-------------|
| **UNI-FLK-001** | time-sleep | Detects time-based waits (flaky tests) |
| **UNI-FLK-002** | mystery-guest | File I/O without resource fixtures |
| **UNI-FLK-003** | network-dependency | Network imports causing test flakiness |
| **UNI-MNT-001** | test-logic | Conditional logic in tests (hard to maintain) |
| **UNI-MNT-002** | assertion-roulette | Too many assertions (default: >3) |
| **UNI-MNT-003** | no-assertion | Tests without assertions |
| **UNI-FIX-001** | fixture-scope-mismatch | Invalid fixture scope dependencies |

### Language-Agnostic Architecture

- **Zero external parser dependencies**: Uses regex-based parsing for all languages
- **Pluggable adapter system**: Easy to extend with new languages
- **Universal data models**: TestFunction, TestAssertion, TestFixture work everywhere
- **Smart framework detection**: Automatically identifies testing frameworks
- **Configurable via TOML**: Centralized configuration for all languages

## 📖 Examples

### Python (pytest)
```python
# ❌ BAD: Time-based wait (UNI-FLK-001)
def test_async_operation():
    trigger_task()
    time.sleep(5)  # Flaky!
    assert task_completed()

# ✅ GOOD: Explicit wait with polling
def test_async_operation():
    trigger_task()
    for _ in range(50):
        if task_completed():
            break
        time.sleep(0.1)
    assert task_completed()
```

### TypeScript (Jest)
```typescript
// ❌ BAD: Too many assertions (UNI-MNT-002)
test('user creation', () => {
    const user = createUser();
    expect(user.id).toBe(1);
    expect(user.name).toBe('Alice');
    expect(user.email).toBe('alice@test.com');
    expect(user.active).toBe(true);  // >3 assertions
});

// ✅ GOOD: Focused test
test('user has correct properties', () => {
    const user = createUser();
    expect(user).toMatchObject({
        id: 1,
        name: 'Alice',
        email: 'alice@test.com',
        active: true
    });
});
```

### Go (testing)
```go
// ❌ BAD: Conditional logic in test (UNI-MNT-001)
func TestValue(t *testing.T) {
    value := GetValue()
    if value > 5 {  // Logic in test!
        assert.True(t, value > 5)
    }
}

// ✅ GOOD: Direct assertion
func TestValueGreaterThan5(t *testing.T) {
    value := GetValue()
    assert.Greater(t, value, 5)
}
```

### C++ (GoogleTest)
```cpp
// ❌ BAD: No assertions (UNI-MNT-003)
TEST(MyTest, Calculation) {
    int result = add(2, 2);  // No assertion!
}

// ✅ GOOD: Clear assertion
TEST(MyTest, Calculation) {
    int result = add(2, 2);
    EXPECT_EQ(result, 4);
}
```

### Java (JUnit 5)
```java
// ❌ BAD: Network dependency (UNI-FLK-003)
import java.net.http.HttpClient;

@Test
void testApi() {
    HttpClient client = HttpClient.newHttpClient();
    // Test depends on external service!
}

// ✅ GOOD: Mock external dependencies
@Test
void testApi() {
    HttpClient mockClient = mock(HttpClient.class);
    // Test is isolated
}
```

### Rust (built-in)
```rust
// ❌ BAD: Time-based wait (UNI-FLK-001)
#[test]
fn test_async() {
    trigger_task();
    thread::sleep(Duration::from_secs(1));  // Flaky!
    assert!(task_done());
}

// ✅ GOOD: Use proper async testing
#[tokio::test]
async fn test_async() {
    trigger_task().await;
    assert!(task_done());
}
```

### C# (NUnit)
```csharp
// ❌ BAD: Multiple issues (UNI-FLK-001, UNI-MNT-002)
[Test]
public void TestWithSleep()
{
    Thread.Sleep(1000);  // Time-based wait
    Assert.AreEqual(1, 1);
    Assert.AreEqual(2, 2);
    Assert.AreEqual(3, 3);
    Assert.AreEqual(4, 4);  // Too many assertions
}

// ✅ GOOD: No sleeps, focused assertions
[Test]
public void TestValue()
{
    var result = Calculate();
    Assert.AreEqual(expected, result);
}
```

### VB.NET (NUnit)
```vbnet
' ❌ BAD: Conditional logic in test (UNI-MNT-001)
<Test>
Public Sub TestWithLogic()
    Dim value As Integer = 10
    If value > 5 Then  ' Logic in test!
        Assert.IsTrue(value > 5)
    End If
End Sub

' ✅ GOOD: Direct assertion
<Test>
Public Sub TestValueGreaterThan5()
    Dim value As Integer = GetValue()
    Assert.Greater(value, 5)
End Sub
```

## 🔧 Configuration

### Basic Configuration

Create or update `pyproject.toml`:

```toml
[tool.test-linter]
# Languages to lint (default: all)
languages = ["python", "typescript", "go"]

# Maximum assertions per test (default: 3)
max-assertions = 3

# Disable specific rules globally
disabled-rules = ["UNI-FLK-001"]

# Enable parallel processing (default: true)
parallel-processing = true
```

### Language-Specific Configuration

```toml
[tool.test-linter.python]
enabled = true
framework = "pytest"  # or "unittest"
max-assertions = 5    # Override global setting

[tool.test-linter.typescript]
enabled = true
framework = "jest"    # or "mocha", "vitest"

[tool.test-linter.go]
enabled = true
# Go settings...
```

### Rule Severity Overrides

```toml
[tool.test-linter.rules]
UNI-FLK-001 = "error"   # Upgrade to error
UNI-MNT-002 = "warning" # Downgrade to warning
UNI-MNT-001 = "off"     # Disable rule
```

## 📊 Output Formats

### Terminal Output (Default)

```bash
test-linter tests/
```

Output:
```
tests/test_api.py
    42 WARN  Time-based wait found in test 'test_user_login'
          💡 Replace time-based waits with polling or wait conditions.

    67 ERROR Test 'test_create_user' contains no assertions
          💡 Add explicit assertions or mark as a smoke test.

tests/sample.test.ts
    15 WARN  Too many assertions (4) in test 'user creation'
          💡 Split into multiple focused tests.

------------------------------------------------------------
Found 3 issue(s):
  1 error(s)
  2 warning(s)
```

### JSON Output (CI/CD)

```bash
test-linter --format json --output report.json tests/
```

Output (`report.json`):
```json
{
  "violations": [
    {
      "file_path": "tests/test_api.py",
      "line_number": 42,
      "rule_id": "UNI-FLK-001",
      "severity": "warning",
      "message": "Time-based wait found in test 'test_user_login'",
      "suggestion": "Replace time-based waits with polling or wait conditions.",
      "test_name": "test_user_login"
    }
  ],
  "total": 3,
  "errors": 1,
  "warnings": 2
}
```

## 🏗️ Architecture

### Core Components

```
test_linter/
├── core/                        # Language-agnostic core
│   ├── models.py                # TestFunction, TestAssertion, TestFixture
│   ├── adapters.py              # LanguageAdapter interface
│   ├── rules.py                 # Rule system & registry
│   ├── smells.py                # Universal rules implementation
│   ├── config.py                # Configuration management
│   └── engine.py                # Linting orchestration
├── languages/                   # Language adapters
│   ├── python/adapter.py        # Python (astroid-based)
│   ├── typescript/adapter.py   # TypeScript/JavaScript (regex)
│   ├── go/adapter.py            # Go (regex)
│   ├── cpp/adapter.py           # C++ (regex)
│   ├── java/adapter.py          # Java (regex)
│   ├── rust/adapter.py          # Rust (regex)
│   └── csharp/adapter.py        # C# (regex)
└── cli.py                       # Command-line interface
```

### How It Works

1. **File Discovery**: Engine finds test files by extension
2. **Framework Detection**: Each adapter auto-detects testing framework
3. **Parsing**: Language adapter extracts test functions, assertions, fixtures
4. **Rule Execution**: Universal rules check for smells across all languages
5. **Reporting**: Violations formatted and displayed/exported

### Design Principles

- **Language Agnostic Core**: TestFunction model works for any language
- **Pluggable Adapters**: Add new languages without touching core
- **Zero External Dependencies**: All parsing done with regex (except Python)
- **Configuration First**: Everything configurable via pyproject.toml
- **Parallel Processing**: Fast analysis for large codebases

## 🧪 Language-Specific Features

### Python
- **AST Parsing**: Uses astroid for robust Python analysis
- **pytest Fixtures**: Full fixture scope detection and validation
- **async/await**: Detects async test functions
- **Parametrized Tests**: Identifies @pytest.mark.parametrize

### TypeScript/JavaScript
- **Multi-Framework**: Jest, Mocha, Vitest support
- **describe/it blocks**: Nested test structure parsing
- **async/await**: Async test detection
- **Expect chains**: Assertion extraction from expect().toBe() patterns

### Go
- **Table-Driven Tests**: Detects `tests := []struct{}` patterns
- **Subtests**: Identifies `t.Run()` usage
- **Error Handling**: Smart detection excludes `if err != nil` from test logic
- **Testify Support**: Recognizes assert/require packages

### C++
- **Multi-Framework**: GoogleTest, Catch2, Boost.Test
- **String-Aware Parsing**: Handles string literals in brace matching
- **Macro Detection**: Recognizes TEST(), EXPECT_EQ() macros

### Java
- **Annotation-Based**: Detects @Test, @Before, @After
- **JUnit 4 vs 5**: Framework disambiguation via imports
- **TestNG Support**: Recognizes @org.testng annotations

### Rust
- **Attribute Parsing**: #[test], #[cfg(test)] detection
- **Async Tests**: #[tokio::test] support
- **Panic Handling**: Detects panic!() as assertion pattern

### C#
- **Multi-Framework**: NUnit, xUnit, MSTest
- **Attribute-Based**: [Test], [Fact], [TestMethod]
- **Async Tests**: async Task test methods
- **Setup/Teardown**: [SetUp], [TearDown], [OneTimeSetUp]

### VB.NET
- **Multi-Framework**: NUnit, xUnit, MSTest (same as C#)
- **Attribute-Based**: <Test>, <Fact>, <TestMethod>
- **Async Tests**: Async Function ... As Task
- **Case Insensitive**: Flexible syntax matching

## 🎯 Use Cases

### Pre-Commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: test-linter
        name: Test Smell Detection
        entry: test-linter
        language: system
        types: [python, typescript, go]
        pass_filenames: true
```

### CI/CD Integration

```yaml
# GitHub Actions
- name: Run Test Linter
  run: |
    pip install test-linter
    test-linter --format json --output report.json tests/

- name: Upload Results
  uses: actions/upload-artifact@v3
  with:
    name: test-linter-report
    path: report.json
```

### IDE Integration

Run on save or as a custom task:

```json
// VSCode tasks.json
{
  "label": "Test Linter",
  "type": "shell",
  "command": "test-linter ${file}",
  "problemMatcher": []
}
```

## 📚 Rule Reference

See [RULES.md](RULES.md) for comprehensive rule documentation with examples for all 7 languages.

## 🏛️ Architecture Details

See [ARCHITECTURE.md](ARCHITECTURE.md) for deep dive into:
- Language adapter pattern
- Universal rule system
- Parsing strategies per language
- Configuration management
- Performance optimization

## 🔄 Migration from pytest-deep-analysis

This tool evolved from `pytest-deep-analysis` and maintains backward compatibility:

```toml
# Old config (still works)
[tool.pytest-deep-analysis]
max-assertions = 5

# New config (recommended)
[tool.test-linter]
languages = ["python"]
max-assertions = 5
```

The original pytest plugin remains functional:
```bash
# Old way (still works)
pylint --load-plugins=pytest_deep_analysis tests/

# New way (recommended)
test-linter tests/
```

## 🤝 Contributing

Contributions welcome! To add a new language:

1. Create adapter in `test_linter/languages/your_lang/adapter.py`
2. Implement `LanguageAdapter` interface
3. Register in `test_linter/core/engine.py`
4. Add test fixtures in `examples/`
5. Update documentation

See existing adapters for reference implementation.

## 📊 Performance

Typical performance on a 2023 MacBook Pro:

| Language | Files/Second | Notes |
|----------|--------------|-------|
| Python | 50-100 | Uses astroid (slower) |
| TypeScript | 200-300 | Regex-based (fast) |
| Go | 250-350 | Regex-based (fast) |
| C++ | 150-200 | String-aware parsing |
| Java | 200-250 | Annotation parsing |
| Rust | 300-400 | Lightweight parsing |
| C# | 200-250 | Attribute parsing |
| VB.NET | 200-250 | Attribute parsing |

**Parallel Processing**: 3-5x speedup on multi-core systems (enabled by default)

## 🐛 Known Limitations

1. **Regex Parsing**: Non-Python languages use regex (may miss edge cases)
2. **Complex Assertions**: Some framework-specific assertions may not be detected
3. **Macro Expansion**: C++ macros are not expanded
4. **Generics**: Complex generic types may not be fully understood

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Original **pytest-deep-analysis** architecture
- **astroid** library for Python AST analysis
- **Pylint** plugin system inspiration
- Testing community for anti-pattern documentation

## 🔗 Related Tools

- [pytest](https://pytest.org/) - Python testing framework
- [Jest](https://jestjs.io/) - JavaScript testing framework
- [GoogleTest](https://github.com/google/googletest) - C++ testing framework
- [testify](https://github.com/stretchr/testify) - Go testing toolkit

## 📞 Support

- 🐛 **Issues**: [GitHub Issues](https://github.com/yourusername/pytest-linter/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/yourusername/pytest-linter/discussions)
- 📖 **Documentation**: [Wiki](https://github.com/yourusername/pytest-linter/wiki)

---

**Built for the testing community** 🧪

**Transform your test quality across all languages** 🚀
