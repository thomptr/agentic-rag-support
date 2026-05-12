variable "project" {
  type = string
}

variable "env" {
  type = string
}

variable "lambda_arns" {
  type        = list(string)
  description = "List of Lambda function ARNs the Gateway is allowed to invoke (from module.lambdas)."
}

variable "cognito_discovery_url" {
  type        = string
  description = "OpenID Connect discovery URL for the Cognito user pool issuing M2M JWTs."
}

variable "cognito_client_id" {
  type        = string
  description = "Cognito M2M app client ID — only tokens issued to this client are accepted."
}

variable "cognito_scope" {
  type        = string
  description = "The OAuth2 scope JWTs must carry (e.g. agentic-rag-tools/gateway.invoke)."
}
