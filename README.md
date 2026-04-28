# pytest-linter

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Fast, tree-sitter-powered test smell detector for **pytest** (Python), written in Rust.

## Quick Start

```bash
# Install from source
cargo install --path .

# Run
pytest-linter /path/to/tests

# JSON output
pytest-linter --format json /path/to/tests

# Incremental mode (only changed files)
pytest-linter --incremental /path/to/tests

# Baseline mode
pytest-linter --baseline violations.json /path/to/tests
pytest-linter --check-baseline violations.json /path/to/tests
```

## Rules (30)

**Flakiness (9):**

| Rule ID | Name | Severity |
|---------|------|----------|
| PYTEST-FLK-001 | TimeSleepRule | Warning |
| PYTEST-FLK-002 | FileIoRule | Warning |
| PYTEST-FLK-003 | NetworkImportRule | Warning |
| PYTEST-FLK-004 | CwdDependencyRule | Warning |
| PYTEST-FLK-005 | MysteryGuestRule | Warning |
| PYTEST-FLK-008 | RandomWithoutSeedRule | Warning |
| PYTEST-FLK-009 | SubprocessWithoutTimeoutRule | Warning |
| PYTEST-XDIST-001 | XdistSharedStateRule | Warning |
| PYTEST-XDIST-002 | XdistFixtureIoRule | Warning |

**Maintenance (12):**

| Rule ID | Name | Severity |
|---------|------|----------|
| PYTEST-MNT-001 | TestLogicRule | Warning |
| PYTEST-MNT-002 | MagicAssertRule | Warning |
| PYTEST-MNT-003 | SuboptimalAssertRule | Info |
| PYTEST-MNT-004 | NoAssertionRule | Error |
| PYTEST-MNT-005 | MockOnlyVerifyRule | Warning |
| PYTEST-MNT-006 | AssertionRouletteRule | Warning |
| PYTEST-MNT-007 | RawExceptionHandlingRule | Warning |
| PYTEST-BDD-001 | BddMissingScenarioRule | Info |
| PYTEST-PBT-001 | PropertyTestHintRule | Info |
| PYTEST-PARAM-001 | ParametrizeEmptyRule | Warning |
| PYTEST-PARAM-002 | ParametrizeDuplicateRule | Warning |
| PYTEST-PARAM-003 | ParametrizeExplosionRule | Warning |

**Fixtures (9):**

| Rule ID | Name | Severity |
|---------|------|----------|
| PYTEST-FIX-001 | AutouseFixtureRule | Warning |
| PYTEST-FIX-003 | InvalidScopeRule | Error |
| PYTEST-FIX-004 | ShadowedFixtureRule | Warning |
| PYTEST-FIX-005 | UnusedFixtureRule | Warning |
| PYTEST-FIX-006 | StatefulSessionFixtureRule | Warning |
| PYTEST-FIX-007 | FixtureMutationRule | Warning |
| PYTEST-FIX-008 | FixtureDbCommitNoCleanupRule | Warning |
| PYTEST-FIX-009 | FixtureOverlyBroadScopeRule | Warning |
| PYTEST-DBC-001 | NoContractHintRule | Info |

## CLI Options

```
Usage: pytest-linter [OPTIONS] [PATHS]...

Arguments:
  [PATHS]...  Files or directories to lint

Options:
  --format <FORMAT>              Output format: terminal, json, sarif
  --output <OUTPUT>              Write output to file instead of stdout
  --no-color                     Disable colored output
  --incremental                  Only lint files changed since --base
  --base <BASE>                  Git ref for incremental mode [default: HEAD]
  --baseline <FILE>              Save violations to baseline file
  --check-baseline <FILE>        Compare against baseline, fail on new violations
  -h, --help                     Print help
```

Exit code: **1** if any `Error` severity violations found, **0** otherwise.

## Configuration

Add to your `pyproject.toml`:

```toml
[tool.pytest-linter]
format = "json"

[tool.pytest-linter.rules.PYTEST-FLK-001]
enabled = false

[tool.pytest-linter.rules.PYTEST-MNT-004]
severity = "warning"
```

## Suppression

Suppress specific rules inline:

```python
def test_something():  # noqa: PYTEST-FLK-001
    time.sleep(1)
    assert True
```

## Architecture

- **tree-sitter** for AST parsing (no regex)
- **Rule trait** with `check(module, all_modules) -> Vec<Violation>`
- **Engine** discovers test files, parses them, runs all rules
- **CLI** via clap with terminal/JSON/SARIF output
- **Parallel** file parsing and rule checking via rayon

## License

MIT
