"""
Design by Contract (DbC) runtime tracker.

This module tracks icontract precondition/postcondition enforcement during
test execution, validating that contracts actually constrain behavior.

This complements static W9018 (pytest-no-contract-hint) by validating:
1. Contracts are actually checked at runtime
2. Contracts detect violations when they should
3. Contracts aren't vacuously true (always pass)
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ContractViolation:
    """Record of a contract violation."""
    contract_type: str  # "precondition" or "postcondition"
    function_name: str
    condition: str
    violated_by: Any


class DbCTracker:
    """
    Track Design by Contract enforcement at runtime.

    Key validations:
    1. **Contract Coverage**: Functions with contracts are actually tested
    2. **Violation Detection**: Contracts catch invalid inputs/outputs
    3. **Non-Vacuous Contracts**: Contracts aren't trivially true
    4. **Contract Completeness**: All important invariants have contracts
    """

    def __init__(self):
        self.contract_violations: List[ContractViolation] = []
        self.contracts_checked: Dict[str, int] = {}
        self.functions_with_contracts: set = set()

    def analyze_contracts(self, test_context: Any) -> List[str]:
        """
        Analyze contract enforcement during test execution.

        Args:
            test_context: Test execution context with contract data

        Returns:
            List of semantic issues found
        """
        issues = []

        contracts_checked = test_context.contracts_checked
        violations = test_context.contract_violations

        # Issue 1: Contracts present but never checked
        if len(contracts_checked) == 0:
            # Check if test calls functions that SHOULD have contracts
            # (based on static W9018 hints)
            issues.append(
                "DBC-NO-CONTRACTS: Test calls no functions with icontract decorators. "
                "Consider adding contracts to complex functions."
            )

        # Issue 2: Contracts checked but no violations
        # This might indicate overly permissive contracts
        if len(contracts_checked) > 0 and len(violations) == 0:
            # Only flag if test has obvious error cases
            if any("error" in call["name"].lower() or "invalid" in call["name"].lower()
                   for call in test_context.function_calls):
                issues.append(
                    "DBC-VACUOUS-CONTRACTS: Contracts checked but no violations detected. "
                    "Contracts may be too permissive or test isn't checking error cases."
                )

        # Issue 3: Violations occurred but were silenced
        if len(violations) > 0:
            # This is actually GOOD - contracts are working!
            # But warn if test passed despite violations
            if test_context.passed:
                issues.append(
                    f"DBC-IGNORED-VIOLATIONS: {len(violations)} contract violations "
                    f"occurred but test passed. Violations may be improperly caught."
                )

        return issues

    def track_contract_check(self, function_name: str, contract_type: str):
        """Record that a contract was checked."""
        key = f"{function_name}:{contract_type}"
        self.contracts_checked[key] = self.contracts_checked.get(key, 0) + 1

    def track_violation(self, violation: ContractViolation):
        """Record a contract violation."""
        self.contract_violations.append(violation)

    def analyze_contract_effectiveness(
        self,
        all_test_contexts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze overall contract effectiveness across all tests.

        Returns:
            Summary of contract enforcement quality
        """
        # Extract unique function names from contracts_checked
        # (contracts_checked keys are "function:contract_type", so split to get unique functions)
        tested_functions = {key.split(":", 1)[0] for key in self.contracts_checked}

        summary = {
            "total_contracts": len(self.functions_with_contracts),
            "contracts_tested": len(tested_functions),
            "violations_detected": len(self.contract_violations),
            "coverage_percentage": 0.0,
            "effectiveness_score": 0.0
        }

        # Calculate contract coverage
        if summary["total_contracts"] > 0:
            summary["coverage_percentage"] = (
                summary["contracts_tested"] / summary["total_contracts"] * 100
            )

        # Calculate effectiveness (violations detected / contracts tested)
        if summary["contracts_tested"] > 0:
            summary["effectiveness_score"] = (
                summary["violations_detected"] / summary["contracts_tested"]
            )

        # Add recommendations
        summary["recommendations"] = []

        if summary["coverage_percentage"] < 70:
            summary["recommendations"].append(
                f"Low contract coverage ({summary['coverage_percentage']:.1f}%). "
                f"Add tests that exercise functions with contracts."
            )

        if summary["effectiveness_score"] < 0.1 and summary["contracts_tested"] > 10:
            summary["recommendations"].append(
                "Contracts rarely detect violations. Consider:\n"
                "  1. Adding negative test cases\n"
                "  2. Strengthening contract conditions\n"
                "  3. Testing boundary conditions"
            )

        return summary
