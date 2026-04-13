# Standard library imports for API and file operations
import json
import logging
from pathlib import Path
from typing import List, Optional

# FastAPI components for REST API implementation
from fastapi import APIRouter, HTTPException, Query

from evaluations.evaluators.composite_evaluator import CompositeEvaluator

# Internal evaluation system components
from evaluations.managers.test_manager import TestCaseManager

# Database models and session management
from shared.database.models.database import get_session
from shared.database.repositories.persona_repository import PersonaRepository

# Core RAG system for generating AI responses
from shared.rag.llama_rag import LlamaRAGSystem

# Configure logger for evaluation API routes
logger = logging.getLogger(__name__)

# Create FastAPI router for evaluation endpoints
# All evaluation routes will be prefixed with /api/v1/evaluation
router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])


@router.post("/run/{username}")
async def run_persona_evaluation(
    username: str,
    persona_name: str = Query("default", description="Persona name (defaults to 'default')"),
    force_regenerate: bool = Query(
        False, description="Force regeneration of test cases from MyClone API"
    ),
    categories: Optional[List[str]] = Query(
        None,
        description="Specific categories to test. Available categories: "
        + "'current_role' (current job and company), "
        + "'skills' (technical and professional skills), "
        + "'background' (work history and experience length), "
        + "'recent_activity' (recent posts and focus areas), "
        + "'social_presence' (websites and social media profiles). "
        + "If not specified, all categories will be evaluated.",
    ),
):
    """
    Execute comprehensive persona evaluation using ground truth data.

    This is the main evaluation endpoint that orchestrates the entire
    evaluation process from test case generation through final scoring.

    Process Flow:
    1. Look up persona in database to get external user mapping
    2. Generate or load test cases from MyClone API data
    3. Filter test cases by categories if specified
    4. Run each test case through RAG system to get AI responses
    5. Evaluate responses using composite evaluator (LlamaIndex + Factual)
    6. Save detailed results to filesystem
    7. Return comprehensive evaluation summary

    Args:
        username (str): Persona username to evaluate (must exist in database)
        force_regenerate (bool): Whether to force fresh test case generation
                               from MyClone API even if cached cases exist
        categories (Optional[List[str]]): Filter to specific test categories:
                                        - current_role: Current job title, company, and position
                                        - skills: Technical skills, expertise, and proficiencies
                                        - background: Work history, experience length, and previous companies
                                        - recent_activity: Recent posts, projects, and current focus areas
                                        - social_presence: Personal websites, social media profiles, online presence
                                        If None, all categories are evaluated

    Returns:
        Dict: Comprehensive evaluation results containing:
            - Overall score and pass/fail status
            - Breakdown by individual metrics (faithfulness, relevancy, factual)
            - Category-specific performance analysis
            - Detailed test case results with feedback
            - Performance timing and metadata
            - Common failure patterns and improvement suggestions

    Raises:
        HTTPException 404: If persona username not found in database
        HTTPException 400: If test case generation fails due to insufficient data
        HTTPException 500: If evaluation process encounters critical errors
    """

    # Log evaluation start for monitoring and debugging
    logger.info(f"Starting comprehensive evaluation for persona: {username}")
    logger.info(f"Force regenerate: {force_regenerate}, Categories: {categories}")

    try:
        # Initialize all evaluation system components
        # These handle test case management, evaluation orchestration, and RAG responses
        test_manager = TestCaseManager()
        evaluator = CompositeEvaluator()
        rag_system = LlamaRAGSystem()

        # Step 1: Look up persona in database to get external user mapping
        # This links internal persona username to external MyClone user data
        logger.info(
            f"Looking up persona {username} (persona: {persona_name}) in database for external user mapping"
        )
        persona = None
        async for session in get_session():
            persona = await PersonaRepository.get_by_username_and_persona(
                session, username, persona_name
            )
            break

        if not persona:
            raise HTTPException(
                404, f"Persona {username} (persona: {persona_name}) not found in database"
            )

        # Step 2: Ensure test cases exist (will fetch from MyClone API if needed)
        logger.info(f"Ensuring test cases exist for {username}")
        test_data = await test_manager.ensure_persona_tests(
            username=username, force_regenerate=force_regenerate
        )

        test_cases = test_data["test_cases"]

        # Filter by categories if specified
        if categories:
            test_cases = [tc for tc in test_cases if tc.get("category") in categories]
            logger.info(f"Filtered to {len(test_cases)} test cases in categories: {categories}")

        if not test_cases:
            raise HTTPException(400, "No test cases available for evaluation")

        # Step 3: Get persona from database (we already got it above)
        # persona is already retrieved

        # Step 3: Run evaluation for each test case
        logger.info(f"Running evaluation on {len(test_cases)} test cases")
        evaluation_results = []

        for i, test_case in enumerate(test_cases, 1):
            logger.info(
                f"Evaluating test case {i}/{len(test_cases)}: {test_case.get('id', 'unknown')}"
            )

            try:
                # Get RAG response
                question = test_case.get("question", "")
                context = await rag_system.retrieve_context(
                    persona_id=persona.id,
                    query=question,
                    top_k=5,
                    include_patterns=True,
                )

                response = await rag_system.generate_response(
                    persona_id=persona.id, query=question, context=context
                )

                # Extract context strings for evaluation
                contexts = [
                    chunk.get("content", "")
                    for chunk in context.get("chunks", [])
                    if chunk.get("content", "").strip()  # Only include non-empty content
                ]

                logger.info(f"Contexts extracted: {len(contexts)} non-empty chunks")
                logger.info(
                    f"First context preview: {contexts[0][:100] if contexts else 'NO CONTEXTS'}"
                )
                logger.info(f"Response preview: {response[:100] if response else 'NO RESPONSE'}")

                # Evaluate response
                result = await evaluator.evaluate_test_case(
                    test_case=test_case, response=response, contexts=contexts
                )

                evaluation_results.append(result)
                logger.debug(
                    f"Test case {test_case.get('id')} completed: "
                    f"score={result.overall_score:.2f}, passed={result.passed}"
                )

            except Exception as e:
                logger.error(f"Error evaluating test case {test_case.get('id', 'unknown')}: {e}")
                # Continue with other test cases
                continue

        if not evaluation_results:
            raise HTTPException(500, "No test cases could be evaluated successfully")

        # Step 4: Generate summary
        logger.info("Generating evaluation summary")
        summary = evaluator.create_evaluation_summary(evaluation_results, username)

        # Step 5: Save results to files
        await _save_evaluation_results(username, evaluation_results, summary)

        logger.info(
            f"Evaluation completed for {username}: "
            f"{summary.tests_passed}/{summary.total_tests} passed, "
            f"overall score: {summary.overall_score:.2f}"
        )

        return {
            "persona_username": username,
            "status": "completed",
            "summary": summary.to_dict(),
            "detailed_results": [result.to_dict() for result in evaluation_results],
            "test_cases_evaluated": len(evaluation_results),
            "categories_tested": list(set(r.category for r in evaluation_results)),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Evaluation failed for {username}: {e}")
        raise HTTPException(500, f"Evaluation failed: {str(e)}")


@router.post("/generate-tests/{username}")
async def generate_test_cases(
    username: str,
    persona_name: str = Query("default", description="Persona name (defaults to 'default')"),
):
    """
    Generate test cases for a persona from external data (without running evaluation)

    Args:
        username: Persona username (external user_id will be looked up automatically)

    Returns:
        Information about generated test cases
    """

    logger.info(f"Generating test cases for persona: {username}")

    try:
        # Get persona from database (to verify it exists)
        persona = None
        async for session in get_session():
            persona = await PersonaRepository.get_by_username_and_persona(
                session, username, persona_name
            )
            break

        if not persona:
            raise HTTPException(
                404, f"Persona {username} (persona: {persona_name}) not found in database"
            )

        test_manager = TestCaseManager()

        # Force regeneration of test cases (will fetch from MyClone API)
        test_data = await test_manager.regenerate_tests(username)

        test_cases = test_data["test_cases"]
        categories = list(set(tc.get("category", "unknown") for tc in test_cases))

        logger.info(f"Generated {len(test_cases)} test cases for {username}")

        return {
            "persona_username": username,
            "status": "generated",
            "test_cases_count": len(test_cases),
            "categories": categories,
            "facts_extracted": len(test_data.get("facts", [])),
            "data_summary": test_data.get("data_summary", {}),
        }

    except Exception as e:
        logger.error(f"Test generation failed for {username}: {e}")
        raise HTTPException(500, f"Test generation failed: {str(e)}")


@router.get("/test-cases/{username}")
async def get_test_cases(username: str):
    """View current test cases for a persona"""

    try:
        test_manager = TestCaseManager()
        test_cases = test_manager.get_test_cases(username)

        if test_cases is None:
            raise HTTPException(404, f"No test cases found for persona: {username}")

        # Get metadata
        metadata = test_manager.get_persona_metadata(username)

        return {
            "persona_username": username,
            "test_cases": test_cases,
            "metadata": metadata,
            "categories": list(set(tc.get("category", "unknown") for tc in test_cases)),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving test cases for {username}: {e}")
        raise HTTPException(500, f"Could not retrieve test cases: {str(e)}")


@router.get("/results/{username}")
async def get_evaluation_results(
    username: str,
    limit: int = Query(10, ge=1, le=50, description="Number of recent results to return"),
):
    """Get recent evaluation results for a persona"""

    try:
        results_dir = Path("evaluations/results") / username

        if not results_dir.exists():
            raise HTTPException(404, f"No evaluation results found for persona: {username}")

        # Get result files sorted by modification time (newest first)
        result_files = []
        for file_path in results_dir.glob("*.json"):
            if file_path.stem.startswith("evaluation_"):
                result_files.append(file_path)

        result_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # Load recent results
        recent_results = []
        for file_path in result_files[:limit]:
            try:
                with open(file_path, "r") as f:
                    result_data = json.load(f)
                    recent_results.append(result_data)
            except Exception as e:
                logger.error(f"Error loading result file {file_path}: {e}")
                continue

        return {
            "persona_username": username,
            "results_count": len(recent_results),
            "results": recent_results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving results for {username}: {e}")
        raise HTTPException(500, f"Could not retrieve results: {str(e)}")


@router.get("/dashboard")
async def evaluation_dashboard():
    """Get overall evaluation dashboard with all personas"""

    try:
        test_manager = TestCaseManager()
        personas = test_manager.list_personas()

        dashboard_data = []

        for persona_username in personas:
            # Get latest result
            results_dir = Path("evaluations/results") / persona_username
            latest_result = None

            if results_dir.exists():
                result_files = list(results_dir.glob("evaluation_*.json"))
                if result_files:
                    # Get most recent file
                    latest_file = max(result_files, key=lambda x: x.stat().st_mtime)
                    try:
                        with open(latest_file, "r") as f:
                            latest_result = json.load(f)
                    except Exception as e:
                        logger.error(f"Error loading latest result for {persona_username}: {e}")

            # Get metadata
            metadata = test_manager.get_persona_metadata(persona_username)

            persona_info = {
                "persona_username": persona_username,
                "has_test_cases": metadata is not None,
                "test_cases_count": metadata.get("test_case_count", 0) if metadata else 0,
                "last_updated": metadata.get("last_updated") if metadata else None,
            }

            if latest_result:
                summary = latest_result.get("summary", {})
                persona_info.update(
                    {
                        "last_evaluated": summary.get("timestamp"),
                        "overall_score": summary.get("overall_score", 0.0),
                        "pass_rate": summary.get("pass_rate", 0.0),
                        "status": "passing" if summary.get("pass_rate", 0.0) >= 0.8 else "failing",
                    }
                )
            else:
                persona_info.update(
                    {
                        "last_evaluated": None,
                        "overall_score": None,
                        "pass_rate": None,
                        "status": "not_evaluated",
                    }
                )

            dashboard_data.append(persona_info)

        # Summary stats
        total_personas = len(dashboard_data)
        passing_personas = sum(1 for p in dashboard_data if p["status"] == "passing")
        failing_personas = sum(1 for p in dashboard_data if p["status"] == "failing")
        not_evaluated = sum(1 for p in dashboard_data if p["status"] == "not_evaluated")

        return {
            "summary": {
                "total_personas": total_personas,
                "passing": passing_personas,
                "failing": failing_personas,
                "not_evaluated": not_evaluated,
            },
            "personas": sorted(dashboard_data, key=lambda x: x["persona_username"]),
        }

    except Exception as e:
        logger.error(f"Error generating dashboard: {e}")
        raise HTTPException(500, f"Could not generate dashboard: {str(e)}")


@router.delete("/clear/{username}")
async def clear_evaluation_data(username: str):
    """Clear all evaluation data (test cases and results) for a persona"""

    try:
        import shutil

        # Clear test cases
        test_cases_dir = Path("evaluations/test-cases") / username
        results_dir = Path("evaluations/results") / username

        removed_items = []

        # Remove test cases folder completely
        if test_cases_dir.exists():
            shutil.rmtree(test_cases_dir)
            removed_items.append("test_cases")
            logger.info(f"Removed test cases directory for {username}")

        # Remove results folder completely
        if results_dir.exists():
            shutil.rmtree(results_dir)
            removed_items.append("results")
            logger.info(f"Removed results directory for {username}")

        if not removed_items:
            raise HTTPException(404, f"No evaluation data found for persona: {username}")

        logger.info(f"Cleared evaluation data for {username}: {', '.join(removed_items)}")

        return {
            "persona_username": username,
            "status": "cleared",
            "items_removed": removed_items,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing evaluation data for {username}: {e}")
        raise HTTPException(500, f"Could not clear evaluation data: {str(e)}")


async def _save_evaluation_results(username: str, results: List, summary):
    """Save evaluation results to files"""

    try:
        # Create results directory
        results_dir = Path("evaluations/results") / username
        results_dir.mkdir(parents=True, exist_ok=True)

        # Create filename with timestamp
        timestamp = summary.timestamp.replace(":", "-").replace(".", "-")
        filename = f"evaluation_{timestamp}.json"

        # Prepare data to save
        evaluation_data = {
            "summary": summary.to_dict(),
            "detailed_results": [result.to_dict() for result in results],
            "metadata": {
                "evaluation_version": "1.0",
                "total_test_cases": len(results),
                "categories": list(set(r.category for r in results)),
            },
        }

        # Save to file
        file_path = results_dir / filename
        with open(file_path, "w") as f:
            json.dump(evaluation_data, f, indent=2, default=str)

        logger.info(f"Saved evaluation results to {file_path}")

    except Exception as e:
        logger.error(f"Error saving evaluation results for {username}: {e}")
        # Don't fail the whole evaluation if saving fails
