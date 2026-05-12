terraform {
  backend "s3" {
    # Bucket is created by `infra/bootstrap` (output: state_bucket_name).
    # For a fresh account, run bootstrap first then sed-replace REPLACE_ACCOUNT_ID
    # with the account ID from `aws sts get-caller-identity`.
    bucket       = "agentic-rag-tfstate-791642260585"
    key          = "dev/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }

  encryption {
    key_provider "aws_kms" "state_key" {
      kms_key_id = "alias/opentofu-state"
      region     = "us-east-1"
      key_spec   = "AES_256"
    }
    method "aes_gcm" "default" {
      keys = key_provider.aws_kms.state_key
    }
    state {
      method   = method.aes_gcm.default
      enforced = true
    }
  }
}
