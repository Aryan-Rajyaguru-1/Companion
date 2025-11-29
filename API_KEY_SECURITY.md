# 🔐 API Key Security - Important Information

## ⚠️ Security Issue Fixed

Your previous commit was **rejected by GitHub** because it contained **hardcoded API keys** in the code. This is a serious security issue!

### What was wrong:
- ❌ API keys were directly in `website/config.py`
- ❌ Keys were in documentation files (`GROQ_INTEGRATION.md`, `SEARCH_HF_UPDATE_NOV2025.md`)
- ❌ These files were about to be committed to public GitHub

### What we fixed:
- ✅ Replaced hardcoded keys with environment variables
- ✅ Created `.env.example` template
- ✅ Updated `.gitignore` to prevent `.env` from being committed
- ✅ Created `setup_api_keys.sh` to help configure keys securely
- ✅ Removed keys from documentation files

---

## 🎯 How to Use API Keys Securely

### Step 1: Create Your .env File

```bash
# Run the setup script
./setup_api_keys.sh

# Or copy the example manually
cp .env.example .env
```

### Step 2: Add Your Real API Keys to .env

Edit `.env` and add your keys:

```bash
# Open in editor
nano .env
# or
code .env
```

Fill in your keys:
```bash
OPENROUTER_TONGYI_KEY=sk-or-v1-your-actual-key-here
OPENROUTER_DEEPSEEK_KEY=sk-or-v1-your-actual-key-here
OPENROUTER_GPT_OSS_KEY=sk-or-v1-your-actual-key-here
HUGGINGFACE_API_KEY=hf_your-actual-token-here
GROQ_API_KEY=gsk_your-actual-key-here
API_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
```

### Step 3: Load Environment Variables

The config files now automatically load from environment:

```python
# website/config.py
GROQ_CONFIG = {
    "api_key": os.getenv("GROQ_API_KEY", ""),  # ✅ Secure!
    # ...
}
```

---

## 🚀 For Cloud Deployment

When deploying to Railway/Render/Fly.io, set environment variables in their dashboard:

### Railway:
1. Go to your project
2. Click **Variables** tab
3. Add each key:
   - `GROQ_API_KEY`
   - `HUGGINGFACE_API_KEY`
   - `OPENROUTER_TONGYI_KEY`
   - etc.

### Render:
1. Go to your service
2. Click **Environment**
3. Add variables

### Fly.io:
```bash
fly secrets set GROQ_API_KEY=your-key
fly secrets set HUGGINGFACE_API_KEY=your-key
# etc.
```

---

## 🔒 Security Best Practices

### ✅ DO:
- Use environment variables for all secrets
- Keep `.env` in `.gitignore`
- Use `.env.example` as a template (no real keys!)
- Rotate API keys regularly
- Use different keys for development and production

### ❌ DON'T:
- Commit API keys to git
- Share `.env` file
- Put keys in code comments
- Post keys in issues/forums
- Use the same key everywhere

---

## 🔄 What Changed in Your Files

### `website/config.py`
**Before:**
```python
GROQ_CONFIG = {
    "api_key": "gsk_YOUR_ACTUAL_KEY_WAS_HERE",  # ❌ Exposed!
}
```

**After:**
```python
GROQ_CONFIG = {
    "api_key": os.getenv("GROQ_API_KEY", ""),  # ✅ Secure!
}
```

### `.gitignore`
Added:
```
# Environment variables (NEVER commit!)
.env
.env.local
.env.production

# API keys and secrets
*.key
*.pem
**/secrets.py
```

---

## 📝 Files Created

1. **`.env.example`** - Template with no real keys
2. **`setup_api_keys.sh`** - Script to create `.env` file
3. **`API_KEY_SECURITY.md`** - This documentation

---

## ✅ Now You Can Deploy Safely!

```bash
# 1. Setup your keys locally
./setup_api_keys.sh
nano .env  # Add your actual keys

# 2. Commit the secure version
git add .
git commit -m "Secure API key configuration"
git push origin main

# 3. Deploy to cloud
./deploy_cloud.sh
# Set environment variables in cloud dashboard
```

---

## 🆘 If Your Keys Were Exposed

Since your keys were in a commit that was rejected (not pushed), you're safe! But if you're concerned:

1. **Revoke the old keys**:
   - OpenRouter: https://openrouter.ai/keys
   - Groq: https://console.groq.com/keys
   - Hugging Face: https://huggingface.co/settings/tokens

2. **Generate new keys**

3. **Add them to `.env`**

---

## 💡 Quick Commands

```bash
# Setup keys
./setup_api_keys.sh

# Edit keys
nano .env

# Generate secure API_KEY for deployment
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Test if keys are loaded
python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print('✅ Keys loaded' if os.getenv('GROQ_API_KEY') else '❌ No keys')"

# Deploy
./deploy_cloud.sh
```

---

**Remember**: `.env` is in `.gitignore` and will NEVER be committed! ✅
