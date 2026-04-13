import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from evaluations.config.settings import evaluation_settings
from evaluations.managers.data_fetcher import ExpertDataFetcher
from evaluations.managers.ground_truth_extractor import Fact, GroundTruthExtractor
from evaluations.managers.test_case_generator import TestCase, TestCaseGenerator

logger = logging.getLogger(__name__)


class TestCaseManager:
    """Manages test case creation, storage, and updates for personas"""

    def __init__(self):
        evaluation_settings.validate_settings()
        self.base_path = evaluation_settings.test_cases_dir
        self.fetcher = ExpertDataFetcher()
        self.extractor = GroundTruthExtractor()
        self.generator = TestCaseGenerator()

    async def ensure_persona_tests(
        self, username: str, force_regenerate: bool = False
    ) -> Dict[str, Any]:
        """
        Main entry point - ensure test cases exist for a persona

        Args:
            username: Persona username for folder structure and API
            force_regenerate: Force regeneration even if tests exist

        Returns:
            Dict containing test cases, facts, and metadata
        """
        persona_folder = self.base_path / username

        if force_regenerate or not persona_folder.exists():
            logger.info(f"Creating new test cases for {username}")
            return await self.create_new_tests(username)

        # Check if existing tests need updating
        if self._should_regenerate_tests(username):
            logger.info(f"Regenerating stale test cases for {username}")
            return await self.regenerate_tests(username)

        # Load existing tests
        logger.info(f"Loading existing test cases for {username}")
        return self._load_existing_tests(username)

    async def create_new_tests(self, username: str) -> Dict[str, Any]:
        """Create folder structure and generate initial tests"""

        # 1. Create persona folder
        persona_folder = self.base_path / username
        persona_folder.mkdir(parents=True, exist_ok=True)

        # 2. Fetch external data using username
        logger.info(f"Fetching data for username {username}")
        user_data = await self.fetcher.fetch_user_data_by_username(username)

        # 3. Validate data
        if not self.fetcher.validate_user_data(user_data):
            raise ValueError(f"Insufficient data for test generation for user {username}")

        # 4. Extract ground truth facts
        logger.info("Extracting ground truth facts")
        facts = self.extractor.extract_facts(user_data)

        logger.info(f"Extracted facts: {facts} (type: {type(facts)})")

        if facts is None:
            raise ValueError(f"Ground truth extractor returned None for user {username}")

        if not facts:
            raise ValueError(f"No ground truth facts could be extracted for user {username}")

        # 5. Generate test cases
        logger.info("Generating test cases")
        test_cases = self.generator.generate_test_cases(username, user_data, facts)

        if not test_cases:
            raise ValueError(f"No test cases could be generated for user {username}")

        # 6. Save everything to files
        self._save_test_structure(username, user_data, facts, test_cases)

        return {
            "status": "created",
            "username": username,
            "test_cases": [tc.to_dict() for tc in test_cases],
            "facts": [self._fact_to_dict(f) for f in facts],
            "data_summary": self.fetcher.get_data_summary(user_data),
        }

    async def regenerate_tests(self, username: str) -> Dict[str, Any]:
        """Regenerate test cases with fresh data"""
        logger.info(f"Regenerating test cases for {username}")

        # Remove existing data and create fresh
        persona_folder = self.base_path / username
        if persona_folder.exists():
            import shutil

            shutil.rmtree(persona_folder)
            logger.info(f"Removed existing test folder for {username}")

        return await self.create_new_tests(username)

    def _should_regenerate_tests(self, username: str) -> bool:
        """Check if test cases need regeneration based on data staleness"""
        metadata_path = self.base_path / username / "metadata.json"

        if not metadata_path.exists():
            return True

        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            # Check time-based staleness (7 days)
            last_updated = datetime.fromisoformat(metadata.get("last_updated", ""))
            if (datetime.now() - last_updated).days > 7:
                logger.info(f"Test cases for {username} are stale (older than 7 days)")
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking staleness for {username}: {e}")
            return True

    def _load_existing_tests(self, username: str) -> Dict[str, Any]:
        """Load existing test cases from files"""
        persona_folder = self.base_path / username

        try:
            # Load metadata
            with open(persona_folder / "metadata.json", "r") as f:
                metadata = json.load(f)

            # Load test cases
            with open(persona_folder / "test_cases.json", "r") as f:
                test_cases = json.load(f)

            # Load facts
            with open(persona_folder / "ground_truth.json", "r") as f:
                facts = json.load(f)

            return {
                "status": "loaded",
                "username": username,
                "test_cases": test_cases,
                "facts": facts,
                "metadata": metadata,
            }

        except Exception as e:
            logger.error(f"Error loading existing tests for {username}: {e}")
            raise ValueError(f"Could not load existing tests for {username}")

    def _save_test_structure(
        self, username: str, user_data: Dict, facts: List[Fact], test_cases: List[TestCase]
    ):
        """Save all test data to structured files"""
        persona_folder = self.base_path / username
        timestamp = datetime.now()

        # Create metadata
        metadata = {
            "username": username,
            "created_at": timestamp.isoformat(),
            "last_updated": timestamp.isoformat(),
            "data_hash": self._compute_data_hash(user_data),
            "version": 1,
            "test_case_count": len(test_cases),
            "fact_count": len(facts),
            "data_summary": self.fetcher.get_data_summary(user_data),
        }

        # Save metadata
        with open(persona_folder / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2, default=str)

        # Save raw data (for debugging/analysis)
        with open(persona_folder / "raw_data.json", "w") as f:
            json.dump(user_data, f, indent=2, default=str)

        # Save ground truth facts
        facts_data = [self._fact_to_dict(fact) for fact in facts]
        with open(persona_folder / "ground_truth.json", "w") as f:
            json.dump(facts_data, f, indent=2, default=str)

        # Save test cases
        test_cases_data = [tc.to_dict() for tc in test_cases]
        with open(persona_folder / "test_cases.json", "w") as f:
            json.dump(test_cases_data, f, indent=2, default=str)

        logger.info(
            f"Saved test structure for {username}: {len(test_cases)} test cases, {len(facts)} facts"
        )

    def _compute_data_hash(self, user_data: Dict) -> str:
        """Compute hash of relevant data fields to detect changes"""
        relevant_data = {
            "experiences": user_data.get("experiences", []),
            "skills": user_data.get("skills", {}),
            "recent_posts": (
                user_data.get("linkedin_posts", [])[:5]
                + user_data.get("tweets", [])[:5]  # Last 5 posts
            ),
            "website_data": user_data.get("website_data", []),
        }

        # Create a stable hash
        data_str = json.dumps(relevant_data, sort_keys=True, default=str)
        return hashlib.md5(data_str.encode()).hexdigest()

    def _fact_to_dict(self, fact: Fact) -> Dict[str, Any]:
        """Convert Fact object to dictionary"""
        return {
            "type": fact.type,
            "assertion": fact.assertion,
            "confidence": fact.confidence,
            "source": fact.source,
            "metadata": fact.metadata,
        }

    def get_test_cases(self, username: str) -> Optional[List[Dict[str, Any]]]:
        """Get test cases for a persona if they exist"""
        test_cases_path = self.base_path / username / "test_cases.json"

        if not test_cases_path.exists():
            return None

        try:
            with open(test_cases_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading test cases for {username}: {e}")
            return None

    def get_persona_metadata(self, username: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a persona if it exists"""
        metadata_path = self.base_path / username / "metadata.json"

        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading metadata for {username}: {e}")
            return None

    def list_personas(self) -> List[str]:
        """List all personas with test cases"""
        personas = []

        if not self.base_path.exists():
            return personas

        for folder in self.base_path.iterdir():
            if folder.is_dir() and not folder.name.startswith("."):
                if (folder / "metadata.json").exists():
                    personas.append(folder.name)

        return sorted(personas)
