output "alb_dns_name" {
  value       = module.ecs.alb_dns_name
  description = "ALB DNS name — use as the base URL for API and frontend"
}

output "ecs_cluster_name" {
  value = module.ecs.cluster_name
}

output "agentcore_runtime_arn" {
  value = module.agentcore.runtime_arn
}

output "agentcore_endpoint_url" {
  value = module.agentcore.endpoint_url
}

output "db_endpoint" {
  value = module.database.db_endpoint
}

output "db_master_secret_arn" {
  value = module.database.db_master_secret_arn
}

output "ecr_agent_url" {
  value = module.ecr.agent_repository_url
}

output "ecr_api_url" {
  value = module.ecr.api_repository_url
}

output "ecr_frontend_url" {
  value = module.ecr.frontend_repository_url
}

output "gateway_id" {
  value = module.agentcore_gateway.gateway_id
}

output "gateway_url" {
  value = module.agentcore_gateway.gateway_url
}

output "cognito_token_url" {
  value = module.cognito.token_url
}

output "cognito_client_id" {
  value = module.cognito.client_id
}

output "cognito_user_pool_id" {
  value = module.cognito.user_pool_id
}

output "cognito_discovery_url" {
  value = module.cognito.discovery_url
}

output "lambda_function_names" {
  value = module.lambdas.lambda_function_names
}
