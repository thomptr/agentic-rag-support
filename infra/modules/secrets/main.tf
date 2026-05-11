terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50"
    }
  }
}

# ── KMS key for secrets encryption ───────────────────────────────────────────
resource "aws_kms_key" "secrets" {
  description             = "${var.project} ${var.env} secrets encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${var.env}-${var.project}-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

# ── API key secrets ───────────────────────────────────────────────────────────
resource "aws_secretsmanager_secret" "openai_api_key" {
  name       = "${var.env}/agentic-rag/openai-api-key"
  kms_key_id = aws_kms_key.secrets.arn

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_secretsmanager_secret" "langfuse_secret_key" {
  name       = "${var.env}/agentic-rag/langfuse-secret-key"
  kms_key_id = aws_kms_key.secrets.arn

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_secretsmanager_secret" "langfuse_public_key" {
  name       = "${var.env}/agentic-rag/langfuse-public-key"
  kms_key_id = aws_kms_key.secrets.arn

  tags = {
    Project = var.project
    Env     = var.env
  }
}

# ── Cognito M2M client_secret ─────────────────────────────────────────────────
# Container + version are both managed here so the value lands in Secrets Manager
# at apply time without a manual put-secret-value step (unlike OpenAI/Langfuse
# which are populated out-of-band).
resource "aws_secretsmanager_secret" "cognito_m2m_client_secret" {
  name       = "${var.env}/agentic-rag/cognito-m2m-client-secret"
  kms_key_id = aws_kms_key.secrets.arn

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_secretsmanager_secret_version" "cognito_m2m_client_secret" {
  # Cognito always issues a client_secret when generate_secret=true, so the
  # value is non-empty at apply time. A count-conditional here would break
  # planning (the value is unknown until module.cognito applies).
  secret_id     = aws_secretsmanager_secret.cognito_m2m_client_secret.id
  secret_string = jsonencode({ COGNITO_M2M_CLIENT_SECRET = var.cognito_m2m_client_secret })
}
