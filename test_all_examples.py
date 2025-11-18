#!/usr/bin/env python3
"""Quick validation script to test all example files."""

import json
import subprocess
from pathlib import Path

examples = [
    ("TypeScript", "examples/typescript-sample.test.ts"),
    ("Go", "examples/go-sample_test.go"),
    ("C++", "examples/cpp-sample_test.cpp"),
    ("Java", "examples/JavaSampleTest.java"),
    ("Rust", "examples/rust_sample_test.rs"),
    ("C#", "examples/CSharpSampleTest.cs"),
]

print("=" * 70)
print("Multi-Language Test Linter - Validation Results")
print("=" * 70)
print()

results = []

for lang_name, file_path in examples:
    print(f"Testing {lang_name}: {file_path}")

    try:
        result = subprocess.run(
            ["python", "-m", "test_linter.cli", file_path, "--format", "json"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode in [0, 1]:  # 0 = no violations, 1 = violations found
            data = json.loads(result.stdout)
            total = data["total"]
            violations_list = data.get("violations", [])
            errors = sum(1 for v in violations_list if v.get("severity") == "error")
            warnings = sum(1 for v in violations_list if v.get("severity") == "warning")
            print(f"  ✓ Found {total} violation(s): {errors} error(s), {warnings} warning(s)")
            results.append((lang_name, True, total))
        else:
            print(f"  ✗ Error: {result.stderr[:100]}")
            results.append((lang_name, False, 0))
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        results.append((lang_name, False, 0))

    print()

print("=" * 70)
print("Summary:")
print("=" * 70)

successful = sum(1 for _, success, _ in results if success)
total_violations = sum(count for _, success, count in results if success)

for lang_name, success, count in results:
    status = "✅" if success else "❌"
    print(f"  {status} {lang_name}: {count} violation(s) detected" if success else f"  {status} {lang_name}: Failed")

print()
print(f"✅ {successful}/{len(examples)} languages validated successfully!")
print(f"📊 Total violations detected across all languages: {total_violations}")
print()
print("=" * 70)
