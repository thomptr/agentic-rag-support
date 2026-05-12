variable "project" {
  type        = string
  description = "Project name used in resource tags and names"
}

variable "env" {
  type        = string
  description = "Environment name (dev, staging, prod)"
}

variable "region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

variable "dev_public_ip_cidr" {
  type        = string
  description = "Optional /32 CIDR for a developer's public IP, allowed inbound to RDS:5432 for POC init/seed. Leave empty to disable."
  default     = ""
}
