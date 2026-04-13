"""
Shared database configuration.

This module provides database connection configuration used by both
the API service and worker containers.
"""

import os
from typing import Dict

from dotenv import load_dotenv

load_dotenv()

# Database connection parameters
POSTGRES_USER = os.getenv("POSTGRES_USER", "myclone_dev_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "myclone_dev_pass")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "myclone_dev_db")


def get_database_params() -> Dict[str, any]:
    """
    Get individual database connection parameters.

    Useful for libraries like LlamaIndex PGVectorStore that need
    individual connection parameters instead of a URL.

    Returns:
        dict: Database connection parameters
    """
    return {
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD,
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "database": POSTGRES_DB,
    }


def get_database_url() -> str:
    """
    Construct database URL from POSTGRES_* environment variables.

    Uses default values for local development. Production environments
    should override these via environment variables.

    Returns:
        str: Async PostgreSQL connection string (postgresql+asyncpg://...)
    """
    return f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
