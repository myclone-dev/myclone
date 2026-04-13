# YouTube Residential Proxy Setup

## Problem
YouTube blocks audio downloads from AWS/ECS datacenter IPs with:
```
ERROR: [youtube] Sign in to confirm you're not a bot
```

## Solution: Residential Proxy with Smart Fallback

The code now implements:
1. **Try without proxy first** (fast, free)
2. **If bot detection → Retry with residential proxy** (bypasses IP blocking)
3. **If still fails → Return error**

---

## ✅ Recommended: ScraperAPI (Free Tier!)

**Why ScraperAPI**:
- ✅ **1,000 free requests/month** (perfect for testing!)
- ✅ Easiest setup (just API key)
- ✅ Automatic retries and rotation
- ✅ YouTube-optimized
- ✅ No cookies needed

**Pricing**:
- Free: 1,000 requests/month
- Hobby: $49/month (100,000 requests)
- Startup: $149/month (500,000 requests)

---

## 🚀 Quick Start (5 minutes)

### Step 1: Sign Up for ScraperAPI (2 minutes)

1. Go to https://www.scraperapi.com/
2. Click "Start Free Trial"
3. Sign up (no credit card required for free tier)
4. Go to Dashboard → Copy your API key

**Your API key will look like**: `scraperapi_abcd1234...`

---

### Step 2: Configure Proxy (1 minute)

**Option A: Hardcode for Testing** (fastest)

Edit `app/config.py` line 140:
```python
youtube_proxy: str = "http://scraperapi:YOUR_API_KEY@proxy-server.scraperapi.com:8001"
```

Replace `YOUR_API_KEY` with your actual ScraperAPI key.

**Option B: Environment Variable** (production)

```bash
# Local testing
export YOUTUBE_PROXY="http://scraperapi:YOUR_API_KEY@proxy-server.scraperapi.com:8001"

# ECS/Production - add to task definition
{
  "environment": [{
    "name": "YOUTUBE_PROXY",
    "value": "http://scraperapi:YOUR_API_KEY@proxy-server.scraperapi.com:8001"
  }]
}
```

**Option C: AWS Secrets Manager** (most secure)

```bash
# Create secret
aws secretsmanager create-secret \
  --name youtube-proxy \
  --secret-string "http://scraperapi:YOUR_API_KEY@proxy-server.scraperapi.com:8001" \
  --region us-east-1

# Task definition
{
  "secrets": [{
    "name": "YOUTUBE_PROXY",
    "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:youtube-proxy"
  }]
}
```

---

### Step 3: Test (2 minutes)

```bash
# Test with the failing URL from your logs
curl -X 'POST' 'https://api.myclone.is/api/v1/voice-processing/jobs' \
  -H 'Content-Type: application/json' \
  -d '{
    "job_type": "voice_extraction",
    "input_source": "https://www.youtube.com/watch?v=hIMMwqr7W7k",
    "user_id": "20c2737a-51f0-481d-a8b3-2c07bf15396d",
    "output_format": "wav",
    "profile": "elevenlabs"
  }'

# Monitor logs
aws logs tail /ecs/voice-processing-worker --follow
```

**Expected Success Logs**:
```
✓ YouTube residential proxy configured
Attempting audio download without proxy...
⚠ Bot detection encountered, retrying with proxy...
✓ Using residential proxy for audio download
✓ Audio downloaded successfully (via proxy)
Worker completed job 8f5a5832-0196-446d-8e30-4ffed044189f
```

---

## 💰 Cost Estimation

### ScraperAPI Pricing

| Volume | Plan | Cost | Cost per Video |
|--------|------|------|----------------|
| Testing/POC | Free | $0 | $0 |
| 100 videos/month | Free | $0 | $0 |
| 1,000 videos/month | Free | $0 | $0 |
| 10,000 videos/month | Hobby | $49/month | $0.0049 |
| 50,000 videos/month | Startup | $149/month | $0.003 |

**Note**: Only charged when proxy is used (not for successful direct downloads!)

---

## 🏗️ How It Works

### Smart Fallback Logic

```python
# Pseudocode
try:
    download_audio(without_proxy)  # Free, fast
    return success
except BotDetectionError:
    if proxy_configured:
        download_audio(with_proxy)  # Costs money, but works
        return success
    else:
        raise error
```

### Benefits
- ✅ **No proxy cost** if direct download works
- ✅ **Automatic retry** with proxy on bot detection
- ✅ **Minimal latency** (tries direct first)
- ✅ **Clear logging** for debugging

---

## 📊 Alternative Providers

### BrightData (Enterprise-Grade)

**Best for**: High volume, maximum reliability

**Pricing**: $500/month for 40GB (~10,000 videos)

**Setup**:
```python
youtube_proxy: str = "http://username-country-us:password@brd.superproxy.io:22225"
```

**When to use**:
- > 50,000 videos/month
- Need 99.9% success rate
- Enterprise support required

**Sign up**: https://brightdata.com/

---

### Webshare (Budget Option)

**Best for**: Low cost testing

**Pricing**: $5/month for 25GB

**Setup**:
```python
youtube_proxy: str = "http://username:password@proxy.webshare.io:80"
```

**When to use**:
- Very low volume (< 1,000 videos/month)
- Budget constrained
- Testing only

**Cons**: Lower success rate, may need more retries

**Sign up**: https://www.webshare.io/

---

## 🔍 Monitoring & Debugging

### Check Proxy Usage

**Monitor logs for**:
```
✓ Audio downloaded successfully (direct)  # No proxy cost
✓ Audio downloaded successfully (via proxy)  # Proxy cost
```

**Track metrics**:
- % downloads using proxy (lower is better = less cost)
- Success rate with/without proxy
- ScraperAPI dashboard shows usage

---

### Troubleshooting

#### "No proxy configured" warning
**Logs**:
```
⚠ No YouTube proxy configured - may encounter bot detection on AWS IPs
```

**Fix**: Set `YOUTUBE_PROXY` environment variable

---

#### Proxy not being used (always direct)
**Cause**: Videos work without proxy (this is good!)

**Verify**: Check if bot detection happens by testing on ECS (AWS IPs more likely to be blocked)

---

#### All downloads using proxy (expensive!)
**Cause**: AWS IPs are heavily rate-limited by YouTube

**Solutions**:
1. **Expected behavior** on ECS - datacenter IPs are always blocked
2. **Reduce cost**: Switch to BrightData (better per-GB pricing at volume)
3. **Optimize**: Cache video metadata to avoid re-downloads

---

#### Proxy fails with 401 Unauthorized
**Cause**: Invalid API key or expired account

**Fix**:
1. Check API key is correct
2. Verify ScraperAPI account is active
3. Check usage hasn't exceeded plan limits

---

## 🔐 Security Best Practices

1. **Never commit API keys** to git:
   ```bash
   echo "*.env" >> .gitignore
   # Never hardcode keys in production!
   ```

2. **Use Secrets Manager** for production:
   - Encrypted at rest
   - Auditable access logs
   - Easy rotation

3. **Rotate keys regularly**:
   - ScraperAPI allows multiple API keys
   - Rotate every 90 days

4. **Monitor usage**:
   - Set up billing alerts in ScraperAPI
   - Track unexpected spikes

---

## 📋 Deployment Checklist

- [ ] Sign up for ScraperAPI (free tier)
- [ ] Copy API key from dashboard
- [ ] Choose deployment method (hardcode/env/secrets)
- [ ] Configure `YOUTUBE_PROXY` variable
- [ ] Test locally (optional)
- [ ] Deploy to ECS
- [ ] Test with failing URL from logs
- [ ] Monitor logs for success
- [ ] Check ScraperAPI dashboard for usage

---

## 🎯 Next Steps

### For Testing (Right Now)
1. Sign up for ScraperAPI free tier
2. Hardcode proxy in `app/config.py:140`
3. Deploy to ECS
4. Test with failing URL
5. **Done!** (takes < 10 minutes)

### For Production (Later)
1. Move to AWS Secrets Manager
2. Set up usage monitoring/alerts
3. Consider BrightData if volume > 50k/month
4. Implement caching to reduce downloads

---

## ❓ FAQ

**Q: Do I still need cookies?**
A: No! Residential proxies provide real residential IPs, which bypass YouTube's bot detection without cookies.

**Q: Will all downloads use the proxy?**
A: No! It tries direct first (free), only uses proxy if bot detection occurs.

**Q: What if I exceed free tier?**
A: ScraperAPI automatically emails you. You can upgrade or implement rate limiting.

**Q: Can I use multiple proxy providers?**
A: Yes! You could add a fallback chain (ScraperAPI → BrightData), but one is usually enough.

**Q: Does this violate YouTube TOS?**
A: Using residential proxies for legitimate use (voice cloning your own content) is generally accepted. Commercial scraping may have different implications.

---

## 📞 Support

**ScraperAPI Support**: support@scraperapi.com
**Documentation**: https://www.scraperapi.com/documentation/

**For issues with this implementation**: Check ECS logs first, then open GitHub issue
