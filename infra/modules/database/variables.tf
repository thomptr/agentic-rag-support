variable "project" {
  type = string
}

variable "env" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "rds_sg_id" {
  type = string
}

variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN for RDS storage encryption"
}

variable "db_name" {
  type    = string
  default = "agentic_rag"
}

variable "db_username" {
  type    = string
  default = "agentic_rag_admin"
}
