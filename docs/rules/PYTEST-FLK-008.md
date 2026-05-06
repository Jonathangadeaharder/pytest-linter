# PYTEST-FLK-008 — RandomWithoutSeedRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FLK-008` |
| **Name** | RandomWithoutSeedRule |
| **Severity** | Warning |
| **Category** | Flakiness |

## Message

> Test '{test}' uses random without fixed seed — causes flaky tests

## Rationale

Using `random` without a fixed seed produces non-deterministic output. Tests that depend on random values will fail intermittently across different runs because the random state varies.

## Suggestion

Call random.seed() at the start of the test or use a fixture

## Examples

### ❌ Bad

```python
import random

def test_shuffle():
    items = list(range(10))
    random.shuffle(items)
    assert items[0] != 0  # may pass or fail unpredictably
```

### ✅ Good

```python
import random

def test_shuffle():
    random.seed(42)
    items = list(range(10))
    random.shuffle(items)
    assert items[0] == 7  # deterministic
```
