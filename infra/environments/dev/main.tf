terraform {
  required_version = ">= 1.8"
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

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project   = var.project
      Env       = var.env
      ManagedBy = "opentofu"
    }
  }
}

provider "awscc" {
  region = var.region
}

# ── Networking ────────────────────────────────────────────────────────────────
module "networking" {
  source             = "../../modules/networking"
  project            = var.project
  env                = var.env
  region             = var.region
  dev_public_ip_cidr = var.dev_public_ip_cidr
}

# ── ECR ───────────────────────────────────────────────────────────────────────
module "ecr" {
  source  = "../../modules/ecr"
  project = var.project
  env     = var.env
}

# ── Cognito (M2M JWT issuer for AgentCore Gateway) ────────────────────────────
module "cognito" {
  source  = "../../modules/cognito"
  project = var.project
  env     = var.env
}

# ── Secrets ───────────────────────────────────────────────────────────────────
module "secrets" {
  source                    = "../../modules/secrets"
  project                   = var.project
  env                       = var.env
  cognito_m2m_client_secret = module.cognito.client_secret
}

# ── Executor Tool Lambdas ─────────────────────────────────────────────────────
module "lambdas" {
  source                  = "../../modules/lambdas"
  project                 = var.project
  env                     = var.env
  shared_layer_zip_path   = "${path.root}/../../../lambdas/_dist/shared-layer.zip"
  lambda_zip_dir          = "${path.root}/../../../lambdas/_dist"
  langfuse_secret_key_arn = module.secrets.langfuse_secret_key_arn
  langfuse_public_key_arn = module.secrets.langfuse_public_key_arn
  langfuse_host           = var.langfuse_host
  secrets_kms_key_arn     = module.secrets.kms_key_arn
}

# ── AgentCore Tool Gateway ────────────────────────────────────────────────────
module "agentcore_gateway" {
  source                = "../../modules/agentcore_gateway"
  project               = var.project
  env                   = var.env
  lambda_arns           = values(module.lambdas.lambda_arns)
  cognito_discovery_url = module.cognito.discovery_url
  cognito_client_id     = module.cognito.client_id
  cognito_scope         = module.cognito.scope
}

# ── Database ──────────────────────────────────────────────────────────────────
module "database" {
  source = "../../modules/database"

  project            = var.project
  env                = var.env
  # POC: using public subnets so init.sql/seed can run from a developer machine.
  # SG ingress is locked to var.dev_public_ip_cidr in the networking module.
  private_subnet_ids = module.networking.public_subnet_ids
  rds_sg_id          = module.networking.rds_sg_id
  kms_key_arn        = module.secrets.kms_key_arn
  db_name            = var.db_name
  db_username        = var.db_username

  depends_on = [module.networking, module.secrets]
}

# ── AgentCore Runtime ─────────────────────────────────────────────────────────
module "agentcore" {
  source = "../../modules/agentcore"

  project                = var.project
  env                    = var.env
  agent_ecr_url          = module.ecr.agent_repository_url
  private_subnet_ids     = module.networking.private_subnet_ids
  agentcore_sg_id        = module.networking.agentcore_sg_id
  db_endpoint            = module.database.db_endpoint
  db_name                = var.db_name
  db_username            = var.db_username
  secrets_kms_key_arn    = module.secrets.kms_key_arn
  openai_api_key_arn     = module.secrets.openai_api_key_arn
  langfuse_secret_key_arn = module.secrets.langfuse_secret_key_arn
  langfuse_public_key_arn = module.secrets.langfuse_public_key_arn
  langfuse_host           = var.langfuse_host

  gateway_url               = module.agentcore_gateway.gateway_url
  cognito_token_url         = module.cognito.token_url
  cognito_client_id         = module.cognito.client_id
  cognito_client_secret_arn = module.secrets.cognito_m2m_client_secret_arn
  cognito_scope             = module.cognito.scope
  db_master_secret_arn      = module.database.db_master_secret_arn

  depends_on = [module.database, module.ecr, module.secrets, module.cognito, module.agentcore_gateway]
}

# ── ECS (API + Frontend + ALB + Auto-scaling) ─────────────────────────────────
module "ecs" {
  source = "../../modules/ecs"

  project                = var.project
  env                    = var.env
  region                 = var.region
  vpc_id                 = module.networking.vpc_id
  public_subnet_ids      = module.networking.public_subnet_ids
  private_subnet_ids     = module.networking.private_subnet_ids
  alb_sg_id              = module.networking.alb_sg_id
  ecs_sg_id              = module.networking.ecs_sg_id
  api_ecr_url            = module.ecr.api_repository_url
  frontend_ecr_url       = module.ecr.frontend_repository_url
  agentcore_runtime_arn  = module.agentcore.runtime_arn
  agentcore_endpoint_url = module.agentcore.endpoint_url
  db_master_secret_arn   = module.database.db_master_secret_arn
  secrets_kms_key_arn    = module.secrets.kms_key_arn
  openai_api_key_arn     = module.secrets.openai_api_key_arn
  langfuse_secret_key_arn = module.secrets.langfuse_secret_key_arn
  langfuse_public_key_arn = module.secrets.langfuse_public_key_arn
  langfuse_host           = var.langfuse_host

  depends_on = [module.agentcore, module.networking, module.secrets, module.database]
}
