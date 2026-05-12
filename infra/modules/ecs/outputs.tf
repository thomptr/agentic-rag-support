output "alb_dns_name" {
  value = aws_lb.main.dns_name
}

output "alb_arn" {
  value = aws_lb.main.arn
}

output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "api_service_arn" {
  value = aws_ecs_service.api.id
}

output "frontend_service_arn" {
  value = aws_ecs_service.frontend.id
}

output "task_execution_role_arn" {
  value = aws_iam_role.task_execution.arn
}

output "task_role_arn" {
  value = aws_iam_role.task.arn
}
