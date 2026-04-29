use std::collections::{HashMap, HashSet};

use crate::engine::{fixture_scope_by_name, make_violation};
use crate::models::{Category, Fixture, FixtureScope, ParsedModule, Severity, Violation};
use crate::rules::{Rule, RuleContext};

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
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
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
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();

        for fixture in &module.fixtures {
            for dep_name in &fixture.dependencies {
                if let Some(dep_scope) = fixture_scope_by_name(ctx.fixture_map, dep_name) {
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
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();

        for fixture in &module.fixtures {
            if let Some(locations) = ctx.fixture_locations.get(&fixture.name) {
                if locations.len() > 1 {
                    violations.push(make_violation(
                        self.id(),
                        self.name(),
                        self.severity(),
                        self.category(),
                        format!(
                            "Fixture '{}' is defined in {} different modules (shadowed)",
                            fixture.name,
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
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();
        for fixture in &module.fixtures {
            if fixture.is_autouse {
                continue;
            }
            if !ctx.used_fixture_names.contains(&fixture.name) {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!("Fixture '{}' is not used by any test or fixture", fixture.name),
                    module.file_path.clone(),
                    fixture.line,
                    Some("Remove the unused fixture or reference it explicitly from tests/other fixtures".to_string()),
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
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
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
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            for dep_name in &test.mutates_fixture_deps {
                let is_mutable_fixture = ctx
                    .fixture_map
                    .get(dep_name)
                    .is_some_and(|fixtures| fixtures.iter().any(|f| f.returns_mutable));
                if is_mutable_fixture {
                    violations.push(make_violation(
                        self.id(),
                        self.name(),
                        self.severity(),
                        self.category(),
                        format!(
                            "Test '{}' mutates fixture '{}' which may affect other tests",
                            test.name, dep_name
                        ),
                        module.file_path.clone(),
                        test.line,
                        Some(
                            "Create a fresh copy of the fixture value before modifying it"
                                .to_string(),
                        ),
                        Some(test.name.clone()),
                    ));
                }
            }
        }
        violations
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
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
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
                    Some("Use yield to provide cleanup or wrap in a transaction".to_string()),
                    None,
                ));
            }
        }
        violations
    }
}

pub struct AutouseCascadeDepthRule;

impl Rule for AutouseCascadeDepthRule {
    fn id(&self) -> &'static str {
        "PYTEST-FIX-009"
    }
    fn name(&self) -> &'static str {
        "AutouseCascadeDepthRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Fixture
    }
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();
        for fixture in &module.fixtures {
            if fixture.is_autouse {
                let mut visited = HashSet::new();
                let depth = compute_cascade_depth(fixture, ctx.fixture_map, &mut visited);
                if depth > 3 {
                    violations.push(make_violation(
                        self.id(),
                        self.name(),
                        self.severity(),
                        self.category(),
                        format!(
                            "Autouse fixture '{}' has dependency cascade depth of {} (> 3)",
                            fixture.name, depth
                        ),
                        module.file_path.clone(),
                        fixture.line,
                        Some("Reduce fixture dependency chain or remove autouse".to_string()),
                        None,
                    ));
                }
            }
        }
        violations
    }
}

fn compute_cascade_depth(
    fixture: &Fixture,
    fixture_map: &HashMap<String, Vec<&Fixture>>,
    visited: &mut HashSet<String>,
) -> usize {
    if visited.contains(&fixture.name) {
        return 0;
    }
    visited.insert(fixture.name.clone());
    let deps = fixture.dependencies.clone();
    let result = if deps.is_empty() {
        1
    } else {
        deps.iter()
            .map(|dep| {
                fixture_map
                    .get(dep)
                    .and_then(|v| {
                        v.iter()
                            .find(|f| f.file_path == fixture.file_path || v.len() == 1)
                            .or_else(|| v.first())
                    })
                    .map(|f| compute_cascade_depth(f, fixture_map, visited))
                    .unwrap_or(1)
            })
            .max()
            .unwrap_or(0)
            + 1
    };
    visited.remove(&fixture.name);
    result
}

pub struct ModuleScopeFixtureMutatedRule;

impl Rule for ModuleScopeFixtureMutatedRule {
    fn id(&self) -> &'static str {
        "PYTEST-FIX-010"
    }
    fn name(&self) -> &'static str {
        "ModuleScopeFixtureMutatedRule"
    }
    fn severity(&self) -> Severity {
        Severity::Error
    }
    fn category(&self) -> Category {
        Category::Fixture
    }
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            for dep in &test.mutates_fixture_deps {
                let is_broad_scoped = ctx.fixture_map.get(dep).is_some_and(|fixtures| {
                    fixtures.iter().any(|f| f.scope >= FixtureScope::Module)
                });
                if is_broad_scoped {
                    violations.push(make_violation(
                        self.id(),
                        self.name(),
                        self.severity(),
                        self.category(),
                        format!(
                            "Test '{}' mutates module/session-scoped fixture '{}' — causes cross-test contamination",
                            test.name, dep
                        ),
                        module.file_path.clone(),
                        test.line,
                        Some(
                            "Use function-scoped fixture or copy the value before mutation"
                                .to_string(),
                        ),
                        Some(test.name.clone()),
                    ));
                }
            }
        }
        violations
    }
}

pub struct YieldWithoutTryFinallyRule;

impl Rule for YieldWithoutTryFinallyRule {
    fn id(&self) -> &'static str {
        "PYTEST-FIX-011"
    }
    fn name(&self) -> &'static str {
        "YieldWithoutTryFinallyRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Fixture
    }
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();
        for fixture in &module.fixtures {
            if fixture.has_yield && !fixture.has_cleanup {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!(
                        "Fixture '{}' uses yield without try/finally cleanup",
                        fixture.name
                    ),
                    module.file_path.clone(),
                    fixture.line,
                    Some(
                        "Wrap yield in try/finally to ensure cleanup runs even on failure"
                            .to_string(),
                    ),
                    None,
                ));
            }
        }
        violations
    }
}

pub struct FixtureNameShadowsBuiltinRule;

impl Rule for FixtureNameShadowsBuiltinRule {
    fn id(&self) -> &'static str {
        "PYTEST-FIX-012"
    }
    fn name(&self) -> &'static str {
        "FixtureNameShadowsBuiltinRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Fixture
    }
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();
        let shadows = [
            "list",
            "dict",
            "set",
            "id",
            "type",
            "input",
            "open",
            "tmp_path",
            "capsys",
            "monkeypatch",
            "request",
            "fixture",
        ];
        for fixture in &module.fixtures {
            if shadows.contains(&fixture.name.as_str()) {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!(
                        "Fixture '{}' shadows a Python builtin or pytest hook",
                        fixture.name
                    ),
                    module.file_path.clone(),
                    fixture.line,
                    Some("Rename the fixture to avoid shadowing built-in names".to_string()),
                    None,
                ));
            }
        }
        violations
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
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            if test.has_assertions
                && !test.uses_pytest_raises
                && !test.has_try_except
                && !test.is_parametrized
            {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!("Test '{}' only tests the happy path — consider adding error/edge case coverage", test.name),
                    module.file_path.clone(),
                    test.line,
                    Some("Add tests for error conditions using pytest.raises".to_string()),
                    Some(test.name.clone()),
                ));
            }
        }
        violations
    }
}
