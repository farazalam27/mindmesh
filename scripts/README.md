# MindMesh Scripts

This directory contains essential DevOps and operational scripts for managing the MindMesh platform.

## Scripts Overview

### 🚀 deploy.sh
**Kubernetes Deployment Automation**
- Automated deployment of all MindMesh services to Kubernetes
- Supports multiple environments (production, staging, development)
- Rolling updates with health checks
- Rollback capabilities

```bash
# Full deployment
./deploy.sh deploy --environment production --version v1.2.3

# Deploy only infrastructure
./deploy.sh deploy-infra --namespace mindmesh-staging

# Check deployment status
./deploy.sh status

# Rollback deployment
./deploy.sh rollback
```

### 🔍 health-check.sh
**Comprehensive Health Monitoring**
- Application and infrastructure health checks
- Continuous monitoring mode
- Alert notifications via webhooks
- Detailed health reports

```bash
# Single health check
./health-check.sh check

# Continuous monitoring
./health-check.sh monitor --interval 60 --webhook https://hooks.slack.com/...

# Generate detailed report
./health-check.sh report --verbose

# Test alert system
./health-check.sh test-alerts
```

### 💾 backup.sh
**Database and Application Backup**
- PostgreSQL database backups
- Redis data backups
- Kubernetes configuration backups
- S3 integration for remote storage
- Encryption and compression support

```bash
# Create full backup
./backup.sh backup --compress --s3-bucket my-backups

# List available backups
./backup.sh list

# Clean up old backups
./backup.sh cleanup --retention 30

# Test backup system
./backup.sh test
```

### 🗄️ init-db.sh
**Database Initialization and Management**
- Database schema creation
- Sample data seeding
- Migration management
- Database reset capabilities

```bash
# Initialize database
./init-db.sh init --environment production

# Run migrations
./init-db.sh migrate --kubectl

# Seed with sample data
./init-db.sh seed --environment development

# Check database status
./init-db.sh status
```

## Common Options

All scripts support these common options:

- `-e, --environment ENV`: Target environment (production, staging, development)
- `-n, --namespace NS`: Kubernetes namespace
- `-v, --verbose`: Enable verbose output
- `-h, --help`: Show help message

## Environment Variables

Set these environment variables for default configuration:

```bash
export NAMESPACE=mindmesh
export ENVIRONMENT=production
export DOCKER_REGISTRY=ghcr.io/farazalam27/mindmesh
export S3_BUCKET=mindmesh-backups
export ALERT_WEBHOOK=https://hooks.slack.com/...
```

## Prerequisites

### Required Tools
- `kubectl` - Kubernetes CLI
- `docker` - Container runtime
- `aws` - AWS CLI (for S3 backups)
- `curl` - HTTP client
- `jq` - JSON processor (recommended)

### Kubernetes Access
Ensure your kubectl is configured to access the target cluster:

```bash
# Check cluster access
kubectl cluster-info

# List namespaces
kubectl get namespaces

# Test permissions
kubectl auth can-i create deployments --namespace mindmesh
```

## Usage Examples

### Production Deployment
```bash
# 1. Deploy infrastructure first
./deploy.sh deploy-infra --environment production

# 2. Deploy applications
./deploy.sh deploy-apps --environment production --version v1.2.3

# 3. Check deployment status
./deploy.sh status

# 4. Monitor health
./health-check.sh monitor --interval 300
```

### Staging Environment Setup
```bash
# 1. Initialize database
./init-db.sh init --environment staging --kubectl

# 2. Deploy all services
./deploy.sh deploy --environment staging --namespace mindmesh-staging

# 3. Seed with test data
./init-db.sh seed --environment staging --kubectl

# 4. Create backup
./backup.sh backup --environment staging
```

### Emergency Procedures

#### Quick Health Check
```bash
./health-check.sh check --namespace mindmesh
```

#### Emergency Rollback
```bash
./deploy.sh rollback --namespace mindmesh
```

#### Database Backup Before Changes
```bash
./backup.sh backup --environment production --webhook $SLACK_WEBHOOK
```

#### Full System Reset (Development Only)
```bash
./init-db.sh reset --environment development --force
./deploy.sh cleanup --namespace mindmesh-dev
```

## Monitoring and Alerts

### Setting Up Continuous Monitoring
```bash
# Start monitoring in background
nohup ./health-check.sh monitor \
  --interval 60 \
  --webhook https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK \
  > /var/log/mindmesh-health.log 2>&1 &
```

### Setting Up Automated Backups
```bash
# Add to crontab for daily backups at 2 AM
0 2 * * * /path/to/scripts/backup.sh backup --environment production --s3-bucket mindmesh-backups

# Weekly cleanup at 3 AM on Sundays
0 3 * * 0 /path/to/scripts/backup.sh cleanup --retention 30
```

## Troubleshooting

### Common Issues

#### Connection Failures
```bash
# Check kubectl configuration
kubectl config current-context
kubectl cluster-info

# Verify namespace exists
kubectl get namespace mindmesh

# Check pod status
kubectl get pods -n mindmesh
```

#### Backup Failures
```bash
# Test database connectivity
./init-db.sh test --kubectl

# Check S3 permissions
aws s3 ls s3://mindmesh-backups/

# Verify disk space
df -h /backups/mindmesh
```

#### Deployment Issues
```bash
# Check deployment status
kubectl get deployments -n mindmesh

# View pod logs
kubectl logs -l app=ideas-service -n mindmesh

# Check events
kubectl get events -n mindmesh --sort-by='.lastTimestamp'
```

### Debug Mode
Enable debug output for all scripts:
```bash
export VERBOSE=true
export DEBUG=true
```

## Security Considerations

### Sensitive Data
- Database passwords are retrieved from Kubernetes secrets
- Use encrypted backups with `--encryption-key`
- Webhook URLs should use HTTPS
- Limit script permissions to necessary operations only

### Access Control
- Scripts should run with minimal required privileges
- Use Kubernetes RBAC for cluster access
- Rotate credentials regularly
- Monitor script execution logs

## Integration with CI/CD

### GitHub Actions Integration
```yaml
- name: Deploy to Production
  run: |
    ./scripts/deploy.sh deploy \
      --environment production \
      --version ${{ github.sha }} \
      --namespace mindmesh
```

### Jenkins Integration
```groovy
stage('Deploy') {
    steps {
        sh '''
            ./scripts/deploy.sh deploy \
                --environment ${ENVIRONMENT} \
                --version ${BUILD_NUMBER} \
                --namespace mindmesh-${ENVIRONMENT}
        '''
    }
}
```

## Contributing

When adding new scripts or modifying existing ones:

1. Follow the established patterns for argument parsing and logging
2. Include comprehensive help text and examples
3. Add error handling and validation
4. Test in development environment first
5. Update this README with new functionality

## Support

For issues with these scripts:
1. Check the verbose output (`-v` flag)
2. Review the logs in `/var/log/mindmesh-*.log`
3. Verify prerequisites and permissions
4. Check the GitHub Issues for known problems