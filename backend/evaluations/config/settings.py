import os
from pathlib import Path

from pydantic_settings import BaseSettings


class EvaluationSettings(BaseSettings):
    # API Configuration
    myclone_api_key: str = os.getenv("MYCLONE_API_KEY", "")
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8001/api/v1")

    # Evaluation thresholds
    faithfulness_threshold: float = 0.8
    relevancy_threshold: float = 0.8
    factual_accuracy_threshold: float = 0.9

    # Test generation settings
    test_cases_per_category: int = 3
    question_variants_per_case: int = 2

    # LLM settings for evaluation
    eval_model: str = "gpt-4o-mini"
    eval_temperature: float = 0.1  # Low temp for consistent evaluation

    # File paths
    base_dir: Path = Path("evaluations")
    test_cases_dir: Path = Path("evaluations/test-cases")
    results_dir: Path = Path("evaluations/results")
    reports_dir: Path = Path("evaluations/reports")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from environment

    def validate_settings(self):
        """Validate required settings"""
        if not self.myclone_api_key:
            raise ValueError("MYCLONE_API_KEY is required for API access")

        # Ensure directories exist
        self.test_cases_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
evaluation_settings = EvaluationSettings()
