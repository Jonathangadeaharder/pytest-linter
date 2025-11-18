"""Command-line interface for test-linter."""

import sys
import argparse
from pathlib import Path
from typing import List, Optional

from test_linter.core.engine import create_default_engine
from test_linter.core.config import load_config
from test_linter.core.rules import RuleViolation
from test_linter.core.models import SmellSeverity


class TerminalReporter:
    """Reports violations to the terminal."""

    COLORS = {
        "red": "\033[91m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "green": "\033[92m",
        "reset": "\033[0m",
    }

    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors and sys.stdout.isatty()

    def report(self, violations: List[RuleViolation]) -> None:
        """Report violations to terminal."""
        if not violations:
            self._print_success("No issues found!")
            return

        # Group by file
        by_file: dict[str, List[RuleViolation]] = {}
        for violation in violations:
            if violation.file_path not in by_file:
                by_file[violation.file_path] = []
            by_file[violation.file_path].append(violation)

        # Print violations by file
        for file_path, file_violations in sorted(by_file.items()):
            self._print_file_header(file_path)

            for violation in sorted(file_violations, key=lambda v: v.line_number):
                self._print_violation(violation)

        # Print summary
        self._print_summary(violations)

    def _print_file_header(self, file_path: str) -> None:
        """Print file header."""
        if self.use_colors:
            print(f"\n{self.COLORS['blue']}{file_path}{self.COLORS['reset']}")
        else:
            print(f"\n{file_path}")

    def _print_violation(self, violation: RuleViolation) -> None:
        """Print a single violation."""
        # Choose color based on severity
        if violation.severity == SmellSeverity.ERROR:
            color = "red"
            prefix = "ERROR"
        elif violation.severity == SmellSeverity.WARNING:
            color = "yellow"
            prefix = "WARN "
        else:
            color = "blue"
            prefix = "INFO "

        # Format location
        location = f"{violation.line_number}"
        if violation.column:
            location += f":{violation.column}"

        # Format message
        if self.use_colors:
            print(
                f"  {location:>6} {self.COLORS[color]}{prefix}{self.COLORS['reset']} "
                f"{violation.message}"
            )
            if violation.suggestion:
                print(f"         {self.COLORS['blue']}💡 {violation.suggestion}{self.COLORS['reset']}")
        else:
            print(f"  {location:>6} {prefix} {violation.message}")
            if violation.suggestion:
                print(f"         Suggestion: {violation.suggestion}")

    def _print_success(self, message: str) -> None:
        """Print success message."""
        if self.use_colors:
            print(f"{self.COLORS['green']}✓ {message}{self.COLORS['reset']}")
        else:
            print(f"✓ {message}")

    def _print_summary(self, violations: List[RuleViolation]) -> None:
        """Print summary of violations."""
        errors = sum(1 for v in violations if v.severity == SmellSeverity.ERROR)
        warnings = sum(1 for v in violations if v.severity == SmellSeverity.WARNING)
        infos = sum(1 for v in violations if v.severity == SmellSeverity.INFO)

        print(f"\n{'-' * 60}")
        print(f"Found {len(violations)} issue(s):")
        if errors > 0:
            self._print_colored(f"  {errors} error(s)", "red")
        if warnings > 0:
            self._print_colored(f"  {warnings} warning(s)", "yellow")
        if infos > 0:
            self._print_colored(f"  {infos} info(s)", "blue")

    def _print_colored(self, message: str, color: str) -> None:
        """Print colored message."""
        if self.use_colors:
            print(f"{self.COLORS[color]}{message}{self.COLORS['reset']}")
        else:
            print(message)


class JSONReporter:
    """Reports violations in JSON format."""

    def report(self, violations: List[RuleViolation]) -> str:
        """Report violations as JSON."""
        import json

        violations_data = [
            {
                "file": v.file_path,
                "line": v.line_number,
                "column": v.column,
                "severity": v.severity.value,
                "category": v.category.value,
                "rule_id": v.rule_id,
                "rule_name": v.rule_name,
                "message": v.message,
                "suggestion": v.suggestion,
                "context": v.context,
            }
            for v in violations
        ]

        return json.dumps(
            {"violations": violations_data, "total": len(violations)}, indent=2
        )


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entry point.

    Args:
        argv: Command-line arguments (uses sys.argv if None)

    Returns:
        Exit code (0 = success, 1 = violations found, 2 = error)
    """
    parser = argparse.ArgumentParser(
        description="Test-linter: Multi-language test code linter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Files or directories to lint",
    )

    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        help="Path to configuration file",
    )

    parser.add_argument(
        "--format",
        choices=["terminal", "json"],
        default="terminal",
        help="Output format",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output file (default: stdout)",
    )

    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )

    parser.add_argument(
        "--language",
        help="Force specific language (auto-detect if not specified)",
    )

    args = parser.parse_args(argv)

    try:
        # Load configuration
        config_file = args.config
        if not config_file and args.paths:
            # Try to find config in first path
            start_dir = args.paths[0] if args.paths[0].is_dir() else args.paths[0].parent
            config = load_config(start_dir=start_dir)
        elif config_file:
            config = load_config(config_file=config_file)
        else:
            from test_linter.core.config import get_default_config
            config = get_default_config()

        # Create engine
        engine = create_default_engine(config)

        # Collect all violations
        all_violations = []

        for path in args.paths:
            if path.is_file():
                violations = engine.lint_files([path])
            elif path.is_dir():
                violations = engine.lint_directory(path, recursive=True)
            else:
                print(f"Error: {path} is not a file or directory", file=sys.stderr)
                return 2

            all_violations.extend(violations)

        # Report results
        if args.format == "terminal":
            reporter = TerminalReporter(use_colors=not args.no_color)
            reporter.report(all_violations)
        elif args.format == "json":
            reporter = JSONReporter()
            output = reporter.report(all_violations)
            if args.output:
                args.output.write_text(output)
            else:
                print(output)

        # Return exit code
        if all_violations:
            # Check if any errors
            has_errors = any(
                v.severity == SmellSeverity.ERROR for v in all_violations
            )
            return 1 if has_errors else 0
        else:
            return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
