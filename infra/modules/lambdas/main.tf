terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50"
    }
  }
}

# ── Shared Lambda Layer (Langfuse SDK, Powertools, tracing helpers) ───────────
resource "aws_lambda_layer_version" "shared" {
  layer_name               = "${var.env}-${var.project}-shared"
  compatible_runtimes      = ["python3.11"]
  compatible_architectures = ["arm64"]
  filename                 = var.shared_layer_zip_path
  source_code_hash         = filebase64sha256(var.shared_layer_zip_path)
}

# ── Per-tool resources via for_each ────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "tool" {
  for_each          = toset(var.tools)
  name              = "/aws/lambda/${var.env}-${var.project}-${each.key}"
  retention_in_days = 14

  tags = {
    Project = var.project
    Env     = var.env
    Tool    = each.key
  }
}

resource "aws_iam_role" "tool" {
  for_each = toset(var.tools)
  name     = "${var.env}-${var.project}-${each.key}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Project = var.project
    Env     = var.env
    Tool    = each.key
  }
}

resource "aws_iam_role_policy" "tool" {
  for_each = toset(var.tools)
  name     = "${var.env}-${var.project}-${each.key}-lambda-policy"
  role     = aws_iam_role.tool[each.key].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "${aws_cloudwatch_log_group.tool[each.key].arn}:*"
      },
      {
        Sid    = "LangfuseSecretsRead"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          var.langfuse_secret_key_arn,
          var.langfuse_public_key_arn,
        ]
      },
      {
        Sid      = "KMSDecryptLangfuse"
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = [var.secrets_kms_key_arn]
      },
    ]
  })
}

resource "aws_lambda_function" "tool" {
  for_each      = toset(var.tools)
  function_name = "${var.env}-${var.project}-${each.key}"
  role          = aws_iam_role.tool[each.key].arn
  filename      = "${var.lambda_zip_dir}/${each.key}.zip"
  source_code_hash = filebase64sha256("${var.lambda_zip_dir}/${each.key}.zip")
  # Zip preserves the lambdas/<tool>/ package path so the handler can keep
  # using package-style imports (consistent with the test suite).
  handler       = "lambdas.${each.key}.handler.lambda_handler"
  runtime       = "python3.11"
  architectures = ["arm64"]
  memory_size   = 256
  timeout       = 15
  layers        = [aws_lambda_layer_version.shared.arn]

  environment {
    variables = {
      TOOL_NAME           = each.key
      LANGFUSE_HOST       = var.langfuse_host
      LANGFUSE_SECRET_REF = var.langfuse_secret_key_arn
      LANGFUSE_PUBLIC_REF = var.langfuse_public_key_arn
      LOG_LEVEL           = var.log_level
    }
  }

  depends_on = [aws_cloudwatch_log_group.tool]

  tags = {
    Project = var.project
    Env     = var.env
    Tool    = each.key
  }
}

# Permission for AgentCore Gateway to invoke each Lambda. The Gateway's role
# is passed in as var.gateway_invoker_role_arn (output by the gateway module).
resource "aws_lambda_permission" "gateway_invoke" {
  for_each      = toset(var.tools)
  statement_id  = "AllowAgentCoreGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.tool[each.key].function_name
  principal     = "bedrock-agentcore.amazonaws.com"
}
