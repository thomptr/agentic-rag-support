output "runtime_arn" {
  value = awscc_bedrockagentcore_runtime.main.agent_runtime_arn
}

output "runtime_id" {
  value = awscc_bedrockagentcore_runtime.main.agent_runtime_id
}

# AgentCore invocation URL pattern: the URL-encoded runtime ARN forms the path.
# The application appends "/invocations" itself (see src/api/agentcore_client.py).
output "endpoint_url" {
  value = "https://bedrock-agentcore.${data.aws_region.current.region}.amazonaws.com/runtimes/${urlencode(awscc_bedrockagentcore_runtime.main.agent_runtime_arn)}"
}

output "iam_role_arn" {
  value = aws_iam_role.agentcore.arn
}
