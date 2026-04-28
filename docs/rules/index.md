# Rule Reference

## Flakiness Rules

Rules that detect patterns likely to cause flaky, non-deterministic tests.

- [PYTEST-FLK-001](FLK-001.md) - time.sleep in test
- [PYTEST-FLK-002](FLK-002.md) - File I/O without tmp_path
- [PYTEST-FLK-003](FLK-003.md) - Network library imports
- [PYTEST-FLK-004](FLK-004.md) - CWD dependency
- [PYTEST-FLK-005](FLK-005.md) - Mystery guest
- [PYTEST-FLK-008](FLK-008.md) - Random without fixed seed
- [PYTEST-FLK-009](FLK-009.md) - Subprocess without timeout

## Maintenance Rules

Rules that detect code smells affecting test maintainability.

- [PYTEST-MNT-001](MNT-001.md) - Conditional logic in test
- [PYTEST-MNT-002](MNT-002.md) - Magic assertion
- [PYTEST-MNT-003](MNT-003.md) - Suboptimal assertion
- [PYTEST-MNT-004](MNT-004.md) - No assertions
- [PYTEST-MNT-005](MNT-005.md) - Mock-only verification
- [PYTEST-MNT-006](MNT-006.md) - Assertion roulette
- [PYTEST-MNT-007](MNT-007.md) - Raw exception handling

## Fixture Rules

Rules that detect problematic fixture patterns.

- [PYTEST-FIX-001](FIX-001.md) - Autouse fixture
- [PYTEST-FIX-003](FIX-003.md) - Invalid scope
- [PYTEST-FIX-004](FIX-004.md) - Shadowed fixture
- [PYTEST-FIX-005](FIX-005.md) - Unused fixture
- [PYTEST-FIX-006](FIX-006.md) - Stateful session fixture
- [PYTEST-FIX-007](FIX-007.md) - Fixture mutation
- [PYTEST-FIX-008](FIX-008.md) - DB commit without cleanup
- [PYTEST-FIX-009](FIX-009.md) - Overly broad scope
