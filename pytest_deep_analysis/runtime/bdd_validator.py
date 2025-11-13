"""
BDD (Behavior-Driven Development) runtime validator.

This module validates that Gherkin scenarios actually execute by mapping
declared steps to actual function calls during test execution.

This addresses the fundamental limitation of static W9016 checks:
- Static: Can only detect PRESENCE of @pytest.mark.scenario
- Runtime: Can verify steps ACTUALLY EXECUTE and map to implementation
"""

from typing import List, Dict, Any
import re
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class GherkinStep:
    """Parsed Gherkin step with execution status."""
    keyword: str  # Given, When, Then, And, But
    text: str
    executed: bool = False
    matched_functions: List[str] = None

    def __post_init__(self):
        if self.matched_functions is None:
            self.matched_functions = []


class BDDValidator:
    """
    Validates BDD scenario execution at runtime.

    Capabilities:
    1. Parse Gherkin steps from docstrings or @scenario markers
    2. Map steps to actual function calls using heuristics
    3. Detect orphan steps (declared but never executed)
    4. Detect zombie functions (execute but not mapped to steps)
    5. Generate Requirements Traceability Matrix (RTM)
    """

    def __init__(self):
        self.step_pattern = re.compile(
            r'^\s*(Given|When|Then|And|But)\s+(.+)$',
            re.MULTILINE
        )

    def parse_gherkin_steps(self, text: str) -> List[GherkinStep]:
        """Parse Gherkin steps from text (docstring or feature file)."""
        steps = []

        for match in self.step_pattern.finditer(text):
            keyword = match.group(1)
            step_text = match.group(2).strip()

            steps.append(GherkinStep(
                keyword=keyword,
                text=step_text
            ))

        return steps

    def validate_scenario_execution(
        self,
        gherkin_steps: List[str],
        function_calls: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Validate that Gherkin steps actually executed.

        Args:
            gherkin_steps: List of Gherkin step strings
            function_calls: Execution trace of function calls

        Returns:
            List of semantic issues found
        """
        issues = []

        # Parse steps if they're strings
        if gherkin_steps and isinstance(gherkin_steps[0], str):
            parsed_steps = []
            for step_str in gherkin_steps:
                match = self.step_pattern.match(step_str)
                if match:
                    parsed_steps.append(GherkinStep(
                        keyword=match.group(1),
                        text=match.group(2).strip()
                    ))
            gherkin_steps = parsed_steps

        if not gherkin_steps:
            return issues

        # Map steps to function calls using fuzzy matching
        function_names = [call["name"] for call in function_calls]

        for step in gherkin_steps:
            matched = self._match_step_to_functions(step, function_names)
            step.matched_functions = matched
            step.executed = len(matched) > 0

        # Detect orphan steps (declared but not executed)
        orphan_steps = [s for s in gherkin_steps if not s.executed]
        if orphan_steps:
            for step in orphan_steps:
                issues.append(
                    f"BDD-ORPHAN-STEP: '{step.keyword} {step.text}' declared but "
                    f"no matching function executed"
                )

        # Detect incomplete scenario coverage
        total_steps = len(gherkin_steps)
        executed_steps = sum(1 for s in gherkin_steps if s.executed)
        coverage = (executed_steps / total_steps * 100) if total_steps > 0 else 0

        if coverage < 80:
            issues.append(
                f"BDD-LOW-COVERAGE: Only {coverage:.1f}% of Gherkin steps "
                f"mapped to executed functions ({executed_steps}/{total_steps})"
            )

        return issues

    def _match_step_to_functions(
        self,
        step: GherkinStep,
        function_names: List[str]
    ) -> List[str]:
        """
        Match a Gherkin step to function names using heuristics.

        Heuristics:
        1. Direct name match (e.g., "Given a user" -> "given_a_user")
        2. Fuzzy match based on keywords
        3. Pattern matching for common BDD conventions
        """
        matches = []

        # Normalize step text for matching
        step_normalized = step.text.lower().replace(" ", "_")
        step_words = set(step.text.lower().split())

        for func_name in function_names:
            func_lower = func_name.lower()

            # 1. Direct substring match
            if step_normalized in func_lower or func_lower in step_normalized:
                matches.append(func_name)
                continue

            # 2. Fuzzy match (>70% similar)
            similarity = SequenceMatcher(None, step_normalized, func_lower).ratio()
            if similarity > 0.7:
                matches.append(func_name)
                continue

            # 3. Keyword overlap (>50% of step words in function name)
            func_words = set(re.findall(r'[a-z]+', func_lower))
            overlap = len(step_words & func_words)
            if overlap > 0 and overlap / len(step_words) > 0.5:
                matches.append(func_name)

        return matches

    def generate_rtm(
        self,
        test_contexts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate Requirements Traceability Matrix (RTM).

        Maps Gherkin scenarios -> Test functions -> Implementation functions.

        Returns:
            Dictionary representation of RTM
        """
        rtm = {
            "scenarios": [],
            "coverage_summary": {
                "total_scenarios": 0,
                "traced_scenarios": 0,
                "orphan_steps": 0,
                "coverage_percentage": 0.0
            }
        }

        for test_id, context in test_contexts.items():
            if not context.gherkin_steps:
                continue

            rtm["scenarios"].append({
                "test_id": test_id,
                "scenario": context.scenario_reference or "Inline docstring",
                "steps": [
                    {
                        "text": f"{s.keyword} {s.text}",
                        "executed": s.executed,
                        "mapped_functions": s.matched_functions
                    }
                    for s in context.gherkin_steps
                ]
            })

            rtm["coverage_summary"]["total_scenarios"] += 1
            if all(s.executed for s in context.gherkin_steps):
                rtm["coverage_summary"]["traced_scenarios"] += 1
            rtm["coverage_summary"]["orphan_steps"] += sum(
                1 for s in context.gherkin_steps if not s.executed
            )

        # Calculate coverage
        total = rtm["coverage_summary"]["total_scenarios"]
        traced = rtm["coverage_summary"]["traced_scenarios"]
        rtm["coverage_summary"]["coverage_percentage"] = (
            (traced / total * 100) if total > 0 else 0.0
        )

        return rtm
