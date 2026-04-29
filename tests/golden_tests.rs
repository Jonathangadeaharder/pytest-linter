use pytest_linter::config::Config;
use pytest_linter::engine::LintEngine;
use std::collections::HashSet;
use std::path::PathBuf;

fn golden_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/golden")
}

fn parse_expected_violations(content: &str) -> HashSet<String> {
    let mut expected = HashSet::new();
    for line in content.lines() {
        let trimmed = line.trim();
        if let Some(idx) = trimmed.find("# expect: ") {
            let rule_id = trimmed[idx + "# expect: ".len()..].trim();
            if rule_id.starts_with("PYTEST-") {
                expected.insert(rule_id.to_string());
            }
        }
    }
    expected
}

fn lint_golden_file(source_name: &str) -> HashSet<String> {
    let src_path = golden_dir().join(source_name);
    let content = std::fs::read_to_string(&src_path)
        .unwrap_or_else(|e| panic!("Failed to read golden file {:?}: {}", src_path, e));

    let dir = tempfile::tempdir().unwrap();
    let test_name = source_name.replace("_patterns", "");
    let dest = dir.path().join(format!("test_{test_name}"));
    std::fs::write(&dest, &content).unwrap();

    let engine = LintEngine::new(Config::default()).unwrap();
    let violations = engine.lint_paths(&[dest]).unwrap();
    violations
        .iter()
        .map(|v| v.rule_id.clone())
        .collect::<HashSet<_>>()
}

fn run_golden_test(file_name: &str) {
    let src_path = golden_dir().join(file_name);
    let content = std::fs::read_to_string(&src_path)
        .unwrap_or_else(|e| panic!("Failed to read golden file {:?}: {}", src_path, e));
    let expected = parse_expected_violations(&content);
    let actual = lint_golden_file(file_name);

    let missing: Vec<_> = expected.difference(&actual).collect();
    let extra: Vec<_> = actual.difference(&expected).collect();

    assert!(
        missing.is_empty() && extra.is_empty(),
        "Golden test mismatch for {}:\n  Missing violations (expected but not found): {:?}\n  Extra violations (found but not expected): {:?}\n  Expected: {:?}\n  Actual: {:?}",
        file_name,
        missing,
        extra,
        expected,
        actual,
    );
}

#[test]
fn test_golden_pytest_patterns() {
    run_golden_test("pytest_patterns.py");
}

#[test]
fn test_golden_hypothesis_patterns() {
    run_golden_test("hypothesis_patterns.py");
}

#[test]
fn test_golden_pandas_patterns() {
    run_golden_test("pandas_patterns.py");
}

#[test]
fn test_golden_django_patterns() {
    run_golden_test("django_patterns.py");
}
