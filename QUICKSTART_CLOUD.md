# 🚀 Quick Start - Deploy Your Brain to Cloud

## Option 1: Railway (Easiest - 5 Minutes) ⭐

### Step 1: Push to GitHub
```bash
git add .
git commit -m "Ready for deployment"
git push origin main
```

### Step 2: Deploy on Railway
1. Go to [railway.app](https://railway.app)
2. Click "Start a New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository
5. Set environment variable: `API_KEY` (generate below)
6. Railway auto-deploys! ✅

### Generate API Key:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Your API will be live at:
```
https://companion-brain-production.up.railway.app
```

---

## Option 2: Test Locally First

```bash
# Test the API server locally
python3 test_api_local.py

# If successful, run deployment script
./deploy_cloud.sh
```

---

## Option 3: Manual Render Deployment

1. Go to [render.com](https://render.com)
2. New + → Web Service
3. Connect GitHub repo
4. Settings:
   - Build: `pip install -r requirements-api.txt`
   - Start: `uvicorn api_server:app --host 0.0.0.0 --port $PORT`
   - Plan: Free
5. Add env vars:
   - `API_KEY`: (your secret key)
   - `ENVIRONMENT`: production
   - `LOG_LEVEL`: INFO

---

## Access Your Brain API

### Python:
```python
from client_library import CompanionBrainCloudClient

brain = CompanionBrainCloudClient(
    base_url="https://your-app.railway.app",
    api_key="your-api-key"
)

result = brain.think("Explain quantum computing")
print(result.response)
```

### cURL:
```bash
curl -X POST https://your-app.railway.app/api/think \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!", "use_agi": true}'
```

### JavaScript:
```javascript
const response = await fetch('https://your-app.railway.app/api/think', {
  method: 'POST',
  headers: {
    'X-API-Key': 'your-key',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ message: 'Hello!', use_agi: true })
});

const result = await response.json();
console.log(result.response);
```

---

## What You Get

✅ Always-on API (24/7)
✅ AGI autonomous decision-making
✅ Access from anywhere (no imports!)
✅ Free hosting
✅ Auto-scaling
✅ Health monitoring
✅ API key security
✅ Rate limiting (100 req/min)

---

## Files Created

- `api_server.py` - FastAPI server with AGI
- `Procfile` - Railway/Heroku config
- `railway.json` - Railway settings
- `render.yaml` - Render config
- `fly.toml` - Fly.io config
- `requirements-api.txt` - Dependencies
- `client_library.py` - Python client
- `deploy_cloud.sh` - Deployment helper
- `CLOUD_DEPLOYMENT.md` - Full guide

---

## Troubleshooting

**503 Brain unavailable**: Check logs, verify dependencies installed

**Slow responses**: Free tier cold starts (~30s first request)

**API key fails**: Verify `X-API-Key` header matches env var

**Rate limited**: 100 requests/minute limit, wait or upgrade

---

## Cost

All platforms have **FREE TIERS**:

- **Railway**: $5 credit/month, 500 hours
- **Render**: Free forever, sleeps after 15min
- **Fly.io**: Free forever, 3 VMs

**Recommendation**: Railway for quick start, Render for long-term free.

---

## Need Help?

1. Test locally: `python3 test_api_local.py`
2. Read full guide: `CLOUD_DEPLOYMENT.md`
3. Check logs on your platform dashboard

---

**Your brain is ready for the cloud! 🧠☁️**
