# PYTEST-FLK-009 — SubprocessWithoutTimeoutRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FLK-009` |
| **Name** | SubprocessWithoutTimeoutRule |
| **Severity** | Warning |
| **Category** | Flakiness |

## Message

> Test '{test}' uses subprocess without timeout — may hang indefinitely

## Rationale

Subprocess calls without a `timeout` parameter can hang indefinitely if the child process stalls. In CI environments this causes builds to time out at the job level rather than failing fast.

## Suggestion

Add timeout parameter to subprocess calls

## Examples

### ❌ Bad

```python
import subprocess

def test_cli():
    result = subprocess.run(['my-cli', 'serve'])
    assert result.returncode == 0
```

### ✅ Good

```python
import subprocess

def test_cli():
    result = subprocess.run(['my-cli', 'serve'], timeout=10)
    assert result.returncode == 0
```
