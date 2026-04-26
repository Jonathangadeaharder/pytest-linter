use crate::models::{Category, Fixture, FixtureScope, ParsedModule, Severity, Violation};
use crate::rules::{Rule, RuleContext};
use anyhow::Result;
use colored::Colorize;
use std::collections::{HashMap, HashSet};
use std::hash::BuildHasher;
use std::io::Write;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

pub struct LintEngine {
    rules: Vec<Box<dyn Rule>>,
}

impl LintEngine {
    #[allow(clippy::missing_errors_doc)]
    pub fn new() -> Result<Self> {
        Ok(Self {
            rules: crate::rules::all_rules(),
        })
    }

    #[allow(clippy::missing_errors_doc)]
    pub fn lint_paths(&self, paths: &[PathBuf]) -> Result<Vec<Violation>> {
        let files = discover_files(paths);
        let mut parser = crate::parser::PythonParser::new()?;
        let modules = parse_files(&mut parser, &files);
        let mut violations = Vec::new();

        let fixture_map = collect_all_fixtures(&modules);
        let used_fixture_names = compute_used_fixture_names(&modules);
        let ctx = RuleContext {
            fixture_map: &fixture_map,
            used_fixture_names: &used_fixture_names,
        };

        for module in &modules {
            for rule in &self.rules {
                let mut v = rule.check(module, &modules, &ctx);
                violations.append(&mut v);
            }
        }

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
                if p.is_file()
                    && p.extension().is_some_and(|e| e == "py")
                    && is_test_file(p)
                {
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
    name.starts_with("test_")
        || name.ends_with("_test.py")
        || name == "conftest.py"
}

fn parse_files(
    parser: &mut crate::parser::PythonParser,
    files: &[PathBuf],
) -> Vec<ParsedModule> {
    let mut modules = Vec::new();
    for file in files {
        match parser.parse_file(file) {
            Ok(m) => modules.push(m),
            Err(e) => eprintln!("Warning: failed to parse {}: {}", file.display(), e),
        }
    }
    modules
}

#[must_use]
pub fn collect_all_fixtures(modules: &[ParsedModule]) -> HashMap<String, Vec<&Fixture>> {
    let mut map: HashMap<String, Vec<&Fixture>> = HashMap::new();
    for module in modules {
        for fixture in &module.fixtures {
            map.entry(fixture.name.clone())
                .or_default()
                .push(fixture);
        }
    }
    map
}

#[must_use]
pub fn fixture_scope_by_name<S: BuildHasher>(
    all_fixtures: &HashMap<String, Vec<&Fixture>, S>,
    name: &str,
) -> Option<FixtureScope> {
    all_fixtures.get(name).and_then(|v| v.first().map(|f| f.scope))
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
                && other_fixture
                    .dependencies
                    .iter()
                    .any(|d| d == fixture_name)
            {
                return true;
            }
        }
    }
    false
}

#[must_use]
pub fn compute_used_fixture_names(modules: &[ParsedModule]) -> HashSet<String> {
    let mut used = HashSet::new();
    for module in modules {
        for test in &module.test_functions {
            for dep in &test.fixture_deps {
                used.insert(dep.clone());
            }
        }
        for fixture in &module.fixtures {
            for dep in &fixture.dependencies {
                used.insert(dep.clone());
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
) -> Result<bool> {
    if no_color {
        colored::control::set_override(false);
    }

    let engine = LintEngine::new()?;
    let violations = engine.lint_paths(paths)?;

    match format {
        "json" => format_json(&violations, output)?,
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
