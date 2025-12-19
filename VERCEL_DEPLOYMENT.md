# 🚀 Vercel Deployment Guide - Companion AI Framework

## Prerequisites

1. **Vercel Account**: Sign up at [vercel.com](https://vercel.com)
2. **Vercel CLI**: Install the Vercel CLI globally
   ```bash
   npm install -g vercel
   # or
   yarn global add vercel
   ```

## Quick Deployment

### 1. Login to Vercel
```bash
vercel login
```

### 2. Deploy from Project Root
```bash
cd "/home/aryan/Documents/Companion deepthink"
vercel --prod
```

### 3. Set Environment Variables
After deployment, set your environment variables in the Vercel dashboard:

```bash
# Security Keys (Generate new ones for production!)
JWT_SECRET=your-production-jwt-secret
API_KEY=your-production-api-key
SECRET_KEY=your-production-flask-secret

# API Keys (Get from respective providers)
OPENROUTER_API_KEY=your-openrouter-key
HUGGINGFACE_API_KEY=your-huggingface-key
GROQ_API_KEY=your-groq-key
BYTEZ_API_KEY=your-bytez-key

# Database (Use Vercel Postgres or external DB)
DATABASE_URL=your-database-url

# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO
DEBUG=false
```

## Manual Environment Variable Setup

You can also set environment variables via CLI:

```bash
# Set production environment
vercel env add JWT_SECRET production
vercel env add API_KEY production
vercel env add SECRET_KEY production
vercel env add OPENROUTER_API_KEY production
vercel env add GROQ_API_KEY production
# ... add other variables
```

## Project Structure for Vercel

```
companion-deepthink/
├── api/
│   ├── app.py              # Vercel entry point
│   └── requirements.txt    # Python dependencies
├── website/
│   ├── frontend/           # Static web files
│   ├── backend/            # Python backend modules
│   └── api/               # Additional API modules
├── vercel.json            # Vercel configuration
├── .vercelignore         # Files to exclude
└── .env                  # Local environment (not deployed)
```

## API Endpoints

After deployment, your API will be available at:
- **Base URL**: `https://your-app.vercel.app`
- **API Routes**: `https://your-app.vercel.app/api/*`
- **Frontend**: `https://your-app.vercel.app/*`

## Testing Deployment

```bash
# Test health endpoint
curl https://your-app.vercel.app/api/health

# Test authentication
curl -X POST https://your-app.vercel.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'
```

## Troubleshooting

### Common Issues:

1. **Module Import Errors**: Ensure all imports in `api/app.py` are correct
2. **Database Connection**: Use Vercel Postgres or external database
3. **Environment Variables**: Check all required variables are set
4. **Cold Starts**: Vercel functions may have cold start delays

### Logs:
```bash
# View deployment logs
vercel logs

# View function logs
vercel logs --follow
```

## Production Optimizations

1. **Database**: Use Vercel Postgres for better performance
2. **Caching**: Implement response caching for API calls
3. **CDN**: Static assets are automatically served via CDN
4. **Analytics**: Enable Vercel Analytics for monitoring

## Security Notes

- ✅ Environment variables are encrypted
- ✅ HTTPS enabled by default
- ✅ CORS configured for security
- ✅ Rate limiting available via middleware

## Redeployment

```bash
# Redeploy with changes
vercel --prod

# Deploy to preview environment first
vercel
```

---

🎉 **Your Companion AI Framework is now ready for Vercel deployment!**