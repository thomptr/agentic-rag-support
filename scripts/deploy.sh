#!/usr/bin/env bash
# Deployment orchestration: build/push container images, apply OpenTofu, force ECS redeployment
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
INFRA_DIR="$(dirname "$0")/../infra/environments/dev"
DOCKER_DIR="$(dirname "$0")/../docker"

# ── Resolve AWS account ID ────────────────────────────────────────────────────
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

echo "==> Deploying to account ${ACCOUNT_ID} in ${REGION}"

# ── ECR login ─────────────────────────────────────────────────────────────────
echo "==> Authenticating with ECR"
aws ecr get-login-password --region "${REGION}" | \
  docker login --username AWS --password-stdin "${ECR_REGISTRY}"

# ── Build and push container images ──────────────────────────────────────────
for IMAGE in agent api frontend; do
  echo "==> Building docker/${IMAGE} image"
  docker build \
    --platform linux/arm64 \
    -f "${DOCKER_DIR}/Dockerfile.${IMAGE}" \
    -t "agentic-rag-${IMAGE}:latest" \
    .
  docker tag "agentic-rag-${IMAGE}:latest" \
    "${ECR_REGISTRY}/agentic-rag-${IMAGE}:latest"
  echo "==> Pushing agentic-rag-${IMAGE}"
  docker push "${ECR_REGISTRY}/agentic-rag-${IMAGE}:latest"
done

# ── OpenTofu apply ────────────────────────────────────────────────────────────
echo "==> Running tofu init"
tofu -chdir="${INFRA_DIR}" init -input=false

echo "==> Running tofu plan"
tofu -chdir="${INFRA_DIR}" plan -out=tfplan -input=false

echo "==> Running tofu apply"
tofu -chdir="${INFRA_DIR}" apply -input=false tfplan

# ── Force ECS redeployment ────────────────────────────────────────────────────
CLUSTER=$(tofu -chdir="${INFRA_DIR}" output -raw ecs_cluster_name)
for SERVICE in api frontend; do
  echo "==> Force-deploying ECS service dev-${SERVICE}"
  aws ecs update-service \
    --cluster "${CLUSTER}" \
    --service "dev-${SERVICE}" \
    --force-new-deployment \
    --region "${REGION}" \
    --query 'service.deployments[0].status' \
    --output text
done

echo "==> Waiting for ECS services to stabilize"
aws ecs wait services-stable \
  --cluster "${CLUSTER}" \
  --services dev-api dev-frontend \
  --region "${REGION}"

echo "==> Deployment complete"
