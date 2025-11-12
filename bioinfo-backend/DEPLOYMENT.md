# Deployment Guide: FastAPI Backend to Google Cloud Run

This guide walks you through deploying the bioinformatics research assistant backend API to Google Cloud Run.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Manual Deployment](#manual-deployment)
- [Configuration](#configuration)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### 1. Google Cloud Setup

1. **Google Cloud Project**
   ```bash
   # Create a new project (or use existing)
   gcloud projects create your-project-id
   gcloud config set project your-project-id
   ```

2. **Enable Billing**
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Enable billing for your project

3. **Install gcloud CLI**
   ```bash
   # macOS
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL

   # Or download from: https://cloud.google.com/sdk/docs/install
   ```

4. **Authenticate**
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

### 2. Local Development

1. **Python 3.11+** installed
2. **Docker** (optional, for local testing)
3. **Environment variables** configured (`.env` file)

## Quick Start

The easiest way to deploy is using the automated script:

```bash
# Set your Google Cloud project ID
export PROJECT_ID="your-project-id"

# Run the deployment script
./deploy.sh
```

This script will:
1. Enable required Google Cloud APIs
2. Create Artifact Registry repository
3. Configure Cloud Build permissions
4. Optionally create secrets in Secret Manager
5. Build and deploy to Cloud Run

**Deployment time:** ~5-10 minutes

## Manual Deployment

If you prefer manual control or need to customize the deployment:

### Step 1: Enable APIs

```bash
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com
```

### Step 2: Create Artifact Registry Repository

```bash
gcloud artifacts repositories create bioinfo-docker-repo \
    --repository-format=docker \
    --location=us-central1 \
    --description="Docker repository for bioinfo backend"
```

### Step 3: Grant Cloud Build Permissions

```bash
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
    --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser"
```

### Step 4: Create Secrets (Optional but Recommended)

```bash
# NCBI credentials
echo -n "your-email@example.com" | gcloud secrets create ncbi-email --data-file=-
echo -n "your-ncbi-api-key" | gcloud secrets create ncbi-api-key --data-file=-

# Grant Cloud Run access to secrets
gcloud secrets add-iam-policy-binding ncbi-email \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding ncbi-api-key \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

### Step 5: Deploy with Cloud Build

```bash
gcloud builds submit \
    --config=cloudbuild.yaml \
    --substitutions=_SERVICE_NAME=bioinfo-backend-api,_REGION=us-central1
```

### Step 6: Get Service URL

```bash
gcloud run services describe bioinfo-backend-api \
    --region=us-central1 \
    --format="value(status.url)"
```

## Configuration

### Environment Variables

Cloud Run services can use environment variables for configuration:

```bash
# Set environment variables
gcloud run services update bioinfo-backend-api \
    --region=us-central1 \
    --set-env-vars=ENVIRONMENT=production \
    --set-env-vars=PROJECT_ID=your-project-id \
    --set-env-vars=CORS_ORIGINS=https://your-frontend.com
```

### Using Secrets

Uncomment the secret lines in `cloudbuild.yaml`:

```yaml
# - '--set-secrets=NCBI_EMAIL=ncbi-email:latest'
# - '--set-secrets=NCBI_API_KEY=ncbi-api-key:latest'
```

Or set them after deployment:

```bash
gcloud run services update bioinfo-backend-api \
    --region=us-central1 \
    --set-secrets=NCBI_EMAIL=ncbi-email:latest \
    --set-secrets=NCBI_API_KEY=ncbi-api-key:latest
```

### CORS Configuration

To allow your frontend to access the API:

```bash
gcloud run services update bioinfo-backend-api \
    --region=us-central1 \
    --set-env-vars=CORS_ORIGINS=https://your-frontend-domain.com,https://your-other-domain.com
```

### Resource Configuration

Adjust CPU, memory, and scaling in `cloudbuild.yaml` or via CLI:

```bash
gcloud run services update bioinfo-backend-api \
    --region=us-central1 \
    --memory=2Gi \
    --cpu=2 \
    --min-instances=1 \
    --max-instances=20
```

## Testing Your Deployment

### 1. Health Check

```bash
SERVICE_URL=$(gcloud run services describe bioinfo-backend-api \
    --region=us-central1 \
    --format="value(status.url)")

curl $SERVICE_URL/api/v1/health
```

Expected response:
```json
{
  "status": "healthy",
  "environment": "production"
}
```

### 2. API Documentation

Visit `https://your-service-url.run.app/docs` to see interactive API documentation.

### 3. Test Search Endpoint

```bash
curl -X POST "$SERVICE_URL/api/v1/search" \
    -H "Content-Type: application/json" \
    -d '{"query": "CRISPR gene editing", "max_results": 5}'
```

## Monitoring

### View Logs

```bash
# Recent logs
gcloud run services logs read bioinfo-backend-api \
    --region=us-central1 \
    --limit=50

# Follow logs in real-time
gcloud run services logs tail bioinfo-backend-api \
    --region=us-central1
```

### Cloud Console

- **Logs**: https://console.cloud.google.com/logs
- **Cloud Run**: https://console.cloud.google.com/run
- **Metrics**: Check CPU, memory, request count, latency in Cloud Run dashboard

### Set Up Alerts

```bash
# Example: Alert on high error rate
gcloud alpha monitoring policies create \
    --notification-channels=your-channel-id \
    --display-name="High Error Rate Alert" \
    --condition-display-name="Error rate > 5%" \
    --condition-threshold-value=5 \
    --condition-threshold-duration=300s
```

## CI/CD Integration

### GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - id: 'auth'
        uses: 'google-github-actions/auth@v1'
        with:
          credentials_json: '${{ secrets.GCP_SA_KEY }}'

      - name: Deploy to Cloud Run
        run: |
          gcloud builds submit \
            --config=cloudbuild.yaml \
            --substitutions=_SERVICE_NAME=bioinfo-backend-api
```

## Troubleshooting

### Build Fails

**Problem:** Docker build fails

**Solution:**
```bash
# Test build locally first
docker build -t test-image .
docker run -p 8080:8080 -e PORT=8080 test-image

# Check Cloud Build logs
gcloud builds list --limit=1
gcloud builds log <BUILD_ID>
```

### Service Not Responding

**Problem:** 503 errors or timeout

**Solutions:**
1. Check if service is running:
   ```bash
   gcloud run services describe bioinfo-backend-api --region=us-central1
   ```

2. Increase timeout:
   ```bash
   gcloud run services update bioinfo-backend-api \
       --region=us-central1 \
       --timeout=300
   ```

3. Check startup time:
   ```bash
   gcloud run services logs read bioinfo-backend-api --region=us-central1 --limit=20
   ```

### CORS Issues

**Problem:** Frontend can't access API

**Solution:**
```bash
# Add your frontend domain to CORS origins
gcloud run services update bioinfo-backend-api \
    --region=us-central1 \
    --set-env-vars=CORS_ORIGINS=https://your-frontend.com
```

### Out of Memory

**Problem:** Container crashes with OOMKilled

**Solution:**
```bash
# Increase memory allocation
gcloud run services update bioinfo-backend-api \
    --region=us-central1 \
    --memory=2Gi
```

### Permission Errors

**Problem:** Cannot access secrets or GCP services

**Solution:**
```bash
# Grant necessary permissions to Cloud Run service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

## Cost Optimization

Cloud Run pricing is based on:
- Request count
- CPU time
- Memory usage
- Network egress

### Tips to Reduce Costs

1. **Scale to zero:** Set `--min-instances=0` for dev environments
2. **Right-size resources:** Start with 1GB RAM, 1 CPU, adjust based on metrics
3. **Use caching:** Implement Redis/Memorystore for frequently accessed data
4. **Optimize cold starts:** Keep dependencies minimal

## Security Best Practices

1. **Use Secret Manager** for sensitive data (API keys, credentials)
2. **Enable authentication** for production:
   ```bash
   gcloud run services update bioinfo-backend-api \
       --region=us-central1 \
       --no-allow-unauthenticated
   ```
3. **Set up VPC connector** if accessing private resources
4. **Regular updates:** Rebuild and redeploy regularly for security patches

## Rollback

If you need to rollback to a previous version:

```bash
# List revisions
gcloud run revisions list --service=bioinfo-backend-api --region=us-central1

# Rollback to specific revision
gcloud run services update-traffic bioinfo-backend-api \
    --region=us-central1 \
    --to-revisions=bioinfo-backend-api-00001-abc=100
```

## Additional Resources

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [Cloud Build Documentation](https://cloud.google.com/build/docs)
- [Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)

## Support

For issues or questions:
- Check Cloud Run logs first
- Review the troubleshooting section
- Open an issue in the repository
