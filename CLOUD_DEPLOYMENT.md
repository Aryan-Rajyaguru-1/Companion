# 🚀 Companion Brain - Cloud Deployment Guide

Deploy your AGI-powered Companion Brain to free cloud platforms and access it anywhere via REST API!

## 🌟 What You Get

- ✅ **Always-On API**: Access your brain 24/7 from anywhere
- ✅ **REST API**: No need to import - just make HTTP requests
- ✅ **Free Hosting**: Railway, Render, or Fly.io free tiers
- ✅ **AGI Enabled**: Full autonomous decision-making
- ✅ **Auto-scaling**: Handles traffic automatically
- ✅ **Health Monitoring**: Built-in health checks
- ✅ **API Security**: API key authentication

## 📋 Prerequisites

1. Git repository (push your code to GitHub)
2. Free account on one of:
   - [Railway](https://railway.app) - **RECOMMENDED** (easiest, most reliable)
   - [Render](https://render.com) - Good alternative
   - [Fly.io](https://fly.io) - More control

## 🎯 Quick Start - Railway (Recommended)

### Step 1: Prepare Your Code

```bash
# Make sure all files are committed
git add .
git commit -m "Prepare for cloud deployment"
git push origin main
```

### Step 2: Deploy to Railway

1. **Go to [Railway.app](https://railway.app)**
2. **Click "Start a New Project"**
3. **Select "Deploy from GitHub repo"**
4. **Choose your repository**
5. **Railway auto-detects everything!** ✨

### Step 3: Set Environment Variables

In Railway dashboard, go to your project → Variables:

```env
API_KEY=your-secret-key-here-change-this
ENVIRONMENT=production
LOG_LEVEL=INFO
PORT=8000
```

### Step 4: Deploy!

Railway automatically:
- Installs dependencies from `requirements-api.txt`
- Runs `Procfile` command
- Exposes your API to the internet
- Provides a public URL like: `https://companion-brain-production.up.railway.app`

**That's it!** 🎉 Your brain is live!

---

## 🔧 Alternative: Deploy to Render

### Step 1: Create Render Account

1. Go to [Render.com](https://render.com)
2. Sign up with GitHub

### Step 2: Create Web Service

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository
3. Configure:
   - **Name**: `companion-brain-api`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements-api.txt`
   - **Start Command**: `uvicorn api_server:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Free`

### Step 3: Add Environment Variables

In Render dashboard → Environment:

```env
API_KEY=your-secret-key-here
ENVIRONMENT=production
LOG_LEVEL=INFO
PYTHON_VERSION=3.12
```

### Step 4: Deploy

Click **"Create Web Service"** - Render will deploy automatically!

URL: `https://companion-brain-api.onrender.com`

---

## ✈️ Alternative: Deploy to Fly.io

### Step 1: Install Fly CLI

```bash
# Linux/Mac
curl -L https://fly.io/install.sh | sh

# Or via package manager
brew install flyctl  # Mac
```

### Step 2: Login and Launch

```bash
# Login to Fly.io
fly auth login

# Launch your app (uses fly.toml)
fly launch

# Set secrets
fly secrets set API_KEY=your-secret-key-here

# Deploy
fly deploy
```

Your API will be at: `https://companion-brain-api.fly.dev`

---

## 🔌 Using Your Cloud API

### Base URL

```
Railway:  https://companion-brain-production.up.railway.app
Render:   https://companion-brain-api.onrender.com
Fly.io:   https://companion-brain-api.fly.dev
```

### API Endpoints

#### 1. Health Check
```bash
curl https://your-app.railway.app/health
```

Response:
```json
{
  "status": "healthy",
  "brain_status": "healthy",
  "agi_enabled": true,
  "autonomy_enabled": true,
  "uptime": 3600.5,
  "timestamp": "2025-11-29T10:30:00"
}
```

#### 2. Think (Main AGI Endpoint)

```bash
curl -X POST https://your-app.railway.app/api/think \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-api-key" \
  -d '{
    "message": "Explain quantum computing and find recent papers on it",
    "use_agi": true
  }'
```

Response:
```json
{
  "success": true,
  "response": "Quantum computing uses quantum mechanics principles...",
  "decision_details": {
    "query_type": "research",
    "modules_used": ["knowledge", "search", "reasoning"],
    "execution_steps": ["gather_information", "perform_reasoning", "generate_response"],
    "confidence": 0.92
  },
  "thinking_time": 2.45,
  "timestamp": "2025-11-29T10:30:00"
}
```

#### 3. Get Statistics

```bash
curl -X GET https://your-app.railway.app/api/stats \
  -H "X-API-Key: your-secret-api-key"
```

#### 4. Check AGI Status

```bash
curl https://your-app.railway.app/api/agi/status \
  -H "X-API-Key: your-secret-api-key"
```

---

## 🐍 Python Client Example

```python
import requests

class CompanionBrainClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
    
    def think(self, message, use_agi=True):
        """Ask the brain to think"""
        response = requests.post(
            f"{self.base_url}/api/think",
            headers=self.headers,
            json={"message": message, "use_agi": use_agi}
        )
        return response.json()
    
    def health(self):
        """Check brain health"""
        response = requests.get(f"{self.base_url}/health")
        return response.json()
    
    def get_stats(self):
        """Get brain statistics"""
        response = requests.get(
            f"{self.base_url}/api/stats",
            headers=self.headers
        )
        return response.json()

# Usage
client = CompanionBrainClient(
    base_url="https://companion-brain-production.up.railway.app",
    api_key="your-secret-api-key"
)

# Think with AGI
result = client.think("What is the meaning of life?")
print(result["response"])
print(f"Used modules: {result['decision_details']['modules_used']}")

# Check health
health = client.health()
print(f"Brain is {health['brain_status']}")
```

---

## 🌐 JavaScript/Node.js Client Example

```javascript
class CompanionBrainClient {
    constructor(baseUrl, apiKey) {
        this.baseUrl = baseUrl.replace(/\/$/, '');
        this.apiKey = apiKey;
    }

    async think(message, useAgi = true) {
        const response = await fetch(`${this.baseUrl}/api/think`, {
            method: 'POST',
            headers: {
                'X-API-Key': this.apiKey,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message, use_agi: useAgi })
        });
        return await response.json();
    }

    async health() {
        const response = await fetch(`${this.baseUrl}/health`);
        return await response.json();
    }

    async getStats() {
        const response = await fetch(`${this.baseUrl}/api/stats`, {
            headers: { 'X-API-Key': this.apiKey }
        });
        return await response.json();
    }
}

// Usage
const brain = new CompanionBrainClient(
    'https://companion-brain-production.up.railway.app',
    'your-secret-api-key'
);

// Think with AGI
const result = await brain.think('Explain quantum computing');
console.log(result.response);
console.log('Modules used:', result.decision_details.modules_used);

// Check health
const health = await brain.health();
console.log('Brain status:', health.brain_status);
```

---

## 🔐 Security Best Practices

### 1. Generate Strong API Key

```python
import secrets
api_key = secrets.token_urlsafe(32)
print(f"Your API key: {api_key}")
```

### 2. Set Environment Variables (Never commit!)

**Railway/Render**: Set in dashboard
**Fly.io**: Use `fly secrets set`

```bash
# Don't do this!
API_KEY=my-key-123  # ❌ Bad - visible in code

# Do this!
fly secrets set API_KEY=$(openssl rand -base64 32)  # ✅ Good
```

### 3. Rate Limiting

The API includes built-in rate limiting:
- **100 requests per minute** per IP/API key
- Automatically returns 429 if exceeded

### 4. CORS Configuration

Edit `api_server.py` to restrict origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specify your domains
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)
```

---

## 📊 Monitoring Your Deployment

### Railway

1. Go to your project
2. Click **"Deployments"** tab
3. View logs in real-time
4. Monitor resource usage

### Render

1. Go to your service
2. Click **"Logs"** tab
3. See all requests and errors
4. Monitor performance metrics

### Fly.io

```bash
# View logs
fly logs

# Monitor status
fly status

# Check app info
fly info
```

---

## 🚨 Troubleshooting

### API Returns 503 "Brain service unavailable"

**Cause**: Brain failed to initialize

**Solution**:
1. Check logs for errors
2. Verify all dependencies installed
3. Check environment variables

```bash
# Railway: View logs in dashboard
# Render: Check Logs tab
# Fly.io: 
fly logs
```

### Slow Response Times

**Cause**: Free tier limitations or cold starts

**Solutions**:
- Railway/Render free tier: Apps sleep after 15min inactivity
- First request after sleep takes ~30s to wake up
- Keep alive: Ping `/health` every 10 minutes
- Upgrade to paid tier for always-on

### API Key Authentication Fails

**Cause**: Missing or wrong API key

**Solution**:
1. Check `X-API-Key` header is set
2. Verify key matches environment variable
3. For development, set `ENVIRONMENT=development` to skip auth

---

## 💰 Cost Comparison

| Platform | Free Tier | Limits | Best For |
|----------|-----------|--------|----------|
| **Railway** | $5 credit/month | 500 hours, sleeps after inactivity | Quick deploy, hobby projects |
| **Render** | Free forever | Sleeps after 15min, 750 hours/month | Long-term free hosting |
| **Fly.io** | Free forever | 3 shared VMs, 160GB transfer | More control, better performance |

**Recommendation**: Start with **Railway** for easiest setup, switch to **Render** for long-term free hosting.

---

## 🎯 Next Steps

1. **Deploy your API** using Railway (5 minutes)
2. **Test it** with curl or Python client
3. **Integrate** into your apps (web, mobile, desktop)
4. **Monitor** usage and performance
5. **Scale** when needed (upgrade tier)

## 📚 Additional Resources

- [API Server Code](/api_server.py)
- [AGI Implementation](/AGI_IMPLEMENTATION_COMPLETE.md)
- [AGI Workflow](/AGI_AUTONOMOUS_WORKFLOW.md)
- [Railway Docs](https://docs.railway.app)
- [Render Docs](https://render.com/docs)
- [Fly.io Docs](https://fly.io/docs)

---

## 🎉 You're All Set!

Your Companion Brain with full AGI capabilities is now:
- ✅ Deployed to the cloud
- ✅ Accessible via REST API
- ✅ Protected with API key
- ✅ Monitoring its health
- ✅ Learning from interactions
- ✅ Ready to scale

**Access it from anywhere - no imports needed!** 🚀

---

*Need help? Check logs, read troubleshooting section, or review the API server code.*
