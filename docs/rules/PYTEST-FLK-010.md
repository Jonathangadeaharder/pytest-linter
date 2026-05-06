# PYTEST-FLK-010 — SocketWithoutBindTimeoutRule

| Property | Value |
|----------|-------|
| **ID** | `PYTEST-FLK-010` |
| **Name** | SocketWithoutBindTimeoutRule |
| **Severity** | Warning |
| **Category** | Flakiness |

## Message

> Test '{test}' uses socket without proper bind and timeout setup

## Rationale

Socket operations without timeout configuration can block indefinitely on connect/accept/recv. Tests that create sockets should always set timeouts to avoid hanging the test suite.

## Suggestion

Add socket.settimeout() or use socket.create_connection() with a timeout

## Examples

### ❌ Bad

```python
import socket

def test_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('localhost', 8080))
    data = s.recv(1024)
```

### ✅ Good

```python
import socket

def test_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect(('localhost', 8080))
    data = s.recv(1024)
```
