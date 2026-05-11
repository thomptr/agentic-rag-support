terraform {
  required_version = ">= 1.8"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.50"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "project" {
  type    = string
  default = "agentic-rag"
}

# ── KMS key for state encryption ──────────────────────────────────────────────
resource "aws_kms_key" "state" {
  description             = "${var.project} OpenTofu state encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = {
    Project   = var.project
    ManagedBy = "opentofu-bootstrap"
  }
}

resource "aws_kms_alias" "state" {
  name          = "alias/opentofu-state"
  target_key_id = aws_kms_key.state.key_id
}

# ── S3 state bucket ───────────────────────────────────────────────────────────
resource "aws_s3_bucket" "state" {
  bucket = "${var.project}-tfstate-${data.aws_caller_identity.current.account_id}"

  tags = {
    Project   = var.project
    ManagedBy = "opentofu-bootstrap"
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.state.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_caller_identity" "current" {}

output "state_bucket_name" {
  value = aws_s3_bucket.state.bucket
}

output "kms_key_arn" {
  value = aws_kms_key.state.arn
}

output "kms_key_alias" {
  value = aws_kms_alias.state.name
}
