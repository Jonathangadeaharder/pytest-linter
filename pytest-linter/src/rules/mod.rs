use crate::models::{ParsedModule, Violation};

pub trait Rule: Send + Sync {
    fn id(&self) -> &'static str;
    fn name(&self) -> &'static str;
    fn severity(&self) -> crate::models::Severity;
    fn category(&self) -> crate::models::Category;
    fn check(&self, module: &ParsedModule, all_modules: &[ParsedModule]) -> Vec<Violation>;
}

pub mod flakiness;
pub mod fixtures;
pub mod maintenance;

pub fn all_rules() -> Vec<Box<dyn Rule>> {
    let mut rules: Vec<Box<dyn Rule>> = Vec::new();

    rules.push(Box::new(flakiness::TimeSleepRule));
    rules.push(Box::new(flakiness::FileIoRule));
    rules.push(Box::new(flakiness::NetworkImportRule));
    rules.push(Box::new(flakiness::CwdDependencyRule));
    rules.push(Box::new(flakiness::MysteryGuestRule));
    rules.push(Box::new(flakiness::XdistSharedStateRule));
    rules.push(Box::new(flakiness::XdistFixtureIoRule));

    rules.push(Box::new(maintenance::TestLogicRule));
    rules.push(Box::new(maintenance::MagicAssertRule));
    rules.push(Box::new(maintenance::SuboptimalAssertRule));
    rules.push(Box::new(maintenance::NoAssertionRule));
    rules.push(Box::new(maintenance::MockOnlyVerifyRule));
    rules.push(Box::new(maintenance::AssertionRouletteRule));
    rules.push(Box::new(maintenance::RawExceptionHandlingRule));
    rules.push(Box::new(maintenance::BddMissingScenarioRule));
    rules.push(Box::new(maintenance::PropertyTestHintRule));
    rules.push(Box::new(maintenance::ParametrizeEmptyRule));
    rules.push(Box::new(maintenance::ParametrizeDuplicateRule));
    rules.push(Box::new(maintenance::ParametrizeExplosionRule));
    rules.push(Box::new(maintenance::ParametrizeNoVariationRule));

    rules.push(Box::new(fixtures::AutouseFixtureRule));
    rules.push(Box::new(fixtures::InvalidScopeRule));
    rules.push(Box::new(fixtures::ShadowedFixtureRule));
    rules.push(Box::new(fixtures::UnusedFixtureRule));
    rules.push(Box::new(fixtures::StatefulSessionFixtureRule));
    rules.push(Box::new(fixtures::FixtureMutationRule));
    rules.push(Box::new(fixtures::FixtureDbCommitNoCleanupRule));
    rules.push(Box::new(fixtures::FixtureOverlyBroadScopeRule));
    rules.push(Box::new(fixtures::NoContractHintRule));

    rules
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_all_rules_returns_29() {
        let rules = all_rules();
        assert_eq!(rules.len(), 29);
    }

    #[test]
    fn test_all_rules_have_unique_ids() {
        let rules = all_rules();
        let mut ids: Vec<&str> = rules.iter().map(|r| r.id()).collect();
        ids.sort();
        ids.dedup();
        assert_eq!(ids.len(), rules.len(), "Rule IDs should be unique");
    }

    #[test]
    fn test_all_rules_have_non_empty_names() {
        let rules = all_rules();
        for rule in &rules {
            assert!(!rule.name().is_empty(), "Rule {} has empty name", rule.id());
        }
    }

    #[test]
    fn test_expected_rule_ids_present() {
        let rules = all_rules();
        let ids: Vec<&str> = rules.iter().map(|r| r.id()).collect();
        let expected = [
            "PYTEST-FLK-001",
            "PYTEST-FLK-002",
            "PYTEST-FLK-003",
            "PYTEST-MNT-001",
            "PYTEST-MNT-004",
            "PYTEST-MNT-006",
            "PYTEST-MNT-007",
            "PYTEST-FIX-001",
        ];
        for id in &expected {
            assert!(ids.contains(id), "Expected rule {} to be present", id);
        }
    }
}
