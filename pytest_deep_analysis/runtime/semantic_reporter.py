"""
Semantic validation report generator.

This module generates comprehensive reports on semantic quality issues
detected during runtime validation.
"""

from typing import Dict, List, Any
from pathlib import Path
import json
from datetime import datetime


class SemanticReporter:
    """
    Generate semantic validation reports in various formats.

    Supported formats:
    - terminal: Colorized terminal output
    - html: Rich HTML report with charts
    - json: Machine-readable JSON for CI integration
    """

    def __init__(
        self,
        test_contexts: Dict[str, Any],
        global_issues: List[str],
        format: str = "terminal"
    ):
        self.test_contexts = test_contexts
        self.global_issues = global_issues
        self.format = format

    def generate(self):
        """Generate report in specified format."""
        if self.format == "terminal":
            self._generate_terminal_report()
        elif self.format == "html":
            self._generate_html_report()
        elif self.format == "json":
            self._generate_json_report()

    def _generate_terminal_report(self):
        """Generate colorized terminal report."""
        print("\n" + "=" * 80)
        print("SEMANTIC VALIDATION REPORT")
        print("=" * 80)

        # Summary statistics
        total_tests = len(self.test_contexts)
        tests_with_issues = sum(
            1 for ctx in self.test_contexts.values()
            if ctx.semantic_issues
        )
        total_issues = sum(
            len(ctx.semantic_issues)
            for ctx in self.test_contexts.values()
        ) + len(self.global_issues)

        print(f"\nSummary:")
        print(f"  Total tests analyzed: {total_tests}")
        print(f"  Tests with semantic issues: {tests_with_issues}")
        print(f"  Total semantic issues: {total_issues}")

        # Global issues
        if self.global_issues:
            print(f"\n{self._colorize('GLOBAL ISSUES:', 'yellow')}")
            for issue in self.global_issues:
                print(f"  • {issue}")

        # Per-test issues
        tests_with_problems = [
            (test_id, ctx)
            for test_id, ctx in self.test_contexts.items()
            if ctx.semantic_issues
        ]

        if tests_with_problems:
            print(f"\n{self._colorize('TEST-SPECIFIC ISSUES:', 'yellow')}")
            for test_id, ctx in tests_with_problems:
                print(f"\n  {self._colorize(test_id, 'cyan')}:")
                for issue in ctx.semantic_issues:
                    severity = self._get_issue_severity(issue)
                    color = {"ERROR": "red", "WARNING": "yellow", "INFO": "blue"}.get(severity, "white")
                    print(f"    • {self._colorize(issue, color)}")

        # Recommendations
        self._print_recommendations()

        print("\n" + "=" * 80 + "\n")

    def _generate_html_report(self):
        """Generate rich HTML report."""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Semantic Validation Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin: 20px 0;
        }}
        .metric {{
            background-color: #f9f9f9;
            padding: 20px;
            border-radius: 5px;
            border-left: 4px solid #4CAF50;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #4CAF50;
        }}
        .metric-label {{
            color: #666;
            margin-top: 5px;
        }}
        .issue {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }}
        .issue.error {{
            background-color: #f8d7da;
            border-left-color: #dc3545;
        }}
        .issue-type {{
            font-weight: bold;
            color: #856404;
        }}
        .test-section {{
            margin: 20px 0;
            padding: 15px;
            background-color: #f9f9f9;
            border-radius: 5px;
        }}
        .recommendation {{
            background-color: #d1ecf1;
            border-left: 4px solid #17a2b8;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Semantic Validation Report</h1>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        {self._generate_html_summary()}
        {self._generate_html_issues()}
        {self._generate_html_recommendations()}
    </div>
</body>
</html>
"""

        # Write to file
        report_path = Path("semantic-validation-report.html")
        report_path.write_text(html_content)
        print(f"\nHTML report generated: {report_path.absolute()}")

    def _generate_html_summary(self) -> str:
        """Generate HTML summary section."""
        total_tests = len(self.test_contexts)
        tests_with_issues = sum(
            1 for ctx in self.test_contexts.values() if ctx.semantic_issues
        )
        total_issues = sum(
            len(ctx.semantic_issues) for ctx in self.test_contexts.values()
        ) + len(self.global_issues)

        return f"""
        <div class="summary">
            <div class="metric">
                <div class="metric-value">{total_tests}</div>
                <div class="metric-label">Tests Analyzed</div>
            </div>
            <div class="metric">
                <div class="metric-value">{tests_with_issues}</div>
                <div class="metric-label">Tests with Issues</div>
            </div>
            <div class="metric">
                <div class="metric-value">{total_issues}</div>
                <div class="metric-label">Total Issues</div>
            </div>
        </div>
        """

    def _generate_html_issues(self) -> str:
        """Generate HTML issues section."""
        html = "<h2>Issues Detected</h2>"

        if self.global_issues:
            html += "<h3>Global Issues</h3>"
            for issue in self.global_issues:
                severity = "error" if "ERROR" in issue or "CRITICAL" in issue else ""
                html += f'<div class="issue {severity}">{issue}</div>'

        tests_with_problems = [
            (test_id, ctx)
            for test_id, ctx in self.test_contexts.items()
            if ctx.semantic_issues
        ]

        if tests_with_problems:
            html += "<h3>Test-Specific Issues</h3>"
            for test_id, ctx in tests_with_problems:
                html += f'<div class="test-section"><strong>{test_id}</strong>'
                for issue in ctx.semantic_issues:
                    severity = "error" if "ERROR" in issue or "CRITICAL" in issue else ""
                    html += f'<div class="issue {severity}">{issue}</div>'
                html += "</div>"

        return html

    def _generate_html_recommendations(self) -> str:
        """Generate HTML recommendations section."""
        recommendations = self._get_recommendations()
        if not recommendations:
            return ""

        html = "<h2>Recommendations</h2>"
        for rec in recommendations:
            html += f'<div class="recommendation">💡 {rec}</div>'

        return html

    def _generate_json_report(self):
        """Generate machine-readable JSON report."""
        report_data = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_tests": len(self.test_contexts),
                "tests_with_issues": sum(
                    1 for ctx in self.test_contexts.values() if ctx.semantic_issues
                ),
                "total_issues": sum(
                    len(ctx.semantic_issues) for ctx in self.test_contexts.values()
                ) + len(self.global_issues)
            },
            "global_issues": self.global_issues,
            "test_issues": {
                test_id: {
                    "test_name": ctx.test_name,
                    "test_file": ctx.test_file,
                    "passed": ctx.passed,
                    "issues": ctx.semantic_issues
                }
                for test_id, ctx in self.test_contexts.items()
                if ctx.semantic_issues
            },
            "recommendations": self._get_recommendations()
        }

        report_path = Path("semantic-validation-report.json")
        report_path.write_text(json.dumps(report_data, indent=2))
        print(f"\nJSON report generated: {report_path.absolute()}")

    def _colorize(self, text: str, color: str) -> str:
        """Add ANSI color codes for terminal output."""
        colors = {
            "red": "\033[91m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "cyan": "\033[96m",
            "white": "\033[97m",
            "reset": "\033[0m"
        }
        return f"{colors.get(color, '')}{text}{colors['reset']}"

    def _get_issue_severity(self, issue: str) -> str:
        """Determine issue severity from message."""
        if any(keyword in issue for keyword in ["ERROR", "CRITICAL", "ORPHAN"]):
            return "ERROR"
        elif any(keyword in issue for keyword in ["WARNING", "LOW-COVERAGE"]):
            return "WARNING"
        else:
            return "INFO"

    def _print_recommendations(self):
        """Print actionable recommendations."""
        recommendations = self._get_recommendations()
        if not recommendations:
            return

        print(f"\n{self._colorize('RECOMMENDATIONS:', 'green')}")
        for rec in recommendations:
            print(f"  💡 {rec}")

    def _get_recommendations(self) -> List[str]:
        """Generate actionable recommendations based on issues."""
        recommendations = []

        # Analyze issue patterns
        all_issues = self.global_issues + [
            issue
            for ctx in self.test_contexts.values()
            for issue in ctx.semantic_issues
        ]

        bdd_issues = [i for i in all_issues if "BDD-" in i]
        pbt_issues = [i for i in all_issues if "PBT-" in i]
        dbc_issues = [i for i in all_issues if "DBC-" in i]
        coverage_issues = [i for i in all_issues if "COVERAGE" in i]

        if bdd_issues:
            recommendations.append(
                "Consider using pytest-bdd to formalize Gherkin scenario execution "
                "and ensure full step coverage."
            )

        if pbt_issues:
            recommendations.append(
                "Review Hypothesis strategies to ensure diverse test case generation. "
                "Consider using composite strategies for complex types."
            )

        if dbc_issues:
            recommendations.append(
                "Add icontract decorators to functions with complex preconditions. "
                "Ensure contracts are tested with both valid and invalid inputs."
            )

        if coverage_issues:
            recommendations.append(
                "Add meaningful assertions to tests that currently pass without verification. "
                "Consider using pytest.raises() for exception testing."
            )

        return recommendations
