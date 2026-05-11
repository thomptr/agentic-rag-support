output "repository_urls" {
  value = { for k, v in aws_ecr_repository.repos : k => v.repository_url }
}

output "agent_repository_url" {
  value = aws_ecr_repository.repos["agentic-rag-agent"].repository_url
}

output "api_repository_url" {
  value = aws_ecr_repository.repos["agentic-rag-api"].repository_url
}

output "frontend_repository_url" {
  value = aws_ecr_repository.repos["agentic-rag-frontend"].repository_url
}
