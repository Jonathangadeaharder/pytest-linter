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

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=pytest_deep_analysis --cov-report=html tests/

# Run specific test file
pytest tests/test_category1_flakiness.py
```

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

Test the linter on the test suite:

```bash
pylint --disable=all --enable=pytest-deep-analysis tests/
```

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

```
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

```python
def test_bad_example():
    """BAD: Brief description (RULE-ID)."""
    # Arrange
    setup_code()

    # Act - This should trigger the warning
    problematic_code()

    # Assert
    assert result


def test_good_example():
    """GOOD: Brief description of best practice."""
    # Demonstrate the correct approach
    proper_code()
    assert result
```

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
