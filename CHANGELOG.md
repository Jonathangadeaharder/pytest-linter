# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-11-13

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
  - 90 automated unit tests covering all linter rules (100% passing)
  - Tests validate message IDs, line numbers, and edge cases
  - Base test infrastructure in `tests/test_harness/base.py` with automatic semantic check filtering
  - Tests for Category 1 (flakiness & maintenance), Category 2 (fixture definition), and Category 3 (fixture interaction)
  - New semantic quality test suite in `tests/test_harness/test_semantic_quality.py` (24 tests)
  - Documentation in `tests/test_harness/README.md`
  - Updated `CONTRIBUTING.md` with testing guidelines
- **Configuration Support** via `pyproject.toml`
  - `magic-assert-allowlist`: Configure domain-specific constants (fixes false positives for HTTP codes, etc.)
  - New `config.py` module for centralized configuration management
  - Python 3.8-3.10 support via `tomli`, Python 3.11+ via built-in `tomllib`
  - Example configuration in `pyproject.toml.example`
  - Documentation in README with real-world examples
- **Improved Development Workflow**:
  - Tests run in <1 second vs manual visual inspection
  - Automated regression detection in CI
  - Clear separation between example files (`tests/test_category*.py`) and automated tests (`tests/test_harness/`)
  - Configurable rules reduce false positives in production codebases
- **Advanced Linter Enhancements**:
  - **Improved Fixture Shadowing Detection** (W9033): Refactored fixture graph to support multiple definitions per name, enabling detection of same-file and cross-file shadowing
  - **Enhanced Type Inference** (E9035): Stateful session fixture detection now uses astroid's inference engine for more accurate mutable type detection
  - **CI/CD Integration**: GitHub Actions workflow with multi-Python testing (3.8-3.12), code quality checks, and coverage reporting
- **Semantic Quality Enforcement** (BDD/PBT/DbC alignment):
  - **E9014** (`pytest-test-no-assert`): Detect assertion-free tests (H-3 heuristic) - CRITICAL indicator of low-value tests
  - **W9015** (`pytest-mock-only-verify`): Detect interaction-only tests without state assertions (H-9 heuristic)
  - **W9016** (`pytest-bdd-missing-scenario`): Enforce BDD traceability via `@pytest.mark.scenario` or Gherkin docstrings
  - **W9017** (`pytest-no-property-test-hint`): Suggest property-based testing (Hypothesis) for heavily parametrized tests
  - **W9018** (`pytest-no-contract-hint`): Suggest Design by Contract (icontract) for complex fixtures
  - These checks bridge the "semantic gap" between syntactic coverage and requirements validation
  - Can be disabled individually via pylint configuration if too opinionated for your workflow
- **Runtime Semantic Validation Plugin** (`pytest --semantic-validate`):
  - **Pytest plugin** for runtime validation of semantic properties impossible to check statically
  - **BDD Validator**: Maps Gherkin steps to actual function execution, detects orphan steps, generates RTM
  - **PBT Analyzer**: Validates Hypothesis strategy diversity, detects trivial properties, analyzes shrinking behavior
  - **DbC Tracker**: Monitors icontract enforcement, detects vacuous contracts, tracks violation rates
  - **Semantic Coverage**: Identifies false-positive tests (pass but verify nothing meaningful)
  - **Multi-format reports**: Terminal (colorized), HTML (with charts), JSON (CI integration)
  - **Low overhead**: Selective validation via `--semantic-checks=bdd,pbt,dbc,coverage`
  - Complete documentation in `pytest_deep_analysis/runtime/README.md`

### Fixed
- Fixture shadowing detection now works for same-file redefinitions (previously a known limitation)
- Stateful session fixture detection is more accurate with type inference (fewer false negatives)
- Fixture graph no longer registers duplicates when using test harness

### Planned Features
- Improved fixture shadowing detection across conftest.py hierarchies
- Detection of fixtures that perform database commits without cleanup
- Warnings about tests that modify fixture state in-place
- Identification of fixtures that could be narrowed in scope
- pytest.mark.parametrize anti-pattern detection
- Custom rule configuration via pyproject.toml
- Integration with pytest-xdist for parallel analysis

### Known Limitations
- ~~Shadowed fixture detection requires refactoring fixture graph structure~~ ✅ **FIXED**
- ~~Session mutation detection is heuristic-based (limited type inference)~~ ✅ **IMPROVED**
- ~~Some false positives on common patterns (e.g., HTTP status code 200)~~ ✅ **FIXED via configuration**
- Performance scales linearly with project size (intentional trade-off)

---

[0.1.0]: https://github.com/yourusername/pytest-deep-analysis/releases/tag/v0.1.0
