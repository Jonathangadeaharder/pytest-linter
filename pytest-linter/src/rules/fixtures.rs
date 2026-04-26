use crate::engine::{
    collect_all_fixtures, fixture_scope_by_name, is_fixture_used_by_any_test_or_fixture,
    make_violation,
};
use crate::models::{Category, ParsedModule, Severity, Violation};
use crate::rules::Rule;
use std::collections::HashMap;
use std::path::PathBuf;

pub struct AutouseFixtureRule;

impl Rule for AutouseFixtureRule {
    fn id(&self) -> &'static str {
        "PYTEST-FIX-001"
    }
    fn name(&self) -> &'static str {
        "AutouseFixtureRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Fixture
    }
    fn check(&self, module: &ParsedModule, _all_modules: &[ParsedModule]) -> Vec<Violation> {
        let mut violations = Vec::new();
        for fixture in &module.fixtures {
            if fixture.is_autouse {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!("Fixture '{}' uses autouse=True", fixture.name),
                    module.file_path.clone(),
                    fixture.line,
                    Some("Explicitly declare fixture dependencies instead".to_string()),
                    None,
                ));
            }
        }
        violations
    }
}

pub struct InvalidScopeRule;

impl Rule for InvalidScopeRule {
    fn id(&self) -> &'static str {
        "PYTEST-FIX-003"
    }
    fn name(&self) -> &'static str {
        "InvalidScopeRule"
    }
    fn severity(&self) -> Severity {
        Severity::Error
    }
    fn category(&self) -> Category {
        Category::Fixture
    }
    fn check(&self, module: &ParsedModule, all_modules: &[ParsedModule]) -> Vec<Violation> {
        let all_fixtures = collect_all_fixtures(all_modules);
        let mut violations = Vec::new();

        for fixture in &module.fixtures {
            for dep_name in &fixture.dependencies {
                if let Some(dep_scope) = fixture_scope_by_name(&all_fixtures, dep_name) {
                    if fixture.scope > dep_scope {
                        violations.push(make_violation(
                            self.id(),
                            self.name(),
                            self.severity(),
                            self.category(),
                            format!(
                                "Fixture '{}' (scope={}) depends on '{}' (scope={}) — fixture scope must not exceed dependency scope",
                                fixture.name, fixture.scope, dep_name, dep_scope
                            ),
                            module.file_path.clone(),
                            fixture.line,
                            Some(format!(
                                "Reduce scope of '{}' to match or be narrower than '{}'",
                                fixture.name, dep_name
                            )),
                            None,
                        ));
                    }
                }
            }
        }
        violations
    }
}

pub struct ShadowedFixtureRule;

impl Rule for ShadowedFixtureRule {
    fn id(&self) -> &'static str {
        "PYTEST-FIX-004"
    }
    fn name(&self) -> &'static str {
        "ShadowedFixtureRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Fixture
    }
    fn check(&self, module: &ParsedModule, all_modules: &[ParsedModule]) -> Vec<Violation> {
        let mut name_to_files: HashMap<String, Vec<(PathBuf, usize)>> = HashMap::new();
        for m in all_modules {
            for f in &m.fixtures {
                name_to_files
                    .entry(f.name.clone())
                    .or_default()
                    .push((m.file_path.clone(), f.line));
            }
        }

        let mut violations = Vec::new();
        for (name, locations) in &name_to_files {
            if locations.len() > 1 {
                for fixture in &module.fixtures {
                    if &fixture.name == name {
                        violations.push(make_violation(
                            self.id(),
                            self.name(),
                            self.severity(),
                            self.category(),
                            format!(
                                "Fixture '{}' is defined in {} different modules (shadowed)",
                                name,
                                locations.len()
                            ),
                            module.file_path.clone(),
                            fixture.line,
                            Some("Rename or consolidate fixture definitions".to_string()),
                            None,
                        ));
                    }
                }
            }
        }
        violations
    }
}

pub struct UnusedFixtureRule;

impl Rule for UnusedFixtureRule {
    fn id(&self) -> &'static str {
        "PYTEST-FIX-005"
    }
    fn name(&self) -> &'static str {
        "UnusedFixtureRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Fixture
    }
    fn check(&self, module: &ParsedModule, all_modules: &[ParsedModule]) -> Vec<Violation> {
        let mut violations = Vec::new();
        for fixture in &module.fixtures {
            if fixture.is_autouse {
                continue;
            }
            if !is_fixture_used_by_any_test_or_fixture(&fixture.name, all_modules) {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!("Fixture '{}' is not used by any test or fixture", fixture.name),
                    module.file_path.clone(),
                    fixture.line,
                    Some("Remove the unused fixture or add autouse=True".to_string()),
                    None,
                ));
            }
        }
        violations
    }
}

pub struct StatefulSessionFixtureRule;

impl Rule for StatefulSessionFixtureRule {
    fn id(&self) -> &'static str {
        "PYTEST-FIX-006"
    }
    fn name(&self) -> &'static str {
        "StatefulSessionFixtureRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Fixture
    }
    fn check(&self, module: &ParsedModule, _all_modules: &[ParsedModule]) -> Vec<Violation> {
        let mut violations = Vec::new();
        for fixture in &module.fixtures {
            if fixture.scope == crate::models::FixtureScope::Session && fixture.returns_mutable {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!(
                        "Session-scoped fixture '{}' returns mutable state",
                        fixture.name
                    ),
                    module.file_path.clone(),
                    fixture.line,
                    Some("Return immutable data or use a factory pattern".to_string()),
                    None,
                ));
            }
        }
        violations
    }
}

pub struct FixtureMutationRule;

impl Rule for FixtureMutationRule {
    fn id(&self) -> &'static str {
        "PYTEST-FIX-007"
    }
    fn name(&self) -> &'static str {
        "FixtureMutationRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Fixture
    }
    fn check(&self, _module: &ParsedModule, _all_modules: &[ParsedModule]) -> Vec<Violation> {
        vec![]
    }
}

pub struct FixtureDbCommitNoCleanupRule;

impl Rule for FixtureDbCommitNoCleanupRule {
    fn id(&self) -> &'static str {
        "PYTEST-FIX-008"
    }
    fn name(&self) -> &'static str {
        "FixtureDbCommitNoCleanupRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Fixture
    }
    fn check(&self, module: &ParsedModule, _all_modules: &[ParsedModule]) -> Vec<Violation> {
        let mut violations = Vec::new();
        for fixture in &module.fixtures {
            if fixture.has_db_commit && !fixture.has_db_rollback && !fixture.has_yield {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!(
                        "Fixture '{}' commits to DB without rollback or cleanup (no yield)",
                        fixture.name
                    ),
                    module.file_path.clone(),
                    fixture.line,
                    Some(
                        "Use yield to provide cleanup or wrap in a transaction".to_string(),
                    ),
                    None,
                ));
            }
        }
        violations
    }
}

pub struct FixtureOverlyBroadScopeRule;

impl Rule for FixtureOverlyBroadScopeRule {
    fn id(&self) -> &'static str {
        "PYTEST-FIX-009"
    }
    fn name(&self) -> &'static str {
        "FixtureOverlyBroadScopeRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Fixture
    }
    fn check(&self, _module: &ParsedModule, _all_modules: &[ParsedModule]) -> Vec<Violation> {
        vec![]
    }
}

pub struct NoContractHintRule;

impl Rule for NoContractHintRule {
    fn id(&self) -> &'static str {
        "PYTEST-DBC-001"
    }
    fn name(&self) -> &'static str {
        "NoContractHintRule"
    }
    fn severity(&self) -> Severity {
        Severity::Info
    }
    fn category(&self) -> Category {
        Category::Enhancement
    }
    fn check(&self, _module: &ParsedModule, _all_modules: &[ParsedModule]) -> Vec<Violation> {
        vec![]
    }
}
