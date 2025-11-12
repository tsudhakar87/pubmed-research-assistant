#!/bin/bash

# Deployment script for FastAPI backend to Google Cloud Run
# This script automates the setup and deployment process

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${PROJECT_ID:-}"
SERVICE_NAME="${SERVICE_NAME:-bioinfo-backend-api}"
REGION="${REGION:-us-central1}"
REPOSITORY="${REPOSITORY:-bioinfo-docker-repo}"

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  Bioinfo Backend Deployment${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# Check if PROJECT_ID is set
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}ERROR: PROJECT_ID is not set${NC}"
    echo "Usage: PROJECT_ID=your-project-id ./deploy.sh"
    echo "Or set it as an environment variable: export PROJECT_ID=your-project-id"
    exit 1
fi

echo "Project ID: $PROJECT_ID"
echo "Service Name: $SERVICE_NAME"
echo "Region: $REGION"
echo "Repository: $REPOSITORY"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}ERROR: gcloud CLI is not installed${NC}"
    echo "Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set the project
echo -e "${YELLOW}Setting gcloud project...${NC}"
gcloud config set project "$PROJECT_ID"

# Enable required APIs
echo -e "${YELLOW}Enabling required Google Cloud APIs...${NC}"
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com

# Create Artifact Registry repository if it doesn't exist
echo -e "${YELLOW}Creating Artifact Registry repository (if needed)...${NC}"
gcloud artifacts repositories describe "$REPOSITORY" \
    --location="$REGION" \
    --format="get(name)" &> /dev/null || \
    gcloud artifacts repositories create "$REPOSITORY" \
        --repository-format=docker \
        --location="$REGION" \
        --description="Docker repository for bioinfo backend"

# Grant Cloud Build permissions to deploy to Cloud Run
echo -e "${YELLOW}Configuring Cloud Build permissions...${NC}"
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
    --role="roles/run.admin" \
    --no-user-output-enabled || true

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
    --role="roles/iam.serviceAccountUser" \
    --no-user-output-enabled || true

# Optional: Create secrets in Secret Manager
echo ""
read -p "Do you want to create secrets in Secret Manager? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Creating secrets...${NC}"

    # NCBI Email
    if ! gcloud secrets describe ncbi-email &> /dev/null; then
        read -p "Enter NCBI Email: " ncbi_email
        echo -n "$ncbi_email" | gcloud secrets create ncbi-email --data-file=-
        echo -e "${GREEN}Created secret: ncbi-email${NC}"
    else
        echo "Secret 'ncbi-email' already exists"
    fi

    # NCBI API Key
    if ! gcloud secrets describe ncbi-api-key &> /dev/null; then
        read -p "Enter NCBI API Key (or press Enter to skip): " ncbi_api_key
        if [ -n "$ncbi_api_key" ]; then
            echo -n "$ncbi_api_key" | gcloud secrets create ncbi-api-key --data-file=-
            echo -e "${GREEN}Created secret: ncbi-api-key${NC}"
        fi
    else
        echo "Secret 'ncbi-api-key' already exists"
    fi

    echo -e "${YELLOW}Note: Update cloudbuild.yaml to use these secrets${NC}"
fi

# Build and deploy using Cloud Build
echo ""
echo -e "${YELLOW}Building and deploying to Cloud Run...${NC}"
echo "This may take several minutes..."
echo ""

gcloud builds submit \
    --config=cloudbuild.yaml \
    --substitutions=_SERVICE_NAME="$SERVICE_NAME",_REGION="$REGION",_REPOSITORY="$REPOSITORY"

# Get the service URL
echo ""
echo -e "${GREEN}Deployment complete!${NC}"
echo ""
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" \
    --region="$REGION" \
    --format="value(status.url)")

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}  Deployment Successful!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo "Service URL: $SERVICE_URL"
echo "API Docs: $SERVICE_URL/docs"
echo "Health Check: $SERVICE_URL/api/v1/health"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Test the API: curl $SERVICE_URL/api/v1/health"
echo "2. Set CORS_ORIGINS env var if you have a frontend:"
echo "   gcloud run services update $SERVICE_NAME \\"
echo "     --region=$REGION \\"
echo "     --set-env-vars=CORS_ORIGINS=https://your-frontend-domain.com"
echo ""
