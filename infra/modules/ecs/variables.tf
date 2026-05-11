variable "project" {
  type = string
}

variable "env" {
  type = string
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "vpc_id" {
  type = string
}

variable "public_subnet_ids" {
  type = list(string)
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "alb_sg_id" {
  type = string
}

variable "ecs_sg_id" {
  type = string
}

variable "api_ecr_url" {
  type = string
}

variable "frontend_ecr_url" {
  type = string
}

variable "agentcore_runtime_arn" {
  type = string
}

variable "agentcore_endpoint_url" {
  type = string
}

variable "db_master_secret_arn" {
  type = string
}

variable "secrets_kms_key_arn" {
  type = string
}

variable "openai_api_key_arn" {
  type = string
}

variable "langfuse_secret_key_arn" {
  type = string
}

variable "langfuse_public_key_arn" {
  type = string
}

variable "log_level" {
  type    = string
  default = "INFO"
}

variable "langfuse_host" {
  type    = string
  default = "https://cloud.langfuse.com"
}
