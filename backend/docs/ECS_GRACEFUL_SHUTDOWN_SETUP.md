# ECS Graceful Shutdown Configuration

This document describes how to configure the ECS task definition to support graceful shutdown of voice processing workers.

## Overview

The voice processing worker has been updated to support graceful shutdown during ECS deployments. This ensures that active jobs complete successfully before the worker container is terminated.

## Required ECS Task Definition Changes

### Update stopTimeout

The task definition must be updated to allow workers sufficient time to complete active jobs before being forcefully terminated.

**Required change**: Set `stopTimeout` to 600 seconds (10 minutes)

### Method 1: Using AWS CLI

```bash
# Get current task definition
aws ecs describe-task-definition \
  --task-definition voice-processing-consumer-production \
  --query 'taskDefinition' \
  > task-def.json

# Edit task-def.json and add/update stopTimeout in containerDefinitions:
# {
#   "containerDefinitions": [{
#     "name": "voice-processing-consumer",
#     "stopTimeout": 600,
#     ... other settings ...
#   }]
# }

# Register updated task definition
aws ecs register-task-definition \
  --cli-input-json file://task-def.json

# Update service to use new task definition
aws ecs update-service \
  --cluster myclone-consumer-production-cluster \
  --service voice-processing-consumer-production \
  --task-definition voice-processing-consumer-production:NEW_REVISION
```

### Method 2: Using Terraform

If using Terraform to manage ECS task definitions:

```hcl
resource "aws_ecs_task_definition" "voice_processing_consumer" {
  family = "voice-processing-consumer-production"

  container_definitions = jsonencode([{
    name      = "voice-processing-consumer"
    image     = "..."
    stopTimeout = 600  # Add this line
    # ... other settings ...
  }])

  # ... other task definition settings ...
}
```

### Method 3: Using AWS Console

1. Navigate to ECS → Task Definitions
2. Select `voice-processing-consumer-production`
3. Click "Create new revision"
4. Under "Container definitions", edit the container
5. Scroll to "Docker configuration"
6. Set "Stop timeout" to 600 seconds
7. Save and create new revision
8. Update the service to use the new revision

## Verification

After deploying the updated task definition, verify the configuration:

```bash
aws ecs describe-task-definition \
  --task-definition voice-processing-consumer-production \
  --query 'taskDefinition.containerDefinitions[0].stopTimeout'
```

Expected output: `600`

## How It Works

### ECS Task Lifecycle with Graceful Shutdown

```
1. ECS sends SIGTERM to container
   ↓
2. Worker receives signal and:
   - Stops accepting new jobs immediately
   - Sets shutdown flags
   - Starts graceful_shutdown() task
   ↓
3. Worker waits up to 570 seconds for current job to complete
   ↓
4. If job completes:
   - Closes NATS connection cleanly
   - Exits with status 0
   - ECS terminates container (no SIGKILL needed)

   If job doesn't complete in time:
   - Logs timeout warning
   - ECS sends SIGKILL after 600 seconds
   - Job will be redelivered by NATS
```

### Timeline Example

```
T+0s:   Deployment starts, new worker launches
T+5s:   New worker starts accepting jobs
T+10s:  ECS sends SIGTERM to old worker
T+10s:  Old worker stops accepting new jobs
T+10s:  Old worker has active job processing
T+110s: Active job completes successfully
T+110s: Old worker closes NATS, exits cleanly
T+115s: ECS terminates old worker container
```

## Monitoring

### CloudWatch Logs

Look for these log messages to verify graceful shutdown:

**Shutdown initiated:**
```
🛑 Received signal 15 (SIGTERM) - initiating graceful shutdown
🔄 Graceful shutdown initiated for worker worker_abc123
   Current job: d3c69d32-eb23-4128-82ac-6ff9b0e63537
   Max wait time: 570s
```

**Waiting for job:**
```
⏳ Waiting for job d3c69d32-eb23-4128-82ac-6ff9b0e63537 to complete... (30s elapsed, 540s remaining)
```

**Clean shutdown:**
```
✅ All jobs completed. Clean shutdown after 95s
✅ NATS connection closed cleanly
📊 Worker worker_abc123 final stats: 42/43 succeeded, 1 failed, uptime: 3245.2s
✅ Worker worker_abc123 stopped
```

**Timeout (job too long):**
```
⚠️ Shutdown timeout reached with active job: d3c69d32-eb23-4128-82ac-6ff9b0e63537.
   ECS will force-kill in ~30 seconds. Job may be redelivered by NATS.
```

### CloudWatch Metrics

Monitor these metrics:

- **ECS Task Count**: Should show overlap during deployments (old + new tasks)
- **Task Startup/Shutdown Duration**: Should see ~100-200s shutdown time for active jobs
- **Job Failure Rate**: Should drop to 0% during deployments

## Troubleshooting

### Issue: Jobs still failing during deployment

**Check:**
1. Verify stopTimeout is set to 600: `aws ecs describe-task-definition ...`
2. Check worker logs for graceful shutdown messages
3. Verify worker code has been deployed (check git commit hash in logs)

### Issue: Deployments taking too long

**Normal behavior**: Deployments will take longer now because workers wait for jobs to complete.

- If no active jobs: ~5-10 seconds
- If active job: Up to job duration + 30 seconds

This is expected and ensures zero job failures.

### Issue: Worker killed before job completes

**Possible causes:**
1. Job takes longer than 570 seconds (increase stopTimeout if needed)
2. ECS service deployment circuit breaker timeout
3. Manual task termination

**Solution:**
- For jobs > 10 minutes: Increase stopTimeout to job_max_duration + 30s
- Check ECS service deployment configuration
- Avoid manual task termination during active processing

## Related Changes

- Worker code: `workers/voice_processing/worker.py`
- GitHub Issue: #237
- Implementation PR: (to be added)

## Rollback

If issues occur, rollback by:

1. Deploy previous task definition revision:
```bash
aws ecs update-service \
  --service voice-processing-consumer-production \
  --task-definition voice-processing-consumer-production:PREVIOUS_REVISION
```

2. Or set stopTimeout back to 30 (not recommended - will cause job failures):
```bash
# Edit task definition and set stopTimeout: 30
aws ecs register-task-definition --cli-input-json file://task-def.json
```

## Next Steps

After this change is deployed:

1. Monitor first few deployments closely
2. Verify zero job failures in CloudWatch logs
3. Consider applying same pattern to scraping_consumer worker
4. Document in runbooks for operations team
