use std::fs;
use tempfile::TempDir;
use vitest_linter::engine::LintEngine;
use vitest_linter::parser::TsParser;
use vitest_linter::run_cli;

fn write_fixture(dir: &TempDir, name: &str, content: &str) -> std::path::PathBuf {
    let path = dir.path().join(name);
    fs::write(&path, content).unwrap();
    path
}

fn parse(path: &std::path::Path) -> vitest_linter::models::ParsedModule {
    let parser = TsParser::new().unwrap();
    parser.parse_file(path).unwrap()
}

fn find_violation<'a>(
    violations: &'a [vitest_linter::models::Violation],
    rule_id: &str,
) -> Option<&'a vitest_linter::models::Violation> {
    violations.iter().find(|v| v.rule_id == rule_id)
}

#[test]
fn flk001_settimeout_triggers_rule() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "timeout.test.ts",
        r#"
import { describe, test, expect } from 'vitest';

test('uses setTimeout', () => {
    setTimeout(() => {
        expect(true).toBe(true);
    }, 1000);
});
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    let v = find_violation(&violations, "VITEST-FLK-001");
    assert!(v.is_some(), "Expected VITEST-FLK-001 violation");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "TimeoutRule");
    assert_eq!(v.severity, vitest_linter::models::Severity::Warning);
    assert_eq!(v.category, vitest_linter::models::Category::Flakiness);
}

#[test]
fn flk002_date_without_fake_timers() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "date.test.ts",
        r#"
import { describe, test, expect } from 'vitest';

test('uses Date.now', () => {
    const now = Date.now();
    expect(now).toBeGreaterThan(0);
});
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    let v = find_violation(&violations, "VITEST-FLK-002");
    assert!(v.is_some(), "Expected VITEST-FLK-002 violation");
    assert_eq!(v.unwrap().rule_name, "DateMockRule");
}

#[test]
fn flk002_date_with_fake_timers_no_violation() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "date_safe.test.ts",
        r#"
import { describe, test, expect, vi } from 'vitest';

test('uses Date.now with fake timers', () => {
    vi.useFakeTimers();
    const now = Date.now();
    expect(now).toBeGreaterThan(0);
});
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    assert!(
        find_violation(&violations, "VITEST-FLK-002").is_none(),
        "Should not trigger VITEST-FLK-002 when useFakeTimers is present"
    );
}

#[test]
fn flk003_network_import_axios() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "network.test.ts",
        r#"
import axios from 'axios';
import { test, expect } from 'vitest';

test('fetches data', () => {
    expect(1).toBe(1);
});
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    let v = find_violation(&violations, "VITEST-FLK-003");
    assert!(v.is_some(), "Expected VITEST-FLK-003 violation");
    assert_eq!(v.unwrap().rule_name, "NetworkImportRule");
}

#[test]
fn mnt001_no_assertions() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "no_assert.test.ts",
        r#"
import { test } from 'vitest';

test('does nothing', () => {
    const x = 1 + 1;
});
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    let v = find_violation(&violations, "VITEST-MNT-001");
    assert!(v.is_some(), "Expected VITEST-MNT-001 violation");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "NoAssertionRule");
    assert_eq!(v.severity, vitest_linter::models::Severity::Error);
}

#[test]
fn mnt002_too_many_assertions() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "many_asserts.test.ts",
        r#"
import { test, expect } from 'vitest';

test('too many assertions', () => {
    expect(1).toBe(1);
    expect(2).toBe(2);
    expect(3).toBe(3);
    expect(4).toBe(4);
    expect(5).toBe(5);
    expect(6).toBe(6);
});
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    let v = find_violation(&violations, "VITEST-MNT-002");
    assert!(v.is_some(), "Expected VITEST-MNT-002 violation");
    assert_eq!(v.unwrap().rule_name, "MultipleExpectRule");
}

#[test]
fn mnt002_exactly_five_assertions_no_violation() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "five_asserts.test.ts",
        r#"
import { test, expect } from 'vitest';

test('exactly five assertions', () => {
    expect(1).toBe(1);
    expect(2).toBe(2);
    expect(3).toBe(3);
    expect(4).toBe(4);
    expect(5).toBe(5);
});
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    assert!(
        find_violation(&violations, "VITEST-MNT-002").is_none(),
        "Exactly 5 assertions should NOT trigger MNT-002 (threshold is > 5)"
    );
}

#[test]
fn mnt003_conditional_logic() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "conditional.test.ts",
        r#"
import { test, expect } from 'vitest';

test('has conditional', () => {
    const x = Math.random();
    if (x > 0.5) {
        expect(true).toBe(true);
    } else {
        expect(false).toBe(false);
    }
});
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    let v = find_violation(&violations, "VITEST-MNT-003");
    assert!(v.is_some(), "Expected VITEST-MNT-003 violation");
    assert_eq!(v.unwrap().rule_name, "ConditionalLogicRule");
}

#[test]
fn mnt004_try_catch() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "trycatch.test.ts",
        r#"
import { test, expect } from 'vitest';

test('has try catch', () => {
    try {
        JSON.parse('invalid');
    } catch (e) {
        expect(e).toBeDefined();
    }
});
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    let v = find_violation(&violations, "VITEST-MNT-004");
    assert!(v.is_some(), "Expected VITEST-MNT-004 violation");
    assert_eq!(v.unwrap().rule_name, "TryCatchRule");
}

#[test]
fn mnt005_skipped_test() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "skipped.test.ts",
        r#"
import { test, expect } from 'vitest';

test.skip('is skipped', () => {
    expect(true).toBe(true);
});
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    let v = find_violation(&violations, "VITEST-MNT-005");
    assert!(v.is_some(), "Expected VITEST-MNT-005 violation");
    let v = v.unwrap();
    assert_eq!(v.rule_name, "EmptyTestRule");
    assert_eq!(v.severity, vitest_linter::models::Severity::Info);
}

#[test]
fn str001_nested_describe() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "nested.test.ts",
        r#"
import { describe, test, expect } from 'vitest';

describe('outer', () => {
    describe('inner', () => {
        test('deeply nested', () => {
            expect(true).toBe(true);
        });
    });
});
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    let v = find_violation(&violations, "VITEST-STR-001");
    assert!(v.is_some(), "Expected VITEST-STR-001 violation");
    assert_eq!(v.unwrap().rule_name, "NestedDescribeRule");
}

#[test]
fn str002_return_in_test() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "return.test.ts",
        r#"
import { test, expect } from 'vitest';

test('has return', () => {
    const result = 1 + 1;
    expect(result).toBe(2);
    return result;
});
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    let v = find_violation(&violations, "VITEST-STR-002");
    assert!(v.is_some(), "Expected VITEST-STR-002 violation");
    assert_eq!(v.unwrap().rule_name, "ReturnInTestRule");
}

#[test]
fn parser_detects_imports() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "imports.test.ts",
        r#"
import { test, expect } from 'vitest';
import axios from 'axios';

test('simple', () => {
    expect(1).toBe(1);
});
"#,
    );
    let module = parse(&path);
    assert!(module.imports.len() >= 2);
    assert!(module.imports.iter().any(|i| i.contains("axios")));
}

#[test]
fn parser_detects_test_blocks() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "blocks.test.ts",
        r#"
import { describe, test, expect } from 'vitest';

test('first', () => {
    expect(1).toBe(1);
});

test('second', () => {
    expect(2).toBe(2);
});
"#,
    );
    let module = parse(&path);
    assert_eq!(module.test_blocks.len(), 2);
}

#[test]
fn clean_file_has_no_violations() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "clean.test.ts",
        r#"
import { test, expect } from 'vitest';

test('clean test', () => {
    expect(1).toBe(1);
});
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    assert!(violations.is_empty(), "Clean file should have no violations: {:?}", violations);
}

#[test]
fn lint_dir_discovers_files() {
    let dir = TempDir::new().unwrap();
    write_fixture(
        &dir,
        "a.test.ts",
        r#"
import { test, expect } from 'vitest';
test('a', () => { expect(1).toBe(1); });
"#,
    );
    write_fixture(
        &dir,
        "b.test.ts",
        r#"
import { test, expect } from 'vitest';
test('b', () => { expect(1).toBe(1); });
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[dir.path().to_path_buf()]).unwrap();
    assert!(violations.is_empty(), "Clean files should have no violations");
}

#[test]
fn engine_ignores_non_test_files() {
    let dir = TempDir::new().unwrap();
    write_fixture(
        &dir,
        "utils.ts",
        r#"
export function add(a: number, b: number) { return a + b; }
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[dir.path().to_path_buf()]).unwrap();
    assert!(violations.is_empty());
}

#[test]
fn engine_ignores_non_test_files_with_test_content() {
    let dir = TempDir::new().unwrap();
    write_fixture(
        &dir,
        "helper.ts",
        r#"
import { test } from 'vitest';
test('no assert', () => { const x = 1; });
"#,
    );
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[dir.path().to_path_buf()]).unwrap();
    assert!(
        violations.is_empty(),
        "Non-test files should be ignored even if they contain test-like code"
    );
}

#[test]
fn new_date_triggers_datemock() {
    let dir = TempDir::new().unwrap();
    let path = write_fixture(
        &dir,
        "newdate.test.ts",
        r#"
import { test, expect } from 'vitest';

test('uses new Date', () => {
    const d = new Date();
    expect(d).toBeDefined();
});
"#,
    );
    let module = parse(&path);
    assert!(module.test_blocks[0].uses_datemock, "new Date() should set uses_datemock");
    let engine = LintEngine::new().unwrap();
    let violations = engine.lint_paths(&[path]).unwrap();
    assert!(find_violation(&violations, "VITEST-FLK-002").is_some());
}

#[test]
fn cli_json_format_with_error() {
    let dir = TempDir::new().unwrap();
    let test_path = write_fixture(
        &dir,
        "no_assert.test.ts",
        r#"
import { test } from 'vitest';
test('no assert', () => { const x = 1; });
"#,
    );
    let output_path = dir.path().join("output.json");
    let has_errors = run_cli(
        &[test_path],
        "json",
        Some(&output_path),
        true,
    )
    .unwrap();

    assert!(has_errors, "Should have errors (MNT-001 is Error severity)");

    let json = fs::read_to_string(&output_path).unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();
    assert!(parsed.is_array(), "JSON output should be an array");
    let arr = parsed.as_array().unwrap();
    assert!(arr.iter().any(|v| v["rule_id"].as_str() == Some("VITEST-MNT-001")));
    assert!(arr.iter().any(|v| v["rule_name"].as_str() == Some("NoAssertionRule")));
}

#[test]
fn cli_json_format_clean_file() {
    let dir = TempDir::new().unwrap();
    let test_path = write_fixture(
        &dir,
        "clean.test.ts",
        r#"
import { test, expect } from 'vitest';
test('clean', () => { expect(1).toBe(1); });
"#,
    );
    let output_path = dir.path().join("output.json");
    let has_errors = run_cli(
        &[test_path],
        "json",
        Some(&output_path),
        true,
    )
    .unwrap();

    assert!(!has_errors, "Clean file should have no errors");

    let json = fs::read_to_string(&output_path).unwrap();
    let parsed: serde_json::Value = serde_json::from_str(&json).unwrap();
    assert!(parsed.as_array().unwrap().is_empty());
}

#[test]
fn cli_terminal_severity_counts() {
    let dir = TempDir::new().unwrap();
    let test_path = write_fixture(
        &dir,
        "mixed.test.ts",
        r#"
import { test, expect } from 'vitest';

test.skip('skipped', () => {});
test('cond', () => { if (true) { expect(1).toBe(1); } });
"#,
    );
    let output_path = dir.path().join("output.txt");
    let has_errors = run_cli(
        &[test_path],
        "terminal",
        Some(&output_path),
        true,
    )
    .unwrap();

    assert!(has_errors, "Should have errors from MNT-001");

    let output = fs::read_to_string(&output_path).unwrap();
    assert!(
        output.contains("1 error(s)"),
        "Expected 1 error in output, got: {}",
        output
    );
    assert!(
        output.contains("1 warning(s)"),
        "Expected 1 warning in output, got: {}",
        output
    );
    assert!(
        output.contains("1 info"),
        "Expected 1 info in output, got: {}",
        output
    );
}

#[test]
fn cli_terminal_clean_file() {
    let dir = TempDir::new().unwrap();
    let test_path = write_fixture(
        &dir,
        "clean.test.ts",
        r#"
import { test, expect } from 'vitest';
test('clean', () => { expect(1).toBe(1); });
"#,
    );
    let output_path = dir.path().join("output.txt");
    let has_errors = run_cli(
        &[test_path],
        "terminal",
        Some(&output_path),
        true,
    )
    .unwrap();

    assert!(!has_errors);
    let output = fs::read_to_string(&output_path).unwrap();
    assert!(output.contains("No test smells detected"));
}

#[test]
fn cli_binary_exits_with_error_for_violations() {
    let dir = TempDir::new().unwrap();
    let test_path = write_fixture(
        &dir,
        "no_assert.test.ts",
        r#"
import { test } from 'vitest';
test('no assert', () => { const x = 1; });
"#,
    );

    let bin = std::env::var("CARGO_BIN_EXE_vitest-linter").unwrap();
    let output = std::process::Command::new(&bin)
        .arg(&test_path)
        .arg("--no-color")
        .output()
        .unwrap();

    assert!(
        !output.status.success(),
        "Binary should exit with error code when violations found"
    );
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(
        stdout.contains("VITEST-MNT-001"),
        "Output should contain MNT-001 violation"
    );
}

#[test]
fn cli_binary_clean_exit() {
    let dir = TempDir::new().unwrap();
    let test_path = write_fixture(
        &dir,
        "clean.test.ts",
        r#"
import { test, expect } from 'vitest';
test('clean', () => { expect(1).toBe(1); });
"#,
    );

    let bin = std::env::var("CARGO_BIN_EXE_vitest-linter").unwrap();
    let output = std::process::Command::new(&bin)
        .arg(&test_path)
        .arg("--no-color")
        .output()
        .unwrap();

    assert!(
        output.status.success(),
        "Binary should exit successfully for clean files"
    );
}
