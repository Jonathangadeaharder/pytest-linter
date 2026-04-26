use crate::engine::make_violation;
use crate::models::{Category, ParsedModule, Severity, Violation};
use crate::rules::{Rule, RuleContext};

pub struct TimeSleepRule;

impl Rule for TimeSleepRule {
    fn id(&self) -> &'static str {
        "PYTEST-FLK-001"
    }
    fn name(&self) -> &'static str {
        "TimeSleepRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Flakiness
    }
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            if test.uses_time_sleep {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!(
                        "Test '{}' uses time.sleep which causes flaky tests",
                        test.name
                    ),
                    module.file_path.clone(),
                    test.line,
                    Some("Use pytest's time mocking or wait for a condition instead".to_string()),
                    Some(test.name.clone()),
                ));
            }
        }
        violations
    }
}

pub struct FileIoRule;

impl Rule for FileIoRule {
    fn id(&self) -> &'static str {
        "PYTEST-FLK-002"
    }
    fn name(&self) -> &'static str {
        "FileIoRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Flakiness
    }
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            if test.uses_file_io {
                let has_tmp = test
                    .fixture_deps
                    .iter()
                    .any(|d| d == "tmp_path" || d == "tmpdir" || d == "tmp_path_factory");
                if !has_tmp {
                    violations.push(make_violation(
                        self.id(),
                        self.name(),
                        self.severity(),
                        self.category(),
                        format!(
                            "Test '{}' uses file I/O without tmp_path/tmpdir fixture",
                            test.name
                        ),
                        module.file_path.clone(),
                        test.line,
                        Some("Use the tmp_path or tmpdir fixture for temporary files".to_string()),
                        Some(test.name.clone()),
                    ));
                }
            }
        }
        violations
    }
}

pub struct NetworkImportRule;

impl Rule for NetworkImportRule {
    fn id(&self) -> &'static str {
        "PYTEST-FLK-003"
    }
    fn name(&self) -> &'static str {
        "NetworkImportRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Flakiness
    }
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
        let network_modules = ["requests", "socket", "httpx", "aiohttp", "urllib"];
        let has_network = module
            .imports
            .iter()
            .any(|imp| network_modules.iter().any(|nm| imp.contains(nm)));
        if has_network {
            vec![make_violation(
                self.id(),
                self.name(),
                self.severity(),
                self.category(),
                "File imports network libraries which may cause flaky tests".to_string(),
                module.file_path.clone(),
                1,
                Some("Mock network calls or use pytest-localserver".to_string()),
                None,
            )]
        } else {
            vec![]
        }
    }
}

pub struct CwdDependencyRule;

impl Rule for CwdDependencyRule {
    fn id(&self) -> &'static str {
        "PYTEST-FLK-004"
    }
    fn name(&self) -> &'static str {
        "CwdDependencyRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Flakiness
    }
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            if test.uses_cwd_dependency {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!(
                        "Test '{}' depends on the current working directory",
                        test.name
                    ),
                    module.file_path.clone(),
                    test.line,
                    Some("Use absolute paths or tmp_path fixture instead".to_string()),
                    Some(test.name.clone()),
                ));
            }
        }
        violations
    }
}

pub struct MysteryGuestRule;

impl Rule for MysteryGuestRule {
    fn id(&self) -> &'static str {
        "PYTEST-FLK-005"
    }
    fn name(&self) -> &'static str {
        "MysteryGuestRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Flakiness
    }
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            if test.uses_file_io {
                let has_tmp = test
                    .fixture_deps
                    .iter()
                    .any(|d| d == "tmp_path" || d == "tmpdir" || d == "tmp_path_factory");
                if !has_tmp {
                    violations.push(make_violation(
                        self.id(),
                        self.name(),
                        self.severity(),
                        self.category(),
                        format!(
                            "Test '{}' may be a Mystery Guest — uses file I/O without temp fixtures",
                            test.name
                        ),
                        module.file_path.clone(),
                        test.line,
                        Some(
                            "Use tmp_path fixture and make test data explicit".to_string(),
                        ),
                        Some(test.name.clone()),
                    ));
                }
            }
        }
        violations
    }
}

pub struct XdistSharedStateRule;

impl Rule for XdistSharedStateRule {
    fn id(&self) -> &'static str {
        "PYTEST-XDIST-001"
    }
    fn name(&self) -> &'static str {
        "XdistSharedStateRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Flakiness
    }
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();
        if ctx.session_mutable_fixtures.is_empty() {
            return violations;
        }

        for test in &module.test_functions {
            for dep in &test.mutates_fixture_deps {
                if ctx.session_mutable_fixtures.contains(dep) {
                    violations.push(make_violation(
                        self.id(),
                        self.name(),
                        self.severity(),
                        self.category(),
                        format!(
                            "Session-scoped fixture '{}' returns mutable state that is modified by test '{}' — unsafe for xdist",
                            dep, test.name
                        ),
                        module.file_path.clone(),
                        test.line,
                        Some("Use function scope or return immutable values".to_string()),
                        Some(test.name.clone()),
                    ));
                }
            }
        }
        violations
    }
}

pub struct XdistFixtureIoRule;

impl Rule for XdistFixtureIoRule {
    fn id(&self) -> &'static str {
        "PYTEST-XDIST-002"
    }
    fn name(&self) -> &'static str {
        "XdistFixtureIoRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Flakiness
    }
    fn check(
        &self,
        module: &ParsedModule,
        _all_modules: &[ParsedModule],
        _ctx: &RuleContext,
    ) -> Vec<Violation> {
        let mut violations = Vec::new();
        for fixture in &module.fixtures {
            if fixture.scope == crate::models::FixtureScope::Session && fixture.uses_file_io {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!(
                        "Session-scoped fixture '{}' uses file I/O — may conflict with xdist workers",
                        fixture.name
                    ),
                    module.file_path.clone(),
                    fixture.line,
                    Some("Use tmp_path_factory or make I/O paths unique per worker".to_string()),
                    None,
                ));
            }
        }
        violations
    }
}
