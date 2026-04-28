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

pub struct LintEngine {
    rules: Vec<Box<dyn Rule>>,
    config: Config,
}

impl LintEngine {
    #[allow(clippy::missing_errors_doc)]
    pub fn new(config: Config) -> Result<Self> {
        let all = crate::rules::all_rules();
        let rules: Vec<Box<dyn Rule>> = all
            .into_iter()
            .filter(|r| config.is_rule_enabled(r.id()))
            .collect();
        Ok(Self { rules, config })
    }

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
                        violation.severity =
                            self.config.rule_severity(rule.id(), rule.severity());
                    }
                    module_violations.append(&mut v);
                }
                module_violations
            })
            .collect();

        let mut violations = violations;
        violations.sort();
        Ok(violations)
    }
}

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

fn is_test_file(path: &Path) -> bool {
    let name = path
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_default();
    name.starts_with("test_") || name.ends_with("_test.py") || name == "conftest.py"
}

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

#[must_use]
pub fn compute_session_mutable_fixtures(modules: &[ParsedModule]) -> HashSet<String> {
    modules
        .iter()
        .flat_map(|m| m.fixtures.iter())
        .filter(|f| f.scope == crate::models::FixtureScope::Session && f.returns_mutable)
        .map(|f| f.name.clone())
        .collect()
}

#[must_use]
pub fn fixture_scope_by_name<S: BuildHasher>(
    all_fixtures: &HashMap<String, Vec<&Fixture>, S>,
    name: &str,
) -> Option<FixtureScope> {
    all_fixtures
        .get(name)
        .and_then(|v| v.iter().min_by_key(|f| f.scope).map(|f| f.scope))
}

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
