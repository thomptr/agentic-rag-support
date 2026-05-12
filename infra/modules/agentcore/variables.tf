variable "project" {
  type = string
}

variable "env" {
  type = string
}

variable "agent_ecr_url" {
  type        = string
  description = "ECR URL for the agent container image"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for AgentCore VPC mode"
}

variable "agentcore_sg_id" {
  type        = string
  description = "Security group ID for AgentCore Runtime ENIs"
}

variable "db_endpoint" {
  type        = string
  description = "RDS endpoint (host:port)"
}

variable "db_name" {
  type    = string
  default = "agentic_rag"
}

variable "db_username" {
  type    = string
  default = "agentic_rag_admin"
}

variable "secrets_kms_key_arn" {
  type = string
}

variable "openai_api_key_arn" {
  type        = string
  description = "Secrets Manager ARN of the OpenAI API key. The runtime reads the value at cold start and stuffs it into settings.openai_api_key (see src/entrypoint/main.py)."
}

variable "db_master_secret_arn" {
  type        = string
  description = "Secrets Manager ARN of the RDS master user secret (AWS-managed). The runtime reads username+password at cold start and rewrites settings.database_url to include them."
  default     = ""
}

variable "langfuse_secret_key_arn" {
  type = string
}

variable "langfuse_public_key_arn" {
  type = string
}

variable "langfuse_host" {
  type    = string
  default = "https://cloud.langfuse.com"
}

variable "log_level" {
  type    = string
  default = "INFO"
}

# ── AgentCore Tool Gateway + Cognito M2M ──────────────────────────────────────
variable "gateway_url" {
  type        = string
  description = "AgentCore Tool Gateway URL. Empty until the Gateway is provisioned."
  default     = ""
}

variable "cognito_token_url" {
  type        = string
  description = "Cognito OAuth2 token endpoint for client_credentials flow."
  default     = ""
}

variable "cognito_client_id" {
  type        = string
  description = "Cognito M2M app client ID."
  default     = ""
}

variable "cognito_client_secret_arn" {
  type        = string
  description = "Secrets Manager ARN of the Cognito M2M client_secret JSON."
  default     = ""
}

variable "cognito_scope" {
  type        = string
  description = "OAuth2 scope to request (e.g. agentic-rag-tools/gateway.invoke)."
  default     = ""
}
