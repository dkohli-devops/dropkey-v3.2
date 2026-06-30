# ═════════════════════════════════════════════════════════════════════════════
# outputs.tf — Terraform Outputs for DropKey AWS Deployment
# ═════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════
# ALB Outputs
# ═════════════════════════════════════════════════════════════════════════════

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_arn" {
  description = "ARN of the Application Load Balancer"
  value       = aws_lb.main.arn
}

output "alb_zone_id" {
  description = "Zone ID of the Application Load Balancer"
  value       = aws_lb.main.zone_id
}

# ═════════════════════════════════════════════════════════════════════════════
# Auto Scaling Group Outputs
# ═════════════════════════════════════════════════════════════════════════════

output "asg_name" {
  description = "Name of the Auto Scaling Group"
  value       = aws_autoscaling_group.main.name
}

output "asg_desired_capacity" {
  description = "Desired capacity of the Auto Scaling Group"
  value       = aws_autoscaling_group.main.desired_capacity
}

output "launch_template_id" {
  description = "ID of the Launch Template"
  value       = aws_launch_template.main.id
}

# ═════════════════════════════════════════════════════════════════════════════
# RDS Outputs
# ═════════════════════════════════════════════════════════════════════════════

output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "rds_address" {
  description = "RDS instance address"
  value       = aws_db_instance.postgres.address
}

output "rds_port" {
  description = "RDS instance port"
  value       = aws_db_instance.postgres.port
}

output "rds_database_name" {
  description = "RDS database name"
  value       = aws_db_instance.postgres.db_name
}

output "rds_master_username" {
  description = "RDS master username"
  value       = aws_db_instance.postgres.username
  sensitive   = true
}

output "rds_resource_id" {
  description = "RDS resource ID"
  value       = aws_db_instance.postgres.resource_id
}

# ═════════════════════════════════════════════════════════════════════════════
# ElastiCache Outputs
# ═════════════════════════════════════════════════════════════════════════════

output "redis_cluster_address" {
  description = "Redis cluster address"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "redis_cluster_port" {
  description = "Redis cluster port"
  value       = aws_elasticache_cluster.redis.port
}

output "redis_engine_version" {
  description = "Redis engine version"
  value       = aws_elasticache_cluster.redis.engine_version
}

output "redis_cluster_id" {
  description = "Redis cluster ID"
  value       = aws_elasticache_cluster.redis.cluster_id
}

# ═════════════════════════════════════════════════════════════════════════════
# S3 Outputs
# ═════════════════════════════════════════════════════════════════════════════

output "s3_uploads_bucket" {
  description = "S3 uploads bucket name"
  value       = aws_s3_bucket.uploads.id
}

output "s3_uploads_arn" {
  description = "S3 uploads bucket ARN"
  value       = aws_s3_bucket.uploads.arn
}

output "s3_alb_logs_bucket" {
  description = "S3 ALB logs bucket name"
  value       = aws_s3_bucket.alb_logs.id
}

# ═════════════════════════════════════════════════════════════════════════════
# VPC Outputs
# ═════════════════════════════════════════════════════════════════════════════

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "VPC CIDR block"
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = aws_subnet.private[*].id
}

output "database_subnet_ids" {
  description = "Database subnet IDs"
  value       = aws_subnet.database[*].id
}

# ═════════════════════════════════════════════════════════════════════════════
# Security Group Outputs
# ═════════════════════════════════════════════════════════════════════════════

output "alb_security_group_id" {
  description = "ALB security group ID"
  value       = aws_security_group.alb.id
}

output "ec2_security_group_id" {
  description = "EC2 security group ID"
  value       = aws_security_group.ec2.id
}

output "rds_security_group_id" {
  description = "RDS security group ID"
  value       = aws_security_group.rds.id
}

output "elasticache_security_group_id" {
  description = "ElastiCache security group ID"
  value       = aws_security_group.elasticache.id
}

# ═════════════════════════════════════════════════════════════════════════════
# CloudWatch Outputs
# ═════════════════════════════════════════════════════════════════════════════

output "application_log_group" {
  description = "Application CloudWatch log group name"
  value       = aws_cloudwatch_log_group.application.name
}

output "redis_log_group" {
  description = "Redis CloudWatch log group name"
  value       = aws_cloudwatch_log_group.redis.name
}

# ═════════════════════════════════════════════════════════════════════════════
# IAM Outputs
# ═════════════════════════════════════════════════════════════════════════════

output "ec2_iam_role_arn" {
  description = "EC2 IAM role ARN"
  value       = aws_iam_role.ec2_role.arn
}

output "ec2_instance_profile_arn" {
  description = "EC2 instance profile ARN"
  value       = aws_iam_instance_profile.ec2.arn
}

# ═════════════════════════════════════════════════════════════════════════════
# KMS Outputs
# ═════════════════════════════════════════════════════════════════════════════

output "ebs_kms_key_id" {
  description = "EBS KMS key ID"
  value       = aws_kms_key.ebs.id
}

output "rds_kms_key_id" {
  description = "RDS KMS key ID"
  value       = aws_kms_key.rds.id
}

output "s3_kms_key_id" {
  description = "S3 KMS key ID"
  value       = aws_kms_key.s3.id
}

# ═════════════════════════════════════════════════════════════════════════════
# Connection Strings
# ═════════════════════════════════════════════════════════════════════════════

output "database_connection_string" {
  description = "PostgreSQL connection string"
  value       = "postgresql://${aws_db_instance.postgres.username}@${aws_db_instance.postgres.endpoint}/${aws_db_instance.postgres.db_name}"
  sensitive   = true
}

output "redis_connection_string" {
  description = "Redis connection string"
  value       = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.port}"
}

# ═════════════════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════════════════

output "deployment_summary" {
  description = "Deployment summary"
  value = {
    alb_dns_name                = aws_lb.main.dns_name
    rds_endpoint                = aws_db_instance.postgres.endpoint
    redis_endpoint              = "${aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.port}"
    s3_uploads_bucket           = aws_s3_bucket.uploads.id
    asg_name                    = aws_autoscaling_group.main.name
    asg_desired_capacity        = aws_autoscaling_group.main.desired_capacity
    vpc_id                      = aws_vpc.main.id
    application_log_group       = aws_cloudwatch_log_group.application.name
  }
}
