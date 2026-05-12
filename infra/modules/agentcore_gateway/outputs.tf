output "gateway_id" {
  value = awscc_bedrockagentcore_gateway.tools.gateway_identifier
}

output "gateway_arn" {
  value = awscc_bedrockagentcore_gateway.tools.gateway_arn
}

output "gateway_url" {
  value = awscc_bedrockagentcore_gateway.tools.gateway_url
}

output "gateway_role_arn" {
  value = aws_iam_role.gateway.arn
}
