# Companion BaaS - Deployment Guide

**Version**: 1.0.0  
**Last Updated**: November 27, 2025

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Helm Deployment](#helm-deployment)
6. [Configuration](#configuration)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Python**: 3.11 or higher
- **Docker**: 20.10 or higher
- **Docker Compose**: 1.29 or higher (for Docker deployment)
- **Kubernetes**: 1.24 or higher (for K8s deployment)
- **Helm**: 3.10 or higher (for Helm deployment)
- **kubectl**: Latest version

### System Requirements

- **CPU**: 2+ cores
- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: 20GB free space
- **Network**: Internet access for Docker images

---

## Local Development

### 1. Clone the Repository

```bash
git clone https://github.com/Aryan-Rajyaguru-1/Companion.git
cd Companion/companion_baas
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.prod.txt
```

### 4. Set Environment Variables

```bash
export JWT_SECRET="your-secret-key-here"
export PORT=8000
export LOG_LEVEL=info
```

### 5. Start the API

```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Verify Installation

```bash
curl http://localhost:8000/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "checks": {"api": true},
  "timestamp": 1764248834.8610585
}
```

---

## Docker Deployment

### Option 1: Docker Compose (Recommended)

**Start Full Stack** (7 services):

```bash
cd companion_baas
docker-compose -f docker-compose.production.yml up -d --build
```

**Services Included**:
- API Service (port 8000)
- Elasticsearch (port 9200)
- Meilisearch (port 7700)
- Redis (port 6379)
- Nginx (port 80)
- Prometheus (port 9090)
- Grafana (port 3000)

**Check Status**:

```bash
docker-compose -f docker-compose.production.yml ps
```

**View Logs**:

```bash
# All services
docker-compose -f docker-compose.production.yml logs -f

# Specific service
docker-compose -f docker-compose.production.yml logs -f api
```

**Stop Stack**:

```bash
docker-compose -f docker-compose.production.yml down
```

### Option 2: Standalone Docker

**Build Image**:

```bash
docker build -t companion-baas:latest .
```

**Run Container**:

```bash
docker run -d \
  --name companion-api \
  -p 8000:8000 \
  -e JWT_SECRET="your-secret-key" \
  -e LOG_LEVEL=info \
  companion-baas:latest
```

**Access API**:

```bash
curl http://localhost:8000/
```

---

## Kubernetes Deployment

### 1. Prerequisites

Ensure you have a running Kubernetes cluster:

```bash
# Verify cluster access
kubectl cluster-info
kubectl get nodes
```

### 2. Create Namespace

```bash
kubectl apply -f k8s/namespace.yaml
```

### 3. Deploy Configuration

```bash
# ConfigMap
kubectl apply -f k8s/configmap.yaml

# Secrets (⚠️  Update secrets first!)
kubectl apply -f k8s/secrets.yaml

# Persistent Volume Claims
kubectl apply -f k8s/pvc.yaml
```

**⚠️  Important**: Edit `k8s/secrets.yaml` and update:
- `JWT_SECRET`: Generate with `openssl rand -base64 32`
- `OPENROUTER_API_KEY`: Your OpenRouter API key
- `ELASTIC_PASSWORD`: Strong password for Elasticsearch

### 4. Deploy Application

```bash
# Deployment
kubectl apply -f k8s/deployment.yaml

# Services
kubectl apply -f k8s/service.yaml

# Ingress (optional, requires Ingress Controller)
kubectl apply -f k8s/ingress.yaml

# Horizontal Pod Autoscaler
kubectl apply -f k8s/hpa.yaml
```

### 5. Verify Deployment

```bash
# Check pods
kubectl get pods -n companion-baas

# Check services
kubectl get svc -n companion-baas

# Check deployment
kubectl get deployment -n companion-baas

# View logs
kubectl logs -f -n companion-baas deployment/companion-api
```

### 6. Access the API

**Using Port Forward**:

```bash
kubectl port-forward -n companion-baas svc/companion-api 8000:8000
```

Then access: http://localhost:8000

**Using Ingress** (if configured):

Access via your configured domain: https://api.companion-baas.example.com

### 7. Scale the Deployment

**Manual Scaling**:

```bash
kubectl scale deployment companion-api -n companion-baas --replicas=5
```

**Auto-Scaling** (via HPA):

Configured to scale between 2-10 pods based on CPU/Memory usage.

---

## Helm Deployment

### 1. Prerequisites

```bash
# Verify Helm installation
helm version

# Add any required repositories
# (None required for this deployment)
```

### 2. Install with Helm

**Default Installation**:

```bash
cd helm
helm install companion-baas ./companion-baas --namespace companion-baas --create-namespace
```

**Custom Values**:

Create a `custom-values.yaml`:

```yaml
api:
  replicaCount: 5
  resources:
    limits:
      memory: "1Gi"
  secrets:
    jwtSecret: "your-production-secret-here"

ingress:
  enabled: true
  hosts:
    - host: api.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
```

Install with custom values:

```bash
helm install companion-baas ./companion-baas \
  --namespace companion-baas \
  --create-namespace \
  --values custom-values.yaml
```

### 3. Verify Installation

```bash
# Check release
helm list -n companion-baas

# Check resources
kubectl get all -n companion-baas
```

### 4. Upgrade Deployment

```bash
# Update values
helm upgrade companion-baas ./companion-baas \
  --namespace companion-baas \
  --values custom-values.yaml
```

### 5. Uninstall

```bash
helm uninstall companion-baas --namespace companion-baas
```

### 6. Helm Chart Values

Key configuration options in `values.yaml`:

```yaml
# API Configuration
api:
  replicaCount: 3               # Number of API replicas
  image:
    repository: companion-baas
    tag: latest
  
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70

  config:
    port: 8000
    logLevel: info
    workers: 4

# Ingress Configuration
ingress:
  enabled: true
  className: "nginx"
  hosts:
    - host: api.companion-baas.example.com
      paths:
        - path: /
          pathType: Prefix

# Enable/Disable Services
elasticsearch:
  enabled: true
meilisearch:
  enabled: true
redis:
  enabled: true
prometheus:
  enabled: true
grafana:
  enabled: true
```

---

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PORT` | API port | `8000` | No |
| `LOG_LEVEL` | Logging level | `info` | No |
| `WORKERS` | Gunicorn workers | `4` | No |
| `JWT_SECRET` | JWT signing secret | - | **Yes** |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` | No |
| `JWT_EXPIRATION_HOURS` | Token expiration | `24` | No |
| `ELASTICSEARCH_URL` | Elasticsearch URL | `http://elasticsearch:9200` | No |
| `MEILISEARCH_URL` | Meilisearch URL | `http://meilisearch:7700` | No |
| `REDIS_URL` | Redis URL | `redis://redis:6379` | No |
| `OPENROUTER_API_KEY` | OpenRouter API key | - | No |
| `GROQ_API_KEY` | Groq API key | - | No |

### Security Configuration

**Generate JWT Secret**:

```bash
openssl rand -base64 32
```

**Update Secrets**:

For Kubernetes:
```bash
kubectl create secret generic companion-api-secrets \
  --from-literal=JWT_SECRET="$(openssl rand -base64 32)" \
  --namespace=companion-baas \
  --dry-run=client -o yaml | kubectl apply -f -
```

For Docker Compose:
Update `.env` file or pass via environment variables.

---

## Troubleshooting

### Common Issues

#### 1. API Not Starting

**Symptom**: Container exits immediately

**Check Logs**:
```bash
# Docker
docker logs companion-api

# Kubernetes
kubectl logs -n companion-baas deployment/companion-api
```

**Common Causes**:
- Missing JWT_SECRET
- Port already in use
- Dependency service not ready

**Solution**:
```bash
# Verify configuration
kubectl get configmap companion-api-config -n companion-baas -o yaml

# Check secrets
kubectl get secret companion-api-secrets -n companion-baas
```

#### 2. Health Check Failing

**Check Health Endpoint**:
```bash
curl http://localhost:8000/health
```

**Verify Dependencies**:
```bash
# Check if Elasticsearch is running
curl http://localhost:9200

# Check if Redis is accessible
redis-cli ping
```

#### 3. Authentication Errors

**Symptom**: 401 Unauthorized errors

**Solution**:
1. Verify JWT_SECRET is set correctly
2. Check token expiration
3. Ensure token is passed in Authorization header:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/search
   ```

#### 4. Performance Issues

**Check Resource Usage**:
```bash
# Kubernetes
kubectl top pods -n companion-baas

# Docker
docker stats companion-api
```

**Scale Up**:
```bash
# Kubernetes
kubectl scale deployment companion-api -n companion-baas --replicas=5

# Or let HPA do it automatically
kubectl get hpa -n companion-baas
```

#### 5. Database Connection Issues

**Elasticsearch Not Ready**:
```bash
# Wait for Elasticsearch to be healthy
kubectl wait --for=condition=Ready pod -l component=elasticsearch -n companion-baas --timeout=300s
```

**Redis Connection Failed**:
```bash
# Test Redis connection
kubectl run redis-test --rm -it --restart=Never --image=redis:7-alpine -- redis-cli -h redis ping
```

### Debug Commands

**View All Resources**:
```bash
kubectl get all -n companion-baas
```

**Describe Pod**:
```bash
kubectl describe pod <pod-name> -n companion-baas
```

**Get Events**:
```bash
kubectl get events -n companion-baas --sort-by='.lastTimestamp'
```

**Port Forward for Debugging**:
```bash
kubectl port-forward -n companion-baas svc/companion-api 8000:8000
```

---

## Next Steps

1. **Configure Monitoring**: See [OPERATIONS.md](OPERATIONS.md)
2. **Set Up CI/CD**: Use the provided `.github/workflows/ci-cd.yml`
3. **Configure SSL/TLS**: Add certificates to Ingress
4. **Set Up Backups**: Configure persistent volume backups
5. **API Documentation**: See [API_DOCS.md](API_DOCS.md)

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/Aryan-Rajyaguru-1/Companion/issues
- Documentation: https://github.com/Aryan-Rajyaguru-1/Companion
- Email: team@companion-baas.example.com

---

**🎉 Companion BaaS - Production-Ready Deployment**
