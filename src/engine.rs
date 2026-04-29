use crate::config::Config;
use crate::models::{Category, Fixture, FixtureScope, ParsedModule, Severity, Violation};
use crate::rules::{Rule, RuleContext};
use anyhow::Result;
use colored::Colorize;
use std::collections::{HashMap, HashSet};
use std::hash::BuildHasher;
use std::io::Write;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

/// Single-pass rule dispatcher. Instead of each rule walking the parsed module
/// data independently, the dispatcher iterates all rules in a single pass per
/// module. This minimizes redundant iteration and provides a single integration
/// point for per-file override resolution.
pub struct RuleDispatcher {
    all_rules: Vec<Box<dyn Rule>>,
}

impl Default for RuleDispatcher {
    fn default() -> Self {
        Self::new()
    }
}

impl RuleDispatcher {
    pub fn new() -> Self {
        Self {
            all_rules: crate::rules::all_rules(),
        }
    }

    /// Check all rules against a single module in one pass, applying per-file
    /// config (global + overrides) for rule enablement and severity.
    pub fn check_module(
        &self,
        module: &ParsedModule,
        all_modules: &[ParsedModule],
        ctx: &RuleContext,
        config: &Config,
    ) -> Result<Vec<Violation>> {
        let effective = config.effective_rules_for_file(&module.file_path)?;
        let mut violations = Vec::new();

        for rule in &self.all_rules {
            let rule_id = rule.id();

            let enabled = effective
                .get(rule_id)
                .map(|rc| rc.enabled.unwrap_or(true))
                .unwrap_or(true);

            if !enabled {
                continue;
            }

            let default_severity = rule.severity();
            let severity = effective
                .get(rule_id)
                .and_then(|rc| rc.severity)
                .unwrap_or(default_severity);

            let mut v = rule.check(module, all_modules, ctx);
            for violation in &mut v {
                violation.severity = severity;
            }
            violations.append(&mut v);
        }

        Ok(violations)
    }
}

/// Memory budget for the linter.
///
/// The engine processes files in a streaming fashion to keep peak RSS within
/// the configured budget (default 256 MB):
///
/// 1. File discovery: Walk directory tree, collect test file paths only.
/// 2. Parsing: Each file is read with `std::fs::read_to_string`, parsed by
///    tree-sitter, and converted to a `ParsedModule`. The source string is
///    dropped after parsing — only extracted metadata (names, flags, fixtures)
///    is retained.
/// 3. Cross-module context: Fixture maps and usage sets are computed once from
///    all parsed modules.
/// 4. Rule checking: The `RuleDispatcher` iterates all rules per module in a
///    single pass, applying per-file overrides.
///
/// For a 1 GB Python repo (~10K test files), estimated peak memory:
///   - ParsedModule structs: ~10-50 MB (lightweight metadata, no source text)
///   - Cross-module context: ~5-10 MB
///   - Violations: ~1-5 MB
///   - Parser + tree-sitter overhead: ~5-10 MB
///   - Total: ~20-75 MB, well within the 256 MB budget.
pub struct LintEngine {
    dispatcher: RuleDispatcher,
    config: Config,
    memory_limit_mb: usize,
}

impl LintEngine {
    #[allow(clippy::missing_errors_doc)]
    pub fn new(config: Config) -> Result<Self> {
        Ok(Self {
            dispatcher: RuleDispatcher::new(),
            config,
            memory_limit_mb: 256,
        })
    }

    /// Create a LintEngine with an explicit memory limit (in MB).
    #[allow(clippy::missing_errors_doc)]
    pub fn with_memory_limit(config: Config, memory_limit_mb: usize) -> Result<Self> {
        Ok(Self {
            dispatcher: RuleDispatcher::new(),
            config,
            memory_limit_mb,
        })
    }

    #[allow(clippy::missing_errors_doc)]
    pub fn lint_paths(&self, paths: &[PathBuf]) -> Result<Vec<Violation>> {
        let files = discover_files(paths);

        let estimated_bytes: u64 = files.len() as u64 * 50_000;
        let estimated_mb = estimated_bytes / 1_048_576;
        if estimated_mb > self.memory_limit_mb as u64 {
            eprintln!(
                "Warning: estimated memory usage ({estimated_mb} MB) exceeds limit ({} MB). \
                 Processing may exceed the configured budget.",
                self.memory_limit_mb
            );
        }

        let mut parser = crate::parser::PythonParser::new()?;

        let modules = parse_files(&mut parser, &files);

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

        let mut violations = Vec::new();
        for module in &modules {
            let mut v = self
                .dispatcher
                .check_module(module, &modules, &ctx, &self.config)?;
            violations.append(&mut v);
        }

        violations.sort();
        Ok(violations)
    }

    #[allow(clippy::missing_errors_doc)]
    pub fn lint_source(&self, source: &str, file_path: &Path) -> Result<Vec<Violation>> {
        let mut parser = crate::parser::PythonParser::new()?;
        let module = parser.parse_source(source, file_path)?;
        let modules = vec![module];

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

        let violations = self
            .dispatcher
            .check_module(&modules[0], &modules, &ctx, &self.config)?;

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

fn parse_files(parser: &mut crate::parser::PythonParser, files: &[PathBuf]) -> Vec<ParsedModule> {
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
    run_linter_with_memory_limit(paths, format, output, no_color, config, 256)
}

#[allow(clippy::missing_errors_doc)]
pub fn run_linter_with_memory_limit(
    paths: &[PathBuf],
    format: &str,
    output: Option<&Path>,
    no_color: bool,
    config: Config,
    memory_limit_mb: usize,
) -> Result<bool> {
    if no_color {
        colored::control::set_override(false);
    }

    let engine = LintEngine::with_memory_limit(config, memory_limit_mb)?;
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
