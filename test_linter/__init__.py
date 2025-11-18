"""
test-linter: A universal test linter supporting multiple programming languages.

This tool provides language-agnostic analysis of test code across Python, TypeScript,
Go, C++, Java, Rust, and C#, targeting common test smells and anti-patterns:
- Test flakiness caused by environment dependencies
- Maintenance overhead from test complexity
- Fixture/setup interaction issues and scope misalignment

Architecture:
- Language-agnostic core with pluggable language adapters
- Supports multiple test frameworks per language
- Unified rule catalog with language-specific implementations

Supported Languages:
- Python (pytest, unittest)
- TypeScript/JavaScript (Jest, Mocha, Vitest)
- Go (testing, testify)
- C++ (GoogleTest, Catch2, Boost.Test)
- Java (JUnit 4/5, TestNG)
- Rust (built-in tests, proptest)
- C# (NUnit, xUnit, MSTest)

Usage:
    test-linter [options] path/to/tests/
"""

__version__ = "0.2.0"
__all__ = ["__version__"]
