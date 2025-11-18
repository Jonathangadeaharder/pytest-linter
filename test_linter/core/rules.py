"""Universal rule system for test smell detection."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set

from test_linter.core.models import (
    TestFunction,
    TestFixture,
    TestSmell,
    SmellCategory,
    SmellSeverity,
    LanguageType,
    TestFramework,
)
from test_linter.core.adapters import ParsedModule


@dataclass
class RuleViolation:
    """Represents a violation of a linting rule."""
    rule_id: str
    rule_name: str
    message: str
    file_path: str
    line_number: int
    column: Optional[int] = None
    severity: SmellSeverity = SmellSeverity.WARNING
    category: SmellCategory = SmellCategory.MAINTENANCE
    suggestion: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


class Rule(ABC):
    """Abstract base class for linting rules.

    Each rule implements a specific check for test smells.
    Rules can be language-agnostic or language-specific.
    """

    def __init__(
        self,
        rule_id: str,
        name: str,
        category: SmellCategory,
        severity: SmellSeverity,
        description: str,
    ):
        self.rule_id = rule_id
        self.name = name
        self.category = category
        self.severity = severity
        self.description = description

    @abstractmethod
    def check(
        self,
        parsed_module: ParsedModule,
        all_modules: Optional[List[ParsedModule]] = None,
    ) -> List[RuleViolation]:
        """Check for violations of this rule.

        Args:
            parsed_module: The module to check
            all_modules: All modules in the project (for cross-file analysis)

        Returns:
            List of violations found
        """
        pass

    def applies_to_language(self, language: LanguageType) -> bool:
        """Check if this rule applies to a specific language.

        Args:
            language: The language to check

        Returns:
            True if the rule applies
        """
        return True  # By default, rules are language-agnostic

    def applies_to_framework(self, framework: TestFramework) -> bool:
        """Check if this rule applies to a specific test framework.

        Args:
            framework: The framework to check

        Returns:
            True if the rule applies
        """
        return True  # By default, rules are framework-agnostic


class UniversalRule(Rule):
    """Base class for rules that apply across all languages.

    These rules detect common test smells that exist regardless
    of the programming language or test framework.
    """
    pass


class LanguageSpecificRule(Rule):
    """Base class for rules specific to a language or framework."""

    def __init__(
        self,
        rule_id: str,
        name: str,
        category: SmellCategory,
        severity: SmellSeverity,
        description: str,
        supported_languages: Optional[List[LanguageType]] = None,
        supported_frameworks: Optional[List[TestFramework]] = None,
    ):
        super().__init__(rule_id, name, category, severity, description)
        self.supported_languages = supported_languages or []
        self.supported_frameworks = supported_frameworks or []

    def applies_to_language(self, language: LanguageType) -> bool:
        """Check if this rule applies to a specific language."""
        if not self.supported_languages:
            return True
        return language in self.supported_languages

    def applies_to_framework(self, framework: TestFramework) -> bool:
        """Check if this rule applies to a specific framework."""
        if not self.supported_frameworks:
            return True
        return framework in self.supported_frameworks


class RuleRegistry:
    """Registry for managing and executing linting rules."""

    def __init__(self):
        self._rules: Dict[str, Rule] = {}
        self._rules_by_category: Dict[SmellCategory, List[Rule]] = {
            category: [] for category in SmellCategory
        }
        self._disabled_rules: Set[str] = set()

    def register(self, rule: Rule) -> None:
        """Register a rule.

        Args:
            rule: The rule to register
        """
        self._rules[rule.rule_id] = rule
        self._rules_by_category[rule.category].append(rule)

    def register_many(self, rules: List[Rule]) -> None:
        """Register multiple rules at once.

        Args:
            rules: List of rules to register
        """
        for rule in rules:
            self.register(rule)

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get a rule by ID.

        Args:
            rule_id: The rule ID

        Returns:
            The rule or None if not found
        """
        return self._rules.get(rule_id)

    def get_rules_for_category(self, category: SmellCategory) -> List[Rule]:
        """Get all rules for a specific category.

        Args:
            category: The category

        Returns:
            List of rules in the category
        """
        return self._rules_by_category.get(category, [])

    def get_applicable_rules(
        self,
        language: LanguageType,
        framework: Optional[TestFramework] = None,
    ) -> List[Rule]:
        """Get all rules applicable to a language/framework.

        Args:
            language: The language
            framework: Optional test framework

        Returns:
            List of applicable rules
        """
        applicable = []
        for rule in self._rules.values():
            if rule.rule_id in self._disabled_rules:
                continue
            if not rule.applies_to_language(language):
                continue
            if framework and not rule.applies_to_framework(framework):
                continue
            applicable.append(rule)
        return applicable

    def disable_rule(self, rule_id: str) -> None:
        """Disable a rule.

        Args:
            rule_id: The rule ID to disable
        """
        self._disabled_rules.add(rule_id)

    def enable_rule(self, rule_id: str) -> None:
        """Enable a previously disabled rule.

        Args:
            rule_id: The rule ID to enable
        """
        self._disabled_rules.discard(rule_id)

    def run_checks(
        self,
        parsed_module: ParsedModule,
        all_modules: Optional[List[ParsedModule]] = None,
    ) -> List[RuleViolation]:
        """Run all applicable rules on a module.

        Args:
            parsed_module: The module to check
            all_modules: All modules in the project (for cross-file analysis)

        Returns:
            List of all violations found
        """
        violations = []
        applicable_rules = self.get_applicable_rules(
            parsed_module.language,
            parsed_module.framework,
        )

        for rule in applicable_rules:
            try:
                rule_violations = rule.check(parsed_module, all_modules)
                violations.extend(rule_violations)
            except Exception as e:
                # Log error but continue with other rules
                print(f"Error running rule {rule.rule_id}: {e}")

        return violations

    def get_all_rules(self) -> List[Rule]:
        """Get all registered rules.

        Returns:
            List of all rules
        """
        return list(self._rules.values())
