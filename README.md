# CloudFront Cache-Behavior Manager — Lambda API

A Python 3.12 Lambda (packaged via Terraform) that **dynamically manages CloudFront cache behaviors** and issues **path-pattern invalidations** through a single HTTPS endpoint. Used at production to let the application layer add or tear down per-path caching rules (e.g. per-member path, per-feature flag) without hand-editing the distribution or running a release.

## Highlights

- **Add/update path-pattern cache behaviors on the fly** — the Lambda talks to CloudFront via `boto3`, fetches the current distribution config + ETag, appends or updates a `CacheBehavior` entry for the supplied `PathPattern`, and reuploads with `UpdateDistribution`.
- **Invalidate + delete in the same call** — the reverse path: create an invalidation for the pattern, then strip the behavior out of the distribution.
- **AWS-managed policies** — reuses the standard managed policies so every new behavior is consistent:
  - `CachePolicyId = xxxx-xxx-xxx-xxxx` (**CachingOptimized**)
  - `OriginRequestPolicyId = xxxx-xxx-xxx-xxxx` (**AllViewer**)
- **HTTPS-first behaviors** — every behavior is created with `ViewerProtocolPolicy = "redirect-to-https"` and the cached/allowed methods restricted to `GET, HEAD`.
- **Single Lambda Function URL** — fronted by a Lambda Function URL; clients POST `{ action, path_pattern }` and the Lambda does the rest.

## Architecture

```
 Client / Service
      │ POST { action: "add" | "remove", path_pattern: "/api/foo/*" }
      ▼
 Lambda Function URL
      │
      ▼
 cache-manager Lambda  (python3.12, boto3)
      │
      ├─ add:    GetDistributionConfig → patch CacheBehaviors → UpdateDistribution
      └─ remove: CreateInvalidation → GetDistributionConfig → drop behavior → UpdateDistribution
      │
      ▼
 CloudFront distribution  (managed CachePolicy + AllViewer ORP)
```

## Tech stack

- **Runtime:** Python 3.12 (Lambda)
- **Libraries:** `boto3` (CloudFront client)
- **IaC:** Terraform
- **AWS services:** Lambda, Lambda Function URL, IAM, CloudFront
- **Managed policies used:** `CachingOptimized`, `AllViewer`

## Repository layout

```
@TERRAFORM_CACHE/
├── README.md
├── .gitignore
├── main.tf         # Lambda + IAM + Function URL + packaging
└── script.py       # Lambda handler: add/update/remove CacheBehavior + invalidate
```

## How it works

### `action = "add"`

1. `GetDistributionConfig(Id=DISTRIBUTION_ID)` → read the current config + ETag.
2. Build a new `CacheBehavior` with:
   - `PathPattern = <input>`
   - `TargetOriginId`, `ViewerProtocolPolicy = "redirect-to-https"`
   - `AllowedMethods = ["GET", "HEAD"]`, `CachedMethods = ["GET", "HEAD"]`
   - `CachePolicyId = CachingOptimized`
   - `OriginRequestPolicyId = AllViewer`
3. Append the behavior (or update in place if the pattern already exists).
4. `UpdateDistribution(IfMatch=ETag, DistributionConfig=...)`.

### `action = "remove"`

1. `CreateInvalidation(DistributionId, Paths=[path_pattern])` to clear edge caches immediately.
2. `GetDistributionConfig` → remove the matching behavior from `CacheBehaviors.Items`.
3. `UpdateDistribution(IfMatch=ETag, ...)` to persist the removal.

## Prerequisites

- Terraform >= 1.x
- AWS CLI with permissions for `lambda:*`, `iam:PassRole`, `cloudfront:GetDistributionConfig`, `cloudfront:UpdateDistribution`, `cloudfront:CreateInvalidation`
- An existing CloudFront distribution ID (set in Lambda env var or `script.py`)

## Deployment

```bash
terraform init
terraform plan
terraform apply
```

Invoke:

```bash
curl -X POST "$LAMBDA_URL" -H 'content-type: application/json' \
     -d '{"action":"add","path_pattern":"/api/member/*"}'

curl -X POST "$LAMBDA_URL" -H 'content-type: application/json' \
     -d '{"action":"remove","path_pattern":"/api/member/*"}'
```

## Teardown

```bash
terraform destroy
```

## Notes

- CloudFront `UpdateDistribution` is eventually consistent — the new behavior may take a few minutes to propagate to all edge locations.
- The Lambda must use `IfMatch = ETag` on every update; concurrent callers racing the same distribution will get `PreconditionFailed` and should retry.
- The managed policy IDs are AWS-wide and stable — safe to hardcode.
- Demonstrates: programmatic CloudFront configuration via boto3, ETag-based optimistic concurrency, AWS-managed cache/origin-request policy reuse, dynamic edge cache rules driven by application state.
