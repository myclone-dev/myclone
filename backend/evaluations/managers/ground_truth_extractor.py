# Standard library imports for type hints and data structures
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List

# Configure logger for ground truth extraction
logger = logging.getLogger(__name__)


@dataclass
class Fact:
    """
    Represents a single ground truth fact about a persona for evaluation purposes.

    Ground truth facts serve as the reference points against which AI persona
    responses are evaluated. Each fact includes confidence scoring to weight
    its importance in evaluation and metadata for debugging and analysis.

    Attributes:
        type (str): Category of fact (current_role, skill, experience, recent_activity, etc.)
                   Used for organizing test cases by topic area
        assertion (str): The factual statement that should be reflected in AI responses
                        Example: "Currently works as Software Engineer at Google"
        confidence (float): Confidence level in this fact (0.0 to 1.0)
                           Higher confidence facts have more weight in evaluation
        source (str): Data source that generated this fact (experiences, skills, social_posts)
                     Used for debugging and data quality assessment
        metadata (Dict[str, Any]): Additional contextual information about the fact
                                  Contains structured data for detailed analysis
    """

    type: str  # Category: current_role, skill, experience, recent_activity, etc.
    assertion: str  # The factual statement to be verified
    confidence: float  # Confidence in this fact (0.0 to 1.0)
    source: str  # Data source: experiences, skills, social_posts, etc.
    metadata: Dict[str, Any] = None  # Additional context and structured data

    def __post_init__(self):
        """Initialize metadata as empty dict if not provided."""
        if self.metadata is None:
            self.metadata = {}


class GroundTruthExtractor:
    """Extracts ground truth facts from user data for test generation"""

    def __init__(self):
        pass

    def extract_facts(self, user_data: Dict[str, Any]) -> List[Fact]:
        """
        Extract all ground truth facts from user data

        Args:
            user_data: Raw data from MyClone API

        Returns:
            List of Fact objects representing ground truth
        """
        facts = []

        logger.info(
            f"Starting fact extraction. User data keys: {list(user_data.keys()) if user_data else 'None'}"
        )

        # Extract current role/position facts
        try:
            role_facts = self._extract_current_role_facts(user_data.get("experiences", []))
            logger.info(f"Role facts: {len(role_facts) if role_facts else 'None'}")
            if role_facts:
                facts.extend(role_facts)
        except Exception as e:
            logger.error(f"Error extracting role facts: {e}")
            return []

        # Extract skills facts
        try:
            skills_facts = self._extract_skills_facts(user_data.get("skills", {}))
            if skills_facts:
                facts.extend(skills_facts)
        except Exception as e:
            logger.error(f"Error extracting skills facts: {e}")

        # Extract experience/background facts
        try:
            exp_facts = self._extract_experience_facts(user_data.get("experiences", []))
            if exp_facts:
                facts.extend(exp_facts)
        except Exception as e:
            logger.error(f"Error extracting experience facts: {e}")

        # Extract recent activity facts
        try:
            activity_facts = self._extract_recent_activity_facts(
                user_data.get("linkedin_posts", []), user_data.get("tweets", [])
            )
            if activity_facts:
                facts.extend(activity_facts)
        except Exception as e:
            logger.error(f"Error extracting activity facts: {e}")

        # Extract website/social presence facts
        try:
            social_facts = self._extract_social_presence_facts(
                user_data.get("website_data", []), user_data.get("tweets", [])
            )
            if social_facts:
                facts.extend(social_facts)
        except Exception as e:
            logger.error(f"Error extracting social facts: {e}")

        logger.info(f"Extracted {len(facts)} ground truth facts")
        return facts

    def _extract_current_role_facts(self, experiences: List[Dict]) -> List[Fact]:
        """Extract facts about current employment"""
        facts = []

        if not experiences:
            return facts

        current_jobs = [exp for exp in experiences if exp.get("is_current", False)]

        for job in current_jobs:
            title = job.get("title", "").strip()
            company = job.get("company", "").strip()
            location = job.get("location", "").strip()

            if title and company:
                facts.append(
                    Fact(
                        type="current_role",
                        assertion=f"Currently works as {title} at {company}",
                        confidence=0.95,
                        source="experiences",
                        metadata={
                            "title": title,
                            "company": company,
                            "location": location,
                            "start_date": job.get("start_date"),
                        },
                    )
                )

                # Separate facts for title and company
                facts.append(
                    Fact(
                        type="current_title",
                        assertion=f"Current job title is {title}",
                        confidence=0.95,
                        source="experiences",
                        metadata={"title": title},
                    )
                )

                facts.append(
                    Fact(
                        type="current_company",
                        assertion=f"Currently works at {company}",
                        confidence=0.95,
                        source="experiences",
                        metadata={"company": company},
                    )
                )

        return facts

    def _extract_skills_facts(self, skills_data: Dict) -> List[Fact]:
        """Extract facts about skills and expertise"""
        facts = []

        skills_list = skills_data.get("skills", [])
        if not skills_list:
            return facts

        # Top skills (first 5 are usually most important)
        top_skills = skills_list[:5]
        for skill in top_skills:
            facts.append(
                Fact(
                    type="skill",
                    assertion=f"Has expertise in {skill}",
                    confidence=0.9,
                    source="skills",
                    metadata={"skill": skill, "priority": "high"},
                )
            )

        # All skills fact
        if len(skills_list) >= 3:
            facts.append(
                Fact(
                    type="skill_summary",
                    assertion=f"Has skills including {', '.join(skills_list[:3])}",
                    confidence=0.85,
                    source="skills",
                    metadata={"skills": skills_list},
                )
            )

        return facts

    def _extract_experience_facts(self, experiences: List[Dict]) -> List[Fact]:
        """Extract facts about work experience and background"""
        facts = []

        if not experiences:
            return facts

        # Total years of experience (approximate)
        total_experience = self._calculate_total_experience(experiences)
        if total_experience > 0:
            facts.append(
                Fact(
                    type="experience_length",
                    assertion=f"Has approximately {total_experience} years of experience",
                    confidence=0.8,
                    source="experiences",
                    metadata={"years": total_experience},
                )
            )

        # Previous companies (excluding current)
        previous_jobs = [exp for exp in experiences if not exp.get("is_current", False)]
        previous_companies = [
            exp.get("company", "").strip() for exp in previous_jobs if exp.get("company")
        ]

        if previous_companies:
            facts.append(
                Fact(
                    type="previous_experience",
                    assertion=f"Previously worked at companies including {', '.join(previous_companies[:3])}",
                    confidence=0.85,
                    source="experiences",
                    metadata={"previous_companies": previous_companies},
                )
            )

        return facts

    def _extract_recent_activity_facts(
        self, linkedin_posts: List[Dict], tweets: List[Dict]
    ) -> List[Fact]:
        """Extract facts about recent posts and activity"""
        facts = []

        if not linkedin_posts and not tweets:
            return facts

        # Combine recent posts (last 30 days)
        cutoff_date = datetime.now() - timedelta(days=30)
        recent_posts = []

        # Process LinkedIn posts
        for post in (linkedin_posts or [])[:10]:  # Recent posts
            posted_at = post.get("posted_at", "")
            if posted_at:
                try:
                    post_date = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
                    if post_date > cutoff_date:
                        recent_posts.append(
                            {"text": post.get("text", ""), "source": "linkedin", "date": post_date}
                        )
                except:
                    # If date parsing fails, still include recent posts
                    recent_posts.append(
                        {"text": post.get("text", ""), "source": "linkedin", "date": None}
                    )

        # Process tweets
        for tweet in (tweets or [])[:10]:  # Recent tweets
            posted_at = tweet.get("posted_at", "")
            if posted_at:
                try:
                    tweet_date = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
                    if tweet_date > cutoff_date:
                        recent_posts.append(
                            {
                                "text": tweet.get("content", ""),
                                "source": "twitter",
                                "date": tweet_date,
                            }
                        )
                except:
                    recent_posts.append(
                        {"text": tweet.get("content", ""), "source": "twitter", "date": None}
                    )

        # Extract topics from recent posts
        if recent_posts:
            topics = self._extract_topics_from_posts([p["text"] for p in recent_posts])
            if topics:
                facts.append(
                    Fact(
                        type="recent_activity",
                        assertion=f"Recently posted about {', '.join(topics[:3])}",
                        confidence=0.7,
                        source="social_posts",
                        metadata={
                            "topics": topics,
                            "post_count": len(recent_posts),
                            "sources": list(set(p["source"] for p in recent_posts)),
                        },
                    )
                )

        return facts

    def _extract_social_presence_facts(
        self, website_data: List[Dict], tweets: List[Dict]
    ) -> List[Fact]:
        """Extract facts about online presence"""
        facts = []

        # Website presence
        if website_data:
            for site in (website_data or [])[:1]:  # Usually just one main website
                url = site.get("website_url", "")
                title = site.get("title", "")
                if url:
                    facts.append(
                        Fact(
                            type="website_presence",
                            assertion=f"Has personal website at {url}",
                            confidence=0.9,
                            source="website_data",
                            metadata={"url": url, "title": title},
                        )
                    )

        # Twitter presence
        if tweets:
            twitter_username = (tweets or [{}])[0].get("twitter_username", "")
            if twitter_username:
                facts.append(
                    Fact(
                        type="social_presence",
                        assertion=f"Active on Twitter as @{twitter_username}",
                        confidence=0.9,
                        source="tweets",
                        metadata={"username": twitter_username},
                    )
                )

        return facts

    def _calculate_total_experience(self, experiences: List[Dict]) -> int:
        """Calculate approximate total years of experience"""
        if not experiences:
            return 0

        total_months = 0

        for exp in experiences:
            start_date = exp.get("start_date", "")
            end_date = exp.get("end_date", "") or datetime.now().strftime("%Y-%m-%d")

            if start_date:
                try:
                    start = datetime.strptime(start_date, "%Y-%m-%d")
                    end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()

                    months = (end.year - start.year) * 12 + (end.month - start.month)
                    total_months += max(0, months)
                except:
                    # If date parsing fails, estimate based on reasonable defaults
                    total_months += 24  # Assume 2 years per job if can't parse

        return max(1, total_months // 12)  # Convert to years

    def _extract_topics_from_posts(self, posts: List[str]) -> List[str]:
        """Extract common topics/themes from posts"""
        if not posts:
            return []

        # Simple topic extraction based on common tech keywords
        topics = []
        text = " ".join(posts).lower()

        # Technology topics
        tech_keywords = {
            "ai": ["ai", "artificial intelligence", "machine learning", "ml", "llm"],
            "software development": ["coding", "programming", "development", "software", "code"],
            "startups": ["startup", "entrepreneur", "founding", "company"],
            "leadership": ["team", "leadership", "management", "leading"],
            "technology": ["tech", "technology", "innovation"],
            "product": ["product", "feature", "launch", "building"],
        }

        for topic, keywords in tech_keywords.items():
            if any(keyword in text for keyword in keywords):
                topics.append(topic)

        return topics[:5]  # Return top 5 topics
