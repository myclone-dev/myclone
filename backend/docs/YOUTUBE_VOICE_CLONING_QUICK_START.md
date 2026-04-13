# YouTube Voice Cloning - Quick Start Guide

## Problem
YouTube blocks audio downloads with: `"Sign in to confirm you're not a bot"`

## Solution (In-Memory Cookies)
Pass YouTube cookies via environment variable - they're loaded **once** into memory at startup.

---

## Step 1: Export YouTube Cookies (2 minutes)

### Using Browser Extension
1. Install extension:
   - **Chrome**: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - **Firefox**: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

2. Go to YouTube.com (make sure you're **logged in**)

3. Click extension → Export → Save as `youtube_cookies.txt`

4. Open the file and copy its entire content (it's plain text)

### What It Looks Like
```
# Netscape HTTP Cookie File
.youtube.com	TRUE	/	TRUE	1234567890	VISITOR_INFO1_LIVE	xyz123...
.youtube.com	TRUE	/	FALSE	1234567890	CONSENT	PENDING+123
...
```

---

## Step 2: Deploy to ECS (5 minutes)

### Option A: Environment Variable (Quick Test)

**ECS Task Definition** (`task-definition.json`):
```json
{
  "containerDefinitions": [
    {
      "name": "voice-processing-worker",
      "image": "your-ecr-repo/voice-processing:latest",
      "environment": [
        {
          "name": "YOUTUBE_COOKIES",
          "value": "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\t..."
        }
      ]
    }
  ]
}
```

⚠️ **Caution**: Cookies visible in task definition (less secure)

### Option B: AWS Secrets Manager (Production)

```bash
# 1. Create secret
aws secretsmanager create-secret \
  --name youtube-cookies \
  --secret-string file://youtube_cookies.txt \
  --region us-east-1

# 2. Update task definition
{
  "secrets": [
    {
      "name": "YOUTUBE_COOKIES",
      "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:youtube-cookies"
    }
  ]
}

# 3. Grant IAM permission to ECS task execution role
{
  "Effect": "Allow",
  "Action": ["secretsmanager:GetSecretValue"],
  "Resource": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:youtube-cookies"
}
```

✅ **Best Practice**: Encrypted, auditable, secure

---

## Step 3: Test (1 minute)

```bash
# Test the failing URL from your logs
curl -X 'POST' 'https://api.myclone.is/api/v1/voice-processing/jobs' \
  -H 'Content-Type: application/json' \
  -d '{
    "job_type": "voice_extraction",
    "input_source": "https://www.youtube.com/watch?v=hIMMwqr7W7k",
    "user_id": "20c2737a-51f0-481d-a8b3-2c07bf15396d",
    "output_format": "wav",
    "profile": "elevenlabs",
    "start_time": 0,
    "end_time": 60
  }'

# Monitor ECS logs
aws logs tail /ecs/voice-processing-worker --follow
```

### Expected Success Logs
```
✓ YouTube cookies configured
✓ Using YouTube cookies for authentication
Downloading audio for video hIMMwqr7W7k...
✓ Audio downloaded successfully
Worker worker_abc123 completed job 8f5a5832-0196-446d-8e30-4ffed044189f
```

### Expected Failure Logs (if no cookies)
```
⚠ YOUTUBE_COOKIES not set - YouTube may block downloads
ERROR: [youtube] hIMMwqr7W7k: Sign in to confirm you're not a bot
```

---

## How It Works (Technical Details)

### In-Memory Cookie Loading
```python
# At worker initialization (once per container)
class YouTubeVideoExtractor:
    def __init__(self):
        self.cookies_file = self._setup_cookies()  # Load from env var

    def _setup_cookies(self):
        cookies_content = os.environ.get("YOUTUBE_COOKIES")
        if cookies_content:
            # Create temp file in /tmp (memory-backed tmpfs)
            fd, temp_path = tempfile.mkstemp(dir="/tmp")
            with os.fdopen(fd, 'w') as f:
                f.write(cookies_content)
            return temp_path  # Reuse for all downloads
        return None
```

### Why `/tmp`?
- Docker containers use **tmpfs** (RAM-based filesystem) for `/tmp`
- File written **once** at startup → stays in RAM
- No disk I/O during downloads
- Auto-cleaned when container stops

### Benefits
- ✅ Load once, use many times
- ✅ No file I/O during downloads
- ✅ No permission issues
- ✅ Simple environment variable
- ✅ Works with Secrets Manager

---

## Maintenance

### Cookie Lifespan
- **Typical**: 3-6 months
- **Heavy usage**: 1-3 months
- **Monitor**: Watch for bot detection errors

### When to Refresh
You'll see this error in logs:
```
ERROR: [youtube] Sign in to confirm you're not a bot
```

### How to Refresh
```bash
# 1. Export fresh cookies from browser (Step 1 above)

# 2. Update Secrets Manager
aws secretsmanager update-secret \
  --secret-id youtube-cookies \
  --secret-string file://youtube_cookies.txt

# 3. Restart ECS tasks (they load secrets at startup)
aws ecs update-service \
  --cluster your-cluster \
  --service voice-processing-worker \
  --force-new-deployment
```

---

## Environment Variables

| Variable | Required | Example |
|----------|----------|---------|
| `YOUTUBE_COOKIES` | ✅ Yes | `# Netscape HTTP Cookie File\n.youtube.com...` |
| `YT_DLP_CACHE_DIR` | No | `/tmp/yt-dlp-cache` (already set) |
| `YOUTUBE_API_KEY` | No | For metadata fallback |

---

## Troubleshooting

### "No cookies configured" warning
**Cause**: `YOUTUBE_COOKIES` env var not set or empty

**Fix**:
1. Check ECS task definition has `YOUTUBE_COOKIES` set
2. If using Secrets Manager, verify IAM permissions
3. Check secret ARN is correct

### "Sign in to confirm you're not a bot" persists
**Causes**:
1. Cookies expired → Refresh them
2. Cookies from logged-out account → Must be logged into YouTube
3. Cookie file format incorrect → Should be Netscape format

**Fix**: Export fresh cookies from browser where you're logged into YouTube

### Job succeeds but no audio file
**Cause**: Time range too short (`start_time: 0, end_time: 10` = only 10 seconds)

**Fix**:
- Remove time restriction: Don't pass `start_time`/`end_time`
- Or increase `end_time` to at least 60 seconds

---

## Security Best Practices

1. **Use Secrets Manager** (not env vars) for production
2. **Rotate cookies** every 3-6 months
3. **Never commit** `youtube_cookies.txt` to git:
   ```bash
   echo "youtube_cookies.txt" >> .gitignore
   ```
4. **Enable CloudTrail** to audit secret access
5. **Use least-privilege IAM**: Only `secretsmanager:GetSecretValue` for specific secret

---

## Quick Checklist

- [ ] Export cookies from browser (logged into YouTube)
- [ ] Choose deployment method (env var or Secrets Manager)
- [ ] Update ECS task definition
- [ ] Grant IAM permissions (if using Secrets Manager)
- [ ] Deploy to ECS
- [ ] Test with sample video
- [ ] Check logs for success
- [ ] Set calendar reminder to refresh cookies in 3 months

---

## Next Steps

1. **Test locally first** (optional):
   ```bash
   export YOUTUBE_COOKIES="$(cat youtube_cookies.txt)"
   poetry run python workers/voice_processing/worker.py
   ```

2. **Deploy to ECS** using method above

3. **Verify** with failing URL from logs

4. **Done!** Voice cloning from YouTube now works

---

## Questions?

**Q: Why not use `--cookies-from-browser`?**
A: Doesn't work in Docker containers (no browser installed)

**Q: Can I use multiple Google accounts?**
A: Yes, but use cookies from account most likely to succeed (verified account, high usage)

**Q: Do cookies expire?**
A: Yes, 3-6 months typically. Monitor logs and refresh when needed.

**Q: Is this against YouTube TOS?**
A: For voice cloning your own content or public videos with permission, generally fine. Commercial use may require different licensing.
