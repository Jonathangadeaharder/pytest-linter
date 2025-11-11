# pytest-deep-analysis

A Pylint plugin for deep, semantic pytest linting that targets the most challenging pain points in the Python testing ecosystem.

## Why This Linter?

### The Market Gap

The Python linting landscape has been fundamentally reshaped by [Ruff](https://github.com/astral-sh/ruff), a Rust-based linter that is 10-100x faster than traditional tools. However, Ruff's speed comes from limiting its analysis to file-local, syntax-level checks.

**The most challenging problems in pytest are semantic, cross-file issues:**

- **Test Flakiness** (65% of QA leaders cite this as their #1 challenge)
- **Fixture Dependency Complexity** - tricky scope interactions and implicit conftest.py magic
- **Maintenance Overhead** - from complex test logic and fixture misuse

These problems require deep, project-wide analysis that only tools like Pylint (via astroid) can provide.

### The Solution: A Hybrid Toolchain

`pytest-deep-analysis` is designed to **complement** Ruff, not compete with it:

- **Ruff**: Fast, file-local linting (style, syntax, imports) - runs in seconds
- **pytest-deep-analysis**: Slow, deep semantic checks (fixtures, scope, dependencies) - runs in CI

This hybrid approach delivers comprehensive coverage without sacrificing developer experience.

## Installation

```bash
pip install pytest-deep-analysis
```

Or install from source:

```bash
git clone https://github.com/yourusername/pytest-deep-analysis.git
cd pytest-deep-analysis
pip install -e .
```

## Quick Start

### 1. Run the linter on your test suite:

```bash
pylint --load-plugins=pytest_deep_analysis --disable=all --enable=pytest-deep-analysis tests/
```

### 2. Configure your project:

Copy the example configuration:

```bash
cp .pylintrc.example .pylintrc
```

### 3. Integrate into CI:

Add to your CI pipeline (e.g., GitHub Actions):

```yaml
- name: Run Deep Pytest Analysis
  run: |
    pip install pytest-deep-analysis
    pylint --disable=all --enable=pytest-deep-analysis tests/
```

## Rules

### Category 1: Test Body Smells (Flakiness & Maintenance)

| Rule ID | Message | Description |
|---------|---------|-------------|
| **W9001** | `pytest-flk-time-sleep` | `time.sleep()` found in test. Use explicit waits instead. |
| **W9002** | `pytest-flk-io-open` | `open()` found in test. Use the `tmp_path` fixture instead. |
| **W9003** | `pytest-flk-network-import` | Network module imported in test file. Mock network calls. |
| **W9004** | `pytest-flk-cwd-dependency` | CWD-sensitive function found. Tests should not depend on working directory. |
| **W9011** | `pytest-mnt-test-logic` | Conditional logic (if/for/while) in test. Follow Arrange-Act-Assert pattern. |
| **W9012** | `pytest-mnt-magic-assert` | Magic number/string in assert. Extract to named constants. |
| **W9013** | `pytest-mnt-suboptimal-assert` | Use direct `assert x == y` instead of `assertTrue(x == y)`. |
| **W9014** | `pytest-fix-fixture-mutation` | Test modifies fixture in-place. Fixtures should not be mutated. |
| **W9015** | `pytest-param-duplicate` | Duplicate values in `@pytest.mark.parametrize`. Remove redundant test cases. |
| **W9016** | `pytest-param-mismatch` | Parameter count mismatch in `@pytest.mark.parametrize`. |

### Category 2: Fixture Definition Smells

| Rule ID | Message | Description |
|---------|---------|-------------|
| **W9021** | `pytest-fix-autouse` | `@pytest.fixture(autouse=True)` detected. Avoid implicit magic. |

### Category 3: Fixture Interaction Smells (Cross-File Analysis)

| Rule ID | Message | Description |
|---------|---------|-------------|
| **E9031** | `pytest-fix-session-mutation` | Session-scoped fixture mutates global state. |
| **E9032** | `pytest-fix-invalid-scope` | Invalid scope dependency (e.g., session fixture cannot depend on function fixture). |
| **W9033** | `pytest-fix-shadowed` | Fixture is shadowed across conftest.py files. |
| **W9034** | `pytest-fix-unused` | Fixture is defined but never used. |
| **E9035** | `pytest-fix-stateful-session` | Session-scoped fixture returns mutable object. |
| **E9036** | `pytest-fix-db-commit` | Fixture performs database commits without proper cleanup. |
| **W9037** | `pytest-fix-scope-overuse` | Fixture scope is broader than necessary. Consider narrowing. |

## Configuration

### Using `pyproject.toml`

You can customize the linter behavior using `pyproject.toml`:

```toml
[tool.pytest-deep-analysis]
# Disable specific rules
disable = [
    "pytest-fix-autouse",
    "pytest-mnt-test-logic"
]

# Ignore file patterns
ignore_patterns = [
    "**/migrations/*",
    "**/generated/*.py"
]

# Feature flags
[tool.pytest-deep-analysis.features]
database_commits = true      # Check for DB commits without cleanup
scope_narrowing = true       # Suggest narrower fixture scopes
fixture_mutations = true     # Warn about fixture mutations in tests
parametrize_checks = true    # Check parametrize usage

# Rule-specific configuration
[tool.pytest-deep-analysis.rules.pytest-fix-autouse]
severity = "error"
```

### Using `.pylintrc`

Alternatively, use Pylint's native configuration:

```ini
[MASTER]
load-plugins=pytest_deep_analysis

[MESSAGES CONTROL]
disable=all
enable=pytest-deep-analysis

# Disable specific rules
disable=pytest-fix-autouse,pytest-mnt-test-logic
```

### Integration with pytest-xdist

The linter automatically detects when running under `pytest-xdist` and serializes fixture graph data for proper parallel analysis:

```bash
# Run tests in parallel - the linter will handle it correctly
pytest -n auto tests/
pylint --load-plugins=pytest_deep_analysis tests/
```

## Examples

### ❌ Bad: Flaky Test with `time.sleep()`

```python
def test_async_operation():
    trigger_async_task()
    time.sleep(5)  # ⚠️ PYTEST-FLK-001
    assert task_completed()
```

### ✅ Good: Explicit Wait Condition

```python
def test_async_operation():
    trigger_async_task()
    for _ in range(50):
        if task_completed():
            break
        time.sleep(0.1)
    assert task_completed()
```

### ❌ Bad: Invalid Fixture Scope Dependency

```python
# conftest.py
@pytest.fixture(scope="session")
def user_session(function_user):  # ⚠️ PYTEST-FIX-003
    # Session fixture cannot depend on function-scoped fixture!
    return {"user": function_user}
```

### ✅ Good: Proper Scope Hierarchy

```python
@pytest.fixture(scope="session")
def db_engine():
    return create_engine("sqlite:///:memory:")

@pytest.fixture(scope="function")
def db_transaction(db_engine):  # ✓ Function can depend on session
    with db_engine.begin() as trans:
        yield trans
        trans.rollback()
```

### ❌ Bad: Shadowed Fixture

```python
# tests/conftest.py
@pytest.fixture
def database():
    return {"host": "localhost"}

# tests/api/conftest.py
@pytest.fixture
def database():  # ⚠️ PYTEST-FIX-004: Shadows parent fixture
    return {"host": "api-server"}
```

### ❌ Bad: Database Commit Without Cleanup

```python
@pytest.fixture(scope="session")
def db_session():
    conn = create_connection()
    conn.execute("CREATE TABLE users ...")
    conn.commit()  # ⚠️ E9036: Commit without cleanup
    yield conn
    # Missing rollback/cleanup!
```

### ✅ Good: Database Fixture with Cleanup

```python
@pytest.fixture(scope="function")
def db_session():
    conn = create_connection()
    conn.execute("CREATE TABLE users ...")
    conn.commit()
    yield conn
    conn.rollback()  # ✓ Proper cleanup
    conn.close()
```

### ❌ Bad: Test Mutates Fixture

```python
@pytest.fixture
def user_dict():
    return {"name": "Alice", "age": 30}

def test_user_update(user_dict):
    user_dict["age"] = 31  # ⚠️ W9014: Mutating fixture in-place
    assert user_dict["age"] == 31
```

### ✅ Good: Test Copies Fixture Data

```python
def test_user_update(user_dict):
    updated_user = user_dict.copy()  # ✓ Create a copy
    updated_user["age"] = 31
    assert updated_user["age"] == 31
```

### ❌ Bad: Fixture Scope Too Broad

```python
@pytest.fixture(scope="session")  # ⚠️ W9037: Only used in one test
def temp_file():
    return "/tmp/test.txt"

def test_file_operations(temp_file):
    # Only test using this fixture
    assert os.path.exists(temp_file)
```

### ✅ Good: Appropriate Fixture Scope

```python
@pytest.fixture(scope="function")  # ✓ Narrower scope
def temp_file():
    return "/tmp/test.txt"
```

### ❌ Bad: Duplicate Parametrize Values

```python
@pytest.mark.parametrize("value", [1, 2, 3, 2, 4])  # ⚠️ W9015: Duplicate "2"
def test_processing(value):
    assert process(value) > 0
```

### ✅ Good: Unique Parametrize Values

```python
@pytest.mark.parametrize("value", [1, 2, 3, 4, 5])  # ✓ All unique
def test_processing(value):
    assert process(value) > 0
```

## Architecture

### Why a Pylint Plugin?

1. **Access to astroid's inference engine**: The only mature Python engine capable of cross-file semantic analysis
2. **Project-wide understanding**: Can trace fixture dependencies across conftest.py files
3. **Proven ecosystem**: Leverages Pylint's established plugin architecture

### Multi-Pass Analysis

The checker operates in two passes:

**Pass 1 (Fixture Discovery):**
- Visit all modules
- Discover all `@pytest.fixture` definitions
- Build a project-wide fixture dependency graph
- Extract scope, autouse, and dependency metadata

**Pass 2 (Validation & Analysis):**
- Analyze test functions and their fixture usage
- Validate fixture scope dependencies
- Detect unused, shadowed, and stateful fixtures
- Perform test body analysis (Categories 1 & 2)

## Development

### Setup Development Environment

```bash
git clone https://github.com/yourusername/pytest-deep-analysis.git
cd pytest-deep-analysis
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest tests/
```

### Run the Linter on Itself

```bash
pylint --disable=all --enable=pytest-deep-analysis pytest_deep_analysis/
```

### Code Formatting

```bash
black pytest_deep_analysis/ tests/
```

## Performance Considerations

This linter is **intentionally slow** because it performs deep, cross-file analysis.

**Recommended Usage:**

- ❌ Don't run in pre-commit hooks or on every save
- ✅ Do run in CI pipelines on pull requests
- ✅ Do run periodically during development (e.g., before committing)
- ✅ Do combine with Ruff for fast, local feedback

**Typical Performance:**

- Small projects (<100 tests): ~2-5 seconds
- Medium projects (100-1000 tests): ~10-30 seconds
- Large projects (1000+ tests): ~30-120 seconds

Compare this to Ruff (runs in <1 second for most projects) to understand the trade-off.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Recent Enhancements (v2.0)

- ✅ Detect fixtures that perform database commits without cleanup (E9036)
- ✅ Warn about tests that modify fixture state in-place (W9014)
- ✅ Identify fixtures that could be narrowed in scope (W9037)
- ✅ Detect parametrize misuse and anti-patterns (W9015, W9016)
- ✅ Integration with pytest-xdist for parallel test analysis
- ✅ Custom rule configuration via pyproject.toml

### Potential Future Enhancements

- [ ] Detect test ordering dependencies (tests that pass/fail based on execution order)
- [ ] Identify missing fixture cleanup code
- [ ] Detect over-mocking (tests that mock too many dependencies)
- [ ] Warn about fixtures with side effects
- [ ] Detect circular fixture dependencies
- [ ] Suggest fixture refactoring opportunities

## License

MIT License - see [LICENSE](LICENSE) for details.

## Related Tools

- [Ruff](https://github.com/astral-sh/ruff) - Fast Python linter (recommended complement)
- [Pylint](https://github.com/PyCQA/pylint) - The Python linter framework
- [pytest](https://pytest.org/) - The testing framework this plugin analyzes
- [astroid](https://github.com/PyCQA/astroid) - The inference engine powering this plugin

## Acknowledgments

This project is inspired by:

- The pytest community's discussions on fixture complexity
- The "Hybrid Toolchain" concept emerging from Ruff's success
- Pylint's astroid engine and its powerful semantic analysis capabilities

---

**Built with ❤️ for the Python testing community**
