import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List

from evaluations.config.settings import evaluation_settings

logger = logging.getLogger(__name__)


@dataclass
class FactCheck:
    """Result of checking a single fact"""

    fact_assertion: str
    present: bool
    confidence: float
    matched_text: str = ""
    reasoning: str = ""


@dataclass
class FactualResult:
    """Result of factual accuracy evaluation"""

    accuracy: float
    fact_checks: List[FactCheck]
    missing_facts: List[str]
    false_information: List[str]
    required_info_missing: List[str]
    factual_passing: bool


class FactualAccuracyEvaluator:
    """Evaluates factual accuracy of responses against ground truth"""

    def __init__(self):
        self.accuracy_threshold = evaluation_settings.factual_accuracy_threshold
        logger.info(f"Factual evaluator initialized with threshold: {self.accuracy_threshold}")

    def evaluate_facts(
        self,
        response: str,
        expected_facts: List[Dict[str, Any]],
        must_include: List[str] = None,
        must_exclude: List[str] = None,
    ) -> FactualResult:
        """
        Evaluate factual accuracy of a response

        Args:
            response: The generated response to evaluate
            expected_facts: List of ground truth facts that should be present
            must_include: Required keywords/concepts that must appear
            must_exclude: False information that should not appear

        Returns:
            FactualResult with accuracy score and detailed breakdown
        """
        must_include = must_include or []
        must_exclude = must_exclude or []

        logger.debug(
            f"Evaluating factual accuracy: {len(expected_facts)} facts, "
            f"{len(must_include)} required items, {len(must_exclude)} excluded items"
        )

        # Check each expected fact
        fact_checks = []
        for fact in expected_facts:
            fact_assertion = fact.get("assertion", "")
            if not fact_assertion:
                continue

            fact_check = self._check_fact_presence(response, fact_assertion)
            fact_checks.append(fact_check)

        # Calculate accuracy
        present_facts = sum(1 for fc in fact_checks if fc.present)
        accuracy = present_facts / len(fact_checks) if fact_checks else 0.0

        # Check for missing required information
        required_info_missing = self._check_required_info(response, must_include)

        # Check for false information
        false_information = self._check_false_information(response, must_exclude)

        # Collect missing facts
        missing_facts = [fc.fact_assertion for fc in fact_checks if not fc.present]

        # Determine if factual evaluation passes
        factual_passing = (
            accuracy >= self.accuracy_threshold
            and len(required_info_missing) == 0
            and len(false_information) == 0
        )

        result = FactualResult(
            accuracy=accuracy,
            fact_checks=fact_checks,
            missing_facts=missing_facts,
            false_information=false_information,
            required_info_missing=required_info_missing,
            factual_passing=factual_passing,
        )

        logger.debug(
            f"Factual evaluation completed: accuracy={accuracy:.2f}, "
            f"missing={len(missing_facts)}, false_info={len(false_information)}, "
            f"passing={factual_passing}"
        )

        return result

    def _check_fact_presence(self, response: str, fact_assertion: str) -> FactCheck:
        """Check if a specific fact is present in the response"""

        response_lower = response.lower()
        fact_lower = fact_assertion.lower()

        # Method 1: Direct substring match
        if fact_lower in response_lower:
            return FactCheck(
                fact_assertion=fact_assertion,
                present=True,
                confidence=0.95,
                matched_text=fact_assertion,
                reasoning="Direct substring match",
            )

        # Method 2: Key entity extraction and matching
        key_entities = self._extract_key_entities(fact_assertion)
        matched_entities = []

        for entity in key_entities:
            if entity.lower() in response_lower:
                matched_entities.append(entity)

        # If most key entities are present, consider fact present
        if key_entities and len(matched_entities) / len(key_entities) >= 0.7:
            return FactCheck(
                fact_assertion=fact_assertion,
                present=True,
                confidence=0.8,
                matched_text=", ".join(matched_entities),
                reasoning=f"Key entities matched: {matched_entities}",
            )

        # Method 3: Fuzzy semantic matching
        semantic_score = self._calculate_semantic_similarity(response, fact_assertion)
        if semantic_score >= 0.7:
            return FactCheck(
                fact_assertion=fact_assertion,
                present=True,
                confidence=semantic_score,
                matched_text="semantic match",
                reasoning=f"Semantic similarity: {semantic_score:.2f}",
            )

        # Fact not found
        return FactCheck(
            fact_assertion=fact_assertion,
            present=False,
            confidence=0.0,
            matched_text="",
            reasoning="No significant matches found",
        )

    def _extract_key_entities(self, fact_assertion: str) -> List[str]:
        """Extract key entities from a fact assertion"""
        # Remove common words and extract meaningful entities
        stop_words = {
            "is",
            "are",
            "was",
            "were",
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "currently",
            "works",
            "has",
            "have",
            "expertise",
            "skilled",
            "experience",
        }

        # Split and clean
        words = re.findall(r"\b[A-Za-z][A-Za-z0-9+#]*\b", fact_assertion)
        entities = [word for word in words if word.lower() not in stop_words and len(word) > 2]

        return entities

    def _calculate_semantic_similarity(self, response: str, fact: str) -> float:
        """Calculate semantic similarity between response and fact"""
        # Simple approach using sequence matching
        # In a production system, you might use sentence embeddings here

        response_words = set(re.findall(r"\b\w+\b", response.lower()))
        fact_words = set(re.findall(r"\b\w+\b", fact.lower()))

        if not fact_words:
            return 0.0

        # Jaccard similarity
        intersection = response_words.intersection(fact_words)
        union = response_words.union(fact_words)

        jaccard_similarity = len(intersection) / len(union) if union else 0.0

        # Boost score if key entities are present
        key_entities = self._extract_key_entities(fact)
        key_entities_lower = {entity.lower() for entity in key_entities}

        matched_key_entities = response_words.intersection(key_entities_lower)
        key_entity_score = (
            len(matched_key_entities) / len(key_entities_lower) if key_entities_lower else 0.0
        )

        # Weighted combination
        combined_score = (jaccard_similarity * 0.4) + (key_entity_score * 0.6)

        return min(combined_score, 1.0)

    def _check_required_info(self, response: str, must_include: List[str]) -> List[str]:
        """Check for presence of required information"""
        missing_required = []
        response_lower = response.lower()

        for required_item in must_include:
            if not required_item:  # Skip empty items
                continue

            if required_item.lower() not in response_lower:
                # Check for partial matches or variations
                if not self._check_partial_match(response_lower, required_item.lower()):
                    missing_required.append(required_item)

        return missing_required

    def _check_false_information(self, response: str, must_exclude: List[str]) -> List[str]:
        """Check for presence of false information that should be excluded"""
        false_info_found = []
        response_lower = response.lower()

        for exclude_item in must_exclude:
            if not exclude_item:  # Skip empty items
                continue

            if exclude_item.lower() in response_lower:
                false_info_found.append(exclude_item)

        return false_info_found

    def _check_partial_match(self, response: str, required_item: str) -> bool:
        """Check for partial matches of required items"""
        # Check for partial word matches
        required_words = required_item.split()
        if len(required_words) > 1:
            # If multi-word, check if most words are present
            matched_words = sum(1 for word in required_words if word in response)
            return matched_words / len(required_words) >= 0.7

        # For single words, check for substring matches
        return any(required_item in word for word in response.split())

    def get_detailed_report(self, result: FactualResult) -> str:
        """Generate a detailed text report of factual evaluation"""
        report = []

        report.append("Factual Accuracy Evaluation Report")
        report.append("==================================")
        report.append(f"Overall Accuracy: {result.accuracy:.2%}")
        report.append(f"Status: {'PASS' if result.factual_passing else 'FAIL'}")
        report.append("")

        # Fact checks
        if result.fact_checks:
            report.append("Fact Verification:")
            for i, fact_check in enumerate(result.fact_checks, 1):
                status = "✓" if fact_check.present else "✗"
                report.append(f"  {i}. {status} {fact_check.fact_assertion}")
                if fact_check.present:
                    report.append(f"     Match: {fact_check.matched_text}")
                    report.append(f"     Confidence: {fact_check.confidence:.2f}")
                report.append(f"     Reasoning: {fact_check.reasoning}")
            report.append("")

        # Missing facts
        if result.missing_facts:
            report.append("Missing Facts:")
            for fact in result.missing_facts:
                report.append(f"  - {fact}")
            report.append("")

        # Required info missing
        if result.required_info_missing:
            report.append("Missing Required Information:")
            for item in result.required_info_missing:
                report.append(f"  - {item}")
            report.append("")

        # False information
        if result.false_information:
            report.append("False Information Found:")
            for item in result.false_information:
                report.append(f"  - {item}")
            report.append("")

        return "\n".join(report)
