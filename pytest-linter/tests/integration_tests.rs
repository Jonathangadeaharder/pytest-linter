use pytest_linter::engine::LintEngine;
use pytest_linter::models::{Category, FixtureScope, Severity};
use pytest_linter::parser::PythonParser;
use std::path::PathBuf;

fn write_temp_file(dir: &std::path::Path, name: &str, content: &str) -> PathBuf {
    let path = dir.join(name);
    std::fs::write(&path, content).unwrap();
    path
}

fn parse_file(path: &PathBuf) -> pytest_linter::models::ParsedModule {
    let mut parser = PythonParser::new().unwrap();
    parser.parse_file(path).unwrap()
}

fn lint_single_file(path: &PathBuf) -> Vec<pytest_linter::models::Violation> {
    let engine = LintEngine::new().unwrap();
    engine.lint_paths(&[path.clone()]).unwrap()
}

fn find_violation<'a>(
    violations: &'a [pytest_linter::models::Violation],
    rule_id: &str,
) -> Option<&'a pytest_linter::models::Violation> {
    violations.iter().find(|v| v.rule_id == rule_id)
}

#[test]
fn test_time_sleep_triggers_flk001() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_flaky.py",
        r#"
import time

def test_waits():
    time.sleep(2)
    assert True
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.test_functions.len(), 1);
    assert!(module.test_functions[0].uses_time_sleep);

    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-FLK-001");
    assert!(v.is_some(), "Expected PYTEST-FLK-001 violation");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "TimeSleepRule");
    assert_eq!(v.severity, Severity::Warning);
    assert_eq!(v.category, Category::Flakiness);
    assert!(v.message.contains("time.sleep"));
    assert!(v.suggestion.is_some());
}

#[test]
fn test_file_io_without_tmp_path_triggers_flk002() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_file_io.py",
        r#"
def test_reads_file():
    f = open("data.txt")
    content = f.read()
    f.close()
    assert content
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.test_functions.len(), 1);
    assert!(module.test_functions[0].uses_file_io);
    assert!(!module.test_functions[0]
        .fixture_deps
        .iter()
        .any(|d| d == "tmp_path"));

    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-FLK-002");
    assert!(v.is_some(), "Expected PYTEST-FLK-002 violation");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "FileIoRule");
    assert_eq!(v.category, Category::Flakiness);
    assert!(v.message.contains("file I/O"));
}

#[test]
fn test_file_io_with_tmp_path_does_not_trigger_flk002() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_file_io_safe.py",
        r#"
def test_reads_file(tmp_path):
    f = open(str(tmp_path / "data.txt"))
    content = f.read()
    f.close()
    assert content
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-FLK-002");
    assert!(v.is_none(), "Should not trigger PYTEST-FLK-002 when tmp_path is used");
}

#[test]
fn test_network_import_triggers_flk003() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_network.py",
        r#"
import requests

def test_api():
    assert True
"#,
    );
    let module = parse_file(&path);
    assert!(module.imports.iter().any(|imp| imp.contains("requests")));

    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-FLK-003");
    assert!(v.is_some(), "Expected PYTEST-FLK-003 violation");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "NetworkImportRule");
    assert_eq!(v.category, Category::Flakiness);
    assert!(v.message.contains("network"));
}

#[test]
fn test_conditional_logic_triggers_mnt001() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_logic.py",
        r#"
def test_with_condition():
    x = 5
    if x > 3:
        assert True
    else:
        assert False
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.test_functions.len(), 1);
    assert!(module.test_functions[0].has_conditional_logic);

    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-MNT-001");
    assert!(v.is_some(), "Expected PYTEST-MNT-001 violation");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "TestLogicRule");
    assert_eq!(v.category, Category::Maintenance);
    assert!(v.message.contains("conditional logic"));
}

#[test]
fn test_no_assertions_triggers_mnt004() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_no_assert.py",
        r#"
def test_does_nothing():
    x = 42
    print(x)
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.test_functions.len(), 1);
    assert!(!module.test_functions[0].has_assertions);

    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-MNT-004");
    assert!(v.is_some(), "Expected PYTEST-MNT-004 violation");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "NoAssertionRule");
    assert_eq!(v.severity, Severity::Error);
    assert_eq!(v.category, Category::Maintenance);
    assert!(v.message.contains("no assertions"));
}

#[test]
fn test_try_except_triggers_mnt007() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_try_except.py",
        r#"
def test_catches_exception():
    try:
        risky_operation()
    except ValueError:
        pass
    assert True
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.test_functions.len(), 1);
    assert!(module.test_functions[0].has_try_except);

    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-MNT-007");
    assert!(v.is_some(), "Expected PYTEST-MNT-007 violation");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "RawExceptionHandlingRule");
    assert!(v.message.contains("try/except"));
    assert!(v.suggestion.as_ref().unwrap().contains("pytest.raises"));
}

#[test]
fn test_autouse_fixture_triggers_fix001() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_autouse.py",
        r#"
import pytest

@pytest.fixture(autouse=True)
def setup_env():
    os.environ["TEST"] = "1"
    yield
    del os.environ["TEST"]

def test_something():
    assert True
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.fixtures.len(), 1);
    assert!(module.fixtures[0].is_autouse);

    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-FIX-001");
    assert!(v.is_some(), "Expected PYTEST-FIX-001 violation");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "AutouseFixtureRule");
    assert_eq!(v.category, Category::Fixture);
    assert!(v.message.contains("autouse"));
}

#[test]
fn test_many_assertions_triggers_mnt006() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_many_asserts.py",
        r#"
def test_many_things():
    assert 1 == 1
    assert 2 == 2
    assert 3 == 3
    assert 4 == 4
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.test_functions.len(), 1);
    assert!(module.test_functions[0].assertion_count > 3);

    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-MNT-006");
    assert!(v.is_some(), "Expected PYTEST-MNT-006 violation");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "AssertionRouletteRule");
    assert!(v.message.contains("assertion roulette"));
}

#[test]
fn test_few_assertions_does_not_trigger_mnt006() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_few_asserts.py",
        r#"
def test_simple():
    assert True
    assert False == False
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-MNT-006");
    assert!(v.is_none(), "Should not trigger PYTEST-MNT-006 with <= 3 assertions");
}

#[test]
fn test_clean_file_has_no_error_violations() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_clean.py",
        r#"
def test_addition():
    assert 1 + 1 == 2

def test_subtraction():
    assert 3 - 1 == 2
"#,
    );
    let violations = lint_single_file(&path);
    let error_violations: Vec<_> = violations
        .iter()
        .filter(|v| v.severity == Severity::Error)
        .collect();
    assert!(
        error_violations.is_empty(),
        "Clean test file should not have Error-severity violations, got: {:?}",
        error_violations
    );
}

#[test]
fn test_engine_lint_paths_end_to_end() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_multi.py",
        r#"
import time
import requests

def test_has_sleep():
    time.sleep(1)
    assert True

def test_no_assert():
    x = 42

def test_many_asserts():
    assert 1 == 1
    assert 2 == 2
    assert 3 == 3
    assert 4 == 4
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    assert!(!violations.is_empty(), "Expected multiple violations");

    let rule_ids: Vec<&str> = violations.iter().map(|v| v.rule_id.as_str()).collect();
    assert!(rule_ids.contains(&"PYTEST-FLK-001"), "Should detect time.sleep");
    assert!(rule_ids.contains(&"PYTEST-FLK-003"), "Should detect network import");
    assert!(rule_ids.contains(&"PYTEST-MNT-004"), "Should detect no assertion");
    assert!(rule_ids.contains(&"PYTEST-MNT-006"), "Should detect assertion roulette");
}

#[test]
fn test_violation_ordering() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_order.py",
        r#"
def test_a():
    assert True

def test_b():
    pass
"#,
    );
    let violations = lint_single_file(&path);
    for i in 1..violations.len() {
        assert!(
            violations[i - 1] <= violations[i],
            "Violations should be sorted: {:?} > {:?}",
            violations[i - 1],
            violations[i]
        );
    }
}

#[test]
fn test_parser_extracts_test_functions() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_parse.py",
        r#"
def helper():
    return 42

def test_one():
    assert helper() == 42

def test_two():
    assert True

def not_a_test():
    pass
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.test_functions.len(), 2);
    let names: Vec<&str> = module
        .test_functions
        .iter()
        .map(|t| t.name.as_str())
        .collect();
    assert!(names.contains(&"test_one"));
    assert!(names.contains(&"test_two"));
    assert!(!names.contains(&"helper"));
    assert!(!names.contains(&"not_a_test"));
}

#[test]
fn test_parser_extracts_imports() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_imports.py",
        r#"
import os
import sys
from pathlib import Path

def test_something():
    assert True
"#,
    );
    let module = parse_file(&path);
    assert!(module.imports.iter().any(|imp| imp.contains("import os")));
    assert!(module.imports.iter().any(|imp| imp.contains("import sys")));
    assert!(module.imports.iter().any(|imp| imp.contains("pathlib")));
}

#[test]
fn test_parser_extracts_fixtures() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_fixtures_parse.py",
        r#"
import pytest

@pytest.fixture
def my_fixture():
    return 42

@pytest.fixture(scope="module")
def module_fixture():
    return {}

def test_uses_fixture(my_fixture):
    assert my_fixture == 42
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.fixtures.len(), 2);

    let f1 = module.fixtures.iter().find(|f| f.name == "my_fixture").unwrap();
    assert_eq!(f1.scope, FixtureScope::Function);
    assert!(!f1.is_autouse);

    let f2 = module.fixtures.iter().find(|f| f.name == "module_fixture").unwrap();
    assert_eq!(f2.scope, FixtureScope::Module);
}

#[test]
fn test_non_test_file_is_ignored() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "helper.py",
        r#"
import time

def test_waits():
    time.sleep(2)
    assert True
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    assert!(violations.is_empty(), "Non-test files should be ignored");
}

#[test]
fn test_conftest_is_recognized_as_test_file() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "conftest.py",
        r#"
import pytest

@pytest.fixture(autouse=True)
def auto_fixture():
    return 42
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    let v = find_violation(&violations, "PYTEST-FIX-001");
    assert!(v.is_some(), "conftest.py should be parsed and autouse detected");
}

#[test]
fn test_mystery_guest_triggers_flk005() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_mystery.py",
        r#"
def test_reads_file():
    f = open("data.txt")
    content = f.read()
    f.close()
    assert content
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-FLK-005");
    assert!(v.is_some(), "Expected PYTEST-FLK-005 Mystery Guest violation");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "MysteryGuestRule");
}

#[test]
fn test_fixture_db_commit_no_cleanup_triggers_fix008() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_db.py",
        r#"
import pytest

@pytest.fixture
def db_fixture():
    conn = get_connection()
    conn.commit()
    return conn

def test_db(db_fixture):
    assert True
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-FIX-008");
    assert!(v.is_some(), "Expected PYTEST-FIX-008 for DB commit without rollback");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "FixtureDbCommitNoCleanupRule");
}

#[test]
fn test_violation_contains_correct_file_path() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_path.py",
        r#"
def test_empty():
    pass
"#,
    );
    let violations = lint_single_file(&path);
    assert!(!violations.is_empty());
    for v in &violations {
        assert_eq!(v.file_path, path);
    }
}

#[test]
fn test_parametrized_test_detection() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_param.py",
        r#"
import pytest

@pytest.mark.parametrize("val", [1, 2, 3])
def test_values(val):
    assert val > 0
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.test_functions.len(), 1);
    assert!(module.test_functions[0].is_parametrized);
    assert!(module.test_functions[0].parametrize_count.is_some());
}

#[test]
fn test_async_test_detection() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_async.py",
        r#"
async def test_async_thing():
    assert True
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.test_functions.len(), 1);
    assert!(module.test_functions[0].is_async);
}

#[test]
fn test_run_linter_clean_file_returns_no_errors() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_clean_lint.py",
        r#"
def test_ok():
    assert True
"#,
    );
    let has_errors =
        pytest_linter::engine::run_linter(&[path], "json", None, true).unwrap();
    assert!(!has_errors);
}

#[test]
fn test_run_linter_with_errors_returns_true() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_bad_lint.py",
        r#"
def test_bad():
    pass
"#,
    );
    let has_errors =
        pytest_linter::engine::run_linter(&[path], "json", None, true).unwrap();
    assert!(has_errors);
}

#[test]
fn test_run_linter_json_to_file() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_json_out.py",
        r#"
def test_ok():
    assert True
"#,
    );
    let output_path = dir.path().join("output.json");
    let has_errors = pytest_linter::engine::run_linter(
        &[path],
        "json",
        Some(&output_path),
        true,
    )
    .unwrap();
    assert!(!has_errors, "Info-only violations should not be errors");
    let content = std::fs::read_to_string(&output_path).unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&content).unwrap();
    assert!(parsed.is_array());
}

#[test]
fn test_run_linter_terminal_to_file() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_term_out.py",
        r#"
def test_bad():
    pass
"#,
    );
    let output_path = dir.path().join("output.txt");
    let has_errors = pytest_linter::engine::run_linter(
        &[path],
        "terminal",
        Some(&output_path),
        true,
    )
    .unwrap();
    assert!(has_errors);
    let content = std::fs::read_to_string(&output_path).unwrap();
    assert!(content.contains("ERROR"));
    assert!(content.contains("Summary"));
}

#[test]
fn test_run_linter_terminal_with_info_violations() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_term_info.py",
        r#"
def test_ok():
    assert 1 + 1 == 2
"#,
    );
    let output_path = dir.path().join("info.txt");
    let has_errors = pytest_linter::engine::run_linter(
        &[path],
        "terminal",
        Some(&output_path),
        true,
    )
    .unwrap();
    assert!(!has_errors, "Info-only violations should not be errors");
    let content = std::fs::read_to_string(&output_path).unwrap();
    assert!(content.contains("Summary"));
    assert!(content.contains("info"));
}

#[test]
fn test_run_linter_no_test_files_no_violations() {
    let dir = tempfile::tempdir().unwrap();
    let output_path = dir.path().join("empty.txt");
    let has_errors = pytest_linter::engine::run_linter(
        &[dir.path().to_path_buf()],
        "terminal",
        Some(&output_path),
        true,
    )
    .unwrap();
    assert!(!has_errors);
    let content = std::fs::read_to_string(&output_path).unwrap();
    assert!(content.contains("No violations found"));
}

#[test]
fn test_run_linter_json_output_contains_violation() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_json_violation.py",
        r#"
def test_no_assert():
    x = 42
"#,
    );
    let output_path = dir.path().join("violations.json");
    pytest_linter::engine::run_linter(
        &[path],
        "json",
        Some(&output_path),
        true,
    )
    .unwrap();
    let content = std::fs::read_to_string(&output_path).unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&content).unwrap();
    let arr = parsed.as_array().unwrap();
    assert!(!arr.is_empty());
    let has_mnt004 = arr.iter().any(|v| v["rule_id"].as_str().unwrap() == "PYTEST-MNT-004");
    assert!(has_mnt004);
}

#[test]
fn test_invalid_scope_triggers_fix003() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_scope.py",
        r#"
import pytest

@pytest.fixture
def func_scoped():
    return 42

@pytest.fixture(scope="session")
def session_scoped(func_scoped):
    return func_scoped

def test_thing(session_scoped):
    assert session_scoped == 42
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-FIX-003");
    assert!(v.is_some(), "Expected PYTEST-FIX-003 for invalid scope");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "InvalidScopeRule");
    assert!(v.message.contains("session_scoped"));
    assert!(v.message.contains("func_scoped"));
}

#[test]
fn test_shadowed_fixture_triggers_fix004() {
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
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path1, path2]).unwrap();
    let v = find_violation(&violations, "PYTEST-FIX-004");
    assert!(v.is_some(), "Expected PYTEST-FIX-004 for shadowed fixture");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "ShadowedFixtureRule");
    assert!(v.message.contains("shared_fix"));
    assert!(v.message.contains("2 different modules"));
}

#[test]
fn test_unused_fixture_triggers_fix005() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_unused.py",
        r#"
import pytest

@pytest.fixture
def unused_fixture():
    return 42

def test_something():
    assert True
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-FIX-005");
    assert!(v.is_some(), "Expected PYTEST-FIX-005 for unused fixture");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "UnusedFixtureRule");
    assert!(v.message.contains("unused_fixture"));
}

#[test]
fn test_stateful_session_fixture_triggers_fix006() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_stateful.py",
        r#"
import pytest

@pytest.fixture(scope="session")
def shared_list():
    return []

def test_uses_list(shared_list):
    shared_list.append(1)
    assert len(shared_list) == 1
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-FIX-006");
    assert!(v.is_some(), "Expected PYTEST-FIX-006 for stateful session fixture");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "StatefulSessionFixtureRule");
    assert!(v.message.contains("shared_list"));
    assert!(v.message.contains("mutable state"));
}

#[test]
fn test_db_commit_no_cleanup_with_yield_does_not_trigger() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_db_yield.py",
        r#"
import pytest

@pytest.fixture
def db_with_cleanup():
    conn = get_conn()
    conn.commit()
    yield conn
    conn.rollback()

def test_db(db_with_cleanup):
    assert True
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-FIX-008");
    assert!(v.is_none(), "Should not trigger FIX-008 when fixture has yield");
}

#[test]
fn test_mock_only_verify_triggers_mnt005() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_mock_verify.py",
        r#"
def test_mock_only(mock_obj):
    mock_obj.assert_called()
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-MNT-005");
    assert!(v.is_some(), "Expected PYTEST-MNT-005 for mock-only verify");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "MockOnlyVerifyRule");
    assert!(v.message.contains("mock_only"));
    assert!(v.message.contains("mocks without checking state"));
}

#[test]
fn test_mock_with_state_assertions_does_not_trigger_mnt005() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_mock_state.py",
        r#"
def test_mock_and_state(mock_obj):
    mock_obj.assert_called()
    assert 1 == 1
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-MNT-005");
    assert!(v.is_none(), "Should not trigger MNT-005 when test has state assertions");
}

#[test]
fn test_bdd_missing_scenario_triggers_bdd001() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_bdd.py",
        r#"
def test_without_gherkin():
    assert True
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-BDD-001");
    assert!(v.is_some(), "Expected PYTEST-BDD-001 for missing BDD scenario");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "BddMissingScenarioRule");
    assert_eq!(v.severity, Severity::Info);
}

#[test]
fn test_bdd_with_gherkin_does_not_trigger_bdd001() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_bdd_ok.py",
        r#"
def test_with_gherkin():
    """Given a setup when an action then a result."""
    assert True
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-BDD-001");
    assert!(v.is_none(), "Should not trigger BDD-001 when docstring has Gherkin");
}

#[test]
fn test_property_test_hint_triggers_pbt001() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_pbt.py",
        r#"
import pytest

@pytest.mark.parametrize("val", [1, 2, 3, 4])
def test_many(val):
    assert val > 0
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-PBT-001");
    assert!(v.is_some(), "Expected PYTEST-PBT-001 for many parametrize cases");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "PropertyTestHintRule");
    assert!(v.message.contains("parametrized cases"));
    assert!(v.suggestion.as_ref().unwrap().contains("hypothesis"));
}

#[test]
fn test_property_test_hint_few_cases_does_not_trigger() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_pbt_few.py",
        r#"
import pytest

@pytest.mark.parametrize("val", [1, 2, 3])
def test_few(val):
    assert val > 0
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-PBT-001");
    assert!(v.is_none(), "Should not trigger PBT-001 with <= 3 cases");
}

#[test]
fn test_parametrize_empty_triggers_param001() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_param_empty.py",
        r#"
import pytest

@pytest.mark.parametrize("val", [1])
def test_single(val):
    assert val > 0
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-PARAM-001");
    assert!(v.is_some(), "Expected PYTEST-PARAM-001 for single parametrize case");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "ParametrizeEmptyRule");
    assert!(v.message.contains("only"));
}

#[test]
fn test_xdist_fixture_io_triggers_xdist002() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_xdist.py",
        r#"
import pytest

@pytest.fixture(scope="session")
def session_data():
    f = open("data.txt")
    data = f.read()
    f.close()
    return data

def test_data(session_data):
    assert session_data
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-XDIST-002");
    assert!(v.is_some(), "Expected PYTEST-XDIST-002 for session fixture with I/O");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "XdistFixtureIoRule");
    assert!(v.message.contains("session_data"));
    assert!(v.message.contains("file I/O"));
}

#[test]
fn test_xdist_fixture_io_function_scope_does_not_trigger() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_xdist_ok.py",
        r#"
import pytest

@pytest.fixture
def func_data():
    f = open("data.txt")
    data = f.read()
    f.close()
    return data

def test_data(func_data):
    assert func_data
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-XDIST-002");
    assert!(v.is_none(), "Should not trigger XDIST-002 for function-scoped fixture");
}

#[test]
fn test_assertion_roulette_exactly_3_does_not_trigger() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_3_asserts.py",
        r#"
def test_three():
    assert 1 == 1
    assert 2 == 2
    assert 3 == 3
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.test_functions[0].assertion_count, 3);
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-MNT-006");
    assert!(
        v.is_none(),
        "Should not trigger PYTEST-MNT-006 with exactly 3 assertions"
    );
}

#[test]
fn test_assertion_roulette_exactly_4_triggers() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_4_asserts.py",
        r#"
def test_four():
    assert 1 == 1
    assert 2 == 2
    assert 3 == 3
    assert 4 == 4
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.test_functions[0].assertion_count, 4);
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-MNT-006");
    assert!(v.is_some(), "Expected PYTEST-MNT-006 with exactly 4 assertions");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "AssertionRouletteRule");
}

#[test]
fn test_parser_parametrize_count_three() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_pcount.py",
        r#"
import pytest

@pytest.mark.parametrize("arg", [1, 2, 3])
def test_values(arg):
    assert arg > 0
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.test_functions.len(), 1);
    assert!(module.test_functions[0].is_parametrized);
    assert_eq!(module.test_functions[0].parametrize_count, Some(3));
}

#[test]
fn test_parser_fixture_scope_session() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_fscope.py",
        r#"
import pytest

@pytest.fixture(scope="session")
def session_fix():
    return 42
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.fixtures.len(), 1);
    assert_eq!(module.fixtures[0].scope, FixtureScope::Session);
}

#[test]
fn test_parser_fixture_scope_class() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_class_scope.py",
        r#"
import pytest

@pytest.fixture(scope="class")
def class_fix():
    return 42
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.fixtures[0].scope, FixtureScope::Class);
}

#[test]
fn test_parser_fixture_scope_package() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_pkg_scope.py",
        r#"
import pytest

@pytest.fixture(scope="package")
def pkg_fix():
    return 42
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.fixtures[0].scope, FixtureScope::Package);
}

#[test]
fn test_parser_fixture_has_yield() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_yield.py",
        r#"
import pytest

@pytest.fixture
def yield_fixture():
    yield 42
    cleanup()
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.fixtures.len(), 1);
    assert!(module.fixtures[0].has_yield);
}

#[test]
fn test_parser_fixture_db_commit() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_db_commit.py",
        r#"
import pytest

@pytest.fixture
def db_fix():
    conn = get_conn()
    conn.commit()
    return conn
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.fixtures.len(), 1);
    assert!(module.fixtures[0].has_db_commit);
    assert!(!module.fixtures[0].has_db_rollback);
}

#[test]
fn test_parser_fixture_db_rollback() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_db_rollback.py",
        r#"
import pytest

@pytest.fixture
def db_fix():
    conn = get_conn()
    conn.rollback()
    return conn
"#,
    );
    let module = parse_file(&path);
    assert!(module.fixtures[0].has_db_rollback);
    assert!(!module.fixtures[0].has_db_commit);
}

#[test]
fn test_parser_fixture_autouse() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_autouse_parse.py",
        r#"
import pytest

@pytest.fixture(autouse=True)
def auto_fix():
    return 42
"#,
    );
    let module = parse_file(&path);
    assert_eq!(module.fixtures.len(), 1);
    assert!(module.fixtures[0].is_autouse);
}

#[test]
fn test_parser_fixture_returns_mutable_list() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_mutable_list.py",
        r#"
import pytest

@pytest.fixture
def mutable_fix():
    return []
"#,
    );
    let module = parse_file(&path);
    assert!(module.fixtures[0].returns_mutable);
}

#[test]
fn test_parser_fixture_returns_mutable_dict() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_mutable_dict.py",
        r#"
import pytest

@pytest.fixture
def mutable_fix():
    return {}
"#,
    );
    let module = parse_file(&path);
    assert!(module.fixtures[0].returns_mutable);
}

#[test]
fn test_parser_fixture_not_mutable() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_not_mutable.py",
        r#"
import pytest

@pytest.fixture
def immutable_fix():
    return 42
"#,
    );
    let module = parse_file(&path);
    assert!(!module.fixtures[0].returns_mutable);
}

#[test]
fn test_stateful_session_dict_triggers_fix006() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_stateful_dict.py",
        r#"
import pytest

@pytest.fixture(scope="session")
def shared_dict():
    return {}

def test_uses_dict(shared_dict):
    assert len(shared_dict) == 0
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-FIX-006");
    assert!(v.is_some(), "Expected PYTEST-FIX-006 for session fixture returning dict");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "StatefulSessionFixtureRule");
}

#[test]
fn test_function_scope_mutable_does_not_trigger_fix006() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_func_mutable.py",
        r#"
import pytest

@pytest.fixture
def local_list():
    return []

def test_uses(local_list):
    assert len(local_list) == 0
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-FIX-006");
    assert!(v.is_none(), "Should not trigger FIX-006 for function-scoped mutable fixture");
}

#[test]
fn test_unused_fixture_with_autouse_does_not_trigger_fix005() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_auto_unused.py",
        r#"
import pytest

@pytest.fixture(autouse=True)
def auto_setup():
    return 42

def test_something():
    assert True
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-FIX-005");
    assert!(v.is_none(), "Autouse fixtures should not trigger unused rule");
}

#[test]
fn test_collect_all_fixtures_cross_module() {
    let dir = tempfile::tempdir().unwrap();
    let _path1 = write_temp_file(
        dir.path(),
        "test_fix_a.py",
        r#"
import pytest

@pytest.fixture
def fixture_a():
    return 1

def test_a(fixture_a):
    assert fixture_a == 1
"#,
    );
    let path2 = write_temp_file(
        dir.path(),
        "test_fix_b.py",
        r#"
import pytest

@pytest.fixture
def fixture_b(fixture_a):
    return fixture_a + 1

def test_b(fixture_b):
    assert fixture_b == 2
"#,
    );
    let module = parse_file(&path2);
    assert_eq!(module.fixtures.len(), 1);
    assert_eq!(module.fixtures[0].name, "fixture_b");
    assert!(module.fixtures[0].dependencies.contains(&"fixture_a".to_string()));
}

#[test]
fn test_violation_has_suggestion_and_test_name() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_details.py",
        r#"
def test_waits():
    import time
    time.sleep(2)
    assert True
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-FLK-001").unwrap();
    assert!(v.suggestion.is_some());
    assert_eq!(v.test_name.as_ref().unwrap(), "test_waits");
}

#[test]
fn test_violation_severity_and_category_consistency() {
    let dir = tempfile::tempdir().unwrap();
    let path = write_temp_file(
        dir.path(),
        "test_consistency.py",
        r#"
def test_no_assert():
    pass
"#,
    );
    let violations = lint_single_file(&path);
    let v = find_violation(&violations, "PYTEST-MNT-004").unwrap();
    assert_eq!(v.rule_id, "PYTEST-MNT-004");
    assert_eq!(v.rule_name, "NoAssertionRule");
    assert_eq!(v.severity, Severity::Error);
    assert_eq!(v.category, Category::Maintenance);
}
