# ISITAI - AI Image Detector

ISITAI (Image Sensitivity and Inspection Tool with AI) is a serverless web application designed to analyze, classify, and detect AI-generated synthetic images.

The platform is built on a high-performance Amazon Web Services (AWS) architecture, optimized to minimize latency and reduce costs through an image-hash caching mechanism powered by ElastiCache (Valkey).

---

## Key Features

- **Instant Analysis:** Upload JPEG, PNG, or WebP images without client-side re-compression to preserve digital artifacts.
- **Smart Hash Caching:** Duplicate image detection using SHA-256 digests stored in ElastiCache Valkey Serverless (24h TTL).
- **Session History:** Anonymous per-session query history powered by DynamoDB.
- **Scalable Serverless Architecture:** Static React frontend (S3 + CloudFront) interacting with REST endpoints on API Gateway and Python AWS Lambda functions.
- **Observability and Monitoring:** Centralized dashboards with CloudWatch metrics and structured logging.

---

## Repository Structure

```text
isitai/
├── infra/            # CloudFormation templates and deployment scripts
├── backend/          # Lambda function handlers and Python modules
│   ├── src/isitai/   # Core backend library
│   ├── mock_model/   # Mock model Function URL handler
│   └── tests/        # Unit and integration tests (pytest)
├── frontend/         # React + Vite TypeScript web application
├── dataset/          # Dataset processing and S3 upload scripts
└── docs/             # Technical documentation and runbooks
```

---

## Tech Stack

- **Frontend:** React, TypeScript, Vite
- **Backend:** Python 3.14, AWS Lambda, API Gateway 
- **Database and Cache:** DynamoDB, ElastiCache Serverless (Valkey 9) 
- **Infrastructure:** AWS CloudFormation, S3, CloudFront 
