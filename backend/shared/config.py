import os

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings

from shared.utils.config_helpers import extract_from_json_or_plain

load_dotenv()


class Settings(BaseSettings):
    # Database
    postgres_user: str = os.getenv("POSTGRES_USER", "persona_user")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "persona_pass")
    postgres_db: str = os.getenv("POSTGRES_DB", "persona_db")
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))

    # OpenAI (used globally: RAG, LiveKit, generation, prompts)
    # Production (ECS): OPENAI_API_KEY may be JSON {"OPENAI_API_KEY":"sk-..."} or plain text
    # Local dev: OPENAI_API_KEY env var from .env file (plain text)
    # get_json_secret handles both: extracts from JSON if JSON, returns as-is if plain text
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # Voyage AI (used for embeddings in RAG when EMBEDDING_PROVIDER=voyage)
    voyage_api_key: str = os.getenv("VOYAGE_API_KEY", "")

    # Embedding provider: "openai" or "voyage"
    # Controls which embedding model and table to use:
    # - voyage: voyage-3.5-lite (512 dims) -> data_llamalite_embeddings
    # - voyage: voyage-3.5-lite (512 dims) -> data_llamalite_embeddings
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "voyage")

    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o")

    # Reranker Configuration
    # Enable/disable document reranking for better retrieval relevance
    # When enabled, fetches 4x more documents and reranks them for optimal results
    use_reranker: bool = os.getenv("USE_RERANKER", "true").lower() == "true"
    reranker_provider: str = os.getenv("RERANKER_PROVIDER", "voyageai")  # Options: "voyageai"
    reranker_model: str = os.getenv("RERANKER_MODEL", "rerank-2.5-lite")  # VoyageAI rerank model

    # Firecrawl (for URL content fetching in RAG)
    firecrawl_api_key: str = os.getenv("FIRECRAWL_API_KEY", "")
    firecrawl_base_url: str = os.getenv("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev/v1")

    # Brave Search API (for internet search in LiveKit agent)
    # Production (ECS): BRAVE_SEARCH_API_KEY env var
    # Local dev: BRAVE_SEARCH_API_KEY env var
    brave_search_api_key: str = os.getenv("BRAVE_SEARCH_API_KEY", "")

    # LiveKit Configuration
    # Production (ECS): LIVEKIT_SECRETS is JSON with keys
    # Local dev: Individual LIVEKIT_* env vars
    # Migrations: Optional (uses defaults if not set)
    livekit_url: str = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    livekit_api_key: str = os.getenv("LIVEKIT_API_KEY", "")
    livekit_api_secret: str = os.getenv("LIVEKIT_API_SECRET", "")
    livekit_agent_name: str = os.getenv("LIVEKIT_AGENT_NAME", "expert_agent")

    # LiveKit Recording Configuration (Egress)
    # Controls voice session recording via LiveKit Cloud egress
    enable_voice_recording: bool = os.getenv("ENABLE_VOICE_RECORDING", "true").lower() == "true"
    recording_format: str = os.getenv("RECORDING_FORMAT", "mp4")  # mp4, webm, or hls

    # SECURITY: Dedicated IAM credentials for LiveKit egress (write-only to recordings/*)
    # Production (ECS): LIVEKIT_EGRESS_SECRETS is JSON with keys
    # Local dev: Individual env vars (AWS_LIVEKIT_EGRESS_ACCESS_KEY_ID, etc.)
    # Principle of least privilege: Separate credentials with minimal S3 permissions
    # Falls back to main AWS credentials if not set (for backward compatibility)
    # See: docs/terraform/README.md for Terraform setup instructions
    aws_livekit_egress_access_key_id: str = ""
    aws_livekit_egress_secret_access_key: str = ""

    @field_validator("aws_livekit_egress_access_key_id", mode="before")
    @classmethod
    def extract_egress_access_key_id(cls, v: str) -> str:
        """Extract from LIVEKIT_EGRESS_SECRETS JSON (production) or use plain text (local)"""
        return extract_from_json_or_plain(v, "AWS_LIVEKIT_EGRESS_ACCESS_KEY_ID")

    @field_validator("aws_livekit_egress_secret_access_key", mode="before")
    @classmethod
    def extract_egress_secret_access_key(cls, v: str) -> str:
        """Extract from LIVEKIT_EGRESS_SECRETS JSON (production) or use plain text (local)"""
        return extract_from_json_or_plain(v, "AWS_LIVEKIT_EGRESS_SECRET_ACCESS_KEY")

    # ElevenLabs Configuration
    # Production (ECS): ELEVENLABS_SECRETS is JSON with ELEVENLABS_API_KEY
    # Local dev: ELEVENLABS_API_KEY env var
    # Migrations: Optional (uses empty string if not set)
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "")

    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_DEFAULT_VOICE_ID", "")  # Set a default ElevenLabs voice ID

    # Cartesia Configuration
    # Production (ECS): CARTESIA_API_KEY env var
    # Local dev: CARTESIA_API_KEY env var
    cartesia_api_key: str = os.getenv("CARTESIA_API_KEY", "")
    cartesia_voice_id: str = os.getenv("CARTESIA_DEFAULT_VOICE_ID", "")  # Set a default Cartesia voice ID

    deepgram_api_key: str = os.getenv("DEEPGRAM_API_KEY", "")

    # Voice Processing API Keys
    # DataLab (Marker.io) - PDF parsing to markdown
    # Production (ECS): VOICE_PROCESSING_SECRETS is JSON with API keys
    # Local dev: Individual env vars
    datalab_api_key: str = os.getenv("DATALAB_API_KEY", "")

    # AssemblyAI Configuration (for voice processing)
    # Production (ECS): VOICE_PROCESSING_SECRETS is JSON with ASSEMBLYAI_API_KEY
    # Local dev: ASSEMBLYAI_API_KEY env var
    assemblyai_api_key: str = os.getenv("ASSEMBLYAI_API_KEY", "")

    # YouTube Data API Configuration (for video metadata)
    # Production (ECS): VOICE_PROCESSING_SECRETS is JSON with YOUTUBE_API_KEY
    # Local dev: YOUTUBE_API_KEY env var
    # Optional: Falls back to yt-dlp if not provided
    youtube_api_key: str = os.getenv("YOUTUBE_API_KEY", "")

    # Webshare Proxy Configuration (for youtube_transcript_api)
    # Used to bypass IP blocking on AWS/cloud providers when fetching YouTube transcripts
    # Production (ECS): VOICE_PROCESSING_SECRETS is JSON with WEBSHARE_PROXY_USERNAME and WEBSHARE_PROXY_PASSWORD
    # Local dev: Individual env vars
    # Optional: Falls back to direct requests if not provided (may encounter IP blocks on AWS)

    # Langfuse Configuration (for LLM observability and tracing)
    # Used by LiveKit and LlamaRAG for tracking LLM interactions
    # Production (ECS): LANGFUSE_SECRETS is JSON with keys
    # Local dev: Individual LANGFUSE_* env vars
    langfuse_public_key: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    langfuse_secret_key: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    langfuse_host: str = os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com")
    webshare_proxy_username: str = os.getenv("WEBSHARE_PROXY_USERNAME", "")
    webshare_proxy_password: str = os.getenv("WEBSHARE_PROXY_PASSWORD", "")

    # YouTube Proxy Configuration (for bypassing IP-based bot detection)
    # Residential proxies route requests through real residential IPs
    # This bypasses YouTube's datacenter IP blocking
    #
    # Recommended providers:
    # - ScraperAPI: Free tier (1,000 req/month), $49/month for 100k requests
    # - BrightData: $500/month for 40GB, best reliability
    # - Webshare: $5/month for 25GB, budget option
    #
    # Format: http://username:password@proxy.example.com:port
    # Example: http://scraperapi:YOUR_API_KEY@proxy-server.scraperapi.com:8001

    # Format: http://username:password@proxy.example.com:port
    youtube_proxy: str = os.getenv("YOUTUBE_PROXY_URL", "")

    # AWS S3 Configuration (for avatar uploads)
    # Production (ECS): AWS_SECRETS is JSON with AWS credentials
    # Local dev: Individual env vars (AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")

    # Vector settings
    # Default 1536 for OpenAI, but can be overridden
    # Set to 512 for Voyage AI voyage-3.5-lite
    vector_dimension: int = int(os.getenv("VECTOR_DIMENSION", "1536"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1000"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "200"))

    @property
    def get_embedding_config(self) -> dict:
        """Get embedding configuration based on provider"""
        if self.embedding_provider == "voyage":
            return {
                "provider": "voyage",
                "model": "voyage-3.5-lite",
                "dimension": 512,
                "table_name": "llamalite_embeddings",  # LlamaIndex prepends "data_"
                "api_key": self.voyage_api_key,
            }
        else:  # default to openai
            return {
                "provider": "openai",
                "model": "text-embedding-3-small",
                "dimension": 1536,
                "table_name": "llamaindex_embeddings",  # LlamaIndex prepends "data_"
                "api_key": self.openai_api_key,
            }

    # Content processing limits
    post_content_limit: int = int(
        os.getenv("POST_CONTENT_LIMIT", "3000")
    )  # Increased for LinkedIn posts (can be much longer)
    profile_content_limit: int = int(os.getenv("PROFILE_CONTENT_LIMIT", "500"))

    # File upload settings
    max_pdf_file_size: int = int(
        os.getenv("MAX_PDF_FILE_SIZE", str(100 * 1024 * 1024))
    )  # Default 100MB
    max_file_upload_size: int = int(
        os.getenv("MAX_FILE_UPLOAD_SIZE", str(5 * 1024 * 1024 * 1024))
    )  # Default 5 GB for all document types

    # AWS S3 settings
    # LocalStack (local dev): No credentials needed, uses unsigned requests
    # Production with IAM: No credentials needed, uses IAM role automatically
    # Production with explicit credentials: Uses AWS_SECRETS JSON (from Secrets Manager)
    aws_endpoint_url: str = os.getenv("AWS_ENDPOINT_URL", "")  # Empty = use real AWS S3
    user_data_bucket: str = os.getenv("USER_DATA_BUCKET", "myclone-user-data")

    # API Authentication
    api_key: str = os.getenv("MYCLONE_API_KEY", "")
    require_api_key: bool = os.getenv("MYCLONE_REQUIRE_API_KEY", "false").lower() == "true"

    # API settings
    api_v1_str: str = "/api/v1"
    project_name: str = os.getenv("PROJECT_NAME", "MyClone")

    # NATS settings
    nats_url: str = os.getenv("NATS_URL", "nats://localhost:4222")

    # S3 settings (for file storage)
    voice_segments_bucket: str = os.getenv("VOICE_SEGMENTS_BUCKET", "")  # Legacy bucket

    # Redis (for caching)
    redis_url: str | None = os.getenv("REDIS_URL", "redis://localhost:6379")

    # LinkedIn OAuth settings
    linkedin_client_id: str = os.getenv("LINKEDIN_CLIENT_ID", "")
    linkedin_client_secret: str = os.getenv("LINKEDIN_CLIENT_SECRET", "")

    @property
    def linkedin_redirect_uri(self) -> str:
        """Construct LinkedIn redirect URI from API_BASE_URL"""
        base_url = os.getenv("API_BASE_URL", "http://localhost:8001")
        base_url = base_url.rstrip("/")

        # Add /api/v1 if not present
        if not base_url.endswith("/api/v1"):
            base_url = f"{base_url}/api/v1"

        return f"{base_url}/auth/linkedin/callback"

    # Google OAuth settings
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")

    @property
    def google_redirect_uri(self) -> str:
        """Construct Google redirect URI from API_BASE_URL"""
        base_url = os.getenv("API_BASE_URL", "http://localhost:8001")
        base_url = base_url.rstrip("/")

        # Add /api/v1 if not present
        if not base_url.endswith("/api/v1"):
            base_url = f"{base_url}/api/v1"

        return f"{base_url}/auth/google/callback"

    # JWT settings
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-key-change-in-production")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expiration_days: int = int(os.getenv("JWT_EXPIRATION_DAYS", "30"))

    @property
    def cookie_domain(self) -> str | None:
        """
        Get cookie domain based on environment.

        Returns the value of COOKIE_DOMAIN env var, or None for local development.
        Set COOKIE_DOMAIN to your root domain in production (e.g., .yourdomain.com).
        """
        return os.getenv("COOKIE_DOMAIN", None)

    # Password Security Configuration
    password_min_length: int = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
    password_require_uppercase: bool = (
        os.getenv("PASSWORD_REQUIRE_UPPERCASE", "true").lower() == "true"
    )
    password_require_lowercase: bool = (
        os.getenv("PASSWORD_REQUIRE_LOWERCASE", "true").lower() == "true"
    )
    password_require_number: bool = os.getenv("PASSWORD_REQUIRE_NUMBER", "true").lower() == "true"
    password_require_special: bool = (
        os.getenv("PASSWORD_REQUIRE_SPECIAL", "false").lower() == "true"
    )
    bcrypt_rounds: int = int(os.getenv("BCRYPT_ROUNDS", "12"))

    # Account Security Configuration
    max_failed_login_attempts: int = int(os.getenv("MAX_FAILED_LOGIN_ATTEMPTS", "5"))
    account_lockout_duration_minutes: int = int(os.getenv("ACCOUNT_LOCKOUT_DURATION_MINUTES", "15"))

    # Email Verification Configuration
    email_verification_token_expiry_hours: int = int(
        os.getenv("EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS", "24")
    )

    # Password Reset Configuration
    password_reset_token_expiry_hours: int = int(
        os.getenv("PASSWORD_RESET_TOKEN_EXPIRY_HOURS", "1")
    )

    # Sentry Configuration
    sentry_dsn: str = os.getenv("SENTRY_DSN", "")
    git_sha: str = os.getenv("GIT_SHA", "unknown")  # Git commit SHA for release tracking

    # Multi-language Support Configuration
    # Supported language codes for TTS and persona responses
    # auto: No language restriction (default, for Cartesia assumes English)
    # en: English, hi: Hindi, es: Spanish, fr: French
    # zh: Chinese, de: German, ar: Arabic, it: Italian
    # el: Greek, cs: Czech, ja: Japanese, pt: Portuguese
    # nl: Dutch, ko: Korean, pl: Polish, sv: Swedish
    supported_languages: dict = {
        "auto": "Auto (No restriction)",
        "en": "English",
        "hi": "Hindi",
        "es": "Spanish",
        "fr": "French",
        "zh": "Chinese",
        "de": "German",
        "ar": "Arabic",
        "it": "Italian",
        "el": "Greek",
        "cs": "Czech",
        "ja": "Japanese",
        "pt": "Portuguese",
        "nl": "Dutch",
        "ko": "Korean",
        "pl": "Polish",
        "sv": "Swedish",
    }

    # Language code mapping for TTS providers
    # Cartesia uses specific language keys
    cartesia_language_map: dict = {
        "auto": "en",  # Default to English for auto
        "en": "en",
        "hi": "hi",
        "es": "es",
        "fr": "fr",
        "zh": "zh",
        "de": "de",
        "ar": "ar",
        "it": "it",
        "el": "el",  # Greek
        "cs": "cs",  # Czech
        "ja": "ja",  # Japanese
        "pt": "pt",  # Portuguese
        "nl": "nl",  # Dutch
        "ko": "ko",  # Korean
        "pl": "pl",  # Polish
        "sv": "sv",  # Swedish
    }

    # Language names mapping (human-readable)
    # Used for system prompt injection and display
    language_names: dict = {
        "en": "English",
        "hi": "Hindi",
        "es": "Spanish",
        "fr": "French",
        "zh": "Chinese",
        "de": "German",
        "ar": "Arabic",
        "it": "Italian",
        "el": "Greek",
        "cs": "Czech",
        "ja": "Japanese",
        "pt": "Portuguese",
        "nl": "Dutch",
        "ko": "Korean",
        "pl": "Polish",
        "sv": "Swedish",
    }

    # Resend Email Configuration (for onboarding emails)
    resend_api_key: str = os.getenv("RESEND_API_KEY", "")
    resend_from_email: str = os.getenv(
        "RESEND_FROM_EMAIL", "noreply@example.com"
    )  # Must be a verified domain

    # Support email (shown in password reset, error pages, etc.)
    support_email: str = os.getenv("SUPPORT_EMAIL", "support@example.com")

    # Slack Notification Configuration (for onboarding notifications)
    slack_webhook_url: str = os.getenv("SLACK_WEBHOOK_URL", "")

    # Encryption settings (for securing OAuth tokens in database)
    # Used to encrypt/decrypt LinkedIn, Google, GitHub access & refresh tokens
    # Prevents token exposure if database is compromised
    # Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
    #
    # IMPORTANT: Uses field_validator instead of default value to handle JSON extraction.
    # Pydantic BaseSettings automatically loads env vars and overrides default values.
    # Since AWS stores this as JSON: {"ENCRYPTION_KEY":"..."}, we need a validator to:
    # 1. Let Pydantic load the raw env var value (JSON string or plain text)
    # 2. Then process it to extract the key from JSON (AWS) or use as-is (local dev)
    #
    # This differs from other secrets like CRUSTDATA_API_KEY which use separate env var
    # names (SCRAPING_CONSUMER_SECRETS vs CRUSTDATA_API_KEY) to avoid this issue.
    encryption_key: str = ""

    @field_validator("encryption_key", mode="before")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        """Extract encryption key from JSON (AWS) or plain text (local)"""
        return extract_from_json_or_plain(v, "ENCRYPTION_KEY")

    # Vercel Domain Integration (for custom domain white-labeling)
    # Required for custom domain feature to work
    # Get token from: https://vercel.com/account/tokens
    # Get project ID from: Project Settings > General
    vercel_api_token: str = os.getenv("VERCEL_API_TOKEN", "")
    vercel_project_id: str = os.getenv("VERCEL_PROJECT_ID", "")
    vercel_team_id: str = os.getenv("VERCEL_TEAM_ID", "")  # Optional, for team projects

    # Additional settings from .env
    database_url_override: str | None = os.getenv("DATABASE_URL", "")
    myclone_api_key: str | None = os.getenv("MYCLONE_API_KEY", "")
    myclone_require_api_key: str | None = os.getenv("MYCLONE_REQUIRE_API_KEY", "false")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key")
    environment: str = os.getenv("ENVIRONMENT", "production")
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    host_port: int = int(os.getenv("HOST_PORT", "8001"))

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def sync_database_url(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from .env


settings = Settings()
