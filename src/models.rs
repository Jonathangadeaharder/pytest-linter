use serde::{Deserialize, Serialize};
use std::cmp::Ordering;
use std::path::PathBuf;

/// Severity level for a lint violation.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Severity {
    Error,
    Warning,
    Info,
}

impl std::fmt::Display for Severity {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Error => write!(f, "error"),
            Self::Warning => write!(f, "warning"),
            Self::Info => write!(f, "info"),
        }
    }
}

/// Category of a lint rule (flakiness, maintenance, fixture, enhancement).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Category {
    Flakiness,
    Maintenance,
    Fixture,
    Enhancement,
}

impl std::fmt::Display for Category {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Flakiness => write!(f, "flakiness"),
            Self::Maintenance => write!(f, "maintenance"),
            Self::Fixture => write!(f, "fixture"),
            Self::Enhancement => write!(f, "enhancement"),
        }
    }
}

/// A single lint violation found by a rule.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Violation {
    pub rule_id: String,
    pub rule_name: String,
    pub severity: Severity,
    pub category: Category,
    pub message: String,
    pub file_path: PathBuf,
    pub line: usize,
    pub col: Option<usize>,
    pub suggestion: Option<String>,
    pub test_name: Option<String>,
}

/// Metadata about an assert statement found in a test.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AssertionInfo {
    pub is_magic: bool,
    pub is_suboptimal: bool,
    pub has_comparison: bool,
    pub expression_text: String,
    pub line: usize,
}

/// Parsed representation of a single test function with all detected characteristics.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct TestFunction {
    pub name: String,
    pub file_path: PathBuf,
    pub line: usize,
    pub is_async: bool,
    pub is_parametrized: bool,
    pub parametrize_count: Option<usize>,
    pub has_assertions: bool,
    pub assertion_count: usize,
    pub has_mock_verifications: bool,
    pub has_state_assertions: bool,
    pub fixture_deps: Vec<String>,
    pub uses_time_sleep: bool,
    pub sleep_value: Option<f64>,
    pub uses_file_io: bool,
    pub uses_network: bool,
    pub has_conditional_logic: bool,
    pub has_try_except: bool,
    pub docstring: Option<String>,
    pub assertions: Vec<AssertionInfo>,
    pub parametrize_values: Vec<Vec<String>>,
    pub uses_cwd_dependency: bool,
    pub uses_pytest_raises: bool,
    pub mutates_fixture_deps: Vec<String>,
    pub body_hash: Option<u64>,
    pub uses_random: bool,
    pub has_random_seed: bool,
    pub uses_subprocess: bool,
    pub has_subprocess_timeout: bool,
    pub mocks_stdlib_module: bool,
    pub mocked_stdlib_targets: Vec<String>,
    pub has_weak_assertions: bool,
    pub weak_assertion_details: Vec<String>,
    pub patch_targets: Vec<String>,
    pub has_magic_mock: bool,
    pub mock_count: usize,
    pub uses_shutil_copy: bool,
}

/// Scope of a pytest fixture, from narrowest (function) to widest (session).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum FixtureScope {
    Function = 1,
    Class = 2,
    Module = 3,
    Package = 4,
    Session = 5,
}

impl std::fmt::Display for FixtureScope {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Function => write!(f, "function"),
            Self::Class => write!(f, "class"),
            Self::Module => write!(f, "module"),
            Self::Package => write!(f, "package"),
            Self::Session => write!(f, "session"),
        }
    }
}

/// Parsed representation of a pytest fixture with scope and dependency info.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(clippy::struct_excessive_bools)]
pub struct Fixture {
    pub name: String,
    pub file_path: PathBuf,
    pub line: usize,
    pub scope: FixtureScope,
    pub is_autouse: bool,
    pub dependencies: Vec<String>,
    pub returns_mutable: bool,
    pub has_yield: bool,
    pub has_db_commit: bool,
    pub has_db_rollback: bool,
    pub has_cleanup: bool,
    pub uses_file_io: bool,
    pub used_by: Vec<String>,
}

/// Result of parsing a single Python test file: imports, tests, and fixtures.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParsedModule {
    pub file_path: PathBuf,
    pub source: String,
    pub imports: Vec<String>,
    pub test_functions: Vec<TestFunction>,
    pub fixtures: Vec<Fixture>,
}

impl PartialEq for Violation {
    fn eq(&self, other: &Self) -> bool {
        self.file_path == other.file_path
            && self.line == other.line
            && self.rule_id == other.rule_id
    }
}

impl Eq for Violation {}

impl PartialOrd for Violation {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for Violation {
    fn cmp(&self, other: &Self) -> Ordering {
        self.file_path
            .cmp(&other.file_path)
            .then(self.line.cmp(&other.line))
            .then(self.rule_id.cmp(&other.rule_id))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_severity_equality() {
        assert_eq!(Severity::Error, Severity::Error);
        assert_ne!(Severity::Error, Severity::Warning);
        assert_ne!(Severity::Warning, Severity::Info);
    }

    #[test]
    fn test_severity_display() {
        assert_eq!(format!("{}", Severity::Error), "error");
        assert_eq!(format!("{}", Severity::Warning), "warning");
        assert_eq!(format!("{}", Severity::Info), "info");
    }

    #[test]
    fn test_category_display() {
        assert_eq!(format!("{}", Category::Flakiness), "flakiness");
        assert_eq!(format!("{}", Category::Maintenance), "maintenance");
        assert_eq!(format!("{}", Category::Fixture), "fixture");
        assert_eq!(format!("{}", Category::Enhancement), "enhancement");
    }

    #[test]
    fn test_fixture_scope_ordering() {
        assert!(FixtureScope::Function < FixtureScope::Class);
        assert!(FixtureScope::Class < FixtureScope::Module);
        assert!(FixtureScope::Module < FixtureScope::Package);
        assert!(FixtureScope::Package < FixtureScope::Session);
    }

    #[test]
    fn test_fixture_scope_display() {
        assert_eq!(format!("{}", FixtureScope::Function), "function");
        assert_eq!(format!("{}", FixtureScope::Class), "class");
        assert_eq!(format!("{}", FixtureScope::Module), "module");
        assert_eq!(format!("{}", FixtureScope::Package), "package");
        assert_eq!(format!("{}", FixtureScope::Session), "session");
    }

    #[test]
    fn test_fixture_scope_values() {
        assert_eq!(FixtureScope::Function as i32, 1);
        assert_eq!(FixtureScope::Class as i32, 2);
        assert_eq!(FixtureScope::Module as i32, 3);
        assert_eq!(FixtureScope::Package as i32, 4);
        assert_eq!(FixtureScope::Session as i32, 5);
    }

    #[test]
    fn test_violation_ordering() {
        let v1 = Violation {
            rule_id: "PYTEST-001".to_string(),
            rule_name: "Rule1".to_string(),
            severity: Severity::Error,
            category: Category::Flakiness,
            message: "msg".to_string(),
            file_path: PathBuf::from("a.py"),
            line: 1,
            col: None,
            suggestion: None,
            test_name: None,
        };
        let v2 = Violation {
            rule_id: "PYTEST-002".to_string(),
            rule_name: "Rule2".to_string(),
            severity: Severity::Warning,
            category: Category::Maintenance,
            message: "msg".to_string(),
            file_path: PathBuf::from("a.py"),
            line: 2,
            col: None,
            suggestion: None,
            test_name: None,
        };
        assert!(v1 < v2);
    }

    #[test]
    fn test_violation_ordering_different_files() {
        let v1 = Violation {
            rule_id: "A".to_string(),
            rule_name: "R".to_string(),
            severity: Severity::Error,
            category: Category::Flakiness,
            message: "m".to_string(),
            file_path: PathBuf::from("a.py"),
            line: 5,
            col: None,
            suggestion: None,
            test_name: None,
        };
        let v2 = Violation {
            rule_id: "A".to_string(),
            rule_name: "R".to_string(),
            severity: Severity::Error,
            category: Category::Flakiness,
            message: "m".to_string(),
            file_path: PathBuf::from("b.py"),
            line: 1,
            col: None,
            suggestion: None,
            test_name: None,
        };
        assert!(v1 < v2);
    }

    #[test]
    fn test_severity_copy() {
        let s = Severity::Error;
        let s2 = s;
        assert_eq!(s, s2);
    }

    #[test]
    fn test_category_copy() {
        let c = Category::Fixture;
        let c2 = c;
        assert_eq!(c, c2);
    }

    #[test]
    fn test_violation_clone() {
        let v = Violation {
            rule_id: "R".to_string(),
            rule_name: "N".to_string(),
            severity: Severity::Warning,
            category: Category::Maintenance,
            message: "msg".to_string(),
            file_path: PathBuf::from("test.py"),
            line: 10,
            col: Some(5),
            suggestion: Some("fix it".to_string()),
            test_name: Some("test_foo".to_string()),
        };
        let v2 = v.clone();
        assert_eq!(v, v2);
    }
}
