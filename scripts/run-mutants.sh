#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

if ! command -v cargo-mutants &>/dev/null; then
    echo "Installing cargo-mutants..."
    cargo install cargo-mutants
fi

cd "$repo_root"

echo "Running cargo-mutants..."
cargo mutants --in-place

echo "Mutation testing complete."
