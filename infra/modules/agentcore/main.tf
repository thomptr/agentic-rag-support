terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50"
    }
    awscc = {
      source  = "hashicorp/awscc"
      version = ">= 1.0"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ── IAM role for AgentCore Runtime ───────────────────────────────────────────
resource "aws_iam_role" "agentcore" {
  name = "${var.env}-${var.project}-agentcore-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "bedrock-agentcore.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_iam_role_policy" "agentcore" {
  name = "${var.env}-${var.project}-agentcore-policy"
  role = aws_iam_role.agentcore.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRPull"
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/bedrock-agentcore/*"
      },
      {
        Sid    = "SecretsRead"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = compact([
          var.openai_api_key_arn,
          var.langfuse_secret_key_arn,
          var.langfuse_public_key_arn,
          var.cognito_client_secret_arn,
          var.db_master_secret_arn,
        ])
      },
      {
        Sid    = "KMSDecrypt"
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = [var.secrets_kms_key_arn]
      },
    ]
  })
}

# ── AgentCore Runtime (awscc provider) ───────────────────────────────────────
# Resource type is awscc_bedrockagentcore_runtime (not _agent_runtime).
# AgentCore runtime names must match ^[a-zA-Z][a-zA-Z0-9_]*$ — no hyphens.
resource "awscc_bedrockagentcore_runtime" "main" {
  agent_runtime_name = replace("${var.env}_${var.project}_agent", "-", "_")
  description        = "Agentic RAG support agent — LangGraph workflow"

  agent_runtime_artifact = {
    container_configuration = {
      container_uri = "${var.agent_ecr_url}:latest"
    }
  }

  network_configuration = {
    network_mode = "VPC"
    network_mode_config = {
      subnets         = var.private_subnet_ids
      security_groups = [var.agentcore_sg_id]
    }
  }

  role_arn = aws_iam_role.agentcore.arn

  environment_variables = {
    # DATABASE_URL is bootstrap (no password); entrypoint resolves the password
    # from db_master_secret_arn at cold start and rewrites settings.database_url.
    DATABASE_URL              = "postgresql+psycopg://${var.db_username}@${var.db_endpoint}/${var.db_name}"
    DB_MASTER_SECRET_ARN      = var.db_master_secret_arn
    DB_HOST                   = var.db_endpoint
    DB_NAME                   = var.db_name
    LOG_LEVEL                 = var.log_level
    DEPLOYMENT_MODE           = "cloud"
    AGENTCORE_MEMORY_ENABLED  = "true"
    OPENAI_API_KEY_ARN        = var.openai_api_key_arn
    GATEWAY_URL               = var.gateway_url
    COGNITO_TOKEN_URL         = var.cognito_token_url
    COGNITO_CLIENT_ID         = var.cognito_client_id
    COGNITO_CLIENT_SECRET_ARN = var.cognito_client_secret_arn
    COGNITO_SCOPE             = var.cognito_scope
    # Langfuse: ARNs are passed verbatim; the entrypoint resolves the JSON
    # secret payload at cold start (the same pattern as OPENAI_API_KEY_ARN).
    LANGFUSE_HOST       = var.langfuse_host
    LANGFUSE_SECRET_REF = var.langfuse_secret_key_arn
    LANGFUSE_PUBLIC_REF = var.langfuse_public_key_arn
  }

  # protocol_configuration is a plain string in the AWSCC schema, not a nested block.
  protocol_configuration = "HTTP"
}

# ── AgentCore Identity credential provider ───────────────────────────────────
# Configures automatic API key injection into the agent runtime via Secrets Manager.
# The @requires_api_key(provider_name="openai") decorator in the entrypoint code
# resolves keys through this identity configuration at invocation time.
resource "aws_secretsmanager_secret_policy" "agentcore_openai_access" {
  secret_arn = var.openai_api_key_arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AgentCoreIdentityAccess"
      Effect = "Allow"
      Principal = {
        AWS = aws_iam_role.agentcore.arn
      }
      Action   = "secretsmanager:GetSecretValue"
      Resource = var.openai_api_key_arn
    }]
  })
}
