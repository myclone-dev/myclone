"""
LiveKit Worker Database Service

This service provides database operations for managing LiveKit worker processes
and active rooms. It's adapted from the demo app but uses the production
database schema with proper foreign key relationships.

Key differences from demo:
- Uses auto-increment id as primary key (allows multiple workers per persona)
- persona_id is UUID with foreign key to personas table
- worker_id in active_rooms references worker_processes.id
- Uses proper enum types in database
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete, func, select, update

from shared.database.models import ActiveRoom, WorkerProcess, get_session
from shared.database.models.database import async_session_maker
from shared.database.models.livekit import WorkerState

logger = logging.getLogger(__name__)


class LiveKitDatabase:
    """Database service for managing LiveKit workers and rooms"""

    def __init__(self):
        self.session_factory = get_session

    async def save_worker(
        self,
        pid: int,
        port: int,
        agent_name: str,
        state: WorkerState = WorkerState.STARTING,
    ):
        """
        Save/update worker in database

        Handles port conflicts after OOM kills by cleaning up stale records.
        If a worker with the same port exists but different PID (dead process),
        the old record is deleted before creating the new one.

        Returns:
            worker_id: The database ID of the worker (for referencing in active_rooms)
        """
        async with async_session_maker() as session:
            try:
                # Check if worker with same pid AND port exists
                stmt = select(WorkerProcess).where(
                    WorkerProcess.pid == pid,
                    WorkerProcess.port == port,
                )
                result = await session.execute(stmt)
                existing_worker = result.scalar_one_or_none()

                if existing_worker:
                    # Update existing worker (same PID + PORT)
                    existing_worker.agent_name = agent_name
                    existing_worker.state = state
                    existing_worker.last_health_check = datetime.utcnow()
                    existing_worker.last_activity = datetime.utcnow()
                    worker_id = existing_worker.id
                    logger.info(f"💾 Updated worker {worker_id} (PID: {pid}, Port: {port})")
                else:
                    # Check if port is used by a different PID (stale record from OOM kill)
                    port_conflict_stmt = select(WorkerProcess).where(WorkerProcess.port == port)
                    port_conflict_result = await session.execute(port_conflict_stmt)
                    conflicting_worker = port_conflict_result.scalar_one_or_none()

                    if conflicting_worker:
                        # Port conflict detected - delete stale record
                        logger.warning(
                            f"🧹 Port {port} conflict detected: "
                            f"Stale worker (ID: {conflicting_worker.id}, PID: {conflicting_worker.pid}) "
                            f"will be replaced by new worker (PID: {pid})"
                        )

                        # Delete the stale worker (CASCADE will handle active_rooms)
                        delete_stmt = delete(WorkerProcess).where(
                            WorkerProcess.id == conflicting_worker.id
                        )
                        await session.execute(delete_stmt)
                        await session.flush()  # Ensure deletion completes before INSERT

                        logger.info(
                            f"🗑️  Deleted stale worker {conflicting_worker.id} (PID: {conflicting_worker.pid}, Port: {port})"
                        )

                    # Create new worker
                    worker = WorkerProcess(
                        pid=pid,
                        port=port,
                        agent_name=agent_name,
                        state=state,
                    )
                    session.add(worker)
                    await session.flush()  # Get the ID
                    worker_id = worker.id
                    logger.info(f"💾 Created worker {worker_id} (PID: {pid}, Port: {port})")

                await session.commit()
                return worker_id

            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Failed to save worker: {e}")

                from shared.monitoring.sentry_utils import capture_exception_with_context

                capture_exception_with_context(
                    e,
                    extra={
                        "pid": pid,
                        "port": port,
                        "agent_name": agent_name,
                        "state": state.value if isinstance(state, WorkerState) else str(state),
                    },
                    tags={
                        "component": "livekit_database",
                        "operation": "save_worker",
                        "severity": "high",
                        "user_facing": "false",
                    },
                )
                raise

    async def get_worker_by_id(self, worker_id: int) -> Optional[Dict]:
        """Get specific worker by database ID"""
        async with async_session_maker() as session:
            try:
                stmt = select(WorkerProcess).where(WorkerProcess.id == worker_id)
                result = await session.execute(stmt)
                worker = result.scalar_one_or_none()

                if worker:
                    return self._worker_to_dict(worker)
                return None

            except Exception as e:
                logger.error(f"❌ Failed to get worker {worker_id}: {e}")
                return None

    async def get_all_workers_simple(self) -> List[Dict]:
        """Get all workers"""
        async with async_session_maker() as session:
            try:
                stmt = select(WorkerProcess).order_by(WorkerProcess.started_at.desc())
                result = await session.execute(stmt)
                workers = result.scalars().all()

                return [self._worker_to_dict(worker) for worker in workers]

            except Exception as e:
                logger.error(f"❌ Failed to get workers: {e}")
                return []

    async def get_active_workers(self) -> List[Dict]:
        """Get all workers that are not terminated"""
        async with async_session_maker() as session:
            try:
                stmt = (
                    select(WorkerProcess)
                    .where(WorkerProcess.state != WorkerState.TERMINATED)
                    .order_by(WorkerProcess.started_at.desc())
                )
                result = await session.execute(stmt)
                workers = result.scalars().all()

                return [self._worker_to_dict(worker) for worker in workers]

            except Exception as e:
                logger.error(f"❌ Failed to get active workers: {e}")
                return []

    async def get_all_workers(self) -> List[Dict]:
        """Get all workers for startup recovery"""
        async with async_session_maker() as session:
            try:
                stmt = select(WorkerProcess).order_by(WorkerProcess.started_at.desc())
                result = await session.execute(stmt)
                workers = result.scalars().all()

                return [self._worker_to_dict(worker) for worker in workers]

            except Exception as e:
                logger.error(f"❌ Failed to get all workers: {e}")
                return []

    async def update_worker_state(self, worker_id: int, state: WorkerState) -> bool:
        """Update worker state by database ID"""
        async with async_session_maker() as session:
            try:
                stmt = (
                    update(WorkerProcess)
                    .where(WorkerProcess.id == worker_id)
                    .values(state=state, last_health_check=datetime.utcnow())
                )
                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.debug(f"🔄 Updated worker {worker_id} state to {state.value}")
                    return True
                return False

            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Failed to update worker {worker_id} state: {e}")

                from shared.monitoring.sentry_utils import capture_exception_with_context

                capture_exception_with_context(
                    e,
                    extra={
                        "worker_id": worker_id,
                        "state": state.value if isinstance(state, WorkerState) else str(state),
                    },
                    tags={
                        "component": "livekit_database",
                        "operation": "update_worker_state",
                        "severity": "medium",
                        "user_facing": "false",
                    },
                )
                return False

    async def update_worker_activity(self, worker_id: int, active_jobs: int = None) -> bool:
        """Update last activity and job count"""
        async with async_session_maker() as session:
            try:
                values = {
                    "last_activity": datetime.utcnow(),
                    "last_health_check": datetime.utcnow(),
                }

                if active_jobs is not None:
                    values["active_jobs"] = active_jobs

                stmt = update(WorkerProcess).where(WorkerProcess.id == worker_id).values(**values)
                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.debug(f"📊 Updated activity for worker {worker_id}")
                    return True
                return False

            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Failed to update worker {worker_id} activity: {e}")

                from shared.monitoring.sentry_utils import capture_exception_with_context

                capture_exception_with_context(
                    e,
                    extra={
                        "worker_id": worker_id,
                        "active_jobs": active_jobs,
                    },
                    tags={
                        "component": "livekit_database",
                        "operation": "update_worker_activity",
                        "severity": "low",
                        "user_facing": "false",
                    },
                )
                return False

    async def delete_worker(self, worker_id: int) -> bool:
        """Remove worker from database"""
        async with async_session_maker() as session:
            try:
                stmt = delete(WorkerProcess).where(WorkerProcess.id == worker_id)
                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info(f"🗑️  Deleted worker {worker_id} from database")
                    return True
                return False

            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Failed to delete worker {worker_id}: {e}")

                from shared.monitoring.sentry_utils import capture_exception_with_context

                capture_exception_with_context(
                    e,
                    extra={
                        "worker_id": worker_id,
                    },
                    tags={
                        "component": "livekit_database",
                        "operation": "delete_worker",
                        "severity": "medium",
                        "user_facing": "false",
                    },
                )
                return False

    async def cleanup_stale_workers(self, max_age_hours: int = 24) -> List[int]:
        """Clean up old workers"""
        async with async_session_maker() as session:
            try:
                cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)

                # Find stale workers
                stmt = select(WorkerProcess).where(WorkerProcess.last_health_check < cutoff_time)
                result = await session.execute(stmt)
                stale_workers = result.scalars().all()

                cleaned_worker_ids = []
                for worker in stale_workers:
                    # Delete stale worker (CASCADE will handle active_rooms)
                    delete_stmt = delete(WorkerProcess).where(WorkerProcess.id == worker.id)
                    await session.execute(delete_stmt)
                    cleaned_worker_ids.append(worker.id)

                await session.commit()

                if cleaned_worker_ids:
                    logger.info(
                        f"🧹 Cleaned up {len(cleaned_worker_ids)} stale workers: {cleaned_worker_ids}"
                    )

                return cleaned_worker_ids

            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Failed to cleanup stale workers: {e}")

                from shared.monitoring.sentry_utils import capture_exception_with_context

                capture_exception_with_context(
                    e,
                    extra={
                        "max_age_hours": max_age_hours,
                        "cutoff_time": (
                            cutoff_time.isoformat() if "cutoff_time" in locals() else None
                        ),
                    },
                    tags={
                        "component": "livekit_database",
                        "operation": "cleanup_stale_workers",
                        "severity": "medium",
                        "user_facing": "false",
                    },
                )
                return []

    # Active Room Management Methods

    async def add_active_room(
        self, room_name: str, worker_id: int, persona_id: UUID, participant_id: str
    ) -> bool:
        """Add a new active room"""
        async with async_session_maker() as session:
            try:
                room = ActiveRoom(
                    room_name=room_name,
                    worker_id=worker_id,
                    persona_id=persona_id,
                    participant_id=participant_id,
                )
                session.add(room)
                await session.commit()
                logger.info(f"📝 Added active room: {room_name} for worker {worker_id}")
                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Failed to add active room {room_name}: {e}")

                from shared.monitoring.sentry_utils import capture_exception_with_context

                capture_exception_with_context(
                    e,
                    extra={
                        "room_name": room_name,
                        "worker_id": worker_id,
                        "persona_id": str(persona_id),
                        "participant_id": participant_id,
                    },
                    tags={
                        "component": "livekit_database",
                        "operation": "add_active_room",
                        "severity": "high",
                        "user_facing": "true",
                    },
                )
                return False

    async def remove_active_room(self, room_name: str) -> bool:
        """Remove an active room"""
        async with async_session_maker() as session:
            try:
                stmt = delete(ActiveRoom).where(ActiveRoom.room_name == room_name)
                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info(f"🗑️ Removed active room: {room_name}")
                    return True
                return False

            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Failed to remove active room {room_name}: {e}")

                from shared.monitoring.sentry_utils import capture_exception_with_context

                capture_exception_with_context(
                    e,
                    extra={
                        "room_name": room_name,
                    },
                    tags={
                        "component": "livekit_database",
                        "operation": "remove_active_room",
                        "severity": "medium",
                        "user_facing": "false",
                    },
                )
                return False

    async def get_active_rooms_for_worker(self, worker_id: int) -> List[Dict]:
        """Get all active rooms for a specific worker"""
        async with async_session_maker() as session:
            try:
                stmt = select(ActiveRoom).where(ActiveRoom.worker_id == worker_id)
                result = await session.execute(stmt)
                rooms = result.scalars().all()

                return [self._room_to_dict(room) for room in rooms]

            except Exception as e:
                logger.error(f"❌ Failed to get rooms for worker {worker_id}: {e}")
                return []

    async def get_active_rooms_for_persona(self, persona_id: UUID) -> List[Dict]:
        """Get all active rooms for a specific persona (across all workers)"""
        async with async_session_maker() as session:
            try:
                stmt = select(ActiveRoom).where(ActiveRoom.persona_id == persona_id)
                result = await session.execute(stmt)
                rooms = result.scalars().all()

                return [self._room_to_dict(room) for room in rooms]

            except Exception as e:
                logger.error(f"❌ Failed to get rooms for persona {persona_id}: {e}")
                return []

    async def get_all_active_rooms(self) -> List[Dict]:
        """Get all active rooms across all workers"""
        async with async_session_maker() as session:
            try:
                stmt = select(ActiveRoom)
                result = await session.execute(stmt)
                rooms = result.scalars().all()

                return [self._room_to_dict(room) for room in rooms]

            except Exception as e:
                logger.error(f"❌ Failed to get all active rooms: {e}")
                return []

    async def update_room_activity(self, room_name: str) -> bool:
        """Update last activity timestamp for a room"""
        async with async_session_maker() as session:
            try:
                stmt = (
                    update(ActiveRoom)
                    .where(ActiveRoom.room_name == room_name)
                    .values(last_activity=datetime.utcnow())
                )
                result = await session.execute(stmt)
                await session.commit()

                return result.rowcount > 0

            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Failed to update room {room_name} activity: {e}")

                from shared.monitoring.sentry_utils import capture_exception_with_context

                capture_exception_with_context(
                    e,
                    extra={
                        "room_name": room_name,
                    },
                    tags={
                        "component": "livekit_database",
                        "operation": "update_room_activity",
                        "severity": "low",
                        "user_facing": "false",
                    },
                )
                return False

    async def cleanup_rooms_for_worker(self, worker_id: int) -> int:
        """Remove all active rooms for a worker (when worker is cleaned up)"""
        async with async_session_maker() as session:
            try:
                stmt = delete(ActiveRoom).where(ActiveRoom.worker_id == worker_id)
                result = await session.execute(stmt)
                await session.commit()

                count = result.rowcount
                if count > 0:
                    logger.info(f"🗑️ Cleaned up {count} rooms for worker {worker_id}")
                return count

            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Failed to cleanup rooms for worker {worker_id}: {e}")

                from shared.monitoring.sentry_utils import capture_exception_with_context

                capture_exception_with_context(
                    e,
                    extra={
                        "worker_id": worker_id,
                    },
                    tags={
                        "component": "livekit_database",
                        "operation": "cleanup_rooms_for_worker",
                        "severity": "medium",
                        "user_facing": "false",
                    },
                )
                return 0

    async def health_check(self) -> Dict:
        """Database health status"""
        async with async_session_maker() as session:
            try:
                # Basic connectivity test
                await session.execute(select(1))

                # Get worker statistics
                stats_stmt = select(
                    func.count().label("total_workers"),
                    func.count()
                    .filter(WorkerProcess.state == WorkerState.HEALTHY)
                    .label("healthy_workers"),
                    func.count()
                    .filter(WorkerProcess.state == WorkerState.IDLE)
                    .label("idle_workers"),
                    func.count()
                    .filter(WorkerProcess.state == WorkerState.STARTING)
                    .label("starting_workers"),
                    func.count()
                    .filter(WorkerProcess.state == WorkerState.TERMINATED)
                    .label("terminated_workers"),
                    func.min(WorkerProcess.started_at).label("oldest_worker"),
                    func.max(WorkerProcess.started_at).label("newest_worker"),
                )

                stats_result = await session.execute(stats_stmt)
                stats = stats_result.first()

                # Get room statistics
                room_stats_stmt = select(func.count().label("total_rooms"))
                room_stats_result = await session.execute(room_stats_stmt)
                room_stats = room_stats_result.first()

                return {
                    "healthy": True,
                    "total_workers": stats.total_workers,
                    "total_rooms": room_stats.total_rooms,
                    "worker_states": {
                        "healthy": stats.healthy_workers,
                        "idle": stats.idle_workers,
                        "starting": stats.starting_workers,
                        "terminated": stats.terminated_workers,
                    },
                    "oldest_worker": (
                        stats.oldest_worker.isoformat() if stats.oldest_worker else None
                    ),
                    "newest_worker": (
                        stats.newest_worker.isoformat() if stats.newest_worker else None
                    ),
                }

            except Exception as e:
                logger.error(f"❌ Database health check failed: {e}")
                return {"healthy": False, "error": str(e)}

    def _worker_to_dict(self, worker: WorkerProcess) -> Dict:
        """Convert WorkerProcess model to dictionary"""
        return {
            "id": worker.id,
            "pid": worker.pid,
            "port": worker.port,
            "agent_name": worker.agent_name,
            "state": worker.state.value if isinstance(worker.state, WorkerState) else worker.state,
            "started_at": worker.started_at,
            "last_health_check": worker.last_health_check,
            "last_activity": worker.last_activity,
            "active_jobs": worker.active_jobs,
            "health_status": worker.health_status,
        }

    def _room_to_dict(self, room: ActiveRoom) -> Dict:
        """Convert ActiveRoom model to dictionary"""
        return {
            "room_name": room.room_name,
            "worker_id": room.worker_id,
            "persona_id": str(room.persona_id),
            "participant_id": room.participant_id,
            "created_at": room.created_at,
            "last_activity": room.last_activity,
        }


# Singleton instance
_livekit_db: Optional[LiveKitDatabase] = None


def get_livekit_database() -> LiveKitDatabase:
    """Get singleton LiveKit database instance"""
    global _livekit_db
    if _livekit_db is None:
        _livekit_db = LiveKitDatabase()
    return _livekit_db
