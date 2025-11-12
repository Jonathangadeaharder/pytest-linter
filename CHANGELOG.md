# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-11-11

### Added

#### Category 1: Test Body Smells (Flakiness)
- **W9001** (`pytest-flk-time-sleep`): Detect `time.sleep()` in test functions
- **W9002** (`pytest-flk-io-open`): Detect direct `open()` calls in tests
- **W9003** (`pytest-flk-network-import`): Detect network module imports
- **W9004** (`pytest-flk-cwd-dependency`): Detect CWD-sensitive functions

#### Category 1: Test Body Smells (Maintenance)
- **W9011** (`pytest-mnt-test-logic`): Detect conditional logic in tests
- **W9012** (`pytest-mnt-magic-assert`): Detect magic numbers/strings in asserts
- **W9013** (`pytest-mnt-suboptimal-assert`): Detect suboptimal assert patterns

#### Category 2: Fixture Definition Smells
- **W9021** (`pytest-fix-autouse`): Detect `autouse=True` fixtures

#### Category 3: Fixture Interaction Smells
- **E9031** (`pytest-fix-session-mutation`): Detect session fixture mutations (planned)
- **E9032** (`pytest-fix-invalid-scope`): Detect invalid fixture scope dependencies
- **W9033** (`pytest-fix-shadowed`): Detect shadowed fixtures (partial implementation)
- **W9034** (`pytest-fix-unused`): Detect unused fixtures
- **E9035** (`pytest-fix-stateful-session`): Detect stateful session fixtures

### Architecture
- Implemented as a Pylint plugin leveraging astroid's inference engine
- Multi-pass analysis for fixture graph building and validation
- Project-wide semantic analysis across conftest.py files

### Documentation
- Comprehensive README with examples and usage guidelines
- Contributing guidelines for developers
- MIT License
- Example Pylint configuration file

### Testing
- Test suite demonstrating all rule categories
- Examples of both anti-patterns and best practices
- Multi-level conftest.py structure for shadowing tests

## [Unreleased]

### Added
- **Automated Test Harness**: Comprehensive test suite using `pylint.testutils`
  - 66 automated unit tests covering all linter rules
  - Tests validate message IDs, line numbers, and edge cases
  - Base test infrastructure in `tests/test_harness/base.py`
  - Tests for Category 1 (flakiness & maintenance), Category 2 (fixture definition), and Category 3 (fixture interaction)
  - Documentation in `tests/test_harness/README.md`
  - Updated `CONTRIBUTING.md` with testing guidelines
- **Improved Development Workflow**:
  - Tests run in <2 seconds vs manual visual inspection
  - Automated regression detection in CI
  - Clear separation between example files (`tests/test_category*.py`) and automated tests (`tests/test_harness/`)

### Planned Features
- Improved fixture shadowing detection across conftest.py hierarchies
- Detection of fixtures that perform database commits without cleanup
- Warnings about tests that modify fixture state in-place
- Identification of fixtures that could be narrowed in scope
- pytest.mark.parametrize anti-pattern detection
- Custom rule configuration via pyproject.toml
- Integration with pytest-xdist for parallel analysis

### Known Limitations
- Shadowed fixture detection requires refactoring fixture graph structure
- Session mutation detection is heuristic-based (limited type inference)
- Some false positives on common patterns (e.g., HTTP status code 200)
- Performance scales linearly with project size (intentional trade-off)

---

[0.1.0]: https://github.com/yourusername/pytest-deep-analysis/releases/tag/v0.1.0
