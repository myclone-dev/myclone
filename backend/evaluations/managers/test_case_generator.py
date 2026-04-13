import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from evaluations.managers.ground_truth_extractor import Fact

logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """Represents a single test case for persona evaluation"""

    id: str
    category: str  # current_role, skills, experience, recent_activity, social_presence
    question: str
    variants: List[str]  # Alternative question phrasings
    expected_facts: List[Dict[str, Any]]  # Ground truth facts (serialized)
    must_include: List[str]  # Required keywords/concepts in response
    must_exclude: List[str]  # False information that should not appear
    difficulty: str = "medium"  # easy, medium, hard
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class TestCaseGenerator:
    """Generates test cases from user data and ground truth facts"""

    def __init__(self):
        pass

    def generate_test_cases(
        self, username: str, user_data: Dict[str, Any], facts: List[Fact]
    ) -> List[TestCase]:
        """
        Generate comprehensive test cases for a persona

        Args:
            username: Persona username
            user_data: Raw user data from API
            facts: Extracted ground truth facts

        Returns:
            List of TestCase objects
        """
        test_cases = []

        # Category 1: Current Role/Position
        test_cases.extend(self._generate_current_role_tests(username, facts, user_data))

        # Category 2: Skills and Expertise
        test_cases.extend(self._generate_skills_tests(username, facts, user_data))

        # Category 3: Professional Background
        test_cases.extend(self._generate_background_tests(username, facts, user_data))

        # Category 4: Recent Activity/Focus
        test_cases.extend(self._generate_recent_activity_tests(username, facts, user_data))

        # Category 5: Social Presence
        test_cases.extend(self._generate_social_presence_tests(username, facts, user_data))

        logger.info(f"Generated {len(test_cases)} test cases for {username}")
        return test_cases

    def _generate_current_role_tests(
        self, username: str, facts: List[Fact], user_data: Dict
    ) -> List[TestCase]:
        """Generate test cases about current employment"""
        test_cases = []

        # Find current role facts
        current_role_facts = [f for f in facts if f.type == "current_role"]
        current_title_facts = [f for f in facts if f.type == "current_title"]
        # current_company_facts = [f for f in facts if f.type == "current_company"]

        if current_role_facts:
            current_fact = current_role_facts[0]
            title = current_fact.metadata.get("title", "")
            company = current_fact.metadata.get("company", "")

            # Test case 1: Current position
            test_cases.append(
                TestCase(
                    id=f"{username}_current_role_001",
                    category="current_role",
                    question="What is your current job?",
                    variants=[
                        "What's your current position?",
                        "Where do you currently work?",
                        "What is your current role?",
                    ],
                    expected_facts=[
                        {
                            "assertion": current_fact.assertion,
                            "confidence": current_fact.confidence,
                            "type": current_fact.type,
                        }
                    ],
                    must_include=[title, company] if title and company else [],
                    must_exclude=self._get_previous_companies(user_data.get("experiences", [])),
                    difficulty="easy",
                    metadata={"focus": "current_employment"},
                )
            )

            # Test case 2: Job title specifically
            if current_title_facts:
                test_cases.append(
                    TestCase(
                        id=f"{username}_current_title_001",
                        category="current_role",
                        question="What is your job title?",
                        variants=["What's your current title?", "What position do you hold?"],
                        expected_facts=[
                            {
                                "assertion": current_title_facts[0].assertion,
                                "confidence": current_title_facts[0].confidence,
                                "type": current_title_facts[0].type,
                            }
                        ],
                        must_include=[title] if title else [],
                        must_exclude=[],
                        difficulty="easy",
                    )
                )

        return test_cases

    def _generate_skills_tests(
        self, username: str, facts: List[Fact], user_data: Dict
    ) -> List[TestCase]:
        """Generate test cases about skills and expertise"""
        test_cases = []

        skill_facts = [f for f in facts if f.type == "skill"]
        # skill_summary_facts = [f for f in facts if f.type == "skill_summary"]

        if skill_facts:
            # Get top skills
            top_skills = [
                f.metadata.get("skill", "") for f in skill_facts[:5] if f.metadata.get("skill")
            ]

            # Test case 1: Main skills
            test_cases.append(
                TestCase(
                    id=f"{username}_skills_001",
                    category="skills",
                    question="What are your main technical skills?",
                    variants=[
                        "What technologies do you work with?",
                        "What are you skilled in?",
                        "What's your expertise?",
                    ],
                    expected_facts=[
                        {"assertion": f.assertion, "confidence": f.confidence, "type": f.type}
                        for f in skill_facts[:3]
                    ],  # Top 3 skills
                    must_include=top_skills[:3],
                    must_exclude=[],
                    difficulty="medium",
                )
            )

            # Test case 2: Specific skill inquiry
            if top_skills:
                main_skill = top_skills[0]
                test_cases.append(
                    TestCase(
                        id=f"{username}_skill_specific_001",
                        category="skills",
                        question=f"Do you have experience with {main_skill}?",
                        variants=[
                            f"Are you familiar with {main_skill}?",
                            f"Have you worked with {main_skill}?",
                        ],
                        expected_facts=[
                            {
                                "assertion": f"Has expertise in {main_skill}",
                                "confidence": 0.9,
                                "type": "skill",
                            }
                        ],
                        must_include=[main_skill],
                        must_exclude=[],
                        difficulty="easy",
                    )
                )

        return test_cases

    def _generate_background_tests(
        self, username: str, facts: List[Fact], user_data: Dict
    ) -> List[TestCase]:
        """Generate test cases about professional background"""
        test_cases = []

        experience_facts = [f for f in facts if f.type == "experience_length"]
        previous_exp_facts = [f for f in facts if f.type == "previous_experience"]

        # Test case 1: Experience length
        if experience_facts:
            exp_fact = experience_facts[0]
            years = exp_fact.metadata.get("years", 0)

            test_cases.append(
                TestCase(
                    id=f"{username}_experience_length_001",
                    category="background",
                    question="How long have you been working in tech?",
                    variants=[
                        "How much experience do you have?",
                        "How long have you been in your field?",
                    ],
                    expected_facts=[
                        {
                            "assertion": exp_fact.assertion,
                            "confidence": exp_fact.confidence,
                            "type": exp_fact.type,
                        }
                    ],
                    must_include=[str(years)] if years > 0 else [],
                    must_exclude=[],
                    difficulty="medium",
                )
            )

        # Test case 2: Previous companies
        if previous_exp_facts:
            prev_fact = previous_exp_facts[0]
            prev_companies = prev_fact.metadata.get("previous_companies", [])[:2]

            test_cases.append(
                TestCase(
                    id=f"{username}_previous_work_001",
                    category="background",
                    question="Where have you worked before?",
                    variants=["What's your work history?", "Tell me about your previous jobs"],
                    expected_facts=[
                        {
                            "assertion": prev_fact.assertion,
                            "confidence": prev_fact.confidence,
                            "type": prev_fact.type,
                        }
                    ],
                    must_include=prev_companies,
                    must_exclude=[],
                    difficulty="medium",
                )
            )

        return test_cases

    def _generate_recent_activity_tests(
        self, username: str, facts: List[Fact], user_data: Dict
    ) -> List[TestCase]:
        """Generate test cases about recent activity and interests"""
        test_cases = []

        activity_facts = [f for f in facts if f.type == "recent_activity"]

        if activity_facts:
            activity_fact = activity_facts[0]
            topics = activity_fact.metadata.get("topics", [])

            test_cases.append(
                TestCase(
                    id=f"{username}_recent_activity_001",
                    category="recent_activity",
                    question="What have you been working on recently?",
                    variants=[
                        "What's keeping you busy lately?",
                        "What are you focused on now?",
                        "Tell me about your recent projects",
                    ],
                    expected_facts=[
                        {
                            "assertion": activity_fact.assertion,
                            "confidence": activity_fact.confidence,
                            "type": activity_fact.type,
                        }
                    ],
                    must_include=topics[:2],  # Top 2 topics
                    must_exclude=[],
                    difficulty="hard",  # Recent activity can be more subjective
                )
            )

        return test_cases

    def _generate_social_presence_tests(
        self, username: str, facts: List[Fact], user_data: Dict
    ) -> List[TestCase]:
        """Generate test cases about online presence"""
        test_cases = []

        website_facts = [f for f in facts if f.type == "website_presence"]
        social_facts = [f for f in facts if f.type == "social_presence"]

        # Test case 1: Website presence
        if website_facts:
            website_fact = website_facts[0]
            url = website_fact.metadata.get("url", "")

            test_cases.append(
                TestCase(
                    id=f"{username}_website_001",
                    category="social_presence",
                    question="Do you have a personal website?",
                    variants=[
                        "Where can I find your portfolio online?",
                        "Do you have an online presence?",
                    ],
                    expected_facts=[
                        {
                            "assertion": website_fact.assertion,
                            "confidence": website_fact.confidence,
                            "type": website_fact.type,
                        }
                    ],
                    must_include=[url] if url else [],
                    must_exclude=[],
                    difficulty="easy",
                )
            )

        # Test case 2: Social media presence
        if social_facts:
            social_fact = social_facts[0]
            twitter_username = social_fact.metadata.get("username", "")

            test_cases.append(
                TestCase(
                    id=f"{username}_social_001",
                    category="social_presence",
                    question="Are you active on social media?",
                    variants=["Do you have a Twitter account?", "Where can I follow you online?"],
                    expected_facts=[
                        {
                            "assertion": social_fact.assertion,
                            "confidence": social_fact.confidence,
                            "type": social_fact.type,
                        }
                    ],
                    must_include=[twitter_username] if twitter_username else [],
                    must_exclude=[],
                    difficulty="easy",
                )
            )

        return test_cases

    def _get_previous_companies(self, experiences: List[Dict]) -> List[str]:
        """Get list of previous companies to exclude from current role questions"""
        if not experiences:
            return []

        previous_companies = []

        for exp in experiences:
            if not exp.get("is_current", False):
                company = exp.get("company", "").strip()
                if company:
                    previous_companies.append(company)

        return previous_companies[:3]  # Limit to avoid too many exclusions
