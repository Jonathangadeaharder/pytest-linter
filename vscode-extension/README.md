# pytest-linter VS Code Extension

Detects test smells in Python/pytest test files via the pytest-linter LSP server.

## Features

- Real-time diagnostics as you type
- Configurable via `pyproject.toml` `[tool.pytest-linter]` section
- Shows warnings, errors, and info inline in your test files

## Requirements

- The `pytest-linter-lsp` binary must be installed and available on your PATH,
  or configured via the `pytestLinter.path` setting.

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `pytestLinter.path` | `pytest-linter-lsp` | Path to the LSP server binary |
| `pytestLinter.enable` | `true` | Enable/disable the extension |

## Installation

1. Build the LSP server: `cargo build --release -p pytest-linter-lsp`
2. Copy `target/release/pytest-linter-lsp` to your PATH
3. Install this extension in VS Code
