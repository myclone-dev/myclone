# External dependencies for HTTP requests and async operations
import asyncio
import json
import logging
from typing import Any, Dict

import aiohttp

# Internal configuration and settings
from evaluations.config.settings import evaluation_settings

# Configure logger for this module
logger = logging.getLogger(__name__)


class ExpertDataFetcher:
    """
    Responsible for fetching user data from the MyClone API for evaluation purposes.

    This class handles:
    - Authentication with MyClone API using Expert Clone API key
    - Robust error handling for various API failure scenarios
    - Support for multiple API response formats (wrapped vs direct)
    - Data validation to ensure minimum requirements for test generation
    - Comprehensive logging for debugging and monitoring

    The MyClone API provides comprehensive user data including:
    - LinkedIn posts and professional content
    - Twitter/X posts and social media engagement
    - Professional experiences and career history
    - Skills and expertise areas
    - Website data and online presence

    This data forms the ground truth against which AI persona responses are evaluated.
    """

    def __init__(self):
        """
        Initialize the data fetcher with API credentials and configuration.

        Validates that all required environment variables are set before proceeding.
        This prevents runtime errors due to missing configuration.
        """
        # Validate all required settings are present
        evaluation_settings.validate_settings()

        # Extract API credentials from validated settings
        self.api_key = evaluation_settings.myclone_api_key
        self.base_url = evaluation_settings.api_base_url

    async def fetch_user_data_by_username(self, username: str) -> Dict[str, Any]:
        """
        Fetch comprehensive user data from MyClone API using username.

        This method handles the complete API interaction lifecycle:
        1. Constructs authenticated request with proper headers
        2. Makes async HTTP GET request with timeout protection
        3. Handles multiple response formats (wrapped vs direct)
        4. Provides detailed error handling for all failure scenarios
        5. Returns clean, validated user data for evaluation

        Args:
            username (str): The username/handle of the persona to fetch data for
                          This should match the username in MyClone's system

        Returns:
            Dict[str, Any]: Comprehensive user data containing:
                - linkedin_posts: List of LinkedIn posts and content
                - tweets: List of Twitter/X posts and engagement data
                - experiences: Professional work history and career data
                - skills: Technical and professional skills with context
                - website_data: Website content and online presence data

        Raises:
            Exception: Various exceptions for different failure scenarios:
                - Authentication failures (401)
                - Invalid username format (400)
                - User not found (404)
                - Server errors (500)
                - Network timeouts and connection issues
                - JSON parsing errors
        """
        # Construct authentication headers for MyClone API
        # X-API-Key is the primary authentication method
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}

        # Build the complete API endpoint URL
        # Uses the new username-based endpoint (changed from user_id)
        url = f"{self.base_url}/user/expert/{username}/data"

        # Create async HTTP session for API communication
        async with aiohttp.ClientSession() as session:
            try:
                # Log the API call for debugging and monitoring
                logger.info(f"Fetching data for username {username} from {url}")

                # Make authenticated GET request with timeout protection
                # 30 second timeout prevents hanging on slow API responses
                async with session.get(url, headers=headers, timeout=30) as response:
                    # Get raw response text for error handling and debugging
                    response_text = await response.text()

                    if response.status == 200:
                        # Success response - attempt to parse JSON
                        try:
                            data = await response.json()
                        except Exception as json_error:
                            # JSON parsing failed - log details for debugging
                            logger.error(f"Failed to parse JSON response: {json_error}")
                            logger.error(f"Raw response text: {response_text}")
                            raise Exception("Invalid JSON response from MyClone API")

                        # Handle multiple API response formats
                        # MyClone API sometimes wraps responses in {success: true, body: {...}}
                        # and sometimes returns data directly
                        if "success" in data:
                            # Wrapped response format - check success flag
                            if data.get("success"):
                                logger.info(f"Successfully fetched data for user {username}")
                                # Extract actual data from 'body' field
                                return data.get("body", {})
                            else:
                                # API returned success=false - extract error details
                                logger.error("MyClone API returned success=false")
                                logger.error(f"Full response data: {json.dumps(data, indent=2)}")

                                # Extract error message from various possible locations in response
                                # Different API versions may place error messages in different fields
                                error_msg = "Unknown error"

                                # Priority order for error message extraction:
                                # 1. Check if body contains error object
                                if isinstance(data.get("body"), dict):
                                    error_msg = data["body"].get("error", error_msg)
                                # 2. Check if error is at root level
                                elif "error" in data:
                                    error_msg = data.get("error")
                                # 3. Check if message is at root level
                                elif "message" in data:
                                    error_msg = data.get("message")
                                # 4. Check if body is a string error message
                                elif isinstance(data.get("body"), str):
                                    error_msg = data.get("body")

                                raise Exception(f"API returned success=false: {error_msg}")
                        else:
                            # Direct data response format (no success/body wrapper)
                            # This is the newer, simpler response format
                            logger.info(f"Successfully fetched data for user {username}")
                            return data

                    # Handle specific HTTP error status codes with meaningful messages
                    elif response.status == 401:
                        raise Exception("Invalid MYCLONE_API_KEY for MyClone API")
                    elif response.status == 400:
                        raise Exception(f"Invalid username format: {username}")
                    elif response.status == 404:
                        raise Exception(f"User {username} not found in MyClone API")
                    elif response.status == 500:
                        raise Exception("MyClone API internal server error")
                    else:
                        # Catch-all for any other HTTP error codes
                        raise Exception(f"MyClone API error {response.status}: {response_text}")

            # Handle various categories of exceptions with specific error messages
            except asyncio.TimeoutError:
                # API call took longer than 30 seconds - likely network or server issue
                raise Exception(f"Timeout fetching data for user {username}")
            except aiohttp.ClientError as e:
                # Network-level errors (DNS, connection refused, etc.)
                logger.error(f"Client error fetching data for {username}: {e}")
                raise Exception(f"Network error: {str(e)}")
            except Exception as e:
                # Catch any other unexpected errors and log them
                logger.error(f"Error fetching data for {username}: {e}")
                raise

    def validate_user_data(self, user_data: Dict[str, Any]) -> bool:
        """
        Validate that user data meets minimum requirements for test case generation.

        This validation ensures we have enough meaningful data to create
        realistic test scenarios. Without sufficient data, evaluation results
        would not be reliable or representative.

        Validation checks:
        1. Presence of all required top-level fields
        2. At least one meaningful data source (experiences, skills, or posts)
        3. Non-empty arrays where data is expected

        Args:
            user_data (Dict[str, Any]): Raw user data fetched from MyClone API
                                      Expected to contain linkedin_posts, tweets,
                                      experiences, skills, and website_data fields

        Returns:
            bool: True if data contains sufficient information for test generation,
                  False if data is insufficient or missing critical components
        """
        # Define the minimum required fields from MyClone API
        # These fields are essential for generating comprehensive test cases
        required_fields = ["linkedin_posts", "tweets", "experiences", "skills", "website_data"]

        # Check that all required top-level fields are present
        for field in required_fields:
            if field not in user_data:
                logger.warning(f"Missing required field: {field}")
                return False

        # Validate that we have meaningful content in at least one major category
        # Even if fields exist, they might be empty arrays or null values

        # Check for professional experience data
        has_experiences = user_data.get("experiences") and len(user_data["experiences"]) > 0

        # Check for skills data (skills field contains nested 'skills' array)
        has_skills = user_data.get("skills") and user_data["skills"].get("skills")

        # Check for social media content (LinkedIn or Twitter posts)
        has_posts = (user_data.get("linkedin_posts") and len(user_data["linkedin_posts"]) > 0) or (
            user_data.get("tweets") and len(user_data["tweets"]) > 0
        )

        # Require at least one meaningful data source for test generation
        if not any([has_experiences, has_skills, has_posts]):
            logger.warning("User data lacks meaningful content for test generation")
            logger.warning("Need at least experiences, skills, or social media posts")
            return False

        # Data validation passed
        return True

    def get_data_summary(self, user_data: Dict[str, Any]) -> Dict[str, int]:
        """
        Generate a summary of available data quantities for logging and monitoring.

        This helps understand the scope and richness of data available for
        a specific user, which can inform test case generation strategies
        and evaluation expectations.

        Args:
            user_data (Dict[str, Any]): Validated user data from MyClone API

        Returns:
            Dict[str, int]: Count of items in each major data category:
                - linkedin_posts: Number of LinkedIn posts available
                - tweets: Number of Twitter/X posts available
                - experiences: Number of work experiences listed
                - skills: Number of skills identified
                - website_data: Number of website data entries
        """
        # Count items in each data category, handling None values gracefully
        return {
            "linkedin_posts": len(user_data.get("linkedin_posts") or []),
            "tweets": len(user_data.get("tweets") or []),
            "experiences": len(user_data.get("experiences") or []),
            # Skills are nested: skills -> skills array
            "skills": len((user_data.get("skills") or {}).get("skills") or []),
            "website_data": len(user_data.get("website_data") or []),
        }
