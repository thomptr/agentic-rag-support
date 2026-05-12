variable "project" {
  type = string
}

variable "env" {
  type = string
}

variable "tools" {
  type        = list(string)
  description = "List of executor tool names to deploy as Lambda functions."
  default     = ["create_ticket", "issue_refund", "order_status"]
}

variable "shared_layer_zip_path" {
  type        = string
  description = "Absolute path to the shared layer zip built by scripts/build-lambda-layer.sh."
}

variable "lambda_zip_dir" {
  type        = string
  description = "Directory containing <tool>.zip artifacts built by scripts/build-lambda.sh."
}

variable "langfuse_secret_key_arn" {
  type = string
}

variable "langfuse_public_key_arn" {
  type = string
}

variable "secrets_kms_key_arn" {
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
