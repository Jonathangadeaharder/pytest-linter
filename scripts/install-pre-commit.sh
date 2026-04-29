#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_CFG="$REPO_ROOT/pre-commit-hooks.yaml"

if ! command -v pre-commit &>/dev/null; then
    echo "Error: pre-commit not found. Install with: pip install pre-commit" >&2
    exit 1
fi

if ! command -v cargo &>/dev/null; then
    echo "Error: cargo not found. Install Rust from https://rustup.rs" >&2
    exit 1
fi

if [ ! -f "$HOOK_CFG" ]; then
    echo "Error: $HOOK_CFG not found" >&2
    exit 1
fi

if [ ! -f "$REPO_ROOT/target/release/pytest-linter" ]; then
    echo "Building pytest-linter release binary..."
    cargo build --release --manifest-path "$REPO_ROOT/Cargo.toml"
fi

pre-commit try-repo "$REPO_ROOT" pytest-linter --verbose
echo ""
echo "To install in your project, add to .pre-commit-config.yaml:"
echo ""
echo "  repos:"
echo "    - repo: https://github.com/Jonathangadeaharder/pytest-linter"
echo "      rev: ''  # Use a tag or commit"
echo "      hooks:"
echo "        - id: pytest-linter"
