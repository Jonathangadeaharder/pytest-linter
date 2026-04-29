# Rules Overview

pytest-linter includes **28 rules** across three categories.

## Flakiness

| Rule ID | Name | Severity |
|---------|------|----------|
| [PYTEST-FLK-001](./PYTEST-FLK-001.md) | TimeSleepRule | Warning |
| [PYTEST-FLK-002](./PYTEST-FLK-002.md) | FileIoRule | Warning |
| [PYTEST-FLK-003](./PYTEST-FLK-003.md) | NetworkImportRule | Warning |
| [PYTEST-FLK-004](./PYTEST-FLK-004.md) | CwdDependencyRule | Warning |
| [PYTEST-FLK-005](./PYTEST-FLK-005.md) | MysteryGuestRule | Warning |
| [PYTEST-XDIST-001](./PYTEST-XDIST-001.md) | XdistSharedStateRule | Warning |
| [PYTEST-XDIST-002](./PYTEST-XDIST-002.md) | XdistFixtureIoRule | Warning |

## Maintenance

| Rule ID | Name | Severity |
|---------|------|----------|
| [PYTEST-MNT-001](./PYTEST-MNT-001.md) | TestLogicRule | Warning |
| [PYTEST-MNT-002](./PYTEST-MNT-002.md) | MagicAssertRule | Warning |
| [PYTEST-MNT-004](./PYTEST-MNT-004.md) | NoAssertionRule | Error |
| [PYTEST-MNT-005](./PYTEST-MNT-005.md) | MockOnlyVerifyRule | Warning |
| [PYTEST-MNT-006](./PYTEST-MNT-006.md) | AssertionRouletteRule | Warning |
| [PYTEST-MNT-007](./PYTEST-MNT-007.md) | RawExceptionHandlingRule | Warning |
| [PYTEST-PARAM-001](./PYTEST-PARAM-001.md) | ParametrizeEmptyRule | Warning |
| [PYTEST-PARAM-002](./PYTEST-PARAM-002.md) | ParametrizeDuplicateRule | Warning |
| [PYTEST-PARAM-003](./PYTEST-PARAM-003.md) | ParametrizeExplosionRule | Warning |

## Fixture

| Rule ID | Name | Severity |
|---------|------|----------|
| [PYTEST-FIX-001](./PYTEST-FIX-001.md) | AutouseFixtureRule | Warning |
| [PYTEST-FIX-003](./PYTEST-FIX-003.md) | InvalidScopeRule | Error |
| [PYTEST-FIX-004](./PYTEST-FIX-004.md) | ShadowedFixtureRule | Warning |
| [PYTEST-FIX-005](./PYTEST-FIX-005.md) | UnusedFixtureRule | Warning |
| [PYTEST-FIX-006](./PYTEST-FIX-006.md) | StatefulSessionFixtureRule | Warning |
| [PYTEST-FIX-007](./PYTEST-FIX-007.md) | FixtureMutationRule | Warning |
| [PYTEST-FIX-008](./PYTEST-FIX-008.md) | FixtureDbCommitNoCleanupRule | Warning |
| [PYTEST-FIX-009](./PYTEST-FIX-009.md) | FixtureOverlyBroadScopeRule | Warning |

## Enhancement

| Rule ID | Name | Severity |
|---------|------|----------|
| [PYTEST-MNT-003](./PYTEST-MNT-003.md) | SuboptimalAssertRule | Info |
| [PYTEST-BDD-001](./PYTEST-BDD-001.md) | BddMissingScenarioRule | Info |
| [PYTEST-PBT-001](./PYTEST-PBT-001.md) | PropertyTestHintRule | Info |
| [PYTEST-DBC-001](./PYTEST-DBC-001.md) | NoContractHintRule | Info |
