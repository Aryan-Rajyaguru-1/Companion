# 🔐 Environment Configuration Guide

## Overview
This guide explains how to configure your Companion AI Framework securely using environment variables.

## Quick Setup

### 1. Generate Secure Keys
Run one of these commands to generate secure random keys:

```bash
# Option 1: Bash script (Linux/Mac)
./generate_secure_keys.sh

# Option 2: Python script (Cross-platform)
python generate_secure_keys.py
```

### 2. Configure Your .env File
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Fill in your API keys from the respective providers:
   - **OpenRouter**: https://openrouter.ai/
   - **Hugging Face**: https://huggingface.co/settings/tokens
   - **Groq**: https://console.groq.com/
   - **Bytez**: https://bytez.com/

3. Update deployment URLs for your specific platform.

## Environment Variables Reference

### 🔑 Required (Security)
- `JWT_SECRET`: For JWT token signing (auto-generate)
- `API_KEY`: For API authentication (auto-generate)
- `SECRET_KEY`: For Flask sessions (auto-generate)

### 🤖 Required (LLM Providers)
- `OPENROUTER_*_KEY`: OpenRouter API keys
- `HUGGINGFACE_API_KEY`: Hugging Face token
- `GROQ_API_KEY`: Groq API key
- `BYTEZ_API_KEY`: Bytez API key

### 🗄️ Database
- `DATABASE_URL`: Database connection string
  - Development: `sqlite:///auth.db`
  - Production: `postgresql://user:pass@host:port/db`

### 🌐 Server Configuration
- `HOST`: Server host (default: `0.0.0.0`)
- `PORT`: Server port (default: `5000`)
- `ENVIRONMENT`: `development` or `production`
- `DEBUG`: `true` or `false`

### 🚀 Deployment URLs
Update these with your actual deployment URLs:
- `VERCEL_URL`
- `RAILWAY_URL`
- `FLY_APP_NAME`
- `RENDER_EXTERNAL_URL`

## Security Best Practices

1. **Never commit `.env` to version control**
2. **Use strong, randomly generated keys**
3. **Rotate keys regularly in production**
4. **Use different keys for different environments**
5. **Restrict CORS origins in production**

## Deployment-Specific Notes

### Vercel
- Set environment variables in Vercel dashboard
- Use `VERCEL_URL` for API calls

### Railway
- Set environment variables in Railway dashboard
- Database URL is automatically provided

### Local Development
- Use `.env` file in project root
- Install `python-dotenv` for automatic loading

## Testing Configuration

Run this to verify your environment is properly configured:

```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('✅ JWT_SECRET:', bool(os.getenv('JWT_SECRET'))); print('✅ API_KEY:', bool(os.getenv('API_KEY'))); print('✅ GROQ_API_KEY:', bool(os.getenv('GROQ_API_KEY')))"
```