# Contributing to pytest-deep-analysis

Thank you for your interest in contributing to pytest-deep-analysis! This document provides guidelines and information for contributors.

## Code of Conduct

This project follows the [Python Community Code of Conduct](https://www.python.org/psf/conduct/). Please be respectful and constructive in all interactions.

## Getting Started

### Development Setup

1. Fork and clone the repository:

```bash
git clone https://github.com/yourusername/pytest-deep-analysis.git
cd pytest-deep-analysis
```

2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install development dependencies:

```bash
pip install -e ".[dev]"
```

4. Verify the installation:

```bash
pytest tests/
```

## Development Workflow

### Running Tests

We use an automated test harness based on `pylint.testutils` to verify the linter works correctly.

```bash
# Run all automated tests
pytest tests/test_harness/

# Run with coverage
pytest --cov=pytest_deep_analysis --cov-report=html tests/test_harness/

# Run specific test category
pytest tests/test_harness/test_category1_flakiness.py
pytest tests/test_harness/test_category1_maintenance.py
pytest tests/test_harness/test_category2_fixtures.py
pytest tests/test_harness/test_category3_fixtures.py

# Run with verbose output
pytest -v tests/test_harness/
```

The test harness automatically:
- Loads the pytest-deep-analysis plugin
- Runs the linter on test code snippets
- Asserts specific messages are generated with correct line numbers
- Validates both positive (should warn) and negative (should not warn) cases

### Code Formatting

We use [Black](https://github.com/psf/black) for code formatting:

```bash
black pytest_deep_analysis/ tests/
```

### Type Checking

We use [mypy](https://github.com/python/mypy) for type checking:

```bash
mypy pytest_deep_analysis/
```

### Running the Linter

Test the linter on the example test files:

```bash
# Run on example test files (manual inspection)
pylint --disable=all --enable=pytest-deep-analysis tests/test_category*.py tests/conftest.py

# Run on the entire tests directory
pylint --disable=all --enable=pytest-deep-analysis tests/
```

Note: The `tests/` directory contains two types of files:
- `tests/test_harness/` - Automated unit tests for the linter (run with pytest)
- `tests/test_category*.py`, `tests/conftest.py` - Example files demonstrating bad/good patterns (run with pylint for manual inspection)

## Contributing Guidelines

### Reporting Bugs

When reporting bugs, please include:

1. **Description**: Clear description of the issue
2. **Reproduction**: Minimal code example that reproduces the problem
3. **Expected behavior**: What you expected to happen
4. **Actual behavior**: What actually happened
5. **Environment**: Python version, Pylint version, OS

### Suggesting New Rules

When proposing new linter rules:

1. **Justification**: Explain the pain point this rule addresses
2. **Category**: Which category does it fit into?
   - Category 1: Test Body Smells (ast-based)
   - Category 2: Fixture Definition Smells (ast-based)
   - Category 3: Fixture Interaction Smells (astroid-based)
3. **Examples**: Provide both bad and good code examples
4. **False Positives**: Discuss potential false positive scenarios
5. **Implementation**: Sketch out the implementation approach

### Submitting Pull Requests

1. **Create a branch**: Use a descriptive branch name
   ```bash
   git checkout -b feature/add-parametrize-check
   ```

2. **Write tests**: Add test cases for your changes
   - Bad examples that should trigger warnings
   - Good examples that should not trigger warnings

3. **Update documentation**:
   - Update README.md if adding new rules
   - Add docstrings to new functions
   - Update CHANGELOG.md

4. **Run checks**: Ensure all tests and linters pass
   ```bash
   pytest tests/
   black pytest_deep_analysis/ tests/
   mypy pytest_deep_analysis/
   ```

5. **Commit**: Use clear, descriptive commit messages
   ```bash
   git commit -m "Add check for pytest.mark.parametrize misuse"
   ```

6. **Push and create PR**:
   ```bash
   git push origin feature/add-parametrize-check
   ```

## Project Structure

```text
pytest-deep-analysis/
├── pytest_deep_analysis/
│   ├── __init__.py          # Plugin registration
│   ├── checkers.py          # Main checker implementation
│   ├── messages.py          # Message definitions
│   └── utils.py             # Utility functions
├── tests/
│   ├── conftest.py          # Test fixtures
│   ├── test_category1_flakiness.py
│   ├── test_category1_maintenance.py
│   ├── test_category3_fixtures.py
│   └── subdir/              # For testing shadowing
│       ├── conftest.py
│       └── test_shadowing.py
├── pyproject.toml           # Project configuration
├── setup.py                 # Setup script
├── README.md                # User documentation
└── CONTRIBUTING.md          # This file
```

## Architecture Overview

### Multi-Pass Analysis

The checker uses a two-pass architecture:

**Pass 1: Fixture Discovery**
- Visits all modules in the project
- Builds a project-wide fixture graph
- Extracts metadata (scope, autouse, dependencies)

**Pass 2: Validation**
- Analyzes test functions and fixture usage
- Validates fixture scope dependencies
- Detects fixture anti-patterns

### Key Classes

- **PytestDeepAnalysisChecker**: Main checker class (inherits from `pylint.checkers.BaseChecker`)
- **FixtureInfo**: Data class storing fixture metadata
- **Utils**: Helper functions for AST/astroid analysis

### Adding a New Rule

1. **Define the message** in `messages.py`:
```python
"W9099": (
    "Your message here",
    "your-rule-symbol",
    "Detailed help text explaining the anti-pattern.",
)
```

2. **Implement the check** in `checkers.py`:
```python
def visit_somenode(self, node: astroid.SomeNode) -> None:
    """Visit a node and check for your anti-pattern."""
    if self._detect_antipattern(node):
        self.add_message(
            "your-rule-symbol",
            node=node,
            line=node.lineno,
        )
```

3. **Add tests** in `tests/`:
```python
def test_bad_pattern():
    """BAD: Should trigger your-rule-symbol."""
    # Code that violates the rule
    pass

def test_good_pattern():
    """GOOD: Should NOT trigger warning."""
    # Code that follows best practices
    pass
```

4. **Update README.md** with the new rule in the appropriate category table.

## Testing Strategy

### Test Categories

1. **Bad Examples**: Code that should trigger warnings
   - Should include rule ID in docstring
   - Should have clear comments explaining why it's bad

2. **Good Examples**: Code that should NOT trigger warnings
   - Should demonstrate best practices
   - Should cover edge cases

3. **Edge Cases**: Tricky scenarios
   - List comprehensions (not test logic)
   - Context managers (pytest.raises)
   - Built-in fixtures (tmp_path, mocker)

### Writing Good Tests

The automated test harness provides two base classes for writing tests:

**1. `PytestDeepAnalysisTestCase` - For single-file analysis:**

```python
from tests.test_harness.base import PytestDeepAnalysisTestCase, msg

class TestMyRule(PytestDeepAnalysisTestCase):
    """Tests for W9XXX: my-rule-symbol"""

    def test_should_trigger_warning(self):
        """Should warn when anti-pattern is detected."""
        code = """
        def test_something():
            bad_pattern()  # Line 3
        """
        self.assert_adds_messages(
            code,
            msg("my-rule-symbol", line=3)
        )

    def test_should_not_trigger(self):
        """Should NOT warn for acceptable code."""
        code = """
        def test_something():
            good_pattern()
        """
        self.assert_no_messages(code)
```

**2. `MultiFileTestCase` - For multi-file analysis (fixture interactions):**

```python
from tests.test_harness.base import MultiFileTestCase

def test_cross_file_fixture_issue():
    """Test fixture shadowing across conftest files."""
    test_case = MultiFileTestCase()

    test_case.setup_files({
        "conftest.py": """
            import pytest
            @pytest.fixture
            def my_fixture():
                return "parent"
        """,
        "subdir/conftest.py": """
            import pytest
            @pytest.fixture
            def my_fixture():  # Shadows parent
                return "child"
        """,
        "subdir/test_foo.py": """
            def test_foo(my_fixture):
                assert my_fixture
        """
    })

    test_case.assert_messages(
        expected=[("subdir/test_foo.py", "pytest-fix-shadowed", 2)],
        files=["subdir/test_foo.py"]
    )

    test_case.cleanup()
```

**Tips for Writing Tests:**
- Use clear, descriptive test names
- Include both positive (should warn) and negative (should not warn) tests
- Specify exact line numbers where warnings should appear
- Test edge cases and tricky scenarios
- Add comments to explain why code should or shouldn't trigger warnings

## Performance Considerations

- This linter prioritizes **depth over speed**
- Avoid adding checks that can be done by fast linters (Ruff, Flake8)
- Focus on semantic, cross-file analysis
- Document performance impact of new rules

## Questions?

- Open an issue for questions
- Tag maintainers for complex architectural questions
- Join discussions in existing issues

## Thank You!

Your contributions help make pytest testing better for the entire Python community!
