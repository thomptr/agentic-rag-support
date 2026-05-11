terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50"
    }
  }
}

data "aws_region" "current" {}

locals {
  domain_prefix = "${var.env}-${var.project}-svc"
  resource_id   = "agentic-rag-tools"
  scope_name    = "gateway.invoke"
}

# ── User Pool (M2M / service-to-service only) ─────────────────────────────────
resource "aws_cognito_user_pool" "svc" {
  name = "${var.env}-${var.project}-svc"

  # M2M-only: no end-user signup, no MFA, no recovery surface.
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_cognito_user_pool_domain" "svc" {
  domain       = local.domain_prefix
  user_pool_id = aws_cognito_user_pool.svc.id
}

# ── Resource Server: defines the scope the agent requests ─────────────────────
resource "aws_cognito_resource_server" "tools" {
  identifier   = local.resource_id
  name         = "${var.env}-${var.project}-tools"
  user_pool_id = aws_cognito_user_pool.svc.id

  scope {
    scope_name        = local.scope_name
    scope_description = "Invoke executor tools via AgentCore Gateway"
  }
}

# ── M2M App Client (client_credentials only) ──────────────────────────────────
resource "aws_cognito_user_pool_client" "agent_runtime" {
  name                                 = "${var.env}-${var.project}-agent-runtime"
  user_pool_id                         = aws_cognito_user_pool.svc.id
  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes                 = ["${local.resource_id}/${local.scope_name}"]

  # No public flows.
  explicit_auth_flows = ["ALLOW_REFRESH_TOKEN_AUTH"]

  depends_on = [aws_cognito_resource_server.tools]
}
