"""
Fuzzy matching utilities for LinkedIn profile search
"""

from difflib import SequenceMatcher
from typing import Optional


def normalize_string(s: Optional[str]) -> str:
    """Normalize string for comparison: lowercase, strip, remove extra spaces"""
    if not s:
        return ""
    return " ".join(s.lower().strip().split())


def string_similarity(s1: Optional[str], s2: Optional[str]) -> float:
    """
    Calculate similarity between two strings using SequenceMatcher.
    Returns a value between 0.0 (no match) and 1.0 (perfect match).
    """
    if not s1 or not s2:
        return 0.0

    s1_norm = normalize_string(s1)
    s2_norm = normalize_string(s2)

    if not s1_norm or not s2_norm:
        return 0.0

    return SequenceMatcher(None, s1_norm, s2_norm).ratio()


def calculate_name_similarity(search_name: str, profile_name: str) -> float:
    """
    Calculate name similarity with word-by-word comparison and initials handling.

    Algorithm:
    1. Split both names into words
    2. Compare each word from search with each word from profile
    3. Handle initials (e.g., "J." matches "John")
    4. Return average of best matches
    """
    if not search_name or not profile_name:
        return 0.0

    search_words = normalize_string(search_name).split()
    profile_words = normalize_string(profile_name).split()

    if not search_words or not profile_words:
        return 0.0

    # Calculate word-level similarities
    total_score = 0.0
    matched_words = 0

    for search_word in search_words:
        best_match = 0.0

        for profile_word in profile_words:
            # Handle initials (e.g., "j" or "j." matches "john")
            if (
                len(search_word) <= 2
                and len(profile_word) > 0
                and search_word.replace(".", "") == profile_word[0]
            ):
                similarity = 0.9  # High score for initial match
            elif (
                len(profile_word) <= 2
                and len(search_word) > 0
                and profile_word.replace(".", "") == search_word[0]
            ):
                similarity = 0.9
            else:
                # Standard string similarity
                similarity = SequenceMatcher(None, search_word, profile_word).ratio()

            best_match = max(best_match, similarity)

        total_score += best_match
        matched_words += 1

    return total_score / matched_words if matched_words > 0 else 0.0


def calculate_weighted_score(
    search_name: str,
    profile_name: str,
    search_title: Optional[str] = None,
    profile_title: Optional[str] = None,
    search_company: Optional[str] = None,
    profile_company: Optional[str] = None,
    search_location: Optional[str] = None,
    profile_location: Optional[str] = None,
) -> float:
    """
    Calculate weighted similarity score for a LinkedIn profile.

    Weights:
    - Name: 40%
    - Title: 30%
    - Company: 20%
    - Location: 10%

    Returns a score between 0.0 and 1.0.
    """
    # Name similarity (required, 40% weight)
    name_score = calculate_name_similarity(search_name, profile_name)
    weighted_score = name_score * 0.4

    # Title similarity (30% weight)
    if search_title and profile_title:
        title_score = string_similarity(search_title, profile_title)
        weighted_score += title_score * 0.3

    # Company similarity (20% weight)
    if search_company and profile_company:
        company_score = string_similarity(search_company, profile_company)
        weighted_score += company_score * 0.2

    # Location similarity (10% weight)
    if search_location and profile_location:
        location_score = string_similarity(search_location, profile_location)
        weighted_score += location_score * 0.1

    return weighted_score
