# ISITAI - AI Image Detector

ISITAI (Image Sensitivity and Inspection Tool with AI) is a serverless web application designed to analyze, classify, and detect AI-generated synthetic images[cite: 1].

The platform is built on a high-performance Amazon Web Services (AWS) architecture[cite: 1], optimized to minimize latency and reduce costs through an image-hash caching mechanism powered by ElastiCache (Valkey)[cite: 1, 45].

---

## Key Features

* Instant Analysis: Upload JPEG, PNG, or WebP images without client-side re-compression to preserve digital artifacts[cite: 2, 13].
* Smart Hash Caching: Duplicate image detection using SHA-256 digests stored in ElastiCache Valkey Serverless (24h TTL)[cite: 1, 21].
* Session History: Anonymous per-session query history powered by DynamoDB[cite: 1, 22].
* Scalable Serverless Architecture: Static React frontend (S3 + CloudFront) interacting with REST endpoints on API Gateway and Python AWS Lambda functions[cite: 1].
* Observability and Monitoring: Centralized dashboards with CloudWatch metrics and structured logging[cite: 34, 35].

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

---

## Tech Stack

* Frontend: React, TypeScript, Vite[cite: 3, 12]
* Backend: Python 3.14, AWS Lambda, API Gateway[cite: 1]
* Database and Cache: DynamoDB, ElastiCache Serverless (Valkey 9)[cite: 1, 19, 22]
* Infrastructure: AWS CloudFormation, S3, CloudFront[cite: 1, 10]
