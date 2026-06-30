# ═════════════════════════════════════════════════════════════════════════════
# variables.tf — Terraform Variables for DropKey AWS Deployment
# ═════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════
# AWS Configuration
# ═════════════════════════════════════════════════════════════════════════════

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
  
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be development, staging, or production."
  }
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "dropkey"
}

# ═════════════════════════════════════════════════════════════════════════════
# VPC Configuration
# ═════════════════════════════════════════════════════════════════════════════

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "bastion_cidr" {
  description = "Bastion host CIDR for SSH access"
  type        = string
  default     = "0.0.0.0/32"
}

# ═════════════════════════════════════════════════════════════════════════════
# ALB Configuration
# ═════════════════════════════════════════════════════════════════════════════

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS"
  type        = string
}

variable "enable_deletion_protection" {
  description = "Enable ALB deletion protection"
  type        = bool
  default     = true
}

# ═════════════════════════════════════════════════════════════════════════════
# EC2 Configuration
# ═════════════════════════════════════════════════════════════════════════════

variable "ami_id" {
  description = "AMI ID for EC2 instances"
  type        = string
  # Default: Ubuntu 22.04 LTS in us-east-1
  default     = "ami-0c55b159cbfafe1f0"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.medium"
}

variable "root_volume_size" {
  description = "Root volume size in GB"
  type        = number
  default     = 30
}

variable "docker_image" {
  description = "Docker image name"
  type        = string
  default     = "dropkey"
}

variable "docker_registry" {
  description = "Docker registry URL"
  type        = string
  default     = "ghcr.io/yourorg"
}

variable "environment_variables" {
  description = "Environment variables for application"
  type        = map(string)
  default = {
    DROPKEY_ENVIRONMENT = "production"
    DROPKEY_DEBUG       = "false"
    DROPKEY_LOG_LEVEL   = "INFO"
  }
}

# ═════════════════════════════════════════════════════════════════════════════
# Auto Scaling Configuration
# ═════════════════════════════════════════════════════════════════════════════

variable "asg_min_size" {
  description = "Auto Scaling Group minimum size"
  type        = number
  default     = 3
}

variable "asg_max_size" {
  description = "Auto Scaling Group maximum size"
  type        = number
  default     = 10
}

variable "asg_desired_capacity" {
  description = "Auto Scaling Group desired capacity"
  type        = number
  default     = 3
}

variable "cpu_target_value" {
  description = "Target CPU utilization percentage for scaling"
  type        = number
  default     = 70
}

# ═════════════════════════════════════════════════════════════════════════════
# RDS Configuration
# ═════════════════════════════════════════════════════════════════════════════

variable "postgres_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "15.3"
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.large"
}

variable "db_allocated_storage" {
  description = "RDS allocated storage in GB"
  type        = number
  default     = 100
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "dropkey"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "dbadmin"
  sensitive   = true
}

variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}

variable "db_multi_az" {
  description = "Enable Multi-AZ deployment"
  type        = bool
  default     = true
}

variable "db_backup_retention_days" {
  description = "Database backup retention days"
  type        = number
  default     = 30
}

variable "db_backup_window" {
  description = "Database backup window (UTC)"
  type        = string
  default     = "02:00-03:00"
}

variable "db_maintenance_window" {
  description = "Database maintenance window"
  type        = string
  default     = "sun:03:00-sun:04:00"
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot on destroy"
  type        = bool
  default     = false
}

# ═════════════════════════════════════════════════════════════════════════════
# ElastiCache Configuration
# ═════════════════════════════════════════════════════════════════════════════

variable "redis_version" {
  description = "Redis version"
  type        = string
  default     = "7.0"
}

variable "redis_node_type" {
  description = "Redis node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_num_nodes" {
  description = "Number of Redis nodes"
  type        = number
  default     = 3
}

variable "redis_auth_token" {
  description = "Redis authentication token"
  type        = string
  sensitive   = true
  default     = ""
}

variable "redis_snapshot_retention" {
  description = "Redis snapshot retention days"
  type        = number
  default     = 5
}

variable "redis_snapshot_window" {
  description = "Redis snapshot window (UTC)"
  type        = string
  default     = "03:00-04:00"
}

# ═════════════════════════════════════════════════════════════════════════════
# CloudWatch Configuration
# ═════════════════════════════════════════════════════════════════════════════

variable "log_retention_days" {
  description = "CloudWatch log retention days"
  type        = number
  default     = 30
}

# ═════════════════════════════════════════════════════════════════════════════
# Tags
# ═════════════════════════════════════════════════════════════════════════════

variable "additional_tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
