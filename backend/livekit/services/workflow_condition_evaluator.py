"""
Condition Evaluator - Generic rule evaluation engine for conversational workflows.

Evaluates conditions against extracted fields with ZERO industry-specific knowledge.
Used by:
- Lead Scorer: quality_signals and risk_penalties conditions
- Summary Formatter: follow_up_rules conditions

Supports operators:
- exists, not_exists
- equals, not_equals
- contains, contains_any, not_contains
- greater_than, less_than, greater_than_or_equal, less_than_or_equal
- in_list (alias: in), not_in_list (alias: not_in)
- regex_match
- word_count_gte, word_count_lte
- Compound: any_of (OR), all_of (AND)

Note: "in" and "in_list" accept both "value" (list) and "values" (list) keys for flexibility.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class ConditionEvaluator:
    """
    Generic condition evaluator with zero industry-specific knowledge.

    All business logic comes from condition configuration, not code.
    """

    def __init__(self):
        """Initialize condition evaluator."""
        self.logger = logging.getLogger(__name__)

    def evaluate(self, condition: Dict[str, Any], extracted_fields: Dict[str, Any]) -> bool:
        """
        Evaluate a condition against extracted fields.

        Args:
            condition: Condition configuration (field, operator, value, etc.)
            extracted_fields: Extracted field data from session

        Returns:
            True if condition matches, False otherwise

        Supported condition formats:
            - Single condition: {"field": "email", "operator": "exists"}
            - Compound OR: {"any_of": [condition1, condition2, ...]}
            - Compound AND: {"all_of": [condition1, condition2, ...]}
        """
        try:
            # Handle compound conditions
            if "any_of" in condition:
                return self._evaluate_any_of(condition["any_of"], extracted_fields)

            if "all_of" in condition:
                return self._evaluate_all_of(condition["all_of"], extracted_fields)

            # Single condition
            return self._evaluate_single_condition(condition, extracted_fields)

        except KeyError as e:
            # Condition references non-existent field (valid - just means field not captured)
            self.logger.debug(f"Condition references field not in extracted_fields: {e}")
            return False

        except Exception as e:
            # Invalid condition syntax or evaluation error
            self.logger.error(f"Condition evaluation error: {e}", exc_info=True)
            capture_exception_with_context(
                e,
                extra={
                    "condition": str(condition),
                    "extracted_fields_count": len(extracted_fields),
                },
                tags={
                    "component": "workflow_condition_evaluator",
                    "operation": "evaluate",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            return False

    def _evaluate_any_of(self, conditions: List[Dict], extracted_fields: Dict) -> bool:
        """Evaluate OR logic - return True if ANY condition matches."""
        if not conditions:
            return False

        return any(self.evaluate(cond, extracted_fields) for cond in conditions)

    def _evaluate_all_of(self, conditions: List[Dict], extracted_fields: Dict) -> bool:
        """Evaluate AND logic - return True if ALL conditions match."""
        if not conditions:
            return False

        return all(self.evaluate(cond, extracted_fields) for cond in conditions)

    def _evaluate_single_condition(
        self, condition: Dict[str, Any], extracted_fields: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a single field condition.

        Args:
            condition: Must contain "field" and "operator"
            extracted_fields: Extracted field data

        Returns:
            True if condition matches
        """
        field_id = condition.get("field")
        operator = condition.get("operator")

        if not field_id or not operator:
            self.logger.warning(f"Invalid condition: missing 'field' or 'operator': {condition}")
            return False

        # Get field value from extracted_fields
        field_value = self._get_field_value(extracted_fields, field_id)

        # Evaluate based on operator
        return self._apply_operator(operator, field_value, condition)

    def _get_field_value(self, extracted_fields: Dict[str, Any], field_id: str) -> Any:
        """
        Extract field value from extracted_fields.

        Handles both formats:
        - ExtractedFieldValue dict: {"value": "...", "confidence": 0.9, ...}
        - Direct value: "..."
        """
        field_data = extracted_fields.get(field_id)

        if field_data is None:
            return None

        # Handle ExtractedFieldValue format (dict with "value" key)
        if isinstance(field_data, dict) and "value" in field_data:
            return field_data["value"]

        # Direct value
        return field_data

    def _apply_operator(self, operator: str, field_value: Any, condition: Dict[str, Any]) -> bool:
        """
        Apply operator to field value.

        Args:
            operator: Operator name (e.g., "exists", "contains", "greater_than")
            field_value: Extracted field value
            condition: Full condition dict (may contain "value", "values", etc.)

        Returns:
            True if operator condition is satisfied
        """
        # Existence operators
        if operator == "exists":
            return self._is_value_present(field_value)

        if operator == "not_exists":
            return not self._is_value_present(field_value)

        # If field doesn't exist for other operators, return False
        if not self._is_value_present(field_value):
            return False

        # String comparison operators
        if operator == "equals":
            return self._equals(field_value, condition.get("value"))

        if operator == "not_equals":
            return not self._equals(field_value, condition.get("value"))

        if operator == "contains":
            return self._contains(field_value, condition.get("value"))

        if operator == "not_contains":
            return not self._contains(field_value, condition.get("value"))

        if operator == "contains_any":
            return self._contains_any(field_value, condition.get("values", []))

        # Numeric comparison operators
        if operator == "greater_than":
            return self._greater_than(field_value, condition.get("value"))

        if operator == "less_than":
            return self._less_than(field_value, condition.get("value"))

        if operator == "greater_than_or_equal":
            return self._greater_than_or_equal(field_value, condition.get("value"))

        if operator == "less_than_or_equal":
            return self._less_than_or_equal(field_value, condition.get("value"))

        # List operators
        # Support both "in_list" (formal) and "in" (shorthand) with "values" or "value" key
        if operator in ("in_list", "in"):
            values = condition.get("values") or condition.get("value", [])
            return self._in_list(field_value, values if isinstance(values, list) else [values])

        if operator in ("not_in_list", "not_in"):
            values = condition.get("values") or condition.get("value", [])
            return not self._in_list(field_value, values if isinstance(values, list) else [values])

        # Pattern matching
        if operator == "regex_match":
            return self._regex_match(field_value, condition.get("pattern"))

        # Word count operators
        if operator == "word_count_gte":
            return self._word_count_gte(field_value, condition.get("value"))

        if operator == "word_count_lte":
            return self._word_count_lte(field_value, condition.get("value"))

        # Unknown operator
        self.logger.warning(f"Unknown operator '{operator}' in condition: {condition}")
        return False

    # ===== Helper Methods =====

    def _is_value_present(self, value: Any) -> bool:
        """Check if value is present (not None, empty string, or null-like)."""
        if value is None:
            return False
        if isinstance(value, str) and value.strip() in ["", "None", "null"]:
            return False
        return True

    def _equals(self, field_value: Any, target_value: Any) -> bool:
        """Case-insensitive string equality."""
        return str(field_value).lower() == str(target_value).lower()

    def _contains(self, field_value: Any, substring: Any) -> bool:
        """Case-insensitive substring check."""
        if substring is None:
            return False
        return str(substring).lower() in str(field_value).lower()

    def _contains_any(self, field_value: Any, substrings: List[Any]) -> bool:
        """Check if field_value contains any of the substrings (case-insensitive)."""
        if not substrings:
            return False

        field_str = str(field_value).lower()
        return any(str(s).lower() in field_str for s in substrings)

    def _greater_than(self, field_value: Any, target_value: Any) -> bool:
        """Numeric greater than comparison."""
        try:
            return float(field_value) > float(target_value)
        except (ValueError, TypeError):
            return False

    def _less_than(self, field_value: Any, target_value: Any) -> bool:
        """Numeric less than comparison."""
        try:
            return float(field_value) < float(target_value)
        except (ValueError, TypeError):
            return False

    def _greater_than_or_equal(self, field_value: Any, target_value: Any) -> bool:
        """Numeric greater than or equal comparison."""
        try:
            return float(field_value) >= float(target_value)
        except (ValueError, TypeError):
            return False

    def _less_than_or_equal(self, field_value: Any, target_value: Any) -> bool:
        """Numeric less than or equal comparison."""
        try:
            return float(field_value) <= float(target_value)
        except (ValueError, TypeError):
            return False

    def _in_list(self, field_value: Any, allowed_values: List[Any]) -> bool:
        """Check if field_value is in allowed_values list (case-insensitive)."""
        if not allowed_values:
            return False

        field_str = str(field_value).lower()
        return field_str in [str(v).lower() for v in allowed_values]

    def _regex_match(self, field_value: Any, pattern: Optional[str]) -> bool:
        """Check if field_value matches regex pattern."""
        if not pattern:
            return False

        try:
            return bool(re.search(pattern, str(field_value), re.IGNORECASE))
        except re.error as e:
            self.logger.warning(f"Invalid regex pattern '{pattern}': {e}")
            return False

    def _word_count_gte(self, field_value: Any, min_words: Any) -> bool:
        """Check if word count >= min_words."""
        try:
            word_count = len(str(field_value).split())
            return word_count >= int(min_words)
        except (ValueError, TypeError):
            return False

    def _word_count_lte(self, field_value: Any, max_words: Any) -> bool:
        """Check if word count <= max_words."""
        try:
            word_count = len(str(field_value).split())
            return word_count <= int(max_words)
        except (ValueError, TypeError):
            return False
