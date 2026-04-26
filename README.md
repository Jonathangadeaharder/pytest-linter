# pytest-linter

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Fast, tree-sitter-powered test smell detectors for **pytest** (Python) and **Vitest** (TypeScript), written in Rust.

## Crates

| Crate | Language | Rules | Description |
|-------|----------|:-----:|-------------|
| [`pytest-linter/`](pytest-linter/) | Python (pytest) | 29 | Detects flakiness, maintenance, and fixture smells in pytest test suites |
| [`vitest-linter/`](vitest-linter/) | TypeScript (Vitest) | 10 | Detects flakiness, maintenance, and structure smells in Vitest test suites |

## Quick Start

### pytest-linter

```bash
cd pytest-linter
cargo build --release
./target/release/pytest-linter /path/to/tests

# JSON output
./target/release/pytest-linter --format json /path/to/tests
```

### vitest-linter

```bash
cd vitest-linter
cargo build --release
./target/release/vitest-linter /path/to/tests

# JSON output
./target/release/vitest-linter --format json /path/to/tests
```

## Rules

### pytest-linter (29 rules)

**Flakiness (7):**
| Rule ID | Name | Severity |
|---------|------|----------|
| PYTEST-FLK-001 | TimeSleepRule | Warning |
| PYTEST-FLK-002 | FileIoRule | Warning |
| PYTEST-FLK-003 | NetworkImportRule | Warning |
| PYTEST-FLK-004 | CwdDependencyRule | *stub* |
| PYTEST-FLK-005 | MysteryGuestRule | Warning |
| PYTEST-XDIST-001 | XdistSharedStateRule | *stub* |
| PYTEST-XDIST-002 | XdistFixtureIoRule | Warning |

**Maintenance (14):**
| Rule ID | Name | Severity |
|---------|------|----------|
| PYTEST-MNT-001 | TestLogicRule | Warning |
| PYTEST-MNT-002 | MagicAssertRule | *stub* |
| PYTEST-MNT-003 | SuboptimalAssertRule | *stub* |
| PYTEST-MNT-004 | NoAssertionRule | Error |
| PYTEST-MNT-005 | MockOnlyVerifyRule | Warning |
| PYTEST-MNT-006 | AssertionRouletteRule | Warning |
| PYTEST-MNT-007 | RawExceptionHandlingRule | Warning |
| PYTEST-BDD-001 | BddMissingScenarioRule | Info |
| PYTEST-PBT-001 | PropertyTestHintRule | Info |
| PYTEST-PARAM-001 | ParametrizeEmptyRule | Warning |
| PYTEST-PARAM-002 | ParametrizeDuplicateRule | *stub* |
| PYTEST-PARAM-003 | ParametrizeExplosionRule | Warning |
| PYTEST-PARAM-004 | ParametrizeNoVariationRule | *stub* |
| PYTEST-DBC-001 | NoContractHintRule | *stub* |

**Fixtures (9):**
| Rule ID | Name | Severity |
|---------|------|----------|
| PYTEST-FIX-001 | AutouseFixtureRule | Warning |
| PYTEST-FIX-003 | InvalidScopeRule | Error |
| PYTEST-FIX-004 | ShadowedFixtureRule | Warning |
| PYTEST-FIX-005 | UnusedFixtureRule | Warning |
| PYTEST-FIX-006 | StatefulSessionFixtureRule | Warning |
| PYTEST-FIX-007 | FixtureMutationRule | *stub* |
| PYTEST-FIX-008 | FixtureDbCommitNoCleanupRule | Warning |
| PYTEST-FIX-009 | FixtureOverlyBroadScopeRule | *stub* |

### vitest-linter (10 rules)

**Flakiness (3):**
| Rule ID | Name | Severity |
|---------|------|----------|
| VITEST-FLK-001 | TimeoutRule | Warning |
| VITEST-FLK-002 | DateMockRule | Warning |
| VITEST-FLK-003 | NetworkImportRule | Warning |

**Maintenance (5):**
| Rule ID | Name | Severity |
|---------|------|----------|
| VITEST-MNT-001 | NoAssertionRule | Error |
| VITEST-MNT-002 | MultipleExpectRule | Warning |
| VITEST-MNT-003 | ConditionalLogicRule | Warning |
| VITEST-MNT-004 | TryCatchRule | Warning |
| VITEST-MNT-005 | EmptyTestRule | Info |

**Structure (2):**
| Rule ID | Name | Severity |
|---------|------|----------|
| VITEST-STR-001 | NestedDescribeRule | Warning |
| VITEST-STR-002 | ReturnInTestRule | Warning |

## CLI Options

Both linters share the same interface:

```
Usage: <linter> [OPTIONS] [PATHS]...

Arguments:
  [PATHS]...  Files or directories to lint [default: .]

Options:
  --format <FORMAT>    Output format: terminal, json [default: terminal]
  --output <OUTPUT>    Write output to file instead of stdout
  --no-color           Disable colored output
  -h, --help           Print help
```

Exit code: **1** if any `Error` severity violations found, **0** otherwise.

## Test Quality

| Crate | Tests | Line Coverage | Mutation Score |
|-------|:-----:|:-------------:|:--------------:|
| pytest-linter | 82 | 91.6% | — |
| vitest-linter | 48 | 89.3% | 100% |

## Architecture

Each crate is fully self-contained — no shared core. Both use the same pattern:

- **tree-sitter** for AST parsing (no regex)
- **Rule trait** with `check(module, all_modules) -> Vec<Violation>`
- **Engine** discovers test files, parses them, runs all rules
- **CLI** via clap with terminal/JSON output

## License

MIT
