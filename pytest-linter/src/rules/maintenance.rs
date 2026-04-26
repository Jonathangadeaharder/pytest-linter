use crate::engine::make_violation;
use crate::models::{Category, ParsedModule, Severity, Violation};
use crate::rules::{Rule, RuleContext};

pub struct TestLogicRule;

impl Rule for TestLogicRule {
    fn id(&self) -> &'static str {
        "PYTEST-MNT-001"
    }
    fn name(&self) -> &'static str {
        "TestLogicRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Maintenance
    }
    fn check(&self, module: &ParsedModule, _all_modules: &[ParsedModule], _ctx: &RuleContext) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            if test.has_conditional_logic {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!("Test '{}' contains conditional logic (if statements)", test.name),
                    module.file_path.clone(),
                    test.line,
                    Some("Split into separate tests or use parametrize".to_string()),
                    Some(test.name.clone()),
                ));
            }
        }
        violations
    }
}

pub struct MagicAssertRule;

impl Rule for MagicAssertRule {
    fn id(&self) -> &'static str {
        "PYTEST-MNT-002"
    }
    fn name(&self) -> &'static str {
        "MagicAssertRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Maintenance
    }
    fn check(&self, module: &ParsedModule, _all_modules: &[ParsedModule], _ctx: &RuleContext) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            for assertion in &test.assertions {
                if assertion.is_magic {
                    violations.push(make_violation(
                        self.id(),
                        self.name(),
                        self.severity(),
                        self.category(),
                        format!(
                            "Magic assertion at line {}: '{}' — this always passes/fails",
                            assertion.line, assertion.expression_text
                        ),
                        module.file_path.clone(),
                        assertion.line,
                        Some("Replace with a meaningful comparison".to_string()),
                        Some(test.name.clone()),
                    ));
                }
            }
        }
        violations
    }
}

pub struct SuboptimalAssertRule;

impl Rule for SuboptimalAssertRule {
    fn id(&self) -> &'static str {
        "PYTEST-MNT-003"
    }
    fn name(&self) -> &'static str {
        "SuboptimalAssertRule"
    }
    fn severity(&self) -> Severity {
        Severity::Info
    }
    fn category(&self) -> Category {
        Category::Enhancement
    }
    fn check(&self, module: &ParsedModule, _all_modules: &[ParsedModule], _ctx: &RuleContext) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            for assertion in &test.assertions {
                if assertion.is_suboptimal {
                    violations.push(make_violation(
                        self.id(),
                        self.name(),
                        self.severity(),
                        self.category(),
                        format!(
                            "Suboptimal assertion at line {}: '{}'",
                            assertion.line, assertion.expression_text
                        ),
                        module.file_path.clone(),
                        assertion.line,
                        Some("Use a more direct assertion pattern".to_string()),
                        Some(test.name.clone()),
                    ));
                }
            }
        }
        violations
    }
}

pub struct NoAssertionRule;

impl Rule for NoAssertionRule {
    fn id(&self) -> &'static str {
        "PYTEST-MNT-004"
    }
    fn name(&self) -> &'static str {
        "NoAssertionRule"
    }
    fn severity(&self) -> Severity {
        Severity::Error
    }
    fn category(&self) -> Category {
        Category::Maintenance
    }
    fn check(&self, module: &ParsedModule, _all_modules: &[ParsedModule], _ctx: &RuleContext) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            if !test.has_assertions {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!("Test '{}' has no assertions", test.name),
                    module.file_path.clone(),
                    test.line,
                    Some("Add assertions to verify expected behavior".to_string()),
                    Some(test.name.clone()),
                ));
            }
        }
        violations
    }
}

pub struct MockOnlyVerifyRule;

impl Rule for MockOnlyVerifyRule {
    fn id(&self) -> &'static str {
        "PYTEST-MNT-005"
    }
    fn name(&self) -> &'static str {
        "MockOnlyVerifyRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Maintenance
    }
    fn check(&self, module: &ParsedModule, _all_modules: &[ParsedModule], _ctx: &RuleContext) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            if test.has_mock_verifications && !test.has_state_assertions {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!(
                        "Test '{}' only verifies mocks without checking state",
                        test.name
                    ),
                    module.file_path.clone(),
                    test.line,
                    Some("Add state assertions to verify actual outcomes".to_string()),
                    Some(test.name.clone()),
                ));
            }
        }
        violations
    }
}

pub struct AssertionRouletteRule;

impl Rule for AssertionRouletteRule {
    fn id(&self) -> &'static str {
        "PYTEST-MNT-006"
    }
    fn name(&self) -> &'static str {
        "AssertionRouletteRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Maintenance
    }
    fn check(&self, module: &ParsedModule, _all_modules: &[ParsedModule], _ctx: &RuleContext) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            if test.assertion_count > 3 && !test.is_parametrized {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!(
                        "Test '{}' has {} assertions (assertion roulette)",
                        test.name, test.assertion_count
                    ),
                    module.file_path.clone(),
                    test.line,
                    Some("Split into smaller, focused tests".to_string()),
                    Some(test.name.clone()),
                ));
            }
        }
        violations
    }
}

pub struct RawExceptionHandlingRule;

impl Rule for RawExceptionHandlingRule {
    fn id(&self) -> &'static str {
        "PYTEST-MNT-007"
    }
    fn name(&self) -> &'static str {
        "RawExceptionHandlingRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Maintenance
    }
    fn check(&self, module: &ParsedModule, _all_modules: &[ParsedModule], _ctx: &RuleContext) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            if test.has_try_except {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!("Test '{}' uses try/except instead of pytest.raises", test.name),
                    module.file_path.clone(),
                    test.line,
                    Some("Use pytest.raises() for exception testing".to_string()),
                    Some(test.name.clone()),
                ));
            }
        }
        violations
    }
}

pub struct BddMissingScenarioRule;

impl Rule for BddMissingScenarioRule {
    fn id(&self) -> &'static str {
        "PYTEST-BDD-001"
    }
    fn name(&self) -> &'static str {
        "BddMissingScenarioRule"
    }
    fn severity(&self) -> Severity {
        Severity::Info
    }
    fn category(&self) -> Category {
        Category::Enhancement
    }
    fn check(&self, module: &ParsedModule, _all_modules: &[ParsedModule], _ctx: &RuleContext) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            let has_gherkin = test.docstring.as_ref().is_some_and(|ds| {
                let lower = ds.to_lowercase();
                lower.contains("given") || lower.contains("when") || lower.contains("then")
            });
            if !has_gherkin {
                violations.push(make_violation(
                    self.id(),
                    self.name(),
                    self.severity(),
                    self.category(),
                    format!("Test '{}' lacks a Gherkin-style docstring scenario", test.name),
                    module.file_path.clone(),
                    test.line,
                    Some("Add a docstring with Given/When/Then structure".to_string()),
                    Some(test.name.clone()),
                ));
            }
        }
        violations
    }
}

pub struct PropertyTestHintRule;

impl Rule for PropertyTestHintRule {
    fn id(&self) -> &'static str {
        "PYTEST-PBT-001"
    }
    fn name(&self) -> &'static str {
        "PropertyTestHintRule"
    }
    fn severity(&self) -> Severity {
        Severity::Info
    }
    fn category(&self) -> Category {
        Category::Enhancement
    }
    fn check(&self, module: &ParsedModule, _all_modules: &[ParsedModule], _ctx: &RuleContext) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            if test.is_parametrized {
                if let Some(count) = test.parametrize_count {
                    if count > 3 {
                        violations.push(make_violation(
                            self.id(),
                            self.name(),
                            self.severity(),
                            self.category(),
                            format!(
                                "Test '{}' has {} parametrized cases — consider property-based testing",
                                test.name, count
                            ),
                            module.file_path.clone(),
                            test.line,
                            Some("Consider using hypothesis for property-based testing".to_string()),
                            Some(test.name.clone()),
                        ));
                    }
                }
            }
        }
        violations
    }
}

pub struct ParametrizeEmptyRule;

impl Rule for ParametrizeEmptyRule {
    fn id(&self) -> &'static str {
        "PYTEST-PARAM-001"
    }
    fn name(&self) -> &'static str {
        "ParametrizeEmptyRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Maintenance
    }
    fn check(&self, module: &ParsedModule, _all_modules: &[ParsedModule], _ctx: &RuleContext) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            if test.is_parametrized {
                if let Some(count) = test.parametrize_count {
                    if count <= 1 {
                        violations.push(make_violation(
                            self.id(),
                            self.name(),
                            self.severity(),
                            self.category(),
                            format!(
                                "Test '{}' is parametrized with only {} case(s)",
                                test.name, count
                            ),
                            module.file_path.clone(),
                            test.line,
                            Some("Add more test cases or remove parametrize".to_string()),
                            Some(test.name.clone()),
                        ));
                    }
                }
            }
        }
        violations
    }
}

pub struct ParametrizeDuplicateRule;

impl Rule for ParametrizeDuplicateRule {
    fn id(&self) -> &'static str {
        "PYTEST-PARAM-002"
    }
    fn name(&self) -> &'static str {
        "ParametrizeDuplicateRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Maintenance
    }
    fn check(&self, module: &ParsedModule, _all_modules: &[ParsedModule], _ctx: &RuleContext) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            for values in &test.parametrize_values {
                let mut seen = std::collections::HashSet::new();
                let mut duplicates = std::collections::HashSet::new();
                for val in values {
                    if !seen.insert(val) {
                        duplicates.insert(val.as_str());
                    }
                }
                if !duplicates.is_empty() {
                    let dup_str: Vec<&str> = duplicates.into_iter().collect();
                    violations.push(make_violation(
                        self.id(),
                        self.name(),
                        self.severity(),
                        self.category(),
                        format!(
                            "Parametrize in test '{}' has duplicate values: {}",
                            test.name,
                            dup_str.join(", ")
                        ),
                        module.file_path.clone(),
                        test.line,
                        Some("Remove duplicate parametrize values".to_string()),
                        Some(test.name.clone()),
                    ));
                }
            }
        }
        violations
    }
}

pub struct ParametrizeExplosionRule;

impl Rule for ParametrizeExplosionRule {
    fn id(&self) -> &'static str {
        "PYTEST-PARAM-003"
    }
    fn name(&self) -> &'static str {
        "ParametrizeExplosionRule"
    }
    fn severity(&self) -> Severity {
        Severity::Warning
    }
    fn category(&self) -> Category {
        Category::Maintenance
    }
    fn check(&self, module: &ParsedModule, _all_modules: &[ParsedModule], _ctx: &RuleContext) -> Vec<Violation> {
        let mut violations = Vec::new();
        for test in &module.test_functions {
            if let Some(count) = test.parametrize_count {
                if count > 20 {
                    violations.push(make_violation(
                        self.id(),
                        self.name(),
                        self.severity(),
                        self.category(),
                        format!(
                            "Test '{}' has {} parametrized cases — combinatorial explosion",
                            test.name, count
                        ),
                        module.file_path.clone(),
                        test.line,
                        Some("Reduce test cases or use hypothesis".to_string()),
                        Some(test.name.clone()),
                    ));
                }
            }
        }
        violations
    }
}

