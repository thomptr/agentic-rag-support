terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50"
    }
  }
}

# ── pgVector parameter group ──────────────────────────────────────────────────
# pgvector does not need to appear in shared_preload_libraries — RDS rejects
# "vector" there (allowed values are auto_explain, pgaudit, pg_cron, etc.).
# The extension is loaded on demand by `CREATE EXTENSION vector` (run from
# scripts/init.sql during Step 7 of the quickstart). The parameter group is
# kept as an attachment point for any future PG16 tuning.
resource "aws_db_parameter_group" "pgvector" {
  name        = "${var.env}-${var.project}-pgvector16"
  family      = "postgres16"
  description = "PostgreSQL 16 base parameter group (pgvector enabled via CREATE EXTENSION)"

  tags = {
    Project = var.project
    Env     = var.env
  }
}

# ── DB subnet group ───────────────────────────────────────────────────────────
# `name_prefix` + create_before_destroy so subnet-set changes force a new
# subnet group resource rather than an in-place modify (RDS rejects in-place
# subnet swaps while the DB instance still references the old subnets).
resource "aws_db_subnet_group" "main" {
  name_prefix = "${var.env}-${var.project}-db-subnets-"
  subnet_ids  = var.private_subnet_ids

  tags = {
    Project = var.project
    Env     = var.env
  }

  lifecycle {
    create_before_destroy = true
  }
}

# ── RDS PostgreSQL 16 ─────────────────────────────────────────────────────────
resource "aws_db_instance" "main" {
  identifier = "${var.env}-${var.project}-db"

  engine         = "postgres"
  engine_version = "16"
  instance_class = "db.t4g.micro"

  allocated_storage     = 20
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = var.kms_key_arn

  db_name  = var.db_name
  username = var.db_username

  manage_master_user_password = true

  parameter_group_name = aws_db_parameter_group.pgvector.name
  db_subnet_group_name = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.rds_sg_id]

  publicly_accessible    = true   # POC: required for local-run init.sql/seed; revert for prod
  multi_az               = false
  deletion_protection    = false
  skip_final_snapshot    = true

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  tags = {
    Project = var.project
    Env     = var.env
  }

  # AWS rejects in-place subnet-group changes for an RDS instance in the same
  # VPC. Forcing replacement when the subnet group is recreated keeps the plan
  # honest (the alternative is OpenTofu trying ModifyDBInstance and failing).
  lifecycle {
    replace_triggered_by = [aws_db_subnet_group.main.id]
  }
}
