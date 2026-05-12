output "kms_key_arn" {
  value = aws_kms_key.secrets.arn
}

output "openai_api_key_arn" {
  value = aws_secretsmanager_secret.openai_api_key.arn
}

output "langfuse_secret_key_arn" {
  value = aws_secretsmanager_secret.langfuse_secret_key.arn
}

output "langfuse_public_key_arn" {
  value = aws_secretsmanager_secret.langfuse_public_key.arn
}

output "cognito_m2m_client_secret_arn" {
  value = aws_secretsmanager_secret.cognito_m2m_client_secret.arn
}
