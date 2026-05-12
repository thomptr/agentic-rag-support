output "lambda_arns" {
  description = "Map of tool_name to Lambda function ARN."
  value       = { for k, v in aws_lambda_function.tool : k => v.arn }
}

output "lambda_function_names" {
  value = { for k, v in aws_lambda_function.tool : k => v.function_name }
}

output "lambda_role_arns" {
  value = { for k, v in aws_iam_role.tool : k => v.arn }
}

output "shared_layer_arn" {
  value = aws_lambda_layer_version.shared.arn
}
