terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50"
    }
  }
}

# ── VPC ───────────────────────────────────────────────────────────────────────
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name    = "${var.env}-${var.project}-vpc"
    Project = var.project
    Env     = var.env
  }
}

# ── Public subnets ────────────────────────────────────────────────────────────
resource "aws_subnet" "public" {
  for_each = {
    a = { cidr = "10.0.1.0/24", az = "${var.region}a" }
    b = { cidr = "10.0.2.0/24", az = "${var.region}b" }
  }

  vpc_id                  = aws_vpc.main.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = true

  tags = {
    Name    = "${var.env}-${var.project}-public-${each.key}"
    Project = var.project
    Env     = var.env
  }
}

# ── Private subnets ───────────────────────────────────────────────────────────
# AZ choice is constrained by AgentCore Runtime: in us-east-1, AgentCore is only
# available in use1-az1, use1-az2, use1-az4. Account-to-AZ-name mappings vary,
# but here us-east-1b → use1-az1 and us-east-1c → use1-az2.
resource "aws_subnet" "private" {
  for_each = {
    a = { cidr = "10.0.12.0/24", az = "${var.region}c" }
    b = { cidr = "10.0.11.0/24", az = "${var.region}b" }
  }

  vpc_id            = aws_vpc.main.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.az

  tags = {
    Name    = "${var.env}-${var.project}-private-${each.key}"
    Project = var.project
    Env     = var.env
  }
}

# ── Internet Gateway ──────────────────────────────────────────────────────────
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name    = "${var.env}-${var.project}-igw"
    Project = var.project
    Env     = var.env
  }
}

# ── Elastic IP for NAT Gateway ────────────────────────────────────────────────
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = {
    Name    = "${var.env}-${var.project}-nat-eip"
    Project = var.project
    Env     = var.env
  }
}

# ── NAT Gateway (in first public subnet) ─────────────────────────────────────
resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public["a"].id

  tags = {
    Name    = "${var.env}-${var.project}-nat"
    Project = var.project
    Env     = var.env
  }

  depends_on = [aws_internet_gateway.main]
}

# ── Public route table ────────────────────────────────────────────────────────
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name    = "${var.env}-${var.project}-public-rt"
    Project = var.project
    Env     = var.env
  }
}

resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

# ── Private route table (via NAT) ─────────────────────────────────────────────
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = {
    Name    = "${var.env}-${var.project}-private-rt"
    Project = var.project
    Env     = var.env
  }
}

resource "aws_route_table_association" "private" {
  for_each       = aws_subnet.private
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}

# ── Security Groups ───────────────────────────────────────────────────────────

resource "aws_security_group" "alb" {
  name        = "${var.env}-${var.project}-alb-sg"
  description = "ALB: inbound HTTP/HTTPS from internet"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Streamlit frontend"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${var.env}-${var.project}-alb-sg"
    Project = var.project
    Env     = var.env
  }
}

resource "aws_security_group" "ecs" {
  name        = "${var.env}-${var.project}-ecs-sg"
  description = "ECS tasks: inbound from ALB only"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${var.env}-${var.project}-ecs-sg"
    Project = var.project
    Env     = var.env
  }
}

resource "aws_security_group" "agentcore" {
  name        = "${var.env}-${var.project}-agentcore-sg"
  description = "AgentCore: outbound to RDS and internet via NAT"
  vpc_id      = aws_vpc.main.id

  egress {
    description     = "RDS PostgreSQL"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.rds.id]
  }

  egress {
    description = "Internet (LLM APIs, ECR)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${var.env}-${var.project}-agentcore-sg"
    Project = var.project
    Env     = var.env
  }
}

resource "aws_security_group" "rds" {
  name        = "${var.env}-${var.project}-rds-sg"
  description = "RDS: inbound PostgreSQL from ECS and AgentCore"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name    = "${var.env}-${var.project}-rds-sg"
    Project = var.project
    Env     = var.env
  }
}

# Separate ingress rules to avoid circular dependency between agentcore and rds SGs
resource "aws_security_group_rule" "rds_from_ecs" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.rds.id
  source_security_group_id = aws_security_group.ecs.id
  description              = "PostgreSQL from ECS"
}

resource "aws_security_group_rule" "rds_from_agentcore" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  security_group_id        = aws_security_group.rds.id
  source_security_group_id = aws_security_group.agentcore.id
  description              = "PostgreSQL from AgentCore"
}

resource "aws_security_group_rule" "rds_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.rds.id
}

# POC: temporary developer-IP access for running init.sql / seed from a laptop.
# Set var.dev_public_ip_cidr to a /32 to enable; clear it (or remove this rule)
# before exposing the env beyond the POC.
resource "aws_security_group_rule" "rds_from_dev_ip" {
  count             = var.dev_public_ip_cidr != "" ? 1 : 0
  type              = "ingress"
  from_port         = 5432
  to_port           = 5432
  protocol          = "tcp"
  security_group_id = aws_security_group.rds.id
  cidr_blocks       = [var.dev_public_ip_cidr]
  description       = "POC: developer public IP for init/seed"
}
