# Runtime Semantic Validation Plugin

**Complement static linting with runtime validation of BDD/PBT/DbC principles.**

---

## Overview

The **runtime semantic validation plugin** provides deep runtime analysis that's impossible to perform statically. It hooks into pytest execution to validate that:

- **BDD**: Gherkin steps actually execute (not just declared)
- **PBT**: Hypothesis strategies generate diverse, meaningful inputs
- **DbC**: icontract preconditions/postconditions actually constrain behavior
- **Semantic Coverage**: Tests verify meaningful properties (not just pass)

This complements the static linter (W9016-W9018) by answering: *"Do the semantic practices we enforce actually work at runtime?"*

---

## Installation

The runtime plugin is included with `pytest-deep-analysis`:

```bash
pip install pytest-deep-analysis
```

The plugin is automatically discovered by pytest via entry points.

---

## Usage

### Basic Usage

Enable runtime validation for all tests:

```bash
pytest --semantic-validate
```

### Selective Validation

Run only specific semantic checks:

```bash
# BDD validation only
pytest --semantic-validate --semantic-checks=bdd

# Multiple checks
pytest --semantic-validate --semantic-checks=bdd,pbt,coverage
```

### Report Formats

Generate reports in different formats:

```bash
# Terminal output (default)
pytest --semantic-validate

# HTML report with visualizations
pytest --semantic-validate --semantic-report=html

# JSON report for CI integration
pytest --semantic-validate --semantic-report=json
```

---

## Validation Types

### 1. BDD Validation (`--semantic-checks=bdd`)

**What it validates:**
- Gherkin steps declared in docstrings actually execute
- Function calls can be mapped to Given/When/Then steps
- Scenario coverage: % of steps with traced execution

**Example:**

```python
@pytest.mark.scenario("user_authentication.feature", "Successful login")
def test_user_login():
    """
    Given a registered user
    When the user logs in with valid credentials
    Then the user should see the dashboard
    """
    user = create_user("alice")  # Maps to "Given"
    response = login(user)        # Maps to "When"
    assert_dashboard(response)    # Maps to "Then"
```

**Runtime Output:**
```
✓ BDD scenario fully traced (100% coverage)
✓ All Gherkin steps mapped to executed functions
```

**Detects:**
- **Orphan Steps**: Steps declared but never executed
- **Low Coverage**: < 80% of steps traced to actual code
- **Missing Mappings**: Steps that don't match any function calls

---

### 2. PBT Analysis (`--semantic-checks=pbt`)

**What it validates:**
- Hypothesis generates diverse test inputs
- Properties aren't trivially true (always pass)
- Shrinking is effective when failures occur

**Example:**

```python
from hypothesis import given, strategies as st

@given(x=st.integers(min_value=1, max_value=1000))
def test_positive_properties(x):
    assert x > 0          # Meaningful property
    assert x ** 2 > x     # Not trivially true for x=1!
```

**Runtime Output:**
```
✓ 100 examples tried
✗ PBT-TRIVIAL-PROPERTY: Property held for all examples
  → Consider strengthening invariants or testing broader domains
```

**Detects:**
- **Too Few Examples**: Strategy generates < 10 examples (too narrow)
- **Trivial Properties**: Properties that never fail (always true)
- **Low Diversity**: Generated inputs are repetitive

---

### 3. DbC Tracking (`--semantic-checks=dbc`)

**What it validates:**
- icontract decorators are actually checked
- Contracts detect violations when they should
- Contracts aren't vacuously true (never violated)

**Example:**

```python
from icontract import require, ensure

@pytest.fixture
@require(lambda: database_available())
@ensure(lambda result: result.is_connected())
def db_connection():
    conn = create_connection()
    yield conn
    conn.close()

def test_database_operations(db_connection):
    # Runtime validates:
    # 1. Precondition checked before yield
    # 2. Postcondition checked after yield
    # 3. Violations are properly raised
    assert db_connection.execute("SELECT 1")
```

**Runtime Output:**
```
✓ 2 contracts checked (precondition, postcondition)
✗ DBC-VACUOUS-CONTRACTS: No violations detected in 50 tests
  → Add negative test cases to verify contracts catch errors
```

**Detects:**
- **No Contracts**: Functions that should have contracts don't
- **Vacuous Contracts**: Never violated (too permissive)
- **Ignored Violations**: Violations occur but test passes

---

### 4. Semantic Coverage (`--semantic-checks=coverage`)

**What it validates:**
- Tests have meaningful assertions (not just pass)
- Mock verifications are paired with state assertions
- Tests that pass but verify nothing are flagged

**Example:**

```python
def test_false_positive():
    """This test passes but verifies NOTHING."""
    x = complex_computation()
    # Missing assertion!

# Runtime detects:
# SEMANTIC-COVERAGE: Test passed but executed no assertions
```

---

## Integration with Static Linter

The runtime plugin complements static checks:

| Rule | Static Check (W9016-W9018) | Runtime Validation |
|------|---------------------------|-------------------|
| **BDD** | Detects missing `@pytest.mark.scenario` | Validates steps actually execute |
| **PBT** | Suggests Hypothesis for many params | Validates strategy diversity |
| **DbC** | Suggests icontract for complex fixtures | Validates contracts are enforced |

**Workflow:**
1. **Static linter** (fast): `pylint` detects missing practices
2. **Runtime validator** (slow): `pytest --semantic-validate` verifies effectiveness

---

## Configuration

### pytest.ini / pyproject.toml

```ini
[tool.pytest.ini_options]
# Enable by default in CI
addopts = "--semantic-validate --semantic-report=json"

# Disable specific checks
semantic_checks = "bdd,pbt"  # Skip DbC
```

### Markers

Register semantic validation markers:

```python
@pytest.mark.scenario("feature.file", "scenario name")
def test_with_bdd_traceability():
    pass

@pytest.mark.property("x + y == y + x for all integers")
def test_with_pbt_documentation():
    pass
```

---

## CI Integration

### GitHub Actions

```yaml
- name: Run tests with semantic validation
  run: |
    pytest --semantic-validate --semantic-report=json

- name: Upload semantic report
  uses: actions/upload-artifact@v3
  with:
    name: semantic-validation-report
    path: semantic-validation-report.json
```

### Fail on Semantic Issues

```python
# conftest.py
def pytest_sessionfinish(session, exitstatus):
    """Fail CI if semantic issues detected."""
    report_path = Path("semantic-validation-report.json")
    if report_path.exists():
        report = json.loads(report_path.read_text())
        if report["summary"]["total_issues"] > 0:
            session.exitstatus = 1  # Fail CI
```

---

## Reports

### Terminal Report

```
================================================================================
SEMANTIC VALIDATION REPORT
================================================================================

Summary:
  Total tests analyzed: 150
  Tests with semantic issues: 12
  Total semantic issues: 24

GLOBAL ISSUES:
  • BDD-MISSING: test_user_login lacks scenario marker or Gherkin docstring

TEST-SPECIFIC ISSUES:

  tests/test_auth.py::test_password_validation:
    • BDD-ORPHAN-STEP: 'Given an invalid password' declared but no matching function executed
    • BDD-LOW-COVERAGE: Only 66.7% of Gherkin steps mapped to executed functions (2/3)

RECOMMENDATIONS:
  💡 Consider using pytest-bdd to formalize Gherkin scenario execution
  💡 Add meaningful assertions to tests that currently pass without verification

================================================================================
```

### HTML Report

Rich HTML report with:
- Summary dashboard with metrics
- Issue breakdown by test and severity
- Actionable recommendations
- Charts showing coverage trends

### JSON Report

Machine-readable format for CI:

```json
{
  "generated_at": "2025-01-13T10:30:00",
  "summary": {
    "total_tests": 150,
    "tests_with_issues": 12,
    "total_issues": 24
  },
  "test_issues": {
    "tests/test_auth.py::test_login": {
      "test_name": "test_login",
      "passed": true,
      "issues": [
        "BDD-ORPHAN-STEP: 'Given a user' not executed"
      ]
    }
  }
}
```

---

## Performance Considerations

Runtime validation adds overhead:

| Validation Type | Overhead | When to Use |
|----------------|----------|-------------|
| BDD | ~5-10% | Always in CI, optional locally |
| PBT | ~10-15% | When using Hypothesis |
| DbC | ~2-5% | When using icontract |
| Coverage | ~15-20% | Full validation runs only |

**Recommendation:** Use `--semantic-checks=<specific>` to minimize overhead.

---

## Limitations

**What Runtime Validation Cannot Do:**

1. **Fix Bad Tests**: Only detects issues, doesn't auto-fix
2. **Prove Correctness**: Runtime validation is heuristic-based
3. **Replace Static Checks**: Complements, doesn't replace static linting
4. **Validate Logic**: Can't determine if invariants are "correct"

**What It CAN Do:**

✅ Detect false-positive tests (pass but verify nothing)
✅ Map Gherkin steps to actual execution
✅ Identify trivial properties in PBT
✅ Track contract enforcement
✅ Generate actionable recommendations

---

## Troubleshooting

### "No semantic issues detected but tests have obvious problems"

**Solution:** Check that markers are properly registered:

```python
# conftest.py
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "scenario: BDD scenario marker"
    )
```

### "BDD steps not mapping to functions"

**Solution:** Use conventional naming or explicit mappings:

```python
# Use snake_case matching step text
def given_a_registered_user():  # Matches "Given a registered user"
    pass
```

### "High overhead, tests run slow"

**Solution:** Use selective validation:

```bash
# Only validate changed tests
pytest --semantic-validate tests/test_new_feature.py

# Or use faster checks only
pytest --semantic-checks=coverage
```

---

## Advanced Usage

### Custom Validators

Extend the plugin with custom validators:

```python
# conftest.py
from pytest_deep_analysis.runtime import SemanticValidationPlugin

def pytest_configure(config):
    plugin = config.pluginmanager.get_plugin("semantic_validation")
    if plugin:
        # Add custom validator
        plugin.register_validator(MyCustomValidator())
```

### Programmatic API

Use the plugin programmatically:

```python
from pytest_deep_analysis.runtime.bdd_validator import BDDValidator

validator = BDDValidator()
issues = validator.validate_scenario_execution(
    gherkin_steps=["Given a user", "When login", "Then success"],
    function_calls=[{"name": "create_user"}, {"name": "login"}]
)
print(issues)  # ["BDD-ORPHAN-STEP: 'Then success' not executed"]
```

---

## See Also

- **Static Linter Docs**: `/docs/static-linter.md`
- **BDD Best Practices**: `/docs/bdd-guide.md`
- **Hypothesis Integration**: `/docs/pbt-guide.md`
- **icontract Guide**: `/docs/dbc-guide.md`
