output "user_pool_id" {
  value = aws_cognito_user_pool.svc.id
}

output "user_pool_arn" {
  value = aws_cognito_user_pool.svc.arn
}

output "client_id" {
  value = aws_cognito_user_pool_client.agent_runtime.id
}

output "client_secret" {
  value     = aws_cognito_user_pool_client.agent_runtime.client_secret
  sensitive = true
}

output "scope" {
  value = "${local.resource_id}/${local.scope_name}"
}

output "token_url" {
  value = "https://${aws_cognito_user_pool_domain.svc.domain}.auth.${data.aws_region.current.region}.amazoncognito.com/oauth2/token"
}

output "discovery_url" {
  value = "https://cognito-idp.${data.aws_region.current.region}.amazonaws.com/${aws_cognito_user_pool.svc.id}/.well-known/openid-configuration"
}

output "issuer_url" {
  value = "https://cognito-idp.${data.aws_region.current.region}.amazonaws.com/${aws_cognito_user_pool.svc.id}"
}
