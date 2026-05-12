output "db_endpoint" {
  # `.address` is just the hostname; `.endpoint` would include `:5432`, which
  # breaks `psql -h` and naive DATABASE_URL templates that already append a port.
  value = aws_db_instance.main.address
}

output "db_name" {
  value = aws_db_instance.main.db_name
}

output "db_master_secret_arn" {
  value = aws_db_instance.main.master_user_secret[0].secret_arn
}

output "db_instance_id" {
  value = aws_db_instance.main.id
}
