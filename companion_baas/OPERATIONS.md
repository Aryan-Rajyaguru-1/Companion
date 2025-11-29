# Companion BaaS - Operations Runbook

**Version**: 1.0.0  
**Last Updated**: November 27, 2025

---

## 📋 Table of Contents

1. [Daily Operations](#daily-operations)
2. [Monitoring & Alerts](#monitoring--alerts)
3. [Scaling Procedures](#scaling-procedures)
4. [Backup & Recovery](#backup--recovery)
5. [Incident Response](#incident-response)
6. [Maintenance Tasks](#maintenance-tasks)
7. [Performance Tuning](#performance-tuning)

---

## Daily Operations

### Morning Checklist

**Check System Health**:

```bash
# Kubernetes
kubectl get pods -n companion-baas
kubectl get hpa -n companion-baas
kubectl top pods -n companion-baas

# API Health
curl https://api.companion-baas.example.com/health
```

**Review Metrics**:
- Visit Grafana: http://grafana.companion-baas.example.com
- Check Prometheus alerts: http://prometheus.companion-baas.example.com/alerts

**Key Metrics to Monitor**:
- API response time (p95 < 100ms)
- Error rate (< 1%)
- Cache hit rate (> 60%)
- CPU usage (< 70%)
- Memory usage (< 80%)
- Pod count and auto-scaling status

### Common Tasks

#### View Logs

```bash
# Real-time logs for all API pods
kubectl logs -f -n companion-baas -l component=api

# Logs for specific pod
kubectl logs -n companion-baas <pod-name>

# Logs with timestamps
kubectl logs -n companion-baas <pod-name> --timestamps

# Previous crashed container
kubectl logs -n companion-baas <pod-name> --previous
```

#### Check Resource Usage

```bash
# Pod resources
kubectl top pods -n companion-baas

# Node resources
kubectl top nodes

# Detailed resource metrics
kubectl describe pod <pod-name> -n companion-baas
```

#### Restart Services

```bash
# Rolling restart (zero downtime)
kubectl rollout restart deployment/companion-api -n companion-baas

# Check rollout status
kubectl rollout status deployment/companion-api -n companion-baas

# Rollback if needed
kubectl rollout undo deployment/companion-api -n companion-baas
```

---

## Monitoring & Alerts

### Prometheus Metrics

**Access Prometheus**:
```
http://prometheus.companion-baas.example.com
```

**Key Metrics**:

| Metric | Description | Alert Threshold |
|--------|-------------|----------------|
| `api_request_duration_seconds` | API response time | p95 > 1s |
| `api_requests_total` | Total requests | N/A |
| `api_errors_total` | Error count | Rate > 5% |
| `cache_hit_rate` | Cache efficiency | < 60% |
| `api_memory_bytes` | Memory usage | > 80% |
| `api_cpu_usage` | CPU usage | > 70% |

**Sample Queries**:

```promql
# Average response time (last 5m)
rate(api_request_duration_seconds_sum[5m]) / rate(api_request_duration_seconds_count[5m])

# Error rate
rate(api_errors_total[5m]) / rate(api_requests_total[5m]) * 100

# Cache hit rate
cache_hits_total / (cache_hits_total + cache_misses_total) * 100

# Memory usage per pod
sum(container_memory_usage_bytes{namespace="companion-baas"}) by (pod)
```

### Grafana Dashboards

**Access Grafana**:
```
http://grafana.companion-baas.example.com
```

**Default Credentials**: admin / admin (change immediately!)

**Recommended Dashboards**:
1. **API Performance**: Response times, throughput, errors
2. **Resource Usage**: CPU, memory, disk, network
3. **Cache Performance**: Hit rates, evictions, memory
4. **Pod Health**: Running pods, restarts, failures

### Alert Rules

**Configure AlertManager** (example):

```yaml
groups:
  - name: companion-baas-alerts
    rules:
      - alert: HighErrorRate
        expr: rate(api_errors_total[5m]) / rate(api_requests_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }}%"

      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API response time"
          description: "p95 latency is {{ $value }}s"

      - alert: LowCacheHitRate
        expr: cache_hits_total / (cache_hits_total + cache_misses_total) < 0.6
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low cache hit rate"
          description: "Cache hit rate is {{ $value }}%"

      - alert: HighMemoryUsage
        expr: (container_memory_usage_bytes / container_spec_memory_limit_bytes) > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value }}%"

      - alert: PodCrashLooping
        expr: rate(kube_pod_container_status_restarts_total{namespace="companion-baas"}[15m]) > 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Pod is crash looping"
          description: "Pod {{ $labels.pod }} is restarting"
```

---

## Scaling Procedures

### Manual Scaling

**Scale API Deployment**:

```bash
# Scale to 5 replicas
kubectl scale deployment companion-api -n companion-baas --replicas=5

# Verify
kubectl get pods -n companion-baas -l component=api
```

**Scale Supporting Services**:

```bash
# Scale Elasticsearch
kubectl scale statefulset elasticsearch -n companion-baas --replicas=3

# Scale Redis (if using statefulset)
kubectl scale statefulset redis -n companion-baas --replicas=3
```

### Auto-Scaling (HPA)

**Check HPA Status**:

```bash
kubectl get hpa -n companion-baas
```

**Update HPA Thresholds**:

```bash
# Edit HPA
kubectl edit hpa companion-api-hpa -n companion-baas

# Or apply updated file
kubectl apply -f k8s/hpa.yaml
```

**HPA Configuration**:

```yaml
spec:
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70  # Scale at 70% CPU
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80  # Scale at 80% memory
```

### Load Testing

**Test Scaling Behavior**:

```bash
# Install k6 (if not installed)
brew install k6  # macOS
# or
sudo apt-get install k6  # Linux

# Create test script (load-test.js)
cat > load-test.js << 'EOF'
import http from 'k6/http';
import { check } from 'k6';

export let options = {
  stages: [
    { duration: '2m', target: 100 },  // Ramp to 100 users
    { duration: '5m', target: 100 },  // Stay at 100 users
    { duration: '2m', target: 200 },  // Ramp to 200 users
    { duration: '5m', target: 200 },  // Stay at 200 users
    { duration: '2m', target: 0 },    // Ramp down
  ],
};

export default function () {
  let response = http.get('http://api.companion-baas.example.com/health');
  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
}
EOF

# Run test
k6 run load-test.js
```

---

## Backup & Recovery

### Data to Backup

1. **Elasticsearch Indices**
2. **Meilisearch Data**
3. **Redis Snapshots** (if persistent)
4. **Configuration Files**
5. **Secrets & Certificates**

### Backup Procedures

#### Elasticsearch Backup

```bash
# Create snapshot repository
curl -X PUT "http://elasticsearch:9200/_snapshot/my_backup" -H 'Content-Type: application/json' -d'
{
  "type": "fs",
  "settings": {
    "location": "/backups/elasticsearch"
  }
}
'

# Create snapshot
curl -X PUT "http://elasticsearch:9200/_snapshot/my_backup/snapshot_$(date +%Y%m%d)" -H 'Content-Type: application/json' -d'
{
  "indices": "*",
  "ignore_unavailable": true,
  "include_global_state": false
}
'

# Verify snapshot
curl -X GET "http://elasticsearch:9200/_snapshot/my_backup/_all"
```

#### Persistent Volume Backup

```bash
# List PVCs
kubectl get pvc -n companion-baas

# Create backup script
#!/bin/bash
NAMESPACE="companion-baas"
BACKUP_DIR="/backups/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# Backup Elasticsearch data
kubectl exec -n $NAMESPACE elasticsearch-0 -- tar czf - /usr/share/elasticsearch/data > $BACKUP_DIR/elasticsearch-data.tar.gz

# Backup Meilisearch data
kubectl exec -n $NAMESPACE meilisearch-0 -- tar czf - /meili_data > $BACKUP_DIR/meilisearch-data.tar.gz

echo "Backup completed: $BACKUP_DIR"
```

#### Configuration Backup

```bash
# Export all Kubernetes resources
kubectl get all -n companion-baas -o yaml > backup-resources.yaml
kubectl get configmap -n companion-baas -o yaml > backup-configmap.yaml
kubectl get secret -n companion-baas -o yaml > backup-secrets.yaml
```

### Recovery Procedures

#### Restore from Backup

```bash
# Restore Elasticsearch snapshot
curl -X POST "http://elasticsearch:9200/_snapshot/my_backup/snapshot_20251127/_restore"

# Restore PVC data
kubectl exec -n companion-baas elasticsearch-0 -- tar xzf - -C /usr/share/elasticsearch/data < elasticsearch-data.tar.gz
```

#### Disaster Recovery

**Complete Environment Recreation**:

```bash
# 1. Recreate namespace
kubectl apply -f k8s/namespace.yaml

# 2. Restore configuration
kubectl apply -f backup-configmap.yaml
kubectl apply -f backup-secrets.yaml

# 3. Restore PVCs
kubectl apply -f k8s/pvc.yaml

# 4. Deploy application
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# 5. Restore data
# (Follow restore procedures above)

# 6. Verify
kubectl get pods -n companion-baas
curl http://api.companion-baas.example.com/health
```

---

## Incident Response

### Severity Levels

| Severity | Description | Response Time |
|----------|-------------|---------------|
| **P0 - Critical** | Complete service outage | Immediate |
| **P1 - High** | Major feature broken | < 1 hour |
| **P2 - Medium** | Minor feature issues | < 4 hours |
| **P3 - Low** | Cosmetic issues | Next business day |

### Incident Response Process

1. **Acknowledge**: Confirm incident in monitoring system
2. **Assess**: Determine severity and impact
3. **Communicate**: Notify team and stakeholders
4. **Investigate**: Gather logs and metrics
5. **Mitigate**: Implement temporary fix
6. **Resolve**: Deploy permanent solution
7. **Document**: Write post-mortem

### Common Incidents

#### P0: API Down

**Symptoms**:
- Health check failing
- 5xx errors
- No responses

**Investigation**:
```bash
# Check pod status
kubectl get pods -n companion-baas

# Check logs
kubectl logs -f -n companion-baas -l component=api --tail=100

# Check events
kubectl get events -n companion-baas --sort-by='.lastTimestamp'
```

**Resolution**:
```bash
# Restart deployment
kubectl rollout restart deployment/companion-api -n companion-baas

# If persistent, rollback
kubectl rollout undo deployment/companion-api -n companion-baas

# Scale up temporarily
kubectl scale deployment companion-api -n companion-baas --replicas=10
```

#### P1: High Error Rate

**Investigation**:
```bash
# Check error logs
kubectl logs -n companion-baas -l component=api | grep -i error

# Check metrics in Prometheus
# Query: rate(api_errors_total[5m])
```

**Resolution**:
- Identify failing endpoint
- Review recent changes
- Rollback if needed
- Fix and redeploy

#### P2: Slow Response Times

**Investigation**:
```bash
# Check resource usage
kubectl top pods -n companion-baas

# Check database performance
# Elasticsearch query performance
# Redis connection stats
```

**Resolution**:
- Scale up pods
- Optimize database queries
- Increase cache TTL
- Review recent code changes

---

## Maintenance Tasks

### Weekly Tasks

- Review and rotate logs
- Check disk usage
- Update security patches
- Review error logs
- Clean up old backups

### Monthly Tasks

- Update dependencies
- Review and optimize database indices
- Performance testing
- Security audit
- Disaster recovery drill

### Quarterly Tasks

- Major version updates
- Infrastructure review
- Capacity planning
- Cost optimization
- Documentation updates

---

## Performance Tuning

### API Optimization

**Increase Workers**:
```yaml
# In values.yaml or configmap
WORKERS: "8"  # Increase from 4
```

**Adjust Cache Settings**:
```yaml
CACHE_L1_SIZE: "200"  # Increase from 100
CACHE_L1_TTL: "120"   # Increase from 60
```

### Database Optimization

**Elasticsearch**:
```bash
# Increase heap size
-Xms2g -Xmx2g
```

**Redis**:
```bash
# Configure maxmemory-policy
maxmemory-policy allkeys-lru
maxmemory 512mb
```

### Kubernetes Resource Tuning

**Update Resource Limits**:
```yaml
resources:
  requests:
    cpu: 200m      # Increase from 100m
    memory: 256Mi  # Increase from 128Mi
  limits:
    cpu: 1000m     # Increase from 500m
    memory: 1Gi    # Increase from 512Mi
```

---

## Contact & Escalation

### On-Call Contacts

- **Primary**: operations@companion-baas.example.com
- **Secondary**: engineering@companion-baas.example.com
- **Manager**: manager@companion-baas.example.com

### External Support

- **Cloud Provider**: support@cloudprovider.com
- **Kubernetes**: https://kubernetes.io/docs/
- **Monitoring**: support@prometheus.io

---

**🚀 Companion BaaS - Operations Excellence**

