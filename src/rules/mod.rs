use crate::models::{Fixture, ParsedModule, Violation};
use std::collections::{HashMap, HashSet};
use std::path::PathBuf;

pub struct RuleContext<'a> {
    pub fixture_map: &'a HashMap<String, Vec<&'a Fixture>>,
    pub used_fixture_names: &'a HashSet<String>,
    pub fixture_locations: &'a HashMap<String, Vec<PathBuf>>,
    pub session_mutable_fixtures: &'a HashSet<String>,
}

pub trait Rule: Send + Sync {
    fn id(&self) -> &'static str;
    fn name(&self) -> &'static str;
    fn severity(&self) -> crate::models::Severity;
    fn category(&self) -> crate::models::Category;
    fn check(
        &self,
        module: &ParsedModule,
        all_modules: &[ParsedModule],
        ctx: &RuleContext,
    ) -> Vec<Violation>;
}

pub mod fixtures;
pub mod flakiness;
pub mod maintenance;

#[must_use]
pub fn all_rules() -> Vec<Box<dyn Rule>> {
    vec![
        Box::new(flakiness::TimeSleepRule),
        Box::new(flakiness::FileIoRule),
        Box::new(flakiness::NetworkImportRule),
        Box::new(flakiness::CwdDependencyRule),
        Box::new(flakiness::MysteryGuestRule),
        Box::new(flakiness::XdistSharedStateRule),
        Box::new(flakiness::XdistFixtureIoRule),
        Box::new(maintenance::TestLogicRule),
        Box::new(maintenance::MagicAssertRule),
        Box::new(maintenance::SuboptimalAssertRule),
        Box::new(maintenance::NoAssertionRule),
        Box::new(maintenance::MockOnlyVerifyRule),
        Box::new(maintenance::AssertionRouletteRule),
        Box::new(maintenance::RawExceptionHandlingRule),
        Box::new(maintenance::BddMissingScenarioRule),
        Box::new(maintenance::PropertyTestHintRule),
        Box::new(maintenance::ParametrizeEmptyRule),
        Box::new(maintenance::ParametrizeDuplicateRule),
        Box::new(maintenance::ParametrizeExplosionRule),
        Box::new(fixtures::AutouseFixtureRule),
        Box::new(fixtures::InvalidScopeRule),
        Box::new(fixtures::ShadowedFixtureRule),
        Box::new(fixtures::UnusedFixtureRule),
        Box::new(fixtures::StatefulSessionFixtureRule),
        Box::new(fixtures::FixtureMutationRule),
        Box::new(fixtures::FixtureDbCommitNoCleanupRule),
        Box::new(fixtures::AutouseCascadeDepthRule),
        Box::new(fixtures::ModuleScopeFixtureMutatedRule),
        Box::new(fixtures::YieldWithoutTryFinallyRule),
        Box::new(fixtures::FixtureNameShadowsBuiltinRule),
        Box::new(flakiness::SocketWithoutBindTimeoutRule),
        Box::new(flakiness::DatetimeInAssertionRule),
        Box::new(maintenance::DuplicateTestBodiesRule),
        Box::new(maintenance::SleepWithValueRule),
        Box::new(maintenance::TestNameLengthRule),
        Box::new(fixtures::NoContractHintRule),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_all_rules_returns_37() {
        let rules = all_rules();
        assert_eq!(rules.len(), 36);
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
