//! Regression tests for the 2026-07-28 portfolio audit:
//! - #125: `UnusedFixtureRule` (PYTEST-FIX-005) must not flag fixtures used only
//!   through `@pytest.mark.usefixtures(...)` or `request.getfixturevalue("...")`.
//! - #126: `ShadowedFixtureRule` (PYTEST-FIX-004) must not flag the documented
//!   conftest -> test-module fixture-override idiom, and should report a genuine
//!   same-scope redefinition once rather than once per defining file.

use pytest_linter::config::Config;
use pytest_linter::engine::LintEngine;
use std::path::PathBuf;

fn write_temp_file(dir: &std::path::Path, name: &str, content: &str) -> PathBuf {
    let path = dir.join(name);
    std::fs::write(&path, content).unwrap();
    path
}

fn lint_paths(paths: &[PathBuf]) -> Vec<pytest_linter::models::Violation> {
    let engine = LintEngine::new(Config::default()).unwrap();
    engine.lint_paths(paths).unwrap()
}

fn violations_with_rule<'a>(
    violations: &'a [pytest_linter::models::Violation],
    rule_id: &str,
) -> Vec<&'a pytest_linter::models::Violation> {
    violations.iter().filter(|v| v.rule_id == rule_id).collect()
}

// --- #125: PYTEST-FIX-005 -------------------------------------------------

#[test]
fn test_usefixtures_mark_fixture_is_not_unused_fix005() {
    let dir = tempfile::tempdir().unwrap();
    let conftest = write_temp_file(
        dir.path(),
        "conftest.py",
        r#"
import pytest

@pytest.fixture
def db_transaction():
    yield "txn"

@pytest.fixture
def only_via_mark():
    return 42
"#,
    );
    let test_file = write_temp_file(
        dir.path(),
        "test_thing.py",
        r#"
import pytest

@pytest.mark.usefixtures("db_transaction", "only_via_mark")
def test_with_mark():
    assert 1 == 1
"#,
    );

    let violations = lint_paths(&[conftest, test_file]);
    let unused = violations_with_rule(&violations, "PYTEST-FIX-005");
    assert!(
        unused.iter().all(|v| !v.message.contains("db_transaction")),
        "fixture used via usefixtures mark should not be flagged: {unused:?}"
    );
    assert!(
        unused.iter().all(|v| !v.message.contains("only_via_mark")),
        "fixture used via usefixtures mark should not be flagged: {unused:?}"
    );
}

#[test]
fn test_getfixturevalue_fixture_is_not_unused_fix005() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_dynamic.py",
        r#"
import pytest

@pytest.fixture
def dynamic_fix():
    return 42

def test_uses_dynamic(request):
    value = request.getfixturevalue("dynamic_fix")
    assert value == 42
"#,
    );

    let violations = lint_paths(&[path]);
    let unused = violations_with_rule(&violations, "PYTEST-FIX-005");
    assert!(
        unused.iter().all(|v| !v.message.contains("dynamic_fix")),
        "fixture requested via getfixturevalue should not be flagged: {unused:?}"
    );
}

#[test]
fn test_genuinely_unused_fixture_still_flagged_fix005() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_unused_control.py",
        r#"
import pytest

@pytest.fixture
def truly_unused():
    return 42

@pytest.mark.usefixtures("something_else")
def test_with_unrelated_mark():
    assert True
"#,
    );

    let violations = lint_paths(&[path]);
    let unused = violations_with_rule(&violations, "PYTEST-FIX-005");
    assert!(
        unused.iter().any(|v| v.message.contains("truly_unused")),
        "a fixture referenced by no test should still be flagged: {unused:?}"
    );
}

// --- #126: PYTEST-FIX-004 -------------------------------------------------

#[test]
fn test_conftest_module_override_not_flagged_fix004() {
    let dir = tempfile::tempdir().unwrap();
    let conftest = write_temp_file(
        dir.path(),
        "conftest.py",
        r#"
import pytest

@pytest.fixture
def client():
    return "base-client"
"#,
    );
    let test_file = write_temp_file(
        dir.path(),
        "test_s.py",
        r#"
import pytest

@pytest.fixture
def client():
    return "module-client"

def test_uses_client(client):
    assert client == "module-client"
"#,
    );

    let violations = lint_paths(&[conftest, test_file]);
    let shadowed = violations_with_rule(&violations, "PYTEST-FIX-004");
    assert!(
        shadowed.iter().all(|v| !v.message.contains("client")),
        "conftest -> module override is a documented idiom and should not be flagged: {shadowed:?}"
    );
}

#[test]
fn test_same_scope_redefinition_still_flagged_once_fix004() {
    let dir = tempfile::tempdir().unwrap();
    let path1 = write_temp_file(
        dir.path(),
        "test_a.py",
        r#"
import pytest

@pytest.fixture
def shared_fix():
    return 42

def test_a(shared_fix):
    assert shared_fix == 42
"#,
    );
    let path2 = write_temp_file(
        dir.path(),
        "test_b.py",
        r#"
import pytest

@pytest.fixture
def shared_fix():
    return "hello"

def test_b(shared_fix):
    assert shared_fix == "hello"
"#,
    );

    let violations = lint_paths(&[path1, path2]);
    let shadowed = violations_with_rule(&violations, "PYTEST-FIX-004");
    assert_eq!(
        shadowed.len(),
        1,
        "genuine same-scope redefinition should be flagged exactly once: {shadowed:?}"
    );
    assert!(shadowed[0].message.contains("shared_fix"));
    assert!(shadowed[0].message.contains("2 different modules"));
}
