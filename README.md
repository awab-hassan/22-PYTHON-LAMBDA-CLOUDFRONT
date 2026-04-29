# Project # 22 - cloudfront-cache-manager-lambda

A Python 3.12 Lambda (provisioned via Terraform) that dynamically manages CloudFront cache behaviors and issues path-pattern invalidations through a single HTTPS endpoint. Lets the application layer add or remove per-path caching rules without manual distribution edits or a release.

## How It Works

```
Client
   |
   | POST { action: "add" | "remove", path_pattern: "/api/foo/*" }
   v
Lambda Function URL
   |
   v
cache-manager Lambda (Python 3.12, boto3)
   |
   +-- add:    GetDistributionConfig -> patch CacheBehaviors -> UpdateDistribution
   +-- remove: CreateInvalidation    -> GetDistributionConfig -> drop behavior -> UpdateDistribution
   |
   v
CloudFront distribution
```

### `action = "add"`

1. `GetDistributionConfig` to fetch current config and `ETag`.
2. Build a new `CacheBehavior` with:
   - `PathPattern = <input>`
   - `ViewerProtocolPolicy = redirect-to-https`
   - `AllowedMethods` and `CachedMethods` set to `GET, HEAD`
   - `CachePolicyId` set to AWS-managed `CachingOptimized`
   - `OriginRequestPolicyId` set to AWS-managed `AllViewer`
3. Append (or update in place if the pattern already exists).
4. `UpdateDistribution(IfMatch=ETag, ...)`.

### `action = "remove"`

1. `CreateInvalidation(DistributionId, Paths=[path_pattern])` to clear edge caches immediately.
2. `GetDistributionConfig` and remove the matching behavior from `CacheBehaviors.Items`.
3. `UpdateDistribution(IfMatch=ETag, ...)` to persist.

## Stack

Python 3.12 · boto3 · Terraform · AWS Lambda · Lambda Function URL · CloudFront · IAM

## Repository Layout

```
cloudfront-cache-manager-lambda/
├── main.tf         # Lambda, IAM role, Function URL, packaging
├── script.py       # Lambda handler: add/remove CacheBehavior + invalidate
├── .gitignore
└── README.md
```

## Prerequisites

- Terraform >= 1.x
- AWS credentials with permissions for: `lambda:*`, `iam:PassRole`, `cloudfront:GetDistributionConfig`, `cloudfront:UpdateDistribution`, `cloudfront:CreateInvalidation`
- An existing CloudFront distribution ID, passed to the Lambda as an environment variable

## Deployment

```bash
terraform init
terraform plan
terraform apply
```

## Usage

```bash
curl -X POST "$LAMBDA_URL" \
  -H 'content-type: application/json' \
  -d '{"action":"add","path_pattern":"/api/member/*"}'

curl -X POST "$LAMBDA_URL" \
  -H 'content-type: application/json' \
  -d '{"action":"remove","path_pattern":"/api/member/*"}'
```

## Notes

- CloudFront `UpdateDistribution` is eventually consistent. New behaviors take a few minutes to propagate across edge locations.
- Every update requires `IfMatch=ETag`. Concurrent callers racing the same distribution will receive `PreconditionFailed` and need to retry.
- AWS-managed policy IDs (`CachingOptimized`, `AllViewer`) are stable across accounts and can be referenced by ID directly.
- Lambda Function URL is exposed without authentication. Add IAM auth or place it behind API Gateway with an authorizer for production use.
