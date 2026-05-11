variable "project" {
  type = string
}

variable "env" {
  type = string
}

variable "cognito_m2m_client_secret" {
  type        = string
  description = "Cognito User Pool M2M client_secret to persist into Secrets Manager. Sourced from module.cognito.client_secret."
  sensitive   = true
  default     = ""
}
