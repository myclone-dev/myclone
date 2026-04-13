from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import List

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Import Base from database.py to ensure consistency
from .database import Base


class WorkerState(PyEnum):
    STARTING = "starting"
    HEALTHY = "healthy"
    IDLE = "idle"
    TERMINATED = "terminated"


class WorkerProcess(Base):
    __tablename__ = "worker_processes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pid: Mapped[int] = mapped_column(Integer)
    port: Mapped[int] = mapped_column(Integer, unique=True)
    agent_name: Mapped[str] = mapped_column(String(100), unique=True)
    state: Mapped[WorkerState] = mapped_column(
        Enum(WorkerState, name="worker_state_enum", values_callable=lambda x: [e.value for e in x]),
        default=WorkerState.STARTING,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_health_check: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    active_jobs: Mapped[int] = mapped_column(Integer, default=0)
    health_status: Mapped[dict] = mapped_column(JSON, default=dict)

    # Relationship to active rooms
    active_rooms: Mapped[List["ActiveRoom"]] = relationship(
        back_populates="worker", cascade="all, delete-orphan"
    )


class ActiveRoom(Base):
    __tablename__ = "active_rooms"

    room_name: Mapped[str] = mapped_column(String(255), primary_key=True)
    worker_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("worker_processes.id", ondelete="CASCADE")
    )
    persona_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("personas.id"))
    participant_id: Mapped[str] = mapped_column(
        String
    )  # LiveKit participant identifier, not FK to users
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationship to worker process
    worker: Mapped["WorkerProcess"] = relationship(back_populates="active_rooms")

    __table_args__ = (
        Index("ix_active_rooms_worker_id", "worker_id"),
        Index("ix_active_rooms_persona_id", "persona_id"),
    )
