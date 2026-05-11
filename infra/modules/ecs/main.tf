terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ── ECS Cluster ───────────────────────────────────────────────────────────────
resource "aws_ecs_cluster" "main" {
  name = "${var.env}-${var.project}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE"]
}

# ── CloudWatch Log Groups ─────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.env}/api"
  retention_in_days = 30

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${var.env}/frontend"
  retention_in_days = 30

  tags = {
    Project = var.project
    Env     = var.env
  }
}

# ── IAM: Task Execution Role ──────────────────────────────────────────────────
resource "aws_iam_role" "task_execution" {
  name = "${var.env}-${var.project}-ecs-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_iam_role_policy_attachment" "task_execution_managed" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "task_execution_secrets" {
  name = "${var.env}-${var.project}-ecs-exec-secrets"
  role = aws_iam_role.task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsRead"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          var.openai_api_key_arn,
          var.langfuse_secret_key_arn,
          var.langfuse_public_key_arn,
          var.db_master_secret_arn,
        ]
      },
      {
        Sid    = "KMSDecrypt"
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = [var.secrets_kms_key_arn]
      },
    ]
  })
}

# ── IAM: Task Role (for ECS tasks to call AWS services) ──────────────────────
resource "aws_iam_role" "task" {
  name = "${var.env}-${var.project}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_iam_role_policy" "task_agentcore_invoke" {
  name = "${var.env}-${var.project}-ecs-task-agentcore"
  role = aws_iam_role.task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AgentCoreInvoke"
      Effect = "Allow"
      Action = ["bedrock-agentcore:InvokeAgentRuntime"]
      # AgentCore invocation hits the runtime's runtime-endpoint sub-resource
      # (e.g. .../runtime/X/runtime-endpoint/DEFAULT), so the policy must allow
      # the runtime ARN AND any child resource under it.
      Resource = [
        var.agentcore_runtime_arn,
        "${var.agentcore_runtime_arn}/*",
      ]
    }]
  })
}

# ── ALB ───────────────────────────────────────────────────────────────────────
resource "aws_lb" "main" {
  name               = "${var.env}-${var.project}-alb"
  load_balancer_type = "application"
  internal           = false
  subnets            = var.public_subnet_ids
  security_groups    = [var.alb_sg_id]

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_lb_target_group" "api" {
  name        = "${var.env}-${var.project}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/health"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_lb_target_group" "frontend" {
  name        = "${var.env}-${var.project}-fe-tg"
  port        = 8501
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = "/_stcore/health"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# Streamlit listener — exposes the frontend on its native port (8501) so the
# `BASE_URL:8501/_stcore/health` health probe in scripts/smoke-test.sh works
# without a Streamlit base-path rewrite.
resource "aws_lb_listener" "frontend_8501" {
  load_balancer_arn = aws_lb.main.arn
  port              = 8501
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }
}

resource "aws_lb_listener_rule" "frontend" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frontend.arn
  }

  condition {
    path_pattern {
      values = ["/frontend*", "/streamlit*"]
    }
  }
}

# ── ECS Task Definitions ──────────────────────────────────────────────────────
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.env}-${var.project}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }
  execution_role_arn = aws_iam_role.task_execution.arn
  task_role_arn      = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "api"
    image     = "${var.api_ecr_url}:latest"
    essential = true

    portMappings = [{ containerPort = 8000, protocol = "tcp" }]

    environment = [
      { name = "DEPLOYMENT_MODE", value = "cloud" },
      { name = "AWS_REGION",      value = var.region },
      { name = "AGENTCORE_RUNTIME_ARN", value = var.agentcore_runtime_arn },
      { name = "AGENTCORE_ENDPOINT_URL", value = var.agentcore_endpoint_url },
      { name = "LOG_LEVEL",       value = var.log_level },
      { name = "LANGFUSE_HOST",   value = var.langfuse_host },
    ]

    secrets = [
      { name = "OPENAI_API_KEY",      valueFrom = var.openai_api_key_arn },
      { name = "LANGFUSE_SECRET_KEY", valueFrom = var.langfuse_secret_key_arn },
      { name = "LANGFUSE_PUBLIC_KEY", valueFrom = var.langfuse_public_key_arn },
      { name = "DATABASE_URL",        valueFrom = var.db_master_secret_arn },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.env}-${var.project}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }
  execution_role_arn = aws_iam_role.task_execution.arn
  task_role_arn      = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name      = "frontend"
    image     = "${var.frontend_ecr_url}:latest"
    essential = true

    portMappings = [{ containerPort = 8501, protocol = "tcp" }]

    environment = [
      { name = "API_URL",    value = "http://${aws_lb.main.dns_name}" },
      { name = "LOG_LEVEL",  value = var.log_level },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.frontend.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  tags = {
    Project = var.project
    Env     = var.env
  }
}

# ── ECS Services ──────────────────────────────────────────────────────────────
resource "aws_ecs_service" "api" {
  name            = "${var.env}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_sg_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.http]

  tags = {
    Project = var.project
    Env     = var.env
  }
}

resource "aws_ecs_service" "frontend" {
  name            = "${var.env}-frontend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_sg_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 8501
  }

  depends_on = [aws_lb_listener.http]

  tags = {
    Project = var.project
    Env     = var.env
  }
}

# ── Application Auto Scaling — API ────────────────────────────────────────────
resource "aws_appautoscaling_target" "api" {
  max_capacity       = 4
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${var.env}-${var.project}-api-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 60.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}

# ── Application Auto Scaling — Frontend ──────────────────────────────────────
resource "aws_appautoscaling_target" "frontend" {
  max_capacity       = 2
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.frontend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "frontend_cpu" {
  name               = "${var.env}-${var.project}-frontend-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.frontend.resource_id
  scalable_dimension = aws_appautoscaling_target.frontend.scalable_dimension
  service_namespace  = aws_appautoscaling_target.frontend.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 60.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60

    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
  }
}
