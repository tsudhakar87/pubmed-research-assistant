# pubmed-research-assistant
This is a project that allows users to automate their research and learning workflows via an application that uses the Google ADK and NCBI APIs. The 

Enable these gcloud APIs:
```
gcloud services enable aiplatform.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable bigquery.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

To run backend locally, first:
`cd bioinfo-backend`
then, either
`uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8080`
or
`python run.py`