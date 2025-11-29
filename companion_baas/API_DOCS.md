# Companion BaaS - API Documentation

**Version**: 1.0.0  
**Base URL**: `http://localhost:8000` (development) | `https://api.companion-baas.example.com` (production)  
**Last Updated**: November 27, 2025

---

## 📋 Table of Contents

1. [Authentication](#authentication)
2. [Core Endpoints](#core-endpoints)
3. [Search API](#search-api)
4. [Execution API](#execution-api)
5. [Monitoring](#monitoring)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)
8. [Code Examples](#code-examples)

---

## Authentication

### Overview

Companion BaaS uses JWT (JSON Web Tokens) for authentication. Tokens have two types:

- **Access Token**: Short-lived (24 hours), used for API requests
- **Refresh Token**: Long-lived (30 days), used to obtain new access tokens

### Authentication Flow

```
1. User logs in with email/password
   ↓
2. Server validates credentials
   ↓
3. Server returns access_token + refresh_token
   ↓
4. Client stores tokens securely
   ↓
5. Client includes access_token in Authorization header for API requests
   ↓
6. When access_token expires, use refresh_token to get new access_token
```

### Demo Users

For testing purposes, two demo users are available:

| Email | Password | Role | Description |
|-------|----------|------|-------------|
| `demo@companion-baas.com` | `demo123` | user | Standard user access |
| `admin@companion-baas.com` | `admin123` | admin | Admin privileges |

---

## Core Endpoints

### 1. Root

Get API information and status.

**Endpoint**: `GET /`

**Authentication**: Not required

**Response**:
```json
{
  "name": "Companion BaaS",
  "version": "1.0.0",
  "status": "operational",
  "timestamp": "2025-11-27T10:30:00Z"
}
```

**Example**:

```bash
curl http://localhost:8000/
```

```python
import requests

response = requests.get("http://localhost:8000/")
print(response.json())
```

```javascript
fetch('http://localhost:8000/')
  .then(res => res.json())
  .then(data => console.log(data));
```

---

### 2. Health Check

Check if the API is healthy and responsive.

**Endpoint**: `GET /health`

**Authentication**: Not required

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-27T10:30:00Z",
  "uptime": 3600,
  "version": "1.0.0"
}
```

**Status Codes**:
- `200 OK`: Service is healthy
- `503 Service Unavailable`: Service is unhealthy

**Example**:

```bash
curl http://localhost:8000/health
```

**Use Cases**:
- Kubernetes liveness probe
- Load balancer health check
- Monitoring systems

---

### 3. Readiness Check

Check if the API is ready to accept traffic.

**Endpoint**: `GET /ready`

**Authentication**: Not required

**Response**:
```json
{
  "status": "ready",
  "services": {
    "elasticsearch": "connected",
    "meilisearch": "connected",
    "redis": "connected"
  },
  "timestamp": "2025-11-27T10:30:00Z"
}
```

**Status Codes**:
- `200 OK`: Service is ready
- `503 Service Unavailable`: Service is not ready (e.g., database disconnected)

**Example**:

```bash
curl http://localhost:8000/ready
```

**Use Cases**:
- Kubernetes readiness probe
- Deployment verification
- Pre-deployment checks

---

### 4. API Information

Get detailed API configuration and capabilities.

**Endpoint**: `GET /api/v1/info`

**Authentication**: Not required

**Response**:
```json
{
  "version": "1.0.0",
  "environment": "production",
  "features": {
    "semantic_search": true,
    "web_intelligence": true,
    "code_execution": true,
    "caching": true
  },
  "limits": {
    "max_query_length": 1000,
    "max_results": 100,
    "rate_limit": "100/minute"
  },
  "search_providers": ["elasticsearch", "meilisearch", "tavily"],
  "cache_enabled": true,
  "cache_hit_rate": 67.5
}
```

**Example**:

```bash
curl http://localhost:8000/api/v1/info
```

---

## Authentication Endpoints

### 5. Login

Authenticate a user and receive JWT tokens.

**Endpoint**: `POST /api/v1/auth/login`

**Authentication**: Not required

**Request Body**:
```json
{
  "email": "demo@companion-baas.com",
  "password": "demo123"
}
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": "user-001",
    "email": "demo@companion-baas.com",
    "name": "Demo User",
    "role": "user"
  }
}
```

**Error Response** (401 Unauthorized):
```json
{
  "detail": "Incorrect email or password"
}
```

**Example**:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@companion-baas.com","password":"demo123"}'
```

```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={
        "email": "demo@companion-baas.com",
        "password": "demo123"
    }
)
tokens = response.json()
print(f"Access Token: {tokens['access_token']}")
```

```javascript
fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'demo@companion-baas.com',
    password: 'demo123'
  })
})
.then(res => res.json())
.then(data => {
  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('refresh_token', data.refresh_token);
});
```

---

### 6. Refresh Token

Get a new access token using a refresh token.

**Endpoint**: `POST /api/v1/auth/refresh`

**Authentication**: Requires valid refresh token in header

**Headers**:
```
Authorization: Bearer <refresh_token>
```

**Response** (200 OK):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**Error Response** (401 Unauthorized):
```json
{
  "detail": "Invalid or expired refresh token"
}
```

**Example**:

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Authorization: Bearer <your_refresh_token>"
```

```python
import requests

headers = {"Authorization": f"Bearer {refresh_token}"}
response = requests.post(
    "http://localhost:8000/api/v1/auth/refresh",
    headers=headers
)
new_tokens = response.json()
```

---

### 7. Get Current User

Get information about the currently authenticated user.

**Endpoint**: `GET /api/v1/auth/me`

**Authentication**: Required (access token)

**Headers**:
```
Authorization: Bearer <access_token>
```

**Response** (200 OK):
```json
{
  "id": "user-001",
  "email": "demo@companion-baas.com",
  "name": "Demo User",
  "role": "user",
  "created_at": "2025-01-01T00:00:00Z",
  "last_login": "2025-11-27T10:30:00Z"
}
```

**Error Response** (401 Unauthorized):
```json
{
  "detail": "Could not validate credentials"
}
```

**Example**:

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <your_access_token>"
```

```python
import requests

headers = {"Authorization": f"Bearer {access_token}"}
response = requests.get(
    "http://localhost:8000/api/v1/auth/me",
    headers=headers
)
user = response.json()
print(f"Logged in as: {user['email']}")
```

---

## Search API

### 8. Semantic Search

Perform semantic search across knowledge base using multiple search providers.

**Endpoint**: `POST /api/v1/search`

**Authentication**: Required (access token)

**Headers**:
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body**:
```json
{
  "query": "What is machine learning?",
  "limit": 10,
  "filters": {
    "category": "ai",
    "language": "en"
  },
  "providers": ["elasticsearch", "meilisearch", "tavily"]
}
```

**Parameters**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | - | Search query (max 1000 chars) |
| `limit` | integer | No | 10 | Max results to return (1-100) |
| `filters` | object | No | {} | Additional search filters |
| `providers` | array | No | all | Search providers to use |

**Response** (200 OK):
```json
{
  "query": "What is machine learning?",
  "total_results": 42,
  "results": [
    {
      "id": "doc-123",
      "title": "Introduction to Machine Learning",
      "content": "Machine learning is a subset of artificial intelligence...",
      "score": 0.95,
      "source": "elasticsearch",
      "metadata": {
        "category": "ai",
        "author": "John Doe",
        "published": "2025-01-15"
      }
    },
    {
      "id": "doc-456",
      "title": "ML Basics",
      "content": "Understanding the fundamentals of ML algorithms...",
      "score": 0.87,
      "source": "meilisearch",
      "metadata": {
        "category": "ai",
        "author": "Jane Smith"
      }
    }
  ],
  "search_time_ms": 45,
  "cache_hit": false,
  "providers_used": ["elasticsearch", "meilisearch"]
}
```

**Example**:

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer <your_access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is machine learning?",
    "limit": 5,
    "providers": ["elasticsearch"]
  }'
```

```python
import requests

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

data = {
    "query": "What is machine learning?",
    "limit": 10,
    "filters": {"category": "ai"}
}

response = requests.post(
    "http://localhost:8000/api/v1/search",
    headers=headers,
    json=data
)

results = response.json()
for result in results['results']:
    print(f"{result['title']}: {result['score']}")
```

```javascript
const searchQuery = async (query) => {
  const response = await fetch('http://localhost:8000/api/v1/search', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      query: query,
      limit: 10
    })
  });
  
  const data = await response.json();
  return data.results;
};

// Usage
const results = await searchQuery('machine learning');
console.log(`Found ${results.length} results`);
```

---

## Execution API

### 9. Code Execution

Execute code snippets in a sandboxed environment.

**Endpoint**: `POST /api/v1/execute`

**Authentication**: Required (access token)

**Headers**:
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body**:
```json
{
  "code": "print('Hello, World!')\nresult = 2 + 2\nprint(f'Result: {result}')",
  "language": "python",
  "timeout": 5,
  "inputs": {}
}
```

**Parameters**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `code` | string | Yes | - | Code to execute |
| `language` | string | Yes | - | Programming language (python, javascript, etc.) |
| `timeout` | integer | No | 5 | Execution timeout in seconds (1-30) |
| `inputs` | object | No | {} | Input variables for the code |

**Response** (200 OK):
```json
{
  "status": "success",
  "output": "Hello, World!\nResult: 4\n",
  "execution_time_ms": 123,
  "language": "python",
  "timestamp": "2025-11-27T10:30:00Z"
}
```

**Error Response** (400 Bad Request):
```json
{
  "status": "error",
  "error": "SyntaxError: invalid syntax",
  "line": 2,
  "output": "",
  "execution_time_ms": 50
}
```

**Example**:

```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Authorization: Bearer <your_access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "code": "print(\"Hello, World!\")",
    "language": "python",
    "timeout": 5
  }'
```

```python
import requests

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

code = """
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

for i in range(10):
    print(f"F({i}) = {fibonacci(i)}")
"""

data = {
    "code": code,
    "language": "python",
    "timeout": 10
}

response = requests.post(
    "http://localhost:8000/api/v1/execute",
    headers=headers,
    json=data
)

result = response.json()
print(result['output'])
```

---

## Monitoring

### 10. Prometheus Metrics

Get Prometheus-formatted metrics for monitoring.

**Endpoint**: `GET /metrics`

**Authentication**: Not required (configure basic auth in production)

**Response** (text/plain):
```
# HELP api_requests_total Total number of API requests
# TYPE api_requests_total counter
api_requests_total{endpoint="/api/v1/search",method="POST",status="200"} 1234

# HELP api_request_duration_seconds API request duration
# TYPE api_request_duration_seconds histogram
api_request_duration_seconds_bucket{le="0.01"} 500
api_request_duration_seconds_bucket{le="0.05"} 800
api_request_duration_seconds_sum 45.2
api_request_duration_seconds_count 1000

# HELP cache_hit_rate Cache hit rate percentage
# TYPE cache_hit_rate gauge
cache_hit_rate 67.5
```

**Example**:

```bash
curl http://localhost:8000/metrics
```

**Use Cases**:
- Prometheus scraping target
- Grafana dashboards
- Alerting rules

---

### 11. Statistics

Get detailed API statistics in JSON format.

**Endpoint**: `GET /stats`

**Authentication**: Not required

**Response**:
```json
{
  "uptime_seconds": 3600,
  "total_requests": 12345,
  "requests_per_second": 3.43,
  "average_response_time_ms": 45.2,
  "error_rate": 0.8,
  "cache": {
    "hit_rate": 67.5,
    "total_hits": 8325,
    "total_misses": 4020,
    "size": 156,
    "memory_mb": 12.4
  },
  "endpoints": {
    "/api/v1/search": {
      "requests": 8500,
      "avg_response_ms": 52.3,
      "errors": 42
    },
    "/api/v1/execute": {
      "requests": 2000,
      "avg_response_ms": 180.5,
      "errors": 15
    }
  },
  "timestamp": "2025-11-27T10:30:00Z"
}
```

**Example**:

```bash
curl http://localhost:8000/stats
```

```python
import requests

response = requests.get("http://localhost:8000/stats")
stats = response.json()

print(f"Uptime: {stats['uptime_seconds']} seconds")
print(f"Total Requests: {stats['total_requests']}")
print(f"Cache Hit Rate: {stats['cache']['hit_rate']}%")
```

---

## Error Handling

### Error Response Format

All errors follow a consistent format:

```json
{
  "detail": "Error message describing what went wrong",
  "status_code": 400,
  "timestamp": "2025-11-27T10:30:00Z",
  "request_id": "req-abc123"
}
```

### HTTP Status Codes

| Code | Name | Description |
|------|------|-------------|
| 200 | OK | Request successful |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Service temporarily unavailable |

### Common Errors

**Authentication Error**:
```json
{
  "detail": "Could not validate credentials",
  "status_code": 401
}
```

**Rate Limit Error**:
```json
{
  "detail": "Rate limit exceeded. Try again in 60 seconds.",
  "status_code": 429,
  "retry_after": 60
}
```

**Validation Error**:
```json
{
  "detail": [
    {
      "loc": ["body", "query"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ],
  "status_code": 422
}
```

---

## Rate Limiting

### Overview

API requests are rate-limited to ensure fair usage and system stability.

**Default Limits**:
- **Unauthenticated**: 20 requests/minute
- **Authenticated**: 100 requests/minute
- **Premium**: 1000 requests/minute

### Rate Limit Headers

Every response includes rate limit information:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1732704600
```

### Handling Rate Limits

```python
import requests
import time

def make_request_with_retry(url, headers, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers)
        
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            continue
            
        return response
    
    raise Exception("Max retries exceeded")
```

---

## Code Examples

### Complete Authentication Flow

```python
import requests
from typing import Optional

class CompanionBaaSClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
    
    def login(self, email: str, password: str):
        """Authenticate and store tokens"""
        response = requests.post(
            f"{self.base_url}/api/v1/auth/login",
            json={"email": email, "password": password}
        )
        response.raise_for_status()
        
        data = response.json()
        self.access_token = data['access_token']
        self.refresh_token = data['refresh_token']
        return data['user']
    
    def refresh(self):
        """Refresh the access token"""
        headers = {"Authorization": f"Bearer {self.refresh_token}"}
        response = requests.post(
            f"{self.base_url}/api/v1/auth/refresh",
            headers=headers
        )
        response.raise_for_status()
        
        data = response.json()
        self.access_token = data['access_token']
    
    def search(self, query: str, limit: int = 10):
        """Perform semantic search"""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = requests.post(
            f"{self.base_url}/api/v1/search",
            headers=headers,
            json={"query": query, "limit": limit}
        )
        response.raise_for_status()
        return response.json()

# Usage
client = CompanionBaaSClient("http://localhost:8000")
user = client.login("demo@companion-baas.com", "demo123")
print(f"Logged in as {user['email']}")

results = client.search("machine learning", limit=5)
print(f"Found {len(results['results'])} results")
```

### JavaScript/TypeScript Client

```javascript
class CompanionBaaSClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl;
    this.accessToken = null;
    this.refreshToken = null;
  }

  async login(email, password) {
    const response = await fetch(`${this.baseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    if (!response.ok) throw new Error('Login failed');

    const data = await response.json();
    this.accessToken = data.access_token;
    this.refreshToken = data.refresh_token;
    
    // Store in localStorage
    localStorage.setItem('access_token', this.accessToken);
    localStorage.setItem('refresh_token', this.refreshToken);
    
    return data.user;
  }

  async refresh() {
    const response = await fetch(`${this.baseUrl}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${this.refreshToken}` }
    });

    if (!response.ok) throw new Error('Refresh failed');

    const data = await response.json();
    this.accessToken = data.access_token;
    localStorage.setItem('access_token', this.accessToken);
  }

  async search(query, limit = 10) {
    const response = await fetch(`${this.baseUrl}/api/v1/search`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ query, limit })
    });

    if (response.status === 401) {
      // Token expired, refresh and retry
      await this.refresh();
      return this.search(query, limit);
    }

    if (!response.ok) throw new Error('Search failed');
    return response.json();
  }
}

// Usage
const client = new CompanionBaaSClient('http://localhost:8000');

(async () => {
  const user = await client.login('demo@companion-baas.com', 'demo123');
  console.log(`Logged in as ${user.email}`);

  const results = await client.search('machine learning', 5);
  console.log(`Found ${results.results.length} results`);
})();
```

---

## Best Practices

### 1. Token Management

- Store tokens securely (never in localStorage for sensitive apps)
- Use HTTP-only cookies for web applications
- Implement automatic token refresh
- Handle token expiration gracefully

### 2. Error Handling

- Always check response status codes
- Implement exponential backoff for retries
- Log errors for debugging
- Show user-friendly error messages

### 3. Performance

- Use caching where appropriate
- Implement request batching for multiple queries
- Monitor API response times
- Use compression for large payloads

### 4. Security

- Always use HTTPS in production
- Never expose tokens in URLs
- Validate and sanitize inputs
- Implement CSRF protection for web apps
- Use environment variables for sensitive data

---

## Support

### Resources

- **Documentation**: https://docs.companion-baas.example.com
- **API Status**: https://status.companion-baas.example.com
- **GitHub**: https://github.com/companion-baas/api

### Contact

- **Email**: support@companion-baas.example.com
- **Discord**: https://discord.gg/companion-baas
- **Twitter**: @companionbaas

---

**🚀 Built with Companion BaaS**
