# YouTube Cookies Setup for ECS/Docker

This guide explains how to fix the "Sign in to confirm you're not a bot" error when downloading YouTube videos in production.

## Problem

YouTube blocks automated yt-dlp requests with:
```
ERROR: [youtube] hIMMwqr7W7k: Sign in to confirm you're not a bot
```

## Solution

Add YouTube authentication cookies to bypass bot detection.

---

## Step 1: Export YouTube Cookies from Browser

### Option A: Using Browser Extension (Recommended)

1. **Install Cookie Extension**:
   - **Chrome**: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - **Firefox**: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

2. **Export Cookies**:
   - Open YouTube.com in your browser
   - Make sure you're **logged in** to your Google account
   - Click the extension icon
   - Click "Export" or "Download"
   - Save as `youtube_cookies.txt`

### Option B: Using yt-dlp (Alternative)

If you have yt-dlp installed locally on a machine with a browser:

```bash
# Export cookies from browser to file
yt-dlp --cookies-from-browser firefox --cookies youtube_cookies.txt \
  --skip-download https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

Replace `firefox` with `chrome`, `edge`, or `safari` as needed.

---

## Step 2: Upload Cookies to AWS

### Option A: AWS Secrets Manager (Recommended for Production)

```bash
# Create secret
aws secretsmanager create-secret \
  --name youtube-cookies \
  --description "YouTube cookies for yt-dlp authentication" \
  --secret-string file://youtube_cookies.txt \
  --region us-east-1

# Verify secret created
aws secretsmanager describe-secret --secret-id youtube-cookies --region us-east-1
```

### Option B: S3 Bucket (Alternative)

```bash
# Upload to S3 (restrict permissions!)
aws s3 cp youtube_cookies.txt s3://your-secrets-bucket/youtube_cookies.txt \
  --region us-east-1

# Make sure bucket has proper encryption and access controls
aws s3api put-object-acl \
  --bucket your-secrets-bucket \
  --key youtube_cookies.txt \
  --acl private
```

---

## Step 3: Configure ECS Task to Use Cookies

### Option A: Secrets Manager (Recommended)

1. **Update ECS Task Definition** (`task-definition.json` or Terraform):

```json
{
  "containerDefinitions": [
    {
      "name": "voice-processing-worker",
      "image": "your-ecr-repo/voice-processing:latest",
      "secrets": [
        {
          "name": "YOUTUBE_COOKIES",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:youtube-cookies"
        }
      ],
      "environment": [
        {
          "name": "YT_DLP_COOKIES_FILE",
          "value": "/app/cookies/youtube_cookies.txt"
        }
      ],
      "entryPoint": [
        "sh",
        "-c",
        "echo \"$YOUTUBE_COOKIES\" > /app/cookies/youtube_cookies.txt && python /app/voice_processing/worker.py"
      ]
    }
  ]
}
```

2. **Grant ECS Task IAM Permissions**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:youtube-cookies"
    }
  ]
}
```

### Option B: S3 Download on Startup (Alternative)

1. **Update docker-compose or ECS startup script**:

```bash
#!/bin/sh
# Download cookies from S3 on container startup
aws s3 cp s3://your-secrets-bucket/youtube_cookies.txt /app/cookies/youtube_cookies.txt

# Start worker
python /app/voice_processing/worker.py
```

2. **Grant S3 read permissions** to ECS task role.

---

## Step 4: Verify Setup

### Check Container Logs

After deploying, check ECS logs for confirmation:

```bash
# View logs
aws logs tail /ecs/voice-processing --follow

# Look for these messages:
# ✓ Using cookie file for authentication: /app/cookies/youtube_cookies.txt
# ✓ Audio downloaded successfully
```

### Test with Sample Video

```bash
curl -X POST 'https://api.myclone.is/api/v1/voice-processing/jobs' \
  -H 'Content-Type: application/json' \
  -d '{
    "job_type": "voice_extraction",
    "input_source": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "user_id": "YOUR_USER_ID",
    "output_format": "wav",
    "profile": "elevenlabs"
  }'

# Monitor job status
curl 'https://api.myclone.is/api/v1/voice-processing/jobs/{job_id}'
```

---

## Maintenance

### Cookie Expiration

- **Expected lifetime**: 3-6 months typically
- **Heavy usage**: May need refresh every 1-3 months
- **Monitor logs** for authentication errors

### Refresh Cookies

When cookies expire, you'll see errors like:
```
✗ Error downloading audio: Sign in to confirm you're not a bot
```

**To refresh**:
1. Repeat Step 1 (export fresh cookies)
2. Update AWS secret:
   ```bash
   aws secretsmanager update-secret \
     --secret-id youtube-cookies \
     --secret-string file://youtube_cookies.txt
   ```
3. Restart ECS tasks (ECS pulls secrets on startup)

### Automate Cookie Refresh (Advanced)

Set up a Lambda function to:
1. Run headless browser with Selenium/Playwright
2. Login to YouTube programmatically
3. Extract cookies
4. Update Secrets Manager
5. Trigger ECS task restart

(This is complex and optional - manual refresh every 3-6 months is usually fine)

---

## Security Best Practices

1. **Never commit cookies to Git**:
   ```bash
   # Add to .gitignore
   echo "youtube_cookies.txt" >> .gitignore
   echo "*_cookies.txt" >> .gitignore
   ```

2. **Rotate cookies regularly**: Every 3-6 months minimum

3. **Use least-privilege IAM**:
   - ECS task only needs `secretsmanager:GetSecretValue` for specific secret
   - Restrict S3 bucket access if using S3 approach

4. **Encrypt secrets**: Secrets Manager encrypts by default, ensure S3 uses KMS if using S3

5. **Audit access**: Enable CloudTrail logging for secret access

---

## Troubleshooting

### "Cookie file not found" warning

```
⚠ No cookie file found - YouTube may block download
  Expected cookie file at: /app/cookies/youtube_cookies.txt (not found)
```

**Solution**: Check environment variable and file permissions:
```bash
# In ECS container (exec into task)
echo $YT_DLP_COOKIES_FILE
ls -la /app/cookies/
```

### "Sign in to confirm you're not a bot" persists

**Possible causes**:
1. Cookies expired (refresh them)
2. Cookies from wrong account (use account that's logged into YouTube)
3. Cookie file format incorrect (should be Netscape format)
4. YouTube flagged the account (try different Google account)

### Cookie file format error

Cookies must be in **Netscape format**:
```
# Netscape HTTP Cookie File
.youtube.com	TRUE	/	TRUE	1234567890	COOKIE_NAME	cookie_value
```

If using browser extension, it should export this format automatically.

---

## Alternative Solutions

### If Cookies Don't Work

1. **Use Proxy Service** (BrightData, Oxylabs):
   ```python
   # In youtube_extractor.py
   ydl_opts["proxy"] = "http://user:pass@proxy.brightdata.com:22225"
   ```
   Cost: $50-200/month

2. **YouTube Data API** (for metadata only):
   - Already implemented in codebase
   - Free 10,000 quota/day
   - Set `YOUTUBE_API_KEY` environment variable

3. **Disable Audio Download** (transcripts only):
   - Use `youtube-transcript-api` (no auth needed)
   - Already working in codebase

---

## Environment Variables Reference

| Variable | Purpose | Example |
|----------|---------|---------|
| `YT_DLP_COOKIES_FILE` | Path to cookies file | `/app/cookies/youtube_cookies.txt` |
| `YT_DLP_CACHE_DIR` | yt-dlp cache directory | `/tmp/yt-dlp-cache` (already set) |
| `YOUTUBE_API_KEY` | YouTube Data API key | `AIzaSy...` (optional fallback) |

---

## Questions?

Contact the team or see:
- [yt-dlp cookie docs](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)
- [YouTube cookie export guide](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)
