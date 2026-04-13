"""
Shared middleware components
"""

from shared.middleware.dynamic_cors import (
    DynamicCORSMiddleware,
    clear_custom_domain_cache,
    extract_domain_from_origin,
    is_valid_custom_domain,
)

__all__ = [
    "DynamicCORSMiddleware",
    "clear_custom_domain_cache",
    "extract_domain_from_origin",
    "is_valid_custom_domain",
]
