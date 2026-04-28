//! Core linting engine: file discovery, parallel parsing, rule execution, and output formatting.

use crate::config::Config;
use crate::models::{Category, Fixture, FixtureScope, ParsedModule, Severity, Violation};
use crate::rules::{Rule, RuleContext};
use anyhow::Result;
use colored::Colorize;
use rayon::prelude::*;
use std::collections::{HashMap, HashSet};
use std::hash::BuildHasher;
use std::io::Write;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

/// Core linting engine that orchestrates rule execution across parsed modules.
pub struct LintEngine {
    rules: Vec<Box<dyn Rule>>,
    config: Config,
}

impl LintEngine {
    /// Create a new engine with rules filtered by the given configuration.
    #[allow(clippy::missing_errors_doc)]
    pub fn new(config: Config) -> Result<Self> {
        let all = crate::rules::all_rules();
        let rules: Vec<Box<dyn Rule>> = all
            .into_iter()
            .filter(|r| config.is_rule_enabled(r.id()))
            .collect();
        Ok(Self { rules, config })
    }

    /// Lint all test files discovered under the given paths and return violations.
    #[allow(clippy::missing_errors_doc)]
    pub fn lint_paths(&self, paths: &[PathBuf]) -> Result<Vec<Violation>> {
        let files = discover_files(paths);
        let modules = parse_files_parallel(&files);

        let fixture_map = collect_all_fixtures(&modules);
        let used_fixture_names = compute_used_fixture_names(&modules);
        let fixture_locations = compute_fixture_locations(&modules);
        let session_mutable_fixtures = compute_session_mutable_fixtures(&modules);

        let ctx = RuleContext {
            fixture_map: &fixture_map,
            used_fixture_names: &used_fixture_names,
            fixture_locations: &fixture_locations,
            session_mutable_fixtures: &session_mutable_fixtures,
        };

        let violations: Vec<Violation> = modules
            .par_iter()
            .flat_map(|module| {
                let mut module_violations = Vec::new();
                for rule in &self.rules {
                    let mut v = rule.check(module, &modules, &ctx);
                    for violation in &mut v {
                        violation.severity = self.config.rule_severity(rule.id(), rule.severity());
                    }
                    module_violations.append(&mut v);
                }
                module_violations
            })
            .collect();

        let suppressions = collect_suppressions(&modules);
        let mut violations: Vec<Violation> = violations
            .into_iter()
            .filter(|v| !is_suppressed(v, &suppressions))
            .collect();
        violations.sort();
        Ok(violations)
    }
}

/// Discover test files from the given paths (files or directories).
fn discover_files(paths: &[PathBuf]) -> Vec<PathBuf> {
    let mut files = Vec::new();

    for path in paths {
        if path.is_file() && path.extension().is_some_and(|e| e == "py") {
            if is_test_file(path) {
                files.push(path.clone());
            }
        } else if path.is_dir() {
            for entry in WalkDir::new(path)
                .into_iter()
                .filter_map(std::result::Result::ok)
            {
                let p = entry.path();
                if p.is_file() && p.extension().is_some_and(|e| e == "py") && is_test_file(p) {
                    files.push(p.to_path_buf());
                }
            }
        }
    }

    files.sort();
    files.dedup();
    files
}

/// Check if a file is a Python test file by naming convention.
fn is_test_file(path: &Path) -> bool {
    let name = path
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_default();
    name.starts_with("test_") || name.ends_with("_test.py") || name == "conftest.py"
}

/// Parse multiple files in parallel using rayon.
fn parse_files_parallel(files: &[PathBuf]) -> Vec<ParsedModule> {
    files
        .par_iter()
        .filter_map(|file| {
            let mut parser = crate::parser::PythonParser::new().ok()?;
            match parser.parse_file(file) {
                Ok(m) => Some(m),
                Err(e) => {
                    eprintln!("Warning: failed to parse {}: {}", file.display(), e);
                    None
                }
            }
        })
        .collect()
}

type SuppressionMap = HashMap<(PathBuf, usize), HashSet<String>>;

fn collect_suppressions(modules: &[ParsedModule]) -> SuppressionMap {
    let mut map: SuppressionMap = HashMap::new();
    for module in modules {
        for (line_idx, line) in module.source.lines().enumerate() {
            let line_num = line_idx + 1;
            if let Some(rules) = parse_noqa_comment(line) {
                map.entry((module.file_path.clone(), line_num))
                    .or_default()
                    .extend(rules);
                // Also suppress on the next line (inline noqa applies to the statement)
                map.entry((module.file_path.clone(), line_num + 1))
                    .or_default()
                    .extend(parse_noqa_comment(line).unwrap_or_default());
            }
        }
    }
    map
}

/// Parse `# noqa` comments from a line and return the suppressed rule IDs.
fn parse_noqa_comment(line: &str) -> Option<Vec<String>> {
    let trimmed = line.trim();
    let noqa_pos = trimmed.find("# noqa")?;
    let after_noqa = &trimmed[noqa_pos + 6..].trim();

    if after_noqa.is_empty() || after_noqa.starts_with(':') {
        let rules_str = if after_noqa.starts_with(':') {
            after_noqa[1..].trim()
        } else {
            // bare `# noqa` suppresses all rules
            return Some(vec!["*".to_string()]);
        };

        if rules_str.is_empty() {
            return Some(vec!["*".to_string()]);
        }

        let rules: Vec<String> = rules_str
            .split(',')
            .map(|r| r.trim().to_string())
            .filter(|r| !r.is_empty())
            .collect();

        if rules.is_empty() {
            return Some(vec!["*".to_string()]);
        }

        return Some(rules);
    }

    None
}

/// Check if a violation is suppressed by a noqa comment.
fn is_suppressed(violation: &Violation, suppressions: &SuppressionMap) -> bool {
    // Check the violation's line
    if let Some(rules) = suppressions.get(&(violation.file_path.clone(), violation.line)) {
        if rules.contains("*") || rules.contains(&violation.rule_id) {
            return true;
        }
    }
    // Also check the line above (noqa on previous line)
    if violation.line > 1 {
        if let Some(rules) = suppressions.get(&(violation.file_path.clone(), violation.line - 1)) {
            if rules.contains("*") || rules.contains(&violation.rule_id) {
                return true;
            }
        }
    }
    false
}

/// Build a map of fixture name to all fixture definitions across modules.
#[must_use]
pub fn collect_all_fixtures(modules: &[ParsedModule]) -> HashMap<String, Vec<&Fixture>> {
    let mut map: HashMap<String, Vec<&Fixture>> = HashMap::new();
    for module in modules {
        for fixture in &module.fixtures {
            map.entry(fixture.name.clone()).or_default().push(fixture);
        }
    }
    map
}

/// Build a map of fixture name to the file paths where it is defined.
#[must_use]
pub fn compute_fixture_locations(modules: &[ParsedModule]) -> HashMap<String, Vec<PathBuf>> {
    let mut map: HashMap<String, Vec<PathBuf>> = HashMap::new();
    for module in modules {
        for fixture in &module.fixtures {
            map.entry(fixture.name.clone())
                .or_default()
                .push(module.file_path.clone());
        }
    }
    map
}

/// Collect names of session-scoped fixtures that return mutable state.
#[must_use]
pub fn compute_session_mutable_fixtures(modules: &[ParsedModule]) -> HashSet<String> {
    modules
        .iter()
        .flat_map(|m| m.fixtures.iter())
        .filter(|f| f.scope == crate::models::FixtureScope::Session && f.returns_mutable)
        .map(|f| f.name.clone())
        .collect()
}

/// Look up the narrowest scope for a fixture by name across all modules.
#[must_use]
pub fn fixture_scope_by_name<S: BuildHasher>(
    all_fixtures: &HashMap<String, Vec<&Fixture>, S>,
    name: &str,
) -> Option<FixtureScope> {
    all_fixtures
        .get(name)
        .and_then(|v| v.iter().min_by_key(|f| f.scope).map(|f| f.scope))
}

/// Check whether a fixture is referenced by any test or other fixture.
#[must_use]
pub fn is_fixture_used_by_any_test_or_fixture(
    fixture_name: &str,
    modules: &[ParsedModule],
) -> bool {
    for module in modules {
        for test in &module.test_functions {
            if test.fixture_deps.iter().any(|d| d == fixture_name) {
                return true;
            }
        }
        for other_fixture in &module.fixtures {
            if other_fixture.name != fixture_name
                && other_fixture.dependencies.iter().any(|d| d == fixture_name)
            {
                return true;
            }
        }
    }
    false
}

/// Compute the transitive closure of fixture names used by tests.
#[must_use]
pub fn compute_used_fixture_names(modules: &[ParsedModule]) -> HashSet<String> {
    let mut fixture_deps_map: HashMap<&str, Vec<&String>> = HashMap::new();
    for module in modules {
        for fixture in &module.fixtures {
            fixture_deps_map.insert(&fixture.name, fixture.dependencies.iter().collect());
        }
    }

    let mut used = HashSet::new();
    let mut worklist = Vec::new();

    for module in modules {
        for test in &module.test_functions {
            for dep in &test.fixture_deps {
                if used.insert(dep.clone()) {
                    worklist.push(dep.clone());
                }
            }
        }
    }

    while let Some(name) = worklist.pop() {
        if let Some(deps) = fixture_deps_map.get(name.as_str()) {
            for dep in deps {
                if used.insert(dep.to_string()) {
                    worklist.push(dep.to_string());
                }
            }
        }
    }

    used
}

/// Construct a `Violation` from the given rule metadata and location info.
#[allow(dead_code, clippy::too_many_arguments)]
#[must_use]
pub fn make_violation(
    rule_id: &'static str,
    rule_name: &'static str,
    severity: Severity,
    category: Category,
    message: String,
    file_path: PathBuf,
    line: usize,
    suggestion: Option<String>,
    test_name: Option<String>,
) -> Violation {
    Violation {
        rule_id: rule_id.to_string(),
        rule_name: rule_name.to_string(),
        severity,
        category,
        message,
        file_path,
        line,
        col: None,
        suggestion,
        test_name,
    }
}

/// Get test files changed since the given git base ref.
#[allow(clippy::missing_errors_doc)]
pub fn get_changed_files(base: &str) -> Result<Vec<PathBuf>> {
    let output = std::process::Command::new("git")
        .args(["diff", "--name-only", "--diff-filter=ACMR", base])
        .output()?;

    if !output.status.success() {
        anyhow::bail!(
            "git diff failed: {}",
            String::from_utf8_lossy(&output.stderr)
        );
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let files: Vec<PathBuf> = stdout
        .lines()
        .map(|line| PathBuf::from(line.trim()))
        .filter(|p| p.extension().is_some_and(|e| e == "py") && is_test_file(p))
        .collect();

    Ok(files)
}

/// Run the full linter pipeline: discover, lint, format output. Returns true if errors found.
#[allow(clippy::missing_errors_doc)]
pub fn run_linter(
    paths: &[PathBuf],
    format: &str,
    output: Option<&Path>,
    no_color: bool,
    config: Config,
) -> Result<bool> {
    if no_color {
        colored::control::set_override(false);
    }

    let engine = LintEngine::new(config)?;
    let violations = engine.lint_paths(paths)?;

    match format {
        "json" => format_json(&violations, output)?,
        "sarif" => format_sarif(&violations, output)?,
        _ => format_terminal(&violations, output)?,
    }

    Ok(violations.iter().any(|v| v.severity == Severity::Error))
}

/// Collect all violations from the given paths without producing output.
#[allow(clippy::missing_errors_doc)]
pub fn collect_violations(paths: &[PathBuf], config: Config) -> Result<Vec<Violation>> {
    let engine = LintEngine::new(config)?;
    engine.lint_paths(paths)
}

#[derive(serde::Serialize, serde::Deserialize)]
struct BaselineEntry {
    file_path: String,
    line: usize,
    rule_id: String,
}

/// Save a baseline of known violations to a JSON file.
#[allow(clippy::missing_errors_doc)]
pub fn save_baseline(violations: &[Violation], path: &Path) -> Result<()> {
    let entries: Vec<BaselineEntry> = violations
        .iter()
        .map(|v| BaselineEntry {
            file_path: v.file_path.to_string_lossy().to_string(),
            line: v.line,
            rule_id: v.rule_id.clone(),
        })
        .collect();
    let json = serde_json::to_string_pretty(&entries)?;
    std::fs::write(path, json)?;
    Ok(())
}

/// Load a baseline of known violations from a JSON file.
#[allow(clippy::missing_errors_doc)]
pub fn load_baseline(path: &Path) -> Result<HashSet<(String, usize, String)>> {
    let content = std::fs::read_to_string(path)?;
    let entries: Vec<BaselineEntry> = serde_json::from_str(&content)?;
    let set: HashSet<(String, usize, String)> = entries
        .into_iter()
        .map(|e| (e.file_path, e.line, e.rule_id))
        .collect();
    Ok(set)
}

/// Filter violations to only those not present in the baseline.
#[allow(clippy::missing_errors_doc)]
pub fn filter_new_violations(
    violations: &[Violation],
    baseline: &HashSet<(String, usize, String)>,
) -> Vec<Violation> {
    violations
        .iter()
        .filter(|v| {
            let key = (
                v.file_path.to_string_lossy().to_string(),
                v.line,
                v.rule_id.clone(),
            );
            !baseline.contains(&key)
        })
        .cloned()
        .collect()
}

/// Format violations as JSON and write to the given path or stdout.
#[allow(clippy::missing_errors_doc)]
pub fn format_json_output(violations: &[Violation], output: Option<&Path>) -> Result<()> {
    format_json(violations, output)
}

/// Format violations as SARIF and write to the given path or stdout.
#[allow(clippy::missing_errors_doc)]
pub fn format_sarif_output(violations: &[Violation], output: Option<&Path>) -> Result<()> {
    format_sarif(violations, output)
}

/// Format violations for terminal display and write to the given path or stdout.
#[allow(clippy::missing_errors_doc)]
pub fn format_terminal_output(
    violations: &[Violation],
    output: Option<&Path>,
    no_color: bool,
) -> Result<()> {
    if no_color {
        colored::control::set_override(false);
    }
    format_terminal(violations, output)
}

fn format_terminal(violations: &[Violation], output_path: Option<&Path>) -> Result<()> {
    let mut writer: Box<dyn Write> = match output_path {
        Some(path) => Box::new(std::fs::File::create(path)?),
        None => Box::new(std::io::stdout()),
    };

    if violations.is_empty() {
        writeln!(writer, "{} No violations found", "✓".green())?;
        return Ok(());
    }

    let error_count = violations
        .iter()
        .filter(|v| v.severity == Severity::Error)
        .count();
    let warning_count = violations
        .iter()
        .filter(|v| v.severity == Severity::Warning)
        .count();
    let info_count = violations
        .iter()
        .filter(|v| v.severity == Severity::Info)
        .count();

    for v in violations {
        let severity_str = match v.severity {
            Severity::Error => "ERROR".red().bold(),
            Severity::Warning => "WARNING".yellow().bold(),
            Severity::Info => "INFO".blue().bold(),
        };

        let location = format!(
            "{}:{}:{}",
            v.file_path.display(),
            v.line,
            v.col.map_or_else(|| "-".to_string(), |c| c.to_string())
        );

        writeln!(
            writer,
            "{} [{}] {} ({})",
            severity_str, v.rule_id, v.message, location
        )?;

        if let Some(ref suggestion) = v.suggestion {
            writeln!(writer, "  {} {}", "→".cyan(), suggestion)?;
        }

        if let Some(ref test_name) = v.test_name {
            writeln!(writer, "  {} test: {}", "→".dimmed(), test_name)?;
        }
    }

    writeln!(writer)?;
    writeln!(
        writer,
        "{}: {} errors, {} warnings, {} info",
        "Summary".bold(),
        error_count.to_string().red(),
        warning_count.to_string().yellow(),
        info_count.to_string().blue()
    )?;

    Ok(())
}

fn format_json(violations: &[Violation], output_path: Option<&Path>) -> Result<()> {
    let json = serde_json::to_string_pretty(violations)?;

    match output_path {
        Some(path) => {
            let mut file = std::fs::File::create(path)?;
            file.write_all(json.as_bytes())?;
        }
        None => println!("{json}"),
    }

    Ok(())
}

fn format_sarif(violations: &[Violation], output_path: Option<&Path>) -> Result<()> {
    let json = crate::output::format_sarif(violations)?;

    match output_path {
        Some(path) => {
            let mut file = std::fs::File::create(path)?;
            file.write_all(json.as_bytes())?;
        }
        None => println!("{json}"),
    }

    Ok(())
}
