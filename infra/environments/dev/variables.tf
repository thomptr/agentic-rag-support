variable "project" {
  type    = string
  default = "agentic-rag"
}

variable "env" {
  type    = string
  default = "dev"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "dev_public_ip_cidr" {
  type        = string
  description = "POC: /32 CIDR (e.g. 1.2.3.4/32) of a developer machine to allow inbound to RDS for init/seed. Leave empty for no public ingress."
  default     = ""
}

variable "db_name" {
  type    = string
  default = "agentic_rag"
}

variable "db_username" {
  type    = string
  default = "agentic_rag_admin"
}
