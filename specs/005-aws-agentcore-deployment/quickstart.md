# Quickstart: AWS AgentCore Deployment

**Feature**: 005-aws-agentcore-deployment
**Date**: 2026-05-09

## Prerequisites

- AWS CLI v2 configured with credentials (`aws configure`)
- AWS account with `BedrockAgentCoreFullAccess` (or equivalent) IAM permissions
- OpenTofu 1.8+ installed (`tofu --version`)
- Docker installed and running
- Python 3.11+ with `uv` package manager
- Node.js 20.x (for AgentCore CLI)
- API keys ready: OpenAI, Langfuse (optional: Anthropic)

## Step 1: Install AgentCore CLI

```bash
npm install -g @anthropic-ai/bedrock-agentcore-cli
# or
pip install bedrock-agentcore
```

## Step 2: Bootstrap State Infrastructure

One-time setup for OpenTofu state management:

```bash
cd infra/bootstrap
tofu init
tofu apply
```

This creates:
- S3 bucket for state storage
- KMS key for state encryption
- S3 bucket versioning for state recovery

Capture the state bucket name for the next step:

```bash
tofu output -raw state_bucket_name   # e.g. agentic-rag-tfstate-<account-id>
```

## Step 3: Configure the Dev Backend

The backend config in `infra/environments/dev/backend.tf` references the account-specific
state bucket created in Step 2 and an OpenTofu encryption block. Before the first
`tofu init` against the dev environment:

1. Replace the bucket placeholder with the value from `tofu output -raw state_bucket_name`:

   ```bash
   ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
   sed -i "s/REPLACE_ACCOUNT_ID/${ACCOUNT_ID}/" infra/environments/dev/backend.tf
   ```

2. Confirm the `key_provider "aws_kms"` block contains all three required arguments
   (`kms_key_id`, `region`, and `key_spec = "AES_256"`). OpenTofu rejects the encryption
   block at `init` time without `key_spec`.

## Step 4: Deploy Infrastructure

```bash
cd infra/environments/dev
tofu init
tofu plan -out=tfplan
tofu apply tfplan
```

This provisions:
- VPC with public/private subnets, NAT Gateway
- RDS PostgreSQL 16 with pgVector
- ECR repositories
- ECS Cluster with ALB
- AgentCore Runtime
- Secrets Manager resources (containers — values populated in Step 5)
- CloudWatch log groups
- IAM roles and policies

## Step 5: Populate Secret Values

The secret containers are created by `tofu apply` above; their values are populated
out-of-band so that secret material is never written to OpenTofu state:

```bash
aws secretsmanager put-secret-value \
  --secret-id dev/agentic-rag/openai-api-key \
  --secret-string '{"OPENAI_API_KEY":"sk-..."}'

aws secretsmanager put-secret-value \
  --secret-id dev/agentic-rag/langfuse-secret-key \
  --secret-string '{"LANGFUSE_SECRET_KEY":"sk-lf-..."}'

aws secretsmanager put-secret-value \
  --secret-id dev/agentic-rag/langfuse-public-key \
  --secret-string '{"LANGFUSE_PUBLIC_KEY":"pk-lf-..."}'
```

If any of these returns `ResourceNotFoundException`, the secret container does not
exist — re-run Step 4 (or `tofu apply -target=module.secrets`) and verify with
`aws secretsmanager list-secrets --query 'SecretList[?contains(Name, \`agentic-rag\`)]'`.

## Step 6: Build and Push Container Images

```bash
# Get ECR login
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build and push agent image
docker build -f docker/Dockerfile.agent -t agentic-rag-agent .
docker tag agentic-rag-agent:latest $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/agentic-rag-agent:latest
docker push $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/agentic-rag-agent:latest

# Build and push API image
docker build -f docker/Dockerfile.api -t agentic-rag-api .
docker tag agentic-rag-api:latest $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/agentic-rag-api:latest
docker push $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/agentic-rag-api:latest

# Build and push frontend image
docker build -f docker/Dockerfile.frontend -t agentic-rag-frontend .
docker tag agentic-rag-frontend:latest $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/agentic-rag-frontend:latest
docker push $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/agentic-rag-frontend:latest
```

## Step 6b: Package and Upload Executor Tool Lambdas

Each executor tool (`create_ticket`, `issue_refund`, `order_status`) is packaged as a zip and a shared Lambda Layer carries common dependencies (Langfuse SDK, AWS Powertools, tracing helpers).

```bash
# One-time per fresh checkout: install build dependencies in a virtualenv
python -m venv .build-venv && source .build-venv/bin/activate
pip install --upgrade pip build

# Build the shared layer (Langfuse + Powertools + tracing helpers)
bash scripts/build-lambda-layer.sh  # outputs lambdas/_dist/shared-layer.zip

# Build each tool's zip (handler + tool-local deps like pydantic)
for tool in create_ticket issue_refund order_status; do
  bash scripts/build-lambda.sh "$tool"  # outputs lambdas/_dist/${tool}.zip
done

# `tofu apply` (Step 4) uploads these zips when their checksums change, then
# wires them to the agentcore_gateway module's Gateway Targets.
cd infra/environments/dev
tofu apply -var dev_public_ip_cidr=${MY_IP}/32
```

After this step:
- One Lambda function per tool exists in the AWS console (`dev-agentic-rag-create_ticket`, etc.).
- The AgentCore Tool Gateway has three Targets, one per Lambda.
- The Cognito User Pool, Resource Server, and M2M App Client are created; the client_secret is stored in Secrets Manager (`dev/agentic-rag/cognito-m2m-client-secret`).

Verify Gateway tool discovery works (using the bedrock-agentcore CLI):

```bash
bedrock-agentcore gateway list-tools \
  --gateway-id $(tofu output -raw gateway_id) \
  --region us-east-1
# Expect: three tools (create_ticket, issue_refund, order_status) with their schemas
```

## Step 7: Initialize Database

Connect to RDS and run the init script:

```bash
# Get the database endpoint from OpenTofu output
DB_ENDPOINT=$(cd infra/environments/dev && tofu output -raw db_endpoint)

# Get the master password from Secrets Manager
DB_SECRET=$(aws secretsmanager get-secret-value \
  --secret-id $(cd infra/environments/dev && tofu output -raw db_master_secret_arn) \
  --query SecretString --output text)

DB_USER=$(echo $DB_SECRET | jq -r '.username')
DB_PASS=$(echo $DB_SECRET | jq -r '.password')

# Run init script
PGPASSWORD=$DB_PASS psql -h $DB_ENDPOINT -U $DB_USER -d agentic_rag -f scripts/init.sql
```

## Step 8: Seed Knowledge Base

Run the document ingestion as an ECS task or locally with the RDS connection:

```bash
DATABASE_URL="postgresql+psycopg://${DB_USER}:${DB_PASS}@${DB_ENDPOINT}:5432/agentic_rag" \
  python -m src.rag.ingest
```

## Step 9: Deploy Services

Update ECS services to use the new images (if not done during `tofu apply`):

```bash
# Force new deployment to pull latest images
aws ecs update-service --cluster dev-agentic-rag --service dev-api --force-new-deployment
aws ecs update-service --cluster dev-agentic-rag --service dev-frontend --force-new-deployment
```

## Step 10: Verify Deployment

```bash
# Run smoke tests
bash scripts/smoke-test.sh

# Or manually:
ALB_DNS=$(cd infra/environments/dev && tofu output -raw alb_dns_name)

# Test API health
curl -s http://${ALB_DNS}/health | jq .

# Test query
curl -s -X POST http://${ALB_DNS}/query \
  -H "Content-Type: application/json" \
  -d '{"query_text": "How do I reset my password?"}' | jq .

# Access frontend
echo "Frontend: http://${ALB_DNS}:8501"
```

## Step 11: Secret Rotation

Rotate any of the four Secrets Manager-backed credentials without rebuilding
the application:

| Secret | What it gates | Rotation flow |
|---|---|---|
| `dev/agentic-rag/openai-api-key` | LLM calls from the agent | Write new value → force runtime redeploy |
| `dev/agentic-rag/langfuse-secret-key` + `langfuse-public-key` | Tracing emission from agent + Lambdas | Write new value → force runtime + Lambda cold start |
| `dev/agentic-rag/cognito-m2m-client-secret` | Agent → Gateway JWT auth | Cognito-managed; rotate via `aws cognito-idp update-user-pool-client` (regenerates secret), then push to Secrets Manager and roll runtime |

### Standard rotation (OpenAI / Langfuse)

```bash
# 1. Put the new value
aws secretsmanager put-secret-value \
  --secret-id dev/agentic-rag/openai-api-key \
  --secret-string '{"OPENAI_API_KEY":"sk-new-..."}' \
  --version-stages AWSCURRENT \
  --region us-east-1

# 2. Force the AgentCore Runtime to pick it up (each Lambda re-reads on cold start)
.venv/bin/python <<'PY'
import boto3
c = boto3.client("bedrock-agentcore-control", region_name="us-east-1")
rt = c.get_agent_runtime(agentRuntimeId="$(cd infra/environments/dev && tofu output -raw agentcore_runtime_arn | awk -F/ '{print $NF}')")
c.update_agent_runtime(
    agentRuntimeId=rt["agentRuntimeId"],
    description=rt.get("description", ""),
    roleArn=rt["roleArn"],
    agentRuntimeArtifact=rt["agentRuntimeArtifact"],
    networkConfiguration=rt["networkConfiguration"],
    protocolConfiguration=rt.get("protocolConfiguration", "HTTP"),
    environmentVariables=rt.get("environmentVariables", {}),
)
PY
```

### Cognito M2M rotation (advanced)

```bash
# 1. Regenerate the client_secret
aws cognito-idp update-user-pool-client \
  --user-pool-id $(cd infra/environments/dev && tofu output -raw cognito_user_pool_id) \
  --client-id $(cd infra/environments/dev && tofu output -raw cognito_client_id) \
  --generate-secret \
  --region us-east-1

# 2. Read the new secret out of Cognito and put it into Secrets Manager
# 3. Force the AgentCore Runtime to pull (as above) so it re-reads the new secret
```

For zero-downtime rotation, push the new value to Secrets Manager **before**
forcing the runtime redeploy — the new container reads the fresh secret on cold
start, while the old container continues serving with the old secret until
AgentCore swaps it.

## Teardown

```bash
# Destroy all infrastructure (except state bucket)
cd infra/environments/dev
tofu destroy

# To also destroy the state bucket (irreversible):
cd infra/bootstrap
tofu destroy
```

### About `dev_public_ip_cidr`

The `-var dev_public_ip_cidr=<your-ip>/32` flag passed to every `tofu apply`
opens a temporary RDS security-group ingress on port 5432 from your laptop's
public IP. It's required for the local `psql` flow in Step 7 (Initialize
Database) and the local seed flow in Step 8.

For a longer-lived dev environment, prefer one of:

- **VPN / Direct Connect** into the VPC — no public-internet exposure to RDS.
- **EC2 bastion** with SSM port forwarding — `aws ssm start-session` tunnels
  5432 through a managed instance in a private subnet.
- **AWS Systems Manager Session Manager Run Command** — one-off psql sessions
  on a temporary EC2 instance, then terminate.

To **disable** the developer ingress entirely, re-run `tofu apply` without the
variable (the default is empty, which omits the SG rule):

```bash
cd infra/environments/dev
tofu apply  # no -var dev_public_ip_cidr
```

## Troubleshooting

### AgentCore Runtime not starting
- Check CloudWatch logs: `/aws/bedrock-agentcore/agentic-rag-agent`
- Verify container image exists in ECR
- Verify VPC subnets have NAT Gateway route for internet access

### ECS tasks failing health checks
- API: Check `curl http://localhost:8000/health` inside container
- Frontend: Check `curl http://localhost:8501/_stcore/health`
- Verify security group allows traffic from ALB

### Database connection failures
- Verify RDS security group allows inbound from ECS and AgentCore security groups
- Verify DATABASE_URL uses the RDS endpoint (not localhost)
- Check if pgVector extension is installed: `SELECT * FROM pg_extension WHERE extname = 'vector';`

### Secrets not available
- Verify ECS task execution role has `secretsmanager:GetSecretValue` permission
- Verify secret ARNs in task definition match actual secret ARNs
- Check that secret values have been populated (Step 5)
