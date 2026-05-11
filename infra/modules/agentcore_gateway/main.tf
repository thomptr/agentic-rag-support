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

# ── IAM role the Gateway assumes when invoking Lambda targets ─────────────────
resource "aws_iam_role" "gateway" {
  name = "${var.env}-${var.project}-gateway-role"

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

resource "aws_iam_role_policy" "gateway_invoke_lambdas" {
  name = "${var.env}-${var.project}-gateway-invoke-lambdas"
  role = aws_iam_role.gateway.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "InvokeToolLambdas"
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = var.lambda_arns
    }]
  })
}

# ── AgentCore Tool Gateway ────────────────────────────────────────────────────
# Note: awscc_bedrockagentcore_gateway is supported in awscc 1.83.0; gateway
# *targets* are not. Targets are registered via a side-channel CLI step (see
# scripts/register-gateway-targets.sh) immediately after this module applies.
resource "awscc_bedrockagentcore_gateway" "tools" {
  # AgentCore Gateway name regex: ^([0-9a-zA-Z][-]?){1,100}$ — allows dashes,
  # rejects underscores (opposite of awscc_bedrockagentcore_runtime).
  name            = "${var.env}-${var.project}-tools"
  description     = "Executor tool gateway — routes agent tool calls to per-tool Lambdas"
  protocol_type   = "MCP"
  authorizer_type = "CUSTOM_JWT"

  authorizer_configuration = {
    custom_jwt_authorizer = {
      discovery_url     = var.cognito_discovery_url
      allowed_audience  = [var.cognito_scope]
      allowed_clients   = [var.cognito_client_id]
    }
  }

  role_arn = aws_iam_role.gateway.arn
}
