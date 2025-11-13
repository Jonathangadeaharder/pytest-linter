# Automated Test Harness for pytest-deep-analysis

This directory contains the automated test suite for the pytest-deep-analysis linter, built using `pylint.testutils`.

## Overview

The test harness validates that the linter correctly:
- **Detects anti-patterns** (positive tests)
- **Ignores acceptable code** (negative tests)
- **Reports correct line numbers** for warnings
- **Handles edge cases** appropriately

## Running Tests

```bash
# Run all tests
python -m pytest tests/test_harness/ -v

# Run specific category
python -m pytest tests/test_harness/test_category1_flakiness.py -v

# Run with coverage
python -m pytest tests/test_harness/ --cov=pytest_deep_analysis --cov-report=html
```

## Test Structure

- **`base.py`**: Core test infrastructure using `pylint.testutils.CheckerTestCase`
- **`test_category1_flakiness.py`**: Tests for W9001-W9004 (flakiness rules)
- **`test_category1_maintenance.py`**: Tests for W9011-W9013 (maintenance rules)
- **`test_category2_fixtures.py`**: Tests for W9021 (fixture definition rules)
- **`test_category3_fixtures.py`**: Tests for E9032, W9033, W9034, E9035 (fixture interaction rules)

## Current Status

**90/90 tests passing** ✅ (100% pass rate)

## Adding New Tests

See `CONTRIBUTING.md` for detailed examples. Quick reference:

```python
from tests.test_harness.base import PytestDeepAnalysisTestCase, msg

class TestMyRule(PytestDeepAnalysisTestCase):
    def test_should_warn(self):
        code = """
        def test_foo():
            bad_pattern()  # Line 3
        """
        self.assert_adds_messages(
            code,
            msg("my-rule-symbol", line=3)
        )

    def test_should_not_warn(self):
        code = """
        def test_foo():
            good_pattern()
        """
        self.assert_no_messages(code)
```

## Benefits of This Approach

Compared to manual testing with `pylint tests/` and visual inspection:

✅ **Automated**: Tests run in CI and catch regressions
✅ **Precise**: Validates exact line numbers and message IDs
✅ **Fast**: Run tests in <2 seconds vs manual inspection
✅ **Comprehensive**: Tests both positive and negative cases
✅ **Documented**: Tests serve as executable specification

## Future Improvements

- [ ] Fix test expectations for magic number edge cases
- [ ] Add more suboptimal assert pattern tests
- [ ] Create multi-file integration tests for fixture shadowing
- [ ] Add performance benchmarks
- [ ] Test message arguments (not just msg_id and line)
