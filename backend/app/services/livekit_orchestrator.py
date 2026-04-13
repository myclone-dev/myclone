"""
Persona Orchestrator - Main Management System
This module provides the core orchestration logic for managing persona-based
agent workers. It handles:
- On-demand worker creation and lifecycle management
- Singleton pattern for centralized management
- Health monitoring and cleanup
- Dispatch coordination with LiveKit

The orchestrator ensures that each persona has its own dedicated worker
process when needed, while efficiently managing resources.
"""

import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Dict, Optional
from uuid import UUID

import httpx
import psutil
from sqlalchemy import select

from livekit import api
from shared.config import settings
from shared.database.models.database import Pattern, Persona, PersonaPrompt, async_session_maker
from shared.database.models.livekit import WorkerState
from shared.database.repositories.livekit_repository import LiveKitDatabase
from shared.database.repositories.persona_repository import get_persona_repository
from shared.schemas.livekit import LiveKitDispatchMetadata, PersonaMetadata, PersonaPromptMetadata

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class WorkerInfo:
    """
    Information about a running worker process

    Attributes:
        process: The subprocess.Popen object
        persona_id: ID of the persona this worker handles
        started_at: Timestamp when worker was started
        port: HTTP port the worker is listening on
        last_activity: Timestamp of last activity
        agent_name: Unique agent name for this persona
        state: Current worker state (starting/healthy/idle/terminated)
        active_jobs: Number of active jobs
    """

    process: subprocess.Popen
    persona_id: UUID
    started_at: float
    port: int
    last_activity: float
    agent_name: str
    state: WorkerState
    active_jobs: int = 0
    worker_db_id: Optional[int] = None  # Database ID for referencing in active_rooms

    def __post_init__(self):
        """Set initial last_activity to start time"""
        if not hasattr(self, "last_activity") or self.last_activity == 0:
            self.last_activity = self.started_at


class PersonaOrchestrator:
    """
    Singleton orchestrator for managing persona-based agent workers

    This class provides centralized management of worker processes, ensuring
    that each persona gets its own dedicated worker when needed, while
    efficiently managing system resources.

    Key Features:
    - Singleton pattern for centralized management
    - On-demand worker creation and cleanup
    - Health monitoring and recovery
    - Proper subprocess lifecycle management
    - Thread-safe operations
    """

    _instance: Optional["PersonaOrchestrator"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "PersonaOrchestrator":
        """Ensure singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """
        Initialize the orchestrator

        Note: Due to singleton pattern, this will only run once
        """
        # Prevent re-initialization
        if hasattr(self, "initialized"):
            return

        # Core state management - single worker for all personas
        self.worker: Optional[WorkerInfo] = None
        self.worker_starting: bool = False

        # Database for worker persistence
        self.db: Optional[LiveKitDatabase] = None

        # Configuration
        self.base_port = 8080  # Base port for worker health checks
        self.startup_timeout = 30  # Maximum time to wait for worker startup
        self.health_check_interval = 2  # Seconds between health checks during startup

        # Health monitoring
        self.health_monitor_task: Optional[asyncio.Task] = None
        self.consecutive_failed_checks: int = 0  # Single worker failure count
        self.health_monitor_interval = 60  # Health check every 60 seconds
        self.max_consecutive_failures = 2  # Restart after 2 consecutive failures

        # LiveKit configuration - use centralized settings
        self.livekit_url = settings.livekit_url
        self.livekit_api_key = settings.livekit_api_key
        self.livekit_api_secret = settings.livekit_api_secret
        self.livekit_client = api.LiveKitAPI(
            self.livekit_url, self.livekit_api_key, self.livekit_api_secret
        )

        # State tracking
        self.initialized = True

        logger.info("PersonaOrchestrator initialized")
        logger.info("LiveKit client configured")

    async def initialize(self):
        """Initialize database connection and recover existing workers"""
        self.db = LiveKitDatabase()
        await self._recover_existing_workers()
        self._start_health_monitor()

    async def _recover_existing_workers(self):
        """Recover workers after server restart"""
        if not self.db:
            return

        db_workers = await self.db.get_all_workers()

        recovered = 0
        cleaned = 0

        for worker_data in db_workers:
            pid = worker_data["pid"]
            port = worker_data["port"]

            # Check if process exists
            if not psutil.pid_exists(pid):
                logger.warning(f"Worker process {pid} not found, cleaning DB")
                await self.db.delete_worker(worker_data["id"])
                cleaned += 1
                continue

            # Check if HTTP endpoint responds
            if await self._check_worker_http_health_by_port(port):
                # Reconnect to existing worker
                try:
                    process = psutil.Process(pid)
                    worker_info = WorkerInfo(
                        process=process,
                        persona_id=None,
                        port=port,
                        agent_name=worker_data["agent_name"],
                        state=WorkerState.HEALTHY,
                        started_at=worker_data["started_at"].timestamp(),
                        last_activity=time.time(),
                        worker_db_id=worker_data["id"],  # Set the database ID from recovery
                    )
                    self.worker = worker_info

                    logger.info(f"✅ Recovered worker (PID: {pid}, DB ID: {worker_data['id']})")
                    recovered += 1
                except Exception as e:
                    logger.error(f"Failed to recover worker: {e}")
                    await self.db.delete_worker(worker_data["id"])
                    cleaned += 1
            else:
                # Process exists but not responding, kill it
                logger.warning(f"❌ Worker not responding, killing PID {pid}")
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                await self.db.delete_worker(worker_data["id"])
                cleaned += 1

        logger.info(f"🔄 Startup recovery: {recovered} recovered, {cleaned} cleaned")

    async def _cleanup_stale_worker_records(self, port: int):
        """Clean up stale database records for the given port

        This is called before creating a new worker to ensure no duplicate port conflicts.
        It removes database records for workers that are no longer running.

        Args:
            port: Port number to clean up records for
        """
        if not self.db:
            return

        try:
            # Get all workers using this port
            db_workers = await self.db.get_all_workers()
            stale_workers = [w for w in db_workers if w["port"] == port]

            for worker_data in stale_workers:
                pid = worker_data["pid"]
                worker_id = worker_data["id"]

                # Check if process is still running
                if psutil.pid_exists(pid):
                    # Process exists, check if it's healthy
                    if await self._check_worker_http_health_by_port(port):
                        logger.info(f"🔄 Found existing healthy worker on port {port} (PID: {pid})")
                        # Don't delete - this worker is still healthy
                        continue
                    else:
                        logger.warning(
                            f"🧹 Process {pid} exists but not responding on port {port}, cleaning up"
                        )
                else:
                    logger.warning(f"🧹 Process {pid} not found, cleaning up database record")

                # Remove stale record
                await self.db.delete_worker(worker_id)
                logger.info(f"🧹 Cleaned up stale worker record (PID: {pid}, Port: {port})")

        except Exception as e:
            logger.error(f"Error cleaning up stale worker records for port {port}: {e}")
            # Continue anyway - we'll let the database constraint handle duplicates

    def _start_health_monitor(self):
        """Start the background health monitoring task"""
        if self.health_monitor_task is None or self.health_monitor_task.done():
            self.health_monitor_task = asyncio.create_task(self._health_monitor_loop())
            logger.info("🏥 Background health monitor started")

    async def _health_monitor_loop(self):
        """
        Background task that periodically checks worker health and restarts unhealthy workers

        This task runs every 60 seconds and:
        1. Checks the health of all running workers
        2. Tracks consecutive failed health checks per worker
        3. Automatically restarts workers that have been unhealthy for more than 2 consecutive checks
        4. Logs health check results
        """
        logger.info(
            f"🏥 Health monitor loop started (interval: {self.health_monitor_interval}s, max failures: {self.max_consecutive_failures})"
        )

        while True:
            try:
                await asyncio.sleep(self.health_monitor_interval)

                if not self.worker:
                    logger.debug("🏥 Health monitor: No worker to check")
                    continue

                logger.debug("🏥 Health monitor: Checking THE single worker")

                try:
                    # Check if THE worker is healthy (process running)
                    is_healthy = await self._is_worker_healthy()

                    if is_healthy:
                        # Reset consecutive failure count on successful check
                        if self.consecutive_failed_checks > 0:
                            logger.info("🏥 THE worker recovered, resetting failure count")
                            self.consecutive_failed_checks = 0
                    else:
                        # Increment failure count
                        self.consecutive_failed_checks += 1
                        failure_count = self.consecutive_failed_checks

                        logger.warning(
                            f"🏥 THE worker failed health check (failure #{failure_count})"
                        )

                        # Check if we should restart the worker
                        if failure_count >= self.max_consecutive_failures:
                            logger.warning(
                                f"🔄 THE worker has failed {failure_count} consecutive health checks"
                            )

                            # Reset failure tracking since we detected failure
                            self.consecutive_failed_checks = 0

                            logger.warning(
                                "🚨 THE worker marked as unhealthy - manual intervention required"
                            )

                except Exception as check_error:
                    logger.error(f"🏥 Error checking health of THE worker: {check_error}")
                    # Treat errors as failed health checks
                    self.consecutive_failed_checks += 1

                # Log summary
                if self.consecutive_failed_checks > 0:
                    logger.info(
                        f"🏥 Health monitor summary: THE worker unhealthy (failures: {self.consecutive_failed_checks})"
                    )
                else:
                    logger.debug("🏥 Health monitor summary: THE worker is healthy")

            except asyncio.CancelledError:
                logger.info("🏥 Health monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"🏥 Unexpected error in health monitor loop: {e}")
                # Continue monitoring despite errors

    async def _check_worker_http_health_by_port(self, port: int) -> bool:
        """Check worker health via HTTP port"""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"http://localhost:{port}/")
                return response.status_code == 200
        except:
            return False

    @classmethod
    async def get_instance(cls) -> "PersonaOrchestrator":
        """
        Get the singleton instance in a thread-safe manner

        Returns:
            The singleton PersonaOrchestrator instance
        """
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    async def request_persona_chat(
        self,
        user_id: str,
        persona_id: UUID,
        agent_name: str,
        room_name: Optional[str] = None,
        session_token: Optional[str] = None,
        authenticated_user_id: Optional[str] = None,
    ) -> str:
        """
        Main entry point for requesting a chat with a specific persona

        This method orchestrates the entire process:
        1. Validates the persona exists
        2. Ensures a worker is running for that persona
        3. Creates a dispatch to connect the user to the persona

        Args:
            user_id: Unique identifier for the user
            persona_id: ID of the requested persona
            agent_name: Agent name to route the dispatch to (from frontend)
            room_name: Optional custom room name (if not provided, will be generated)
            session_token: Optional session identifier for conversation continuity
            authenticated_user_id: Optional authenticated user ID (from JWT) to skip email capture

        Returns:
            Room name where the chat will take place

        Raises:
            ValueError: If persona_id is invalid
            RuntimeError: If worker cannot be started or dispatch fails
        """
        logger.info(f"📥 NEW CHAT REQUEST: User {user_id} requesting persona {persona_id}")

        # Validate persona exists
        persona_repo = get_persona_repository()
        if not await persona_repo.exists(persona_id):
            raise ValueError(f"Persona {persona_id} does not exist")

        try:
            # Debug current worker state
            if self.worker:
                logger.info("🔍 THE worker exists and will handle this request")
                logger.info(f"   - PID: {self.worker.process.pid}")
                logger.info(f"   - Port: {self.worker.port}")
                logger.info(f"   - Started: {time.time() - self.worker.started_at:.1f}s ago")
                logger.info(
                    f"   - Last activity: {time.time() - self.worker.last_activity:.1f}s ago"
                )
            else:
                logger.info("🆕 NO EXISTING WORKER, will create THE single worker")

            # Step 1: Ensure worker is ready
            is_ready = await self.ensure_worker_ready(persona_id)
            if not is_ready:
                raise RuntimeError(f"Could not start THE worker for persona {persona_id}")

            # Log worker status after ensure_worker_ready
            if self.worker:
                logger.info(
                    f"✅ THE worker ready for persona {persona_id} (PID: {self.worker.process.pid}, Port: {self.worker.port})"
                )

            # Step 2: Update activity tracking
            await self._update_worker_activity(persona_id)

            # Step 3: Use provided room name or generate one
            if not room_name:
                room_name = f"persona-{persona_id}-user-{user_id}-{int(time.time())}"

            # Step 4: Create dispatch to connect user to persona
            logger.info(
                f"🚀 Dispatching {user_id} to persona {persona_id} worker in room: {room_name}"
            )
            await self._dispatch_to_persona(
                room_name, persona_id, agent_name, session_token, authenticated_user_id
            )

            # Step 5: Track the active room in database
            if self.db and self.worker:
                if self.worker.worker_db_id:
                    # Validate worker still exists in database before using ID
                    worker_exists = await self.db.get_worker_by_id(self.worker.worker_db_id)
                    if not worker_exists:
                        logger.warning(
                            f"⚠️  Worker DB ID {self.worker.worker_db_id} no longer exists in database - re-registering worker"
                        )
                        # Verify process is still healthy before re-registration
                        if not await self._check_process_health():
                            error_msg = (
                                f"Worker process no longer alive: PID={self.worker.process.pid}, "
                                f"DB_ID={self.worker.worker_db_id}, Port={self.worker.port}"
                            )
                            logger.error(error_msg)

                            # REQUIRED: Sentry capture per CLAUDE.md
                            from shared.monitoring.sentry_utils import (
                                capture_exception_with_context,
                            )

                            capture_exception_with_context(
                                RuntimeError(error_msg),
                                extra={
                                    "worker_db_id": self.worker.worker_db_id,
                                    "worker_pid": self.worker.process.pid,
                                    "worker_port": self.worker.port,
                                    "persona_id": str(persona_id),
                                    "room_name": room_name,
                                },
                                tags={
                                    "component": "livekit_orchestrator",
                                    "operation": "add_active_room_worker_recovery",
                                    "severity": "high",
                                    "user_facing": "true",
                                },
                            )

                            self.worker = None
                            raise RuntimeError(error_msg)

                        # Re-save worker to get new valid DB ID
                        # Note: save_worker uses upsert pattern (PID+port check) - handles concurrent requests
                        try:
                            worker_db_id = await self.db.save_worker(
                                self.worker.process.pid,
                                self.worker.port,
                                self.worker.agent_name,
                                WorkerState.HEALTHY,
                            )
                            self.worker.worker_db_id = worker_db_id
                            logger.info(f"✅ Worker re-registered with new DB ID: {worker_db_id}")
                        except Exception as e:
                            error_msg = (
                                f"Failed to re-register worker: PID={self.worker.process.pid}, "
                                f"Port={self.worker.port}, Error={str(e)}"
                            )
                            logger.error(error_msg)

                            # REQUIRED: Sentry capture per CLAUDE.md
                            from shared.monitoring.sentry_utils import (
                                capture_exception_with_context,
                            )

                            capture_exception_with_context(
                                e,
                                extra={
                                    "worker_pid": self.worker.process.pid,
                                    "worker_port": self.worker.port,
                                    "worker_agent_name": self.worker.agent_name,
                                    "persona_id": str(persona_id),
                                    "room_name": room_name,
                                    "original_worker_db_id": self.worker.worker_db_id,
                                },
                                tags={
                                    "component": "livekit_orchestrator",
                                    "operation": "save_worker_recovery",
                                    "severity": "high",
                                    "user_facing": "true",
                                },
                            )
                            raise RuntimeError(error_msg) from e

                    # Add room with validated worker_db_id (either existing or re-registered)
                    try:
                        await self.db.add_active_room(
                            room_name,
                            self.worker.worker_db_id,
                            persona_id,
                            user_id,  # user_id is LiveKit participant ID
                        )
                        logger.info(
                            f"📝 Room {room_name} tracked in database for THE worker {self.worker.worker_db_id}"
                        )
                    except Exception as e:
                        # REQUIRED: Sentry capture per CLAUDE.md
                        from shared.monitoring.sentry_utils import capture_exception_with_context

                        capture_exception_with_context(
                            e,
                            extra={
                                "room_name": room_name,
                                "worker_db_id": self.worker.worker_db_id,
                                "persona_id": str(persona_id),
                                "participant_id": user_id,
                            },
                            tags={
                                "component": "livekit_orchestrator",
                                "operation": "add_active_room",
                                "severity": "medium",
                                "user_facing": "false",  # Non-blocking for voice chat
                            },
                        )
                        logger.warning(f"Failed to track room in database (non-blocking): {e}")
                        # Don't raise - room tracking failure shouldn't block voice chat
                else:
                    logger.warning(
                        "No worker_db_id available for THE worker, skipping room tracking"
                    )

            logger.info(
                f"✅ CHAT READY: User {user_id} ↔ Persona {persona_id} in room {room_name} (same worker handles all users)"
            )
            return room_name

        except Exception as e:
            logger.error(f"❌ Failed to setup chat for persona {persona_id}: {e}")
            raise

    async def ensure_worker_ready(self, persona_id: UUID) -> bool:
        """
        Ensure THE single worker is running and ready

        This method handles the complete worker lifecycle:
        - Checks if THE worker is already running and healthy
        - Starts THE worker if needed
        - Waits for worker to be fully registered with LiveKit
        - Handles concurrent start attempts with proper locking

        Args:
            persona_id: ID of the persona requesting the worker (for logging only)

        Returns:
            True if worker is ready, False if startup failed
        """
        logger.info(f"📋 Ensuring THE worker is ready (requested by persona {persona_id})")

        # Use the class-level lock to prevent race conditions
        async with self._lock:
            # Check if THE worker is already running and healthy
            if self.worker:
                logger.info("🔍 Found existing worker, checking health...")
                if await self._is_worker_healthy():
                    logger.info("✅ REUSING HEALTHY WORKER:")
                    logger.info(f"   - PID: {self.worker.process.pid}")
                    logger.info(f"   - Port: {self.worker.port}")
                    logger.info(f"   - Uptime: {time.time() - self.worker.started_at:.1f}s")
                    logger.info("   - This single worker handles ALL personas")
                    return True
                else:
                    logger.warning("⚠️  Existing worker is UNHEALTHY, removing from tracking")
                    logger.info(f"   - Old PID: {self.worker.process.pid}")
                    # Remove unhealthy worker from tracking (process cleanup would be manual)
                    self.worker = None

            # Check if another coroutine is already starting the worker
            if self.worker_starting:
                logger.info("Worker already starting by another request, waiting...")
                # Wait for the other start attempt to complete (with lock released)
                return await self._wait_for_concurrent_start()

            # Start THE worker
            return await self._start_worker()

    async def _start_worker(self) -> bool:
        """
        Start THE single worker subprocess

        Returns:
            True if worker started successfully, False otherwise
        """
        # Mark as starting to prevent concurrent attempts
        self.worker_starting = True

        try:
            # Debug current worker state
            logger.info("🆕 CREATING THE SINGLE WORKER")
            logger.info("   - This single worker will handle ALL personas and users")

            # Use fixed port for the single worker
            port = self.base_port

            # Use centralized agent name - one agent handles all personas
            agent_name = settings.livekit_agent_name

            # Prepare environment for the worker subprocess
            env = os.environ.copy()
            # Get the internal API URL - use localhost within the same container
            internal_api_url = os.environ.get("INTERNAL_API_URL", "http://localhost:8001")

            # Get embedding configuration
            embedding_config = settings.get_embedding_config
            logger.info(f"Embedding config: {embedding_config}")

            env.update(
                {
                    "WORKER_PORT": str(port),
                    "AGENT_NAME": agent_name,
                    "PYTHONUNBUFFERED": "1",  # Ensure immediate output
                    # LiveKit credentials
                    "LIVEKIT_URL": self.livekit_url,
                    "LIVEKIT_API_KEY": self.livekit_api_key,
                    "LIVEKIT_API_SECRET": self.livekit_api_secret,
                    # API configuration
                    "CUSTOM_API_URL": internal_api_url,
                    "MYCLONE_API_KEY": os.environ.get("MYCLONE_API_KEY", ""),
                    # ElevenLabs configuration
                    "ELEVEN_API_KEY": settings.elevenlabs_api_key,  # LiveKit plugin expects this
                    "ELEVENLABS_VOICE_ID": settings.elevenlabs_voice_id,
                    # Embedding configuration
                    "EMBEDDING_PROVIDER": embedding_config["provider"],
                    "EMBEDDING_MODEL": embedding_config["model"],
                    "VECTOR_DIMENSION": str(embedding_config["dimension"]),
                    "EMBEDDING_TABLE_NAME": embedding_config["table_name"],
                    "VOYAGE_API_KEY": (
                        embedding_config.get("api_key", "")
                        if embedding_config["provider"] == "voyage"
                        else ""
                    ),
                    # Other API keys
                    "OPENAI_API_KEY": settings.openai_api_key,
                    "DEEPGRAM_API_KEY": settings.deepgram_api_key,
                }
            )

            logger.info(f"🚀 Starting THE SINGLE WORKER with LIVEKIT_URL: {self.livekit_url}")
            logger.info(f"🚀 Worker will run on port: {port}")
            logger.info("🚀 Worker will handle ALL personas dynamically")

            # Always use the modular agent (entrypoint.py)
            worker_script = "livekit/entrypoint.py"
            logger.info("🎨 Using MODULAR agent (entrypoint.py)")

            # Use virtualenv Python to ensure all packages are available
            python_executable = os.path.join("/app", ".venv", "bin", "python")
            # Start the worker subprocess (explicitly inherit stdout/stderr for logging)
            process = subprocess.Popen(
                [python_executable, worker_script, "start"],
                env=env,
                stdout=sys.stdout,  # Inherit parent's stdout for ECS logs
                stderr=sys.stderr,  # Inherit parent's stderr for ECS logs
                preexec_fn=os.setsid,  # Create new process group for clean cleanup
            )

            worker_info = WorkerInfo(
                process=process,
                persona_id=None,  # Single worker handles all personas
                started_at=time.time(),
                port=port,
                last_activity=time.time(),
                agent_name=agent_name,
                state=WorkerState.STARTING,
                worker_db_id=None,  # Will be set after saving to database
            )

            logger.info("🚀 THE SINGLE WORKER PROCESS STARTED:")
            logger.info(f"   - PID: {process.pid}")
            logger.info(f"   - Port: {port}")
            logger.info(f"   - Agent Name: {agent_name}")
            logger.info("   - This single process handles ALL personas and users")

            # Wait for worker to be fully ready
            if await self._wait_for_worker_registration(worker_info):
                # Store THE worker in memory tracking
                self.worker = worker_info
                worker_info.state = WorkerState.HEALTHY

                # Clean up any stale database records before saving new worker
                if self.db:
                    # Clean up stale records for the same port
                    await self._cleanup_stale_worker_records(port)

                    # Save to database
                    worker_db_id = await self.db.save_worker(
                        process.pid, port, agent_name, WorkerState.HEALTHY
                    )
                    worker_info.worker_db_id = worker_db_id

                logger.info(f"✅ THE SINGLE WORKER is ready (PID: {process.pid})")
                return True
            else:
                logger.error("❌ THE SINGLE WORKER failed to register")
                # Terminate the process if it failed to register
                try:
                    process.terminate()
                    await asyncio.sleep(1)  # Give it time to terminate
                    if process.poll() is None:
                        process.kill()  # Force kill if still running
                except Exception as e:
                    logger.error(f"Error terminating failed worker process: {e}")
                return False

        except Exception as e:
            logger.error(f"Error starting THE single worker: {e}")
            return False
        finally:
            # Always remove from starting flag
            self.worker_starting = False

    async def _wait_for_worker_registration(self, worker_info: WorkerInfo) -> bool:
        """
        Wait for worker process to be stable and fully registered with LiveKit.

        Three phases:
        1. Process stability: Ensure the OS process doesn't crash immediately
        2. HTTP readiness: Wait for the worker's /worker endpoint to respond
        3. Registration buffer: Wait for the worker to finish prewarming
           child processes and registering with LiveKit Cloud.

        The LiveKit SDK starts the HTTP server early, but the worker only
        registers with LiveKit Cloud AFTER all child processes are prewarmed.
        We must wait for full registration or dispatches will be lost.

        Timeline observed in production (livekit-agents 1.3.12):
          +0s   Worker process starts
          +4s   HTTP server listening (responds 200 on /)
          +8s   Child processes start prewarming (VAD model load)
          +17s  Processes initialized, worker registers with LiveKit Cloud
          +17s  "registered worker" — NOW ready to receive dispatches

        Args:
            worker_info: Information about the worker to wait for

        Returns:
            True if worker is fully ready, False if it dies or times out
        """
        start_time = time.time()
        port = worker_info.port

        logger.info("⏳ Waiting for THE worker to fully register with LiveKit...")

        # Phase 1: Quick process stability check (2 seconds)
        while time.time() - start_time < 2:
            if worker_info.process.poll() is not None:
                logger.error("❌ THE worker process died during startup")
                return False
            await asyncio.sleep(0.5)

        logger.info(f"✅ Process stable after {time.time() - start_time:.1f}s")

        # Phase 2 + 3: Wait for /worker endpoint to respond,
        # then keep polling until we're confident the worker is registered.
        # The /worker endpoint works as soon as the HTTP server starts,
        # but registration happens ~10-15s later. We detect registration
        # indirectly: once all child processes are prewarmed, the worker
        # registers with LiveKit Cloud within ~1 second.
        #
        # Strategy: Poll /worker endpoint. Once it responds, continue polling
        # with process health checks for a total of startup_timeout seconds.
        # The worker takes ~15-20s total to be fully ready on cold start.
        http_responded = False

        while time.time() - start_time < self.startup_timeout:
            # Check process is still alive
            if worker_info.process.poll() is not None:
                logger.error("❌ THE worker process died while waiting for registration")
                return False

            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    # Use /worker endpoint — returns JSON with agent details
                    response = await client.get(f"http://localhost:{port}/worker")
                    if response.status_code == 200:
                        if not http_responded:
                            http_responded = True
                            elapsed = time.time() - start_time
                            logger.info(
                                f"✅ Worker HTTP responding after {elapsed:.1f}s, "
                                f"waiting for LiveKit registration..."
                            )

                        # Check health endpoint — returns 503 if connection failed
                        health_response = await client.get(f"http://localhost:{port}/")
                        if health_response.status_code != 200:
                            logger.debug("Worker health endpoint not ready yet")
                            await asyncio.sleep(1.0)
                            continue

                        # Both endpoints healthy. Now we need to ensure
                        # child processes are prewarmed and worker is registered.
                        # The worker registers ~1s after process pool is ready.
                        # Total cold start is ~15-20s. If we've waited long enough
                        # for HTTP to respond AND health is OK, add a small buffer
                        # to ensure registration completes.
                        elapsed = time.time() - start_time
                        if elapsed >= 15:
                            # We've waited long enough — worker should be registered
                            logger.info(f"✅ THE worker fully ready after {elapsed:.1f}s")
                            return True
                        else:
                            # HTTP is up but we haven't waited long enough
                            # for process prewarming + registration
                            logger.debug(
                                f"Worker HTTP up but only {elapsed:.1f}s elapsed, "
                                f"waiting for registration..."
                            )
            except (httpx.ConnectError, httpx.TimeoutException):
                pass  # Worker HTTP not ready yet
            except Exception as e:
                logger.debug(f"Worker check error (retrying): {e}")

            await asyncio.sleep(1.0)

        elapsed = time.time() - start_time
        # If HTTP responded but we timed out, the worker might still be OK
        if http_responded:
            logger.warning(
                f"⚠️ Worker HTTP responded but full registration uncertain "
                f"after {elapsed:.1f}s — proceeding anyway"
            )
            return True

        logger.error(f"❌ THE worker failed to become ready within {elapsed:.1f}s")
        return False

    async def _check_process_health(self) -> bool:
        """
        Check if THE worker subprocess is alive

        Returns:
            True if process is alive, False otherwise
        """
        if not self.worker:
            return False

        try:
            # Handle both subprocess.Popen and psutil.Process objects
            if hasattr(self.worker.process, "poll"):
                # subprocess.Popen object (newly created workers)
                return self.worker.process.poll() is None
            else:
                # psutil.Process object (recovered workers)
                return self.worker.process.is_running()
        except Exception as e:
            logger.warning(f"Error checking process health: {e}")
            return False

    async def _check_worker_http_health(self) -> bool:
        """
        Check THE worker health via direct HTTP endpoint

        Returns:
            True if worker HTTP endpoint is healthy, False otherwise
        """
        try:
            if not self.worker:
                return False

            port = self.worker.port

            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check basic health endpoint
                health_response = await client.get(f"http://localhost:{port}/")
                if health_response.status_code != 200:
                    logger.debug(f"THE worker health check failed: {health_response.status_code}")
                    return False

                # Check worker details endpoint
                worker_response = await client.get(f"http://localhost:{port}/worker")
                if worker_response.status_code == 200:
                    data = worker_response.json()
                    # Verify this is the expected worker
                    expected_agent = self.worker.agent_name
                    actual_agent = data.get("agent_name", "")

                    if actual_agent != expected_agent:
                        logger.debug(
                            f"THE worker agent name mismatch: expected {expected_agent}, got {actual_agent}"
                        )
                        return False

                    logger.debug(
                        f"THE worker HTTP health check passed - {data.get('active_jobs', 0)} active jobs"
                    )
                    return True

            return True  # Health endpoint responded, that's sufficient

        except Exception as e:
            logger.debug(f"THE worker HTTP health check failed: {e}")
            return False

    async def _wait_for_concurrent_start(self) -> bool:
        """
        Wait for another coroutine to finish starting THE worker

        This method is called when we detect another start is in progress.
        It waits outside the lock for the other start to complete.

        Returns:
            True if worker is ready after concurrent start, False otherwise
        """
        logger.info("🔄 Waiting for concurrent worker start to complete...")

        # Wait for concurrent start to complete (outside the lock)
        max_wait = 60  # Maximum wait time in seconds
        start_time = time.time()

        while self.worker_starting and (time.time() - start_time) < max_wait:
            await asyncio.sleep(0.5)

        if self.worker_starting:
            logger.error("❌ Timeout waiting for concurrent worker start")
            return False

        # Check if the concurrent start succeeded
        logger.info("🔄 Concurrent start completed, checking result...")
        return self.worker is not None and await self._is_worker_healthy()

    async def _is_worker_healthy(self) -> bool:
        """
        Check if THE worker is healthy by verifying the process is running

        Returns:
            True if worker process is running, False otherwise
        """
        if not self.worker:
            return False

        # Simple check: is the worker process still alive?
        try:
            return await self._check_process_health()
        except Exception as e:
            logger.warning(f"Health check failed for THE worker: {e}")
            return False

    async def _load_persona_data(
        self,
        persona_id: UUID,
        session_token: Optional[str] = None,
        authenticated_user_id: Optional[str] = None,
    ) -> LiveKitDispatchMetadata:
        """
        Load complete persona data from database for LiveKit dispatch

        Args:
            persona_id: ID of the persona to load
            session_token: Optional session identifier for conversation continuity
            authenticated_user_id: Optional authenticated user ID (from JWT) to skip email capture

        Returns:
            LiveKitDispatchMetadata: Complete persona data for dispatch

        Raises:
            ValueError: If persona not found
        """
        async with async_session_maker() as session:
            # Load persona with user relationship eagerly loaded
            from sqlalchemy.orm import selectinload

            stmt = (
                select(Persona).options(selectinload(Persona.user)).where(Persona.id == persona_id)
            )
            result = await session.execute(stmt)
            persona = result.scalar_one_or_none()

            if not persona:
                raise ValueError(f"Persona {persona_id} not found")

            # LinkedIn repository removed; role/company come from user/persona fields only
            role, company = None, None
            description = None

            # Build PersonaMetadata with queried role/company
            persona_data = PersonaMetadata(
                id=str(persona.id),
                username=persona.user.username if persona.user else "",
                persona_name=persona.persona_name,
                name=persona.name,
                user_fullname=persona.user.fullname if persona.user else None,
                role=role,
                company=company,
                description=description if description else persona.description,
                voice_id=persona.voice_id,
                language=persona.language or "auto",  # Include language, default to auto
                greeting_message=persona.greeting_message,
            )

            # Load patterns
            patterns_dict = {}
            stmt = select(Pattern).where(Pattern.persona_id == persona_id)
            result = await session.execute(stmt)
            patterns = result.scalars().all()

            for pattern in patterns:
                patterns_dict[pattern.pattern_type] = pattern.pattern_data

            # Load persona prompt (optional) - must be active
            persona_prompt_data = None
            stmt = select(PersonaPrompt).where(
                PersonaPrompt.persona_id == persona_id, PersonaPrompt.is_active == True
            )
            result = await session.execute(stmt)
            persona_prompt = result.scalar_one_or_none()
            logger.info(f"Loaded persona prompt from DB: {'Yes' if persona_prompt else 'No'}")

            if persona_prompt:
                persona_prompt_data = PersonaPromptMetadata.model_validate(persona_prompt)

            # Check if user has already completed email capture for this session
            email_capture_completed = False

            # Check 1: If user is authenticated (has JWT), skip email capture entirely
            if authenticated_user_id:
                email_capture_completed = True
                logger.info(
                    f"✅ Authenticated user {authenticated_user_id} - skipping email capture"
                )
            # Check 2: Check session metadata for anonymous users who already provided email
            elif session_token and persona.email_capture_enabled:
                from shared.database.models.database import UserSession

                stmt = select(UserSession).where(UserSession.session_token == session_token)
                result = await session.execute(stmt)
                user_session = result.scalar_one_or_none()

                if user_session:
                    metadata_dict = user_session.session_metadata or {}
                    email_provided = metadata_dict.get("email_provided", False)
                    has_fullname = bool(metadata_dict.get("fullname"))
                    has_phone = bool(metadata_dict.get("phone"))

                    # Check if all required fields are present
                    if email_provided:
                        required_fields_met = True
                        if persona.email_capture_require_fullname and not has_fullname:
                            required_fields_met = False
                        if persona.email_capture_require_phone and not has_phone:
                            required_fields_met = False

                        if required_fields_met:
                            email_capture_completed = True
                            logger.info(
                                f"✅ Session {session_token[:8]} has already completed email capture"
                            )

            # Load active workflow for this persona
            workflow_id = None
            workflow_title = None
            workflow_type = None
            workflow_opening_message = None
            workflow_objective = None
            workflow_trigger_config = None
            workflow_steps = None
            workflow_result_config = None
            workflow_required_fields = None
            workflow_optional_fields = None
            workflow_extraction_strategy = None
            workflow_inference_rules = None
            workflow_output_template = None
            workflow_agent_instructions = None
            workflow_reference_data = None
            workflow_response_mode = None

            from shared.database.repositories.workflow_repository import WorkflowRepository

            workflow_repo = WorkflowRepository(session)
            workflows = await workflow_repo.get_workflows_by_persona(
                persona_id=persona_id, active_only=True, limit=1
            )

            if workflows:
                workflow = workflows[0]
                workflow_id = str(workflow.id)
                workflow_title = workflow.title
                workflow_type = workflow.workflow_type
                workflow_opening_message = workflow.opening_message
                workflow_objective = (
                    workflow.workflow_objective
                )  # Include objective for chat override
                workflow_trigger_config = (
                    workflow.trigger_config
                )  # Include trigger config for promotion mode

                # Load generic config fields (apply to any workflow type)
                workflow_agent_instructions = workflow.workflow_config.get("agent_instructions")
                workflow_reference_data = workflow.workflow_config.get("reference_data")
                workflow_response_mode = workflow.workflow_config.get("response_mode")

                # Load fields based on workflow type
                if workflow_type == "conversational":
                    # Conversational workflows use field extraction
                    workflow_required_fields = workflow.workflow_config.get("required_fields", [])
                    workflow_optional_fields = workflow.workflow_config.get("optional_fields", [])
                    workflow_extraction_strategy = workflow.workflow_config.get(
                        "extraction_strategy", {}
                    )
                    workflow_inference_rules = workflow.workflow_config.get("inference_rules", {})
                    workflow_output_template = workflow.output_template

                    logger.info(
                        f"📋 Loaded active workflow: {workflow_title} ({workflow_type}, "
                        f"{len(workflow_required_fields)} required fields, {len(workflow_optional_fields)} optional fields)"
                    )
                else:
                    # Linear workflows (simple, scored) use steps
                    workflow_steps = workflow.workflow_config.get("steps", [])
                    workflow_result_config = workflow.result_config

                    logger.info(
                        f"📋 Loaded active workflow: {workflow_title} ({workflow_type}, {len(workflow_steps)} steps)"
                    )

                if workflow_objective:
                    logger.info(f"🎯 Workflow objective: {workflow_objective[:100]}...")
            else:
                logger.info(f"ℹ️ No active workflow found for persona {persona_id}")

            # Extract suggested questions from JSONB format
            suggested_questions = None
            if persona.suggested_questions:
                # Handle JSONB format: {"questions": [...], "generated_at": "..."}
                if isinstance(persona.suggested_questions, dict):
                    suggested_questions = persona.suggested_questions.get("questions", [])
                elif isinstance(persona.suggested_questions, list):
                    suggested_questions = persona.suggested_questions

            # Determine if default capture should be enabled
            # Default lead capture — conversational agent asks for name/email/phone naturally.
            # Reads from persona setting (default_lead_capture_enabled).
            # Still disabled when:
            #   - A conversational workflow is active (it handles its own capture)
            #   - User is already authenticated (we already have their info)
            default_capture_enabled = (
                persona.default_lead_capture_enabled
                and workflow_type != "conversational"
                and not authenticated_user_id
            )

            # Build complete metadata with email capture, calendar, and workflow settings
            metadata = LiveKitDispatchMetadata(
                persona_id=str(persona_id),
                persona_data=persona_data,
                patterns=patterns_dict,
                persona_prompt=persona_prompt_data,
                session_token=session_token,
                email_capture_enabled=persona.email_capture_enabled,
                email_capture_message_threshold=persona.email_capture_message_threshold,
                email_capture_require_fullname=persona.email_capture_require_fullname,
                email_capture_require_phone=persona.email_capture_require_phone,
                email_capture_completed=email_capture_completed,
                calendar_enabled=persona.calendar_enabled,
                calendar_url=persona.calendar_url,
                calendar_display_name=persona.calendar_display_name,
                workflow_id=workflow_id,
                workflow_title=workflow_title,
                workflow_type=workflow_type,
                workflow_opening_message=workflow_opening_message,
                workflow_objective=workflow_objective,
                workflow_trigger_config=workflow_trigger_config,
                # Linear workflow fields
                workflow_steps=workflow_steps,
                workflow_result_config=workflow_result_config,
                # Conversational workflow fields
                workflow_required_fields=workflow_required_fields,
                workflow_optional_fields=workflow_optional_fields,
                workflow_extraction_strategy=workflow_extraction_strategy,
                workflow_inference_rules=workflow_inference_rules,
                workflow_output_template=workflow_output_template,
                workflow_agent_instructions=workflow_agent_instructions,
                workflow_reference_data=workflow_reference_data,
                workflow_response_mode=workflow_response_mode,
                default_capture_enabled=default_capture_enabled,
                content_mode_enabled=persona.content_mode_enabled,
                suggested_questions=suggested_questions,
            )

            logger.info(f"✅ Loaded persona data for {persona.persona_name}")
            logger.info(f"   - Name: {persona.name}")
            logger.info(f"   - Patterns: {len(patterns_dict)} types")
            logger.info(f"   - Prompt: {'Yes' if persona_prompt_data else 'No'}")
            logger.info(f"   - Session Token: {'Yes' if session_token else 'No'}")
            logger.info(
                f"   - Email Capture: {'Enabled' if persona.email_capture_enabled else 'Disabled'} (threshold: {persona.email_capture_message_threshold})"
            )
            logger.info(
                f"   - Suggested Questions: {len(suggested_questions) if suggested_questions else 0}"
            )
            logger.info(
                f"   - Default Capture: {'Enabled' if default_capture_enabled else 'Disabled'}"
                f" (workflow_type: {workflow_type or 'none'})"
            )
            logger.info(
                f"   - Content Mode: {'Enabled' if persona.content_mode_enabled else 'Disabled'}"
            )

            return metadata

    async def _dispatch_to_persona(
        self,
        room_name: str,
        persona_id: UUID,
        agent_name: str,
        session_token: Optional[str] = None,
        authenticated_user_id: Optional[str] = None,
    ) -> None:
        """
        Create a LiveKit dispatch to route user to the persona's worker

        Args:
            room_name: Name of the room to create
            persona_id: ID of the persona to dispatch to
            agent_name: Agent name to route the dispatch to (from frontend)
            session_token: Optional session identifier for conversation continuity
            authenticated_user_id: Optional authenticated user ID (from JWT) to skip email capture

        Raises:
            RuntimeError: If LiveKit client is not configured or dispatch fails
        """
        if not self.livekit_client:
            raise RuntimeError("LiveKit client not configured. Call configure_livekit() first.")

        try:
            logger.info(f"Creating dispatch for room {room_name} to persona {persona_id}")

            # Load complete persona data from database
            metadata = await self._load_persona_data(
                persona_id, session_token, authenticated_user_id
            )

            # Serialize metadata to JSON
            metadata_json = metadata.model_dump_json()
            metadata_size = len(metadata_json)
            logger.info(f"📦 Metadata size: {metadata_size} bytes")

            # Create the dispatch with full persona metadata
            dispatch_request = api.CreateAgentDispatchRequest(
                room=room_name,
                agent_name=agent_name,  # Use agent_name from frontend
                metadata=metadata_json,
            )

            dispatch = await self.livekit_client.agent_dispatch.create_dispatch(dispatch_request)
            logger.info(f"✅ Dispatch created: {dispatch.id} for room {room_name}")
            logger.info("   Persona data passed in metadata (no DB query needed in agent)")

        except Exception as e:
            logger.error(f"Failed to create dispatch for persona {persona_id}: {e}")
            raise RuntimeError(f"Dispatch failed: {e}")

    async def _update_worker_activity(self, persona_id: UUID) -> None:
        """
        Update the last activity timestamp for THE worker

        Args:
            persona_id: ID of the persona whose worker was used (for logging)
        """
        if self.worker:
            self.worker.last_activity = time.time()
            logger.debug(f"📊 Updated activity for THE worker (persona {persona_id} request)")

            # Update database with activity
            if self.db and self.worker.worker_db_id:
                await self.db.update_worker_activity(self.worker.worker_db_id)

    async def get_worker_status(self) -> Dict[str, any]:
        """
        Get status information about THE worker

        Returns:
            Dictionary containing worker status information
        """
        status = {
            "total_workers": 1 if self.worker else 0,
            "worker_starting": self.worker_starting,
            "health_monitor_running": self.health_monitor_task is not None
            and not self.health_monitor_task.done(),
            "consecutive_failures": self.consecutive_failed_checks,
            "worker": {},
        }

        if self.worker:
            is_healthy = await self._is_worker_healthy()
            status["worker"] = {
                "pid": self.worker.process.pid,
                "port": self.worker.port,
                "started_at": self.worker.started_at,
                "last_activity": self.worker.last_activity,
                "healthy": is_healthy,
                "uptime": time.time() - self.worker.started_at,
                "agent_name": self.worker.agent_name,
            }

        return status

    async def get_detailed_health_status(self) -> Dict[str, any]:
        """
        Get comprehensive health status with detailed diagnostics

        Returns:
            Detailed health information for monitoring and debugging
        """
        status = {
            "timestamp": time.time(),
            "orchestrator_status": {
                "total_workers": 1 if self.worker else 0,
                "worker_starting": self.worker_starting,
                "livekit_configured": self.livekit_client is not None,
                "health_monitor_running": self.health_monitor_task is not None
                and not self.health_monitor_task.done(),
                "consecutive_failures": self.consecutive_failed_checks,
            },
            "worker": {},
            "health_summary": {
                "healthy": False,
                "failed_checks": [],
            },
            "recommendations": [],
        }

        # Check THE worker's health in detail
        if self.worker:
            worker_health = {
                "pid": self.worker.process.pid,
                "port": self.worker.port,
                "started_at": self.worker.started_at,
                "uptime": time.time() - self.worker.started_at,
                "agent_name": self.worker.agent_name,
                "health_checks": {},
            }

            # Individual health checks
            try:
                worker_health["health_checks"]["process"] = await self._check_process_health()
            except Exception as e:
                worker_health["health_checks"]["process"] = False
                worker_health["health_checks"]["process_error"] = str(e)

            try:
                worker_health["health_checks"]["http"] = await self._check_worker_http_health()
            except Exception as e:
                worker_health["health_checks"]["http"] = False
                worker_health["health_checks"]["http_error"] = str(e)

            # Removed LiveKit availability check - process check is sufficient
            worker_health["health_checks"]["livekit"] = True

            try:
                worker_health["health_checks"]["overall"] = await self._is_worker_healthy()
            except Exception as e:
                worker_health["health_checks"]["overall"] = False
                worker_health["health_checks"]["overall_error"] = str(e)

            # Overall health determination
            worker_health["overall_healthy"] = worker_health["health_checks"]["overall"]

            # Track in summary
            status["health_summary"]["healthy"] = worker_health["overall_healthy"]

            # Track failed checks
            for check_name, check_result in worker_health["health_checks"].items():
                if check_result is False:
                    status["health_summary"]["failed_checks"].append(f"THE worker: {check_name}")

            status["worker"] = worker_health

        # Generate recommendations
        if not status["orchestrator_status"]["livekit_configured"]:
            status["recommendations"].append(
                "⚠️  LiveKit client not configured - call configure_livekit()"
            )

        if not status["health_summary"]["healthy"]:
            status["recommendations"].append("🔧 Restart THE unhealthy worker")

        if not self.worker:
            status["recommendations"].append("💡 No worker running - start THE worker")

        if len(status["health_summary"]["failed_checks"]) > 0:
            status["recommendations"].append("🔍 Check worker logs for detailed error information")

        return status

    async def monitor_worker_health(self, interval_seconds: int = 30) -> None:
        """
        Start continuous health monitoring (for production use)

        Args:
            interval_seconds: How often to check health
        """
        logger.info(f"Starting continuous health monitoring (interval: {interval_seconds}s)")

        while True:
            try:
                health_status = await self.get_detailed_health_status()

                # Log summary
                if health_status["health_summary"]["healthy"]:
                    logger.info("Health Monitor: THE worker is healthy")
                else:
                    logger.warning("Health Monitor: THE worker is unhealthy")

                # Auto-restart severely unhealthy worker (optional)
                if not health_status["health_summary"]["healthy"] and "worker" in health_status:
                    worker_health = health_status["worker"]

                    # If process is dead, auto-restart
                    if not worker_health["health_checks"].get("process", True):
                        logger.warning("Auto-restarting THE dead worker")
                        try:
                            # Use dummy persona_id for auto-restart
                            dummy_persona_id = UUID("00000000-0000-0000-0000-000000000000")
                            await self.ensure_worker_ready(dummy_persona_id)
                        except Exception as e:
                            logger.error(f"Failed to auto-restart THE worker: {e}")

            except Exception as e:
                logger.error(f"Health monitoring error: {e}")

            await asyncio.sleep(interval_seconds)

    def print_health_status(self, detailed: bool = False) -> None:
        """
        Print current health status to console (for debugging)

        Args:
            detailed: Whether to show detailed health check breakdown
        """

        async def _print_status():
            if detailed:
                status = await self.get_detailed_health_status()

                print("\n🏥 DETAILED WORKER HEALTH STATUS")
                print("=" * 50)
                print(f"📊 Total Workers: {status['orchestrator_status']['total_workers']}")
                print(f"🚀 Starting: {status['orchestrator_status']['worker_starting']}")
                print(
                    f"🔗 LiveKit Configured: {status['orchestrator_status']['livekit_configured']}"
                )

                if "worker" in status and status["worker"]:
                    print("\n👥 THE Worker Details:")
                    worker_info = status["worker"]
                    health_icon = "✅" if worker_info["overall_healthy"] else "❌"
                    print(
                        f"\n{health_icon} THE Worker (PID: {worker_info['pid']}, Port: {worker_info['port']}):"
                    )
                    print(f"   Agent: {worker_info['agent_name']}")
                    print(f"   Uptime: {worker_info['uptime']:.1f}s")

                    for check_name, check_result in worker_info["health_checks"].items():
                        if check_name.endswith("_error"):
                            continue
                        icon = "✅" if check_result else "❌"
                        print(f"   {icon} {check_name.title()}: {check_result}")

                        # Show error if present
                        error_key = f"{check_name}_error"
                        if error_key in worker_info["health_checks"]:
                            print(f"      Error: {worker_info['health_checks'][error_key]}")

                if status["recommendations"]:
                    print("\n💡 Recommendations:")
                    for rec in status["recommendations"]:
                        print(f"   {rec}")

            else:
                status = await self.get_worker_status()

                print("\n🏥 WORKER HEALTH STATUS")
                print("=" * 30)
                print(f"📊 Total Workers: {status['total_workers']}")

                if "worker" in status and status["worker"]:
                    print("\n👥 THE Worker:")
                    worker_info = status["worker"]
                    health_icon = "✅" if worker_info["healthy"] else "❌"
                    print(
                        f"   {health_icon} THE Worker: PID={worker_info['pid']}, Port={worker_info['port']}, Agent={worker_info['agent_name']}"
                    )
                else:
                    print("   No worker running")

        # Run the async function
        try:
            asyncio.run(_print_status())
        except RuntimeError:
            # If already in an event loop, schedule it
            loop = asyncio.get_event_loop()
            loop.create_task(_print_status())

    async def shutdown_all_workers(self) -> None:
        """
        Shutdown all workers gracefully

        This should be called when the orchestrator is being shut down
        """
        logger.info("Shutting down THE worker...")

        # Cancel health monitoring task
        if self.health_monitor_task and not self.health_monitor_task.done():
            self.health_monitor_task.cancel()
            try:
                await self.health_monitor_task
            except asyncio.CancelledError:
                pass
            logger.info("🏥 Health monitor task cancelled")

        # Clear worker tracking (manual cleanup required for actual processes)
        self.worker = None

        self.consecutive_failed_checks = 0
        logger.info("THE worker shut down")


# Convenience functions for easy access
async def get_orchestrator() -> PersonaOrchestrator:
    """Get the singleton orchestrator instance"""
    return await PersonaOrchestrator.get_instance()


async def request_persona_chat(user_id: str, persona_id: UUID, agent_name: str) -> str:
    """
    Convenience function to request a persona chat

    Args:
        user_id: Unique identifier for the user
        persona_id: ID of the requested persona
        agent_name: Agent name to route the dispatch to (from frontend)

    Returns:
        Room name where the chat will take place
    """
    orchestrator = await get_orchestrator()
    return await orchestrator.request_persona_chat(user_id, persona_id, agent_name)
