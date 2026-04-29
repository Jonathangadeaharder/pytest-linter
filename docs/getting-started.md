# Getting Started

## Installation

### Prebuilt Binary

Download the latest release for your platform from [GitHub Releases](https://github.com/your-org/pytest-linter/releases):

| Platform | File |
|----------|------|
| Linux x86_64 | `pytest-linter-x86_64-unknown-linux-gnu.tar.gz` |
| Linux ARM64 | `pytest-linter-aarch64-unknown-linux-gnu.tar.gz` |
| macOS Intel | `pytest-linter-x86_64-apple-darwin.tar.gz` |
| macOS Apple Silicon | `pytest-linter-aarch64-apple-darwin.tar.gz` |
| Windows x86_64 | `pytest-linter-x86_64-pc-windows-msvc.exe.zip` |

Extract and place the binary on your `PATH`.

### pip

```bash
pip install pytest-linter
```

### Homebrew

```bash
brew install your-org/tap/pytest-linter
```

### Cargo

```bash
cargo install pytest-linter
```

## Quick Start

Run on a file or directory:

```bash
pytest-linter tests/
```

Run on a single file with JSON output:

```bash
pytest-linter --format json tests/test_api.py
```

Write output to a file:

```bash
pytest-linter --format sarif --output results.sarif tests/
```

## CLI Options

```
Usage: pytest-linter [OPTIONS] [PATHS]...

Arguments:
  [PATHS]...  Files or directories to lint [default: .]

Options:
  --format <FORMAT>    Output format: terminal, json, sarif [default: terminal]
  --output <OUTPUT>    Write output to file instead of stdout
  --no-color           Disable colored output
  -h, --help           Print help
```

## Configuration

Create a `[tool.pytest-linter]` section in `pyproject.toml`:

```toml
[tool.pytest-linter]
# Ignore specific rules
ignore = ["PYTEST-FLK-001", "PYTEST-BDD-001"]

# Set minimum severity level
min-severity = "warning"
```

## Pre-commit Integration

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/your-org/pytest-linter
    rev: v0.1.0
    hooks:
      - id: pytest-linter
```

## CI Integration

### GitHub Actions

```yaml
- name: Lint tests
  run: |
    curl -sL https://github.com/your-org/pytest-linter/releases/latest/download/pytest-linter-x86_64-unknown-linux-gnu.tar.gz | tar xz
    ./pytest-linter --format sarif --output pytest-linter.sarif tests/
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No Error-severity violations found |
| 1 | One or more Error-severity violations found |
