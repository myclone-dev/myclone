# LiveKit Recording Architecture

**Purpose**: Audio recording for voice agent conversations using LiveKit egress

**Documentation Date**: 2026-01-20

---

## Overview

This document outlines the architecture for recording voice agent conversations using LiveKit's egress feature. Recordings enable quality assurance, training data collection, user playback, and compliance/audit trails.

## LiveKit Egress Options

### Available Recording Types

1. **Room Composite Egress** (Recommended for our use case)
   - Records entire room (all participants) as single output
   - Captures full conversation: user + AI agent
   - Output formats: MP4 file, HLS segments
   - Storage: S3, local file, RTMP stream
   - Lifecycle: Auto-stops when room ends
   - **Best for**: Full conversation archives

2. **Track Composite Egress**
   - Records specific audio/video tracks separately
   - Granular control: user mic track, agent TTS track
   - **Best for**: Per-speaker processing/analysis

3. **Participant Egress**
   - Records single participant's audio+video
   - Simpler API than Track Composite
   - **Best for**: Single-participant recording

4. **Auto Egress**
   - Automatic recording on room creation
   - Configure via `CreateRoom` egress field
   - **Best for**: Always-on recording policy

## Recommended Approach for Expert Clone

### Primary Strategy: Room Composite Egress

**Why Room Composite?**
- Captures complete conversation context (user questions + agent responses)
- Simpler than managing separate tracks
- Automatic lifecycle management (stops when room ends)
- Single file per session (easier storage/retrieval)

**Storage**: AWS S3 (existing bucket: `myclone-user-data-production`)

**File Organization**:
```
s3://myclone-user-data-production/
  recordings/
    {persona_id}/
      {session_id}.mp4
```

## Architecture Components

### 1. LiveKitEgressService (New)

**Location**: `shared/services/livekit_egress_service.py`

**Responsibilities**:
- Start/stop room recordings
- Configure S3 upload destinations
- Track egress status
- Handle recording errors

**Key Methods**:
```python
class LiveKitEgressService:
    async def start_room_recording(
        room_name: str,
        persona_id: UUID,
        session_id: UUID,
        output_filename: Optional[str] = None
    ) -> Optional[str]:  # Returns egress_id
        """Start recording room conversation to S3"""

    async def stop_recording(egress_id: str) -> bool:
        """Stop active recording"""

    async def get_recording_status(egress_id: str) -> Optional[dict]:
        """Get recording status/metadata"""
```

### 2. Database Schema Updates

**Migration**: `alembic/versions/6b98f2f67c4c_add_recording_fields_to_voice_sessions.py`

**Add to `voice_sessions` table**:
```sql
-- Create enum type first
CREATE TYPE recording_status_enum AS ENUM (
    'disabled', 'starting', 'active', 'stopping',
    'completed', 'failed', 'stopped'
);

-- Add columns
ALTER TABLE voice_sessions ADD COLUMN egress_id VARCHAR(255);
ALTER TABLE voice_sessions ADD COLUMN recording_s3_path TEXT;
ALTER TABLE voice_sessions ADD COLUMN recording_status recording_status_enum DEFAULT 'disabled';
```

**Recording Status Values** (RecordingStatus enum):
- `disabled`: Recording not enabled for this session
- `starting`: Recording initiation in progress
- `active`: Actively recording
- `stopping`: Recording stop in progress
- `completed`: Successfully saved to S3
- `failed`: Recording failed
- `stopped`: Manually stopped

### 3. VoiceSessionOrchestrator (Separation of Concerns)

**Location**: `shared/services/voice_session_orchestrator.py`

**Architecture Pattern**: Orchestrator coordinates two separate services:
- **VoiceUsageService**: Handles usage tracking (duration, heartbeats, quota)
- **LiveKitEgressService**: Handles recording management (start/stop egress)

**Why Separate?**
- Single Responsibility Principle: Usage tracking ≠ Recording management
- Independent failures: Recording errors don't affect usage tracking
- Easier testing: Mock each service independently
- Cleaner code: Each service has focused, specific purpose

**Implementation**:
```python
class VoiceSessionOrchestrator:
    """Coordinates voice session lifecycle: usage tracking + recording"""

    def __init__(self, db: AsyncSession):
        self.usage_service = VoiceUsageService(db)
        self.recording_service = LiveKitEgressService()

    async def start_session(
        self,
        persona_id: UUID,
        room_name: str,
        session_token: Optional[str] = None,
    ) -> VoiceSession:
        """
        Start voice session with usage tracking and optional recording

        Flow:
        1. Create session record (VoiceUsageService)
        2. Start recording if enabled (LiveKitEgressService)
        3. Return session with egress_id populated
        """
        # Step 1: Create session and start usage tracking
        session = await self.usage_service.start_voice_session(
            persona_id=persona_id,
            room_name=room_name,
            session_token=session_token,
        )

        # Step 2: Start recording if enabled (non-blocking)
        if settings.enable_voice_recording:
            try:
                egress_id = await self.recording_service.start_room_recording(
                    room_name=room_name,
                    persona_id=persona_id,
                    session_id=session.id,
                )

                if egress_id:
                    session.egress_id = egress_id
                    session.recording_s3_path = f"recordings/{persona_id}/{session.id}.mp4"
                    session.recording_status = RecordingStatus.ACTIVE

            except Exception as e:
                # Recording failure doesn't block session
                logger.error(f"Failed to start recording: {e}")
                session.recording_status = RecordingStatus.FAILED

        return session

    async def end_session(
        self,
        session_id: UUID,
        final_duration_seconds: int,
    ) -> VoiceSession:
        """
        End voice session: stop recording, update usage

        Flow:
        1. Stop recording if active (LiveKitEgressService)
        2. Update usage tracking (VoiceUsageService)
        3. Return updated session
        """
        session = await self.usage_service.get_session_by_id(session_id)

        # Step 1: Stop recording if active (non-blocking)
        if session.egress_id and session.recording_status == RecordingStatus.ACTIVE:
            try:
                success = await self.recording_service.stop_recording(session.egress_id)
                session.recording_status = RecordingStatus.COMPLETED if success else RecordingStatus.FAILED
            except Exception as e:
                logger.error(f"Failed to stop recording: {e}")
                session.recording_status = RecordingStatus.FAILED

        # Step 2: Update usage tracking
        session = await self.usage_service.end_voice_session(
            session_id=session_id,
            final_duration_seconds=final_duration_seconds,
        )

        return session
```

### 4. API Route Integration

**Location**: `app/api/livekit_routes.py`

**Changes**: Replace `VoiceUsageService` with `VoiceSessionOrchestrator`

**Start Session (Line 229)**:
```python
@router.post("/connection-details", response_model=ConnectionDetailsResponse)
async def get_connection_details(
    request: ConnectionDetailsRequest,
    db: AsyncSession = Depends(get_session),
):
    # Create orchestrator instead of usage service
    session_orchestrator = VoiceSessionOrchestrator(db)

    # Dispatch agent to room
    await orchestrator.request_persona_chat(...)

    # Start session with recording (if enabled)
    voice_session = await session_orchestrator.start_session(
        persona_id=persona.id,
        room_name=room_name,
        session_token=request.session_token,
    )
    # voice_session.egress_id will be populated if recording started

    return ConnectionDetailsResponse(...)
```

**Agent Shutdown Callback (Automatic Cleanup)**:

**⚠️ IMPORTANT**: The `/end` endpoint has been **removed**. Session cleanup is now **agent-driven** via LiveKit shutdown callbacks.

**Location**: `livekit/livekit_agent_retrieval.py:2412-2527`

```python
# In entrypoint() function
async def end_voice_session_callback():
    """
    End voice session when agent shuts down (ALL disconnect scenarios)

    Runs automatically when:
    - User clicks "End Call" (normal disconnect)
    - Browser crashes
    - Network failure
    - Force quit app
    - Tab closed
    """
    try:
        async with async_session_maker() as db_session:
            orchestrator = VoiceSessionOrchestrator(db_session)

            # Find session by room_name (more reliable than session_id)
            voice_session = await orchestrator.usage_service.get_session_by_room(
                ctx.room.name
            )

            if voice_session and voice_session.status == VoiceSessionStatus.ACTIVE:
                # Calculate duration from start time
                duration_seconds = int(
                    (datetime.now(timezone.utc) - voice_session.started_at).total_seconds()
                )

                # Stop recording + update usage (orchestrator handles both)
                await orchestrator.end_session(
                    session_id=voice_session.id,
                    final_duration_seconds=duration_seconds,
                )
                await db_session.commit()

                logger.info(f"✅ Voice session ended by agent shutdown: {voice_session.id}")
    except Exception as e:
        logger.error(f"Failed to end voice session: {e}", exc_info=True)

# Register shutdown callback (runs BEFORE save_conversation)
ctx.add_shutdown_callback(end_voice_session_callback)  # Stop recording + update usage
ctx.add_shutdown_callback(save_conversation_and_send_summary)  # Save chat history
ctx.add_shutdown_callback(flush_trace)
ctx.add_shutdown_callback(cleanup_agent)
```

**Why This Approach?**
- ✅ **Always runs** - Guaranteed cleanup regardless of how user disconnects
- ✅ **No frontend dependency** - Doesn't rely on frontend calling an API
- ✅ **Handles all edge cases** - Crashes, force-quit, network failure, etc.
- ✅ **Simpler** - Single source of truth for session cleanup

### 5. LiveKit Webhooks (Optional Verification Layer)

**Purpose**: Additional verification and metadata collection

With **agent shutdown callbacks** handling cleanup automatically, webhooks serve as:
- ✅ **Verification layer** - Confirm recording actually stopped in LiveKit
- ✅ **Metadata collection** - Get file size, duration from LiveKit
- ✅ **Backup mechanism** - If agent crashes before callback runs

**Webhook Events from LiveKit**:

#### Available Webhook Events

**1. `egress_ended` Event** ⭐ **PRIMARY SOLUTION**

Fires when recording completes (manual stop OR auto-stop when room closes)

```json
{
  "event": "egress_ended",
  "id": "event-uuid",
  "egressInfo": {
    "egressId": "EG_...",
    "roomId": "RM_...",
    "roomName": "persona-123-user-456-1234567890",
    "status": "EGRESS_COMPLETE",  // or EGRESS_FAILED
    "startedAt": 1234567800,
    "endedAt": 1234567890,
    "fileResults": [{
      "filename": "recordings/123/456.mp4",
      "location": "s3://myclone-user-data-production/recordings/123/456.mp4",
      "size": 2048576,
      "duration": 90.5
    }],
    "error": null
  }
}
```

**2. `room_finished` Event**

Fires when room closes (all participants left)

```json
{
  "event": "room_finished",
  "room": {
    "sid": "RM_...",
    "name": "persona-123-user-456-1234567890",
    "numParticipants": 0
  }
}
```

**3. `participant_left` Event**

Fires when user disconnects

```json
{
  "event": "participant_left",
  "room": { "sid": "RM_...", "name": "..." },
  "participant": {
    "identity": "voice_assistant_user_1234",
    "state": "DISCONNECTED"
  }
}
```

#### Webhook Implementation

**Location**: `app/api/livekit_webhook_routes.py` (NEW)

```python
from fastapi import APIRouter, Request, HTTPException, Header
from livekit.webhook import WebhookReceiver

router = APIRouter(prefix="/api/v1/webhooks", tags=["livekit-webhooks"])

@router.post("/livekit")
async def livekit_webhook_handler(
    request: Request,
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_session),
):
    """
    Handle LiveKit webhook events

    Events:
    - egress_ended: Recording completed → Update DB
    - room_finished: Room closed → Cleanup
    - participant_left: User disconnected → Optional handling
    """
    try:
        # 1. Verify webhook signature (security)
        body = await request.body()
        webhook_receiver = WebhookReceiver(
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret
        )
        event = webhook_receiver.receive(body, authorization)

        # 2. Route to appropriate handler
        if event.event == "egress_ended":
            await handle_egress_ended(event.egress_info, db)

        elif event.event == "room_finished":
            await handle_room_finished(event.room, db)

        elif event.event == "participant_left":
            await handle_participant_left(event.room, event.participant, db)

        return {"success": True}

    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        capture_exception_with_context(
            e,
            extra={"event_type": event.event if event else None},
            tags={
                "component": "livekit_webhooks",
                "operation": "webhook_handler",
                "severity": "high",
                "user_facing": "false",
            }
        )
        raise HTTPException(status_code=500, detail=str(e))


async def handle_egress_ended(egress_info: EgressInfo, db: AsyncSession):
    """
    Update recording status when egress completes

    This solves the edge case of stale recordings!
    """
    egress_id = egress_info.egress_id
    status = egress_info.status

    logger.info(f"📥 Webhook: egress_ended, egress_id={egress_id}, status={status}")

    # Find session by egress_id
    result = await db.execute(
        select(VoiceSession).where(VoiceSession.egress_id == egress_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        logger.warning(f"Session not found for egress_id={egress_id}")
        return

    # Update recording status based on LiveKit status
    if status == "EGRESS_COMPLETE":
        session.recording_status = RecordingStatus.COMPLETED

        # Optional: Save file metadata from webhook
        if egress_info.file_results:
            file_result = egress_info.file_results[0]
            session.recording_s3_path = file_result.filename
            # Could also save: file_result.size, file_result.duration

        logger.info(f"✅ Recording completed: session_id={session.id}")

    elif status == "EGRESS_FAILED":
        session.recording_status = RecordingStatus.FAILED
        logger.error(f"❌ Recording failed: session_id={session.id}, error={egress_info.error}")

    await db.commit()


async def handle_room_finished(room: Room, db: AsyncSession):
    """
    Handle room closure (all participants left)

    Verification layer: Confirms session ended properly
    """
    room_name = room.name

    logger.info(f"📥 Webhook: room_finished, room={room_name}")

    # Find active session by room_name
    result = await db.execute(
        select(VoiceSession).where(
            VoiceSession.room_name == room_name,
            VoiceSession.status == VoiceSessionStatus.ACTIVE
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        return

    # Verification: Confirm session ended (should have been handled by agent callback)
    logger.info(f"Webhook verification: Session ended for room {session.id}")

    # Mark session as disconnected
    session.status = VoiceSessionStatus.DISCONNECTED
    session.ended_at = datetime.now(timezone.utc)

    # Recording status will be updated by egress_ended webhook
    # (LiveKit auto-stops egress when room closes)

    await db.commit()
```

#### Webhook Configuration

**LiveKit Cloud Dashboard**:
1. Navigate to: https://cloud.livekit.io/projects/YOUR_PROJECT/settings
2. Go to: **Webhooks** section
3. Add webhook URL: `https://api.myclone.is/api/v1/webhooks/livekit`
4. Enable events:
   - ✅ `egress_ended` (HIGH PRIORITY)
   - ✅ `room_finished` (MEDIUM PRIORITY)
   - ✅ `participant_left` (OPTIONAL)

**Security**: Webhooks are signed with HMAC-SHA256 using your API secret. The `WebhookReceiver` automatically verifies signatures.

#### Benefits Over Polling

**Before (Polling)**:
```
User disconnects → Recording stays "active" in DB → Cron job polls every 15 min → Eventually fixes stale status
```

**After (Webhooks)**:
```
User disconnects → LiveKit: participant_left → room_finished → egress auto-stops → egress_ended webhook → DB updated in real-time
```

✅ **Automatic**: No polling, no cron jobs
✅ **Real-time**: Status updates within seconds
✅ **Reliable**: Handles all edge cases (disconnect, timeout, error)
✅ **Complete**: Get file size, duration, S3 path from webhook
✅ **Idempotent**: Can replay webhooks safely

#### Testing Webhooks Locally

**Option 1: ngrok**
```bash
ngrok http 8001
# Use ngrok URL in LiveKit dashboard
# https://abc123.ngrok.io/api/v1/webhooks/livekit
```

**Option 2: LiveKit CLI**
```bash
livekit-cli webhook simulate \
  --event egress_ended \
  --egress-id EG_test123 \
  --url http://localhost:8001/api/v1/webhooks/livekit
```

## Configuration

### Environment Variables

**Required for Recording**:
```env
# Existing (already configured)
LIVEKIT_URL=wss://livekit.myclone.is
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
USER_DATA_BUCKET=myclone-user-data-production

# NEW: Recording control (optional)
ENABLE_VOICE_RECORDING=true  # Global toggle
RECORDING_FORMAT=mp4  # mp4, webm, or hls
```

### Settings Updates

**Add to `shared/config.py`**:
```python
class Settings(BaseSettings):
    # Existing LiveKit settings...

    # NEW: Recording configuration
    enable_voice_recording: bool = os.getenv("ENABLE_VOICE_RECORDING", "true").lower() == "true"
    recording_format: str = os.getenv("RECORDING_FORMAT", "mp4")
```

## Recording Lifecycle

### Complete Flow Diagram

```
1. Frontend: User clicks "Start Voice Call"
   ↓
2. POST /api/v1/livekit/connection-details
   ↓
3. livekit_routes.py (Line 229):
   session_orchestrator = VoiceSessionOrchestrator(db)
   ↓
4. Orchestrator dispatches LiveKit agent to room
   ↓
5. session_orchestrator.start_session()
   ├─> VoiceUsageService.start_voice_session()
   │   └─> Create session record in DB
   │
   └─> IF settings.enable_voice_recording:
       └─> LiveKitEgressService.start_room_recording()
           ├─> Send AWS credentials to LiveKit Cloud
           ├─> Start Room Composite Egress
           ├─> LiveKit Cloud begins recording audio
           └─> Return egress_id
           ↓
           Update session:
           - session.egress_id = egress_id
           - session.recording_status = RecordingStatus.ACTIVE
           - session.recording_s3_path = "recordings/{persona_id}/{session_id}.mp4"
   ↓
6. User connects to room via frontend
   ↓
7. Conversation happens (user mic + agent TTS → recorded by LiveKit)
   ↓
8. User disconnects (ANY WAY - normal, crash, force-quit, etc.)
   ↓
   Frontend: room.disconnect()  ← Just this! No API call needed
   ↓
9. User leaves LiveKit room
   ↓
10. Agent detects user left → Agent shuts down
    ↓
11. Agent Shutdown Callback: end_voice_session_callback() ✅ AUTOMATIC
    ├─> Find session by room_name
    ├─> Check if session is ACTIVE
    ├─> IF ACTIVE:
    │   ├─> Calculate duration from started_at timestamp
    │   ├─> orchestrator.end_session()
    │   │   ├─> LiveKitEgressService.stop_recording(egress_id)
    │   │   │   └─> LiveKit Cloud: Stop egress
    │   │   │       ↓
    │   │   │       LiveKit: Finalize MP4, upload to S3
    │   │   │       ↓
    │   │   │       ✅ Recording uploaded to S3
    │   │   │
    │   │   └─> VoiceUsageService.end_voice_session()
    │   │       ├─> Mark session COMPLETED
    │   │       ├─> Update duration_seconds
    │   │       └─> Add duration to owner's monthly quota
    │   │
    │   └─> Commit to database
    │
    └─> ELSE: Log "Session already ended" (skip duplicate work)
    ↓
12. Optional: LiveKit Webhook: egress_ended (EGRESS_COMPLETE)
    └─> handle_egress_ended() - Verification layer
        └─> Confirm recording_status = COMPLETED
    ↓
Final State:
- ✅ Recording in S3: recordings/{persona_id}/{session_id}.mp4
- ✅ DB status correct: recording_status = COMPLETED
- ✅ Usage updated: owner's quota charged
- ✅ Works for ALL disconnect scenarios (normal, crash, force-quit)
```

### Timeline Visualization

```
Time:  0s          5s          60s         120s        180s
       |           |           |           |           |
       ↓           ↓           ↓           ↓           ↓
┌──────┴───────────┴───────────┴───────────┴───────────┴──────┐
│  [USER CONNECTS]                          [USER DISCONNECTS] │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │   🎙️  LIVEKIT EGRESS RECORDING ACTIVE              │    │
│  │   (Room Composite - captures all room audio)        │    │
│  │   ├─ User microphone → STT                          │    │
│  │   └─ Agent TTS output                               │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
│  User: "Hello"                                                │
│  Agent: "Hi! How can I help?"                                 │
│  User: "Tell me about your experience"                        │
│  Agent: "I worked at Google for 5 years..."                   │
│  [... conversation continues ...]                             │
└───────────────────────────────────────────────────────────────┘
                                    ↓
                    s3://myclone-user-data-production/
                        recordings/
                          {persona_id}/
                            {session_id}.mp4  ← Full conversation
                                    ↓
                    📥 WEBHOOK: egress_ended
                                    ↓
                    DB: recording_status = COMPLETED
```

### Error Handling

**Recording Failures Should NOT Block Voice Sessions**:
- If `start_room_recording()` fails → log error, continue without recording
- If `stop_recording()` fails → log error, mark as failed (recording may still exist)
- Recording is a **non-critical feature** for voice chat functionality

**Sentry Monitoring**:
```python
# All egress errors captured with context
capture_exception_with_context(
    e,
    extra={
        "egress_id": egress_id,
        "room_name": room_name,
        "persona_id": str(persona_id),
        "s3_path": s3_path,
    },
    tags={
        "component": "livekit_egress",
        "operation": "start_room_recording",
        "severity": "medium",
        "user_facing": "false",
    }
)
```

## Data Access & Privacy

### Recording Ownership

**Recordings belong to**:
- Persona owner (the user who created the persona)
- NOT the conversation participant (anonymous user)

**Access Control**:
```python
async def get_recording_url(
    persona_id: UUID,
    session_id: UUID,
    user_id: UUID  # Requesting user
) -> Optional[str]:
    """
    Get presigned S3 URL for recording download

    Authorization:
    - User must be persona owner
    - Session must belong to persona
    """
    # Verify ownership
    persona = await get_persona(persona_id)
    if persona.user_id != user_id:
        raise PermissionError("Not authorized")

    # Generate presigned URL
    s3_path = f"recordings/{persona_id}/{session_id}.mp4"
    url = generate_presigned_url(s3_path, expires_in=3600)
    return url
```

### GDPR/Privacy Compliance

**Considerations**:
1. **Consent**: Inform users that conversations may be recorded
2. **Retention**: Define retention period (e.g., 30 days, 90 days)
3. **Deletion**: Support user requests to delete recordings
4. **Encryption**: S3 server-side encryption (SSE-S3 or SSE-KMS)

**Implementation**:
```python
# Add to persona settings
class Persona:
    recording_enabled: bool = True  # Per-persona toggle
    recording_retention_days: int = 90  # Auto-delete after 90 days

# Cleanup job (scheduled task)
async def cleanup_expired_recordings():
    """Delete recordings older than retention period"""
    cutoff = datetime.now() - timedelta(days=90)
    expired_sessions = await db.query(VoiceSession).filter(
        VoiceSession.created_at < cutoff,
        VoiceSession.recording_s3_path.isnot(None)
    ).all()

    for session in expired_sessions:
        # Delete from S3
        await s3_client.delete_object(
            Bucket=settings.user_data_bucket,
            Key=session.recording_s3_path
        )
        # Clear database reference
        session.recording_s3_path = None
        session.recording_status = "deleted"
```

## API Endpoints (Future)

### Recording Management Routes

**Location**: `app/api/recording_routes.py` (new file)

```python
# List recordings for a persona
GET /api/v1/personas/{persona_id}/recordings
Response: [
    {
        "session_id": "uuid",
        "created_at": "2026-01-20T10:00:00Z",
        "duration_seconds": 180,
        "recording_status": "completed",
        "s3_path": "recordings/{persona_id}/{session_id}.mp4"
    }
]

# Get presigned URL for download
GET /api/v1/personas/{persona_id}/recordings/{session_id}/download
Response: {
    "download_url": "https://s3.amazonaws.com/...",
    "expires_at": "2026-01-20T11:00:00Z"
}

# Delete recording (GDPR compliance)
DELETE /api/v1/personas/{persona_id}/recordings/{session_id}
Response: {"success": true}
```

## Cost Considerations

### LiveKit Egress Pricing

**LiveKit Cloud** (if using hosted):
- Egress charges based on duration + output
- Room composite: ~$0.015/minute
- Example: 100 sessions/day × 5 min avg = 500 min/day × $0.015 = **$7.50/day** (~$225/month)

**Self-Hosted LiveKit**:
- No egress fees
- Only S3 storage + transfer costs

### S3 Storage Costs

**Audio-only MP4** (typical sizes):
- 128 kbps audio: ~1 MB/minute
- 5-minute conversation: ~5 MB
- 1000 sessions/month: ~5 GB/month
- S3 Standard: $0.023/GB = **~$0.12/month** (negligible)

### Recommendation

Start with **audio-only MP4** to S3:
- Minimal storage costs
- Easy playback (standard format)
- Good quality for QA/training

## Implementation Phases

### Phase 1: Basic Recording (MVP) ✅ **COMPLETED**
- [x] Create `LiveKitEgressService` (shared/services/livekit_egress_service.py)
- [x] Add egress fields to `voice_sessions` table (migration: 6b98f2f67c4c)
- [x] Create `VoiceSessionOrchestrator` to coordinate usage + recording
- [x] Integrate recording start in orchestrator.start_session()
- [x] Integrate recording stop in orchestrator.end_session()
- [x] Update livekit_routes.py to use orchestrator
- [ ] Test recording lifecycle end-to-end (pending)

**Files Created**:
- `shared/services/livekit_egress_service.py` - Egress management
- `shared/services/voice_session_orchestrator.py` - Session coordination
- `alembic/versions/6b98f2f67c4c_add_recording_fields_to_voice_sessions.py` - Database migration
- `docs/LIVEKIT_RECORDING_ARCHITECTURE.md` - Architecture documentation

**Files Modified**:
- `shared/database/models/voice_session.py` - Added recording fields
- `shared/config.py` - Added recording configuration
- `app/api/livekit_routes.py` - Use orchestrator instead of usage service
- `shared/services/voice_usage_service.py` - Removed recording logic (clean separation)

### Phase 2: LiveKit Webhooks (Recommended - Next Priority)
- [ ] Create `app/api/livekit_webhook_routes.py`
- [ ] Implement `handle_egress_ended()` - Update recording status automatically
- [ ] Implement `handle_room_finished()` - Handle disconnected sessions
- [ ] Implement `handle_participant_left()` (optional)
- [ ] Add webhook signature verification (WebhookReceiver)
- [ ] Configure webhook URL in LiveKit Cloud dashboard
- [ ] Test webhooks locally (ngrok or LiveKit CLI)
- [ ] Register routes in main.py

**Benefits**:
- Eliminates need for polling/cron jobs
- Real-time status updates
- Handles all edge cases automatically
- Production-grade reliability

### Phase 3: Access Control
- [ ] Create `RecordingService` for access control
- [ ] Implement presigned URL generation
- [ ] Add owner verification
- [ ] Test download flow

### Phase 4: UI Integration
- [ ] Add recordings list endpoint
- [ ] Add download endpoint
- [ ] Frontend: Recordings page (show list)
- [ ] Frontend: Playback UI (audio player)

### Phase 5: Compliance & Cleanup
- [ ] Add consent disclosure to voice UI
- [ ] Implement retention policy
- [ ] Create cleanup scheduled task
- [ ] Add delete endpoint (GDPR)
- [ ] Enable S3 encryption

## Testing Plan

### Unit Tests
```python
# Test egress service
async def test_start_room_recording():
    service = LiveKitEgressService()
    egress_id = await service.start_room_recording(
        room_name="test-room",
        persona_id=persona_id,
        session_id=session_id
    )
    assert egress_id is not None

async def test_stop_recording():
    service = LiveKitEgressService()
    success = await service.stop_recording(egress_id)
    assert success is True
```

### Integration Tests
```python
# Test full recording lifecycle
async def test_voice_session_recording():
    # 1. Start session
    session = await voice_service.start_voice_session(...)
    assert session.egress_id is not None
    assert session.recording_status == "started"

    # 2. End session
    session = await voice_service.end_voice_session(...)
    assert session.recording_status == "completed"

    # 3. Verify S3 file exists
    exists = await s3_file_exists(session.recording_s3_path)
    assert exists is True
```

### Manual Testing
1. Start voice session via frontend
2. Have conversation with agent
3. End session
4. Check S3 bucket for recording file
5. Download and verify audio quality
6. Verify metadata in database

## Monitoring & Alerts

### Key Metrics (Sentry/Logs)
- Recording start success rate
- Recording failure reasons (S3 auth, egress timeout, etc.)
- Average recording duration
- S3 upload success rate
- Storage usage trends

### Alerts
- **High failure rate** (>10% recording starts fail)
- **S3 quota exceeded** (approaching bucket limit)
- **Orphaned egress** (egress running but session ended)

## References

- [LiveKit Egress Documentation](https://docs.livekit.io/transport/media/ingress-egress/egress/)
- [LiveKit Python SDK - Egress API](https://docs.livekit.io/reference/python/livekit.api.egress/)
- [LiveKit Room Composite Egress](https://docs.livekit.io/transport/media/ingress-egress/egress/#room-composite-egress)

## Next Steps

1. **Review this architecture** with team
2. **Decide on recording policy**:
   - Always record? Per-persona toggle? User opt-in?
   - Retention period?
   - Privacy/GDPR requirements?
3. **Estimate costs** based on expected usage
4. **Implement Phase 1** (basic recording)
5. **Test in staging** before production rollout
