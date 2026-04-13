import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api import custom_domain_routes  # Custom domain white-label integration
from app.api import custom_email_domain_routes  # Custom email domain for whitelabel emails
from app.api import evaluation_routes  # LiveKit agent evaluation endpoints
from app.api import knowledge_library_routes  # Knowledge Library management
from app.api import langfuse  # Langfuse prompt management (modular)
from app.api import persona_access_routes  # Persona Access Control (visitor OTP verification)
from app.api import persona_knowledge_routes  # Persona-Knowledge relationships
from app.api import visitor_management_routes  # Visitor Whitelist Management (dashboard)
from app.api import webhook_routes  # Webhook management endpoints
from app.api import (  # Add document routes
    auth_routes,
    cartesia_api,
    conversation_routes,
    document_routes,
    eleven_labs,
    google_oauth_routes,
    ingestion_routes,
    job_routes,
    linkedin_oauth_routes,
    livekit_routes,
    prompt_routes,
    prompt_template_routes,
    routes,
    session_routes,
    template_routes,
    user_routes,
    voice_clone_routes,
    voice_processing_routes,
    workflow_routes,
)
from app.services.livekit_orchestrator import get_orchestrator
from shared.config import settings
from shared.database.models.database import init_db
from shared.middleware import DynamicCORSMiddleware
from shared.monitoring.sentry_middleware import SentryContextMiddleware
from shared.monitoring.sentry_utils import init_sentry

# Initialize Sentry first (before any logging or app initialization)
init_sentry(component="api")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)

# Ensure specific loggers are at INFO level
logging.getLogger("app.core.llama_rag").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager

    Handles startup and shutdown of the orchestrator and its resources.
    """
    orchestrator = None

    # Startup
    logger.info("Starting up Digital Persona System...")

    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized successfully")

        # Initialize orchestrator (singleton)
        orchestrator = await get_orchestrator()

        # Initialize database connection and recovery
        await orchestrator.initialize()

        # Initialize voice processing service
        try:
            await voice_processing_routes.initialize_voice_processing()
            logger.info("✅ Voice processing service initialized")
        except Exception as e:
            logger.warning(f"⚠️  Voice processing service initialization failed: {e}")
            logger.warning("Voice processing endpoints will be unavailable")

        logger.info("✅ API server startup completed")
        logger.info(f"✅ LiveKit configured: {orchestrator.livekit_url}")
        logger.info("LiveKit agent will be started dynamically when voice chat is requested")

        yield

    except Exception as e:
        logger.error(f"Failed to start API server: {e}")
        # Continue even if orchestrator initialization fails
        yield

    finally:
        # Shutdown
        logger.info("Shutting down Digital Persona System...")

        if orchestrator:
            try:
                await orchestrator.shutdown_all_workers()
                logger.info("✅ THE worker shut down successfully")
            except Exception as e:
                logger.error(f"Error during worker shutdown: {e}")

        # Shutdown voice processing service
        try:
            await voice_processing_routes.shutdown_voice_processing()
            logger.info("✅ Voice processing service shut down successfully")
        except Exception as e:
            logger.error(f"Error during voice processing shutdown: {e}")

        logger.info("✅ Shutdown completed")


app = FastAPI(
    title=settings.project_name,
    version="1.0.0",
    description="Digital Persona/Clone System - Mimics thinking and communication patterns",
    lifespan=lifespan,
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Dynamic CORS middleware - supports platform domains AND verified custom domains
# Custom domains are validated against the database with caching
app.add_middleware(
    DynamicCORSMiddleware,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Sentry context middleware (after CORS, before routes)
app.add_middleware(SentryContextMiddleware)

# Include routers with /api/v1 prefix (primary)
app.include_router(routes.router, prefix=settings.api_v1_str)
app.include_router(user_routes.router, tags=["Users"])
app.include_router(linkedin_oauth_routes.router, tags=["LinkedIn OAuth"])
app.include_router(google_oauth_routes.router, tags=["Google OAuth"])
app.include_router(auth_routes.router, tags=["Email/Password Auth"])

# Routers without prefix (for specific paths)
app.include_router(session_routes.router)  # Enhanced session tracking
app.include_router(conversation_routes.router)  # Conversation history endpoints
app.include_router(ingestion_routes.router)
app.include_router(livekit_routes.router)  # LiveKit authentication
app.include_router(eleven_labs.router)  # ElevenLabs voice cloning
app.include_router(cartesia_api.router)  # Cartesia voice cloning
app.include_router(voice_clone_routes.router)  # Unified voice clone API (all platforms)
app.include_router(voice_processing_routes.router)  # Voice processing async jobs
app.include_router(prompt_routes.router)
app.include_router(prompt_template_routes.router)  # Prompt template management
app.include_router(langfuse.router)  # Langfuse prompt management (modular structure)
app.include_router(document_routes.router)  # Document management
app.include_router(knowledge_library_routes.router)  # Knowledge Library management
app.include_router(persona_knowledge_routes.router)  # Persona-Knowledge relationships
app.include_router(persona_access_routes.router)  # Persona Access Control (public endpoints)
app.include_router(visitor_management_routes.router)  # Visitor Management (dashboard endpoints)
app.include_router(webhook_routes.router)  # Webhook management endpoints
app.include_router(job_routes.router)  # Unified job status tracking
app.include_router(workflow_routes.router)  # Workflow system
app.include_router(template_routes.router)  # Workflow template library
app.include_router(custom_domain_routes.router)  # Custom domain white-label integration
app.include_router(custom_email_domain_routes.router)  # Custom email domain whitelabel
app.include_router(evaluation_routes.router)  # LiveKit agent evaluation endpoints


@app.get("/api")
async def api_root():
    return {
        "message": "Digital Persona System API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get(f"{settings.api_v1_str}")
async def api_v1_root():
    return {
        "message": "Digital Persona System API v1",
        "version": "1.0.0",
        "docs": "/docs",
        "health": f"{settings.api_v1_str}/health",
    }
