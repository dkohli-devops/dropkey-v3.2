# ═════════════════════════════════════════════════════════════════════════════
# main.tf — Terraform Main Configuration for DropKey AWS Deployment
#
# Usage:
#   terraform init
#   terraform plan -out=tfplan
#   terraform apply tfplan
# ═════════════════════════════════════════════════════════════════════════════

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment for remote state storage
  # backend "s3" {
  #   bucket         = "dropkey-terraform-state"
  #   key            = "prod/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-lock"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "DropKey"
      Environment = var.environment
      Terraform   = "true"
      CreatedAt   = timestamp()
    }
  }
}

# ═════════════════════════════════════════════════════════════════════════════
# VPC & NETWORKING
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

# Public Subnets
resource "aws_subnet" "public" {
  count                   = length(var.availability_zones)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.${count.index * 16}.0/20"
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-${count.index + 1}"
  }
}

# Private Subnets (for RDS, ElastiCache, EC2)
resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index * 16 + 4}.0/22"
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${var.project_name}-private-${count.index + 1}"
  }
}

# Database Subnets
resource "aws_subnet" "database" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index * 16 + 8}.0/23"
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${var.project_name}-database-${count.index + 1}"
  }
}

# ═════════════════════════════════════════════════════════════════════════════
# SECURITY GROUPS
# ═════════════════════════════════════════════════════════════════════════════

# ALB Security Group
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb-sg"
  description = "Security group for ALB"
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

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-alb-sg"
  }
}

# EC2 Security Group
resource "aws_security_group" "ec2" {
  name        = "${var.project_name}-ec2-sg"
  description = "Security group for EC2 instances"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.bastion_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-ec2-sg"
  }
}

# RDS Security Group
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "Security group for RDS"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-rds-sg"
  }
}

# ElastiCache Security Group
resource "aws_security_group" "elasticache" {
  name        = "${var.project_name}-elasticache-sg"
  description = "Security group for ElastiCache"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-elasticache-sg"
  }
}

# ═════════════════════════════════════════════════════════════════════════════
# APPLICATION LOAD BALANCER
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = var.enable_deletion_protection
  enable_http2               = true
  enable_cross_zone_load_balancing = true

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.id
    prefix  = "alb-logs"
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-alb"
  }

  depends_on = [aws_s3_bucket.alb_logs]
}

# Target Group
resource "aws_lb_target_group" "main" {
  name        = "${var.project_name}-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "instance"

  health_check {
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health/ready"
    matcher             = "200"
  }

  stickiness {
    type            = "lb_cookie"
    enabled         = true
    cookie_duration = 86400
  }

  tags = {
    Name = "${var.project_name}-tg"
  }
}

# HTTP Listener (redirect to HTTPS)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# HTTPS Listener
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.main.arn
  }
}

# ═════════════════════════════════════════════════════════════════════════════
# AUTO SCALING
# ═════════════════════════════════════════════════════════════════════════════

# Launch Template
resource "aws_launch_template" "main" {
  name_prefix   = "${var.project_name}-"
  image_id      = var.ami_id
  instance_type = var.instance_type

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size
    delete_on_termination = true
    encrypted             = true
    kms_key_id            = aws_kms_key.ebs.arn

    tags = {
      Name = "${var.project_name}-root"
    }
  }

  iam_instance_profile {
    arn = aws_iam_instance_profile.ec2.arn
  }

  security_groups = [aws_security_group.ec2.id]

  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    docker_image       = var.docker_image
    docker_registry    = var.docker_registry
    aws_region         = var.aws_region
    rds_endpoint       = aws_db_instance.postgres.endpoint
    redis_endpoint     = aws_elasticache_cluster.redis.cache_nodes[0].address
    s3_bucket          = aws_s3_bucket.uploads.id
    environment_vars   = var.environment_variables
  }))

  monitoring {
    enabled = true
  }

  tag_specifications {
    resource_type = "instance"

    tags = {
      Name = "${var.project_name}-instance"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Auto Scaling Group
resource "aws_autoscaling_group" "main" {
  name                = "${var.project_name}-asg"
  vpc_zone_identifier = aws_subnet.private[*].id
  target_group_arns   = [aws_lb_target_group.main.arn]
  health_check_type   = "ELB"
  health_check_grace_period = 300

  min_size         = var.asg_min_size
  max_size         = var.asg_max_size
  desired_capacity = var.asg_desired_capacity

  launch_template {
    id      = aws_launch_template.main.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "${var.project_name}-asg-instance"
    propagate_at_launch = true
  }

  termination_policies = [
    "OldestInstance",
    "Default"
  ]

  lifecycle {
    create_before_destroy = true
  }
}

# Target Tracking Scaling Policy (CPU)
resource "aws_autoscaling_policy" "cpu" {
  name                   = "${var.project_name}-cpu-tracking"
  policy_type            = "TargetTrackingScaling"
  autoscaling_group_name = aws_autoscaling_group.main.name

  target_tracking_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ASGAverageCPUUtilization"
    }

    target_value = var.cpu_target_value
  }
}

# ═════════════════════════════════════════════════════════════════════════════
# RDS PostgreSQL
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_db_subnet_group" "postgres" {
  name       = "${var.project_name}-db-subnet"
  subnet_ids = aws_subnet.database[*].id

  tags = {
    Name = "${var.project_name}-db-subnet"
  }
}

resource "aws_db_instance" "postgres" {
  identifier     = "${var.project_name}-postgres"
  engine         = "postgres"
  engine_version = var.postgres_version
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.rds.arn

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  multi_az               = var.db_multi_az
  backup_retention_period = var.db_backup_retention_days
  backup_window          = var.db_backup_window
  maintenance_window     = var.db_maintenance_window
  copy_tags_to_snapshot  = true

  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = "${var.project_name}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"

  enabled_cloudwatch_logs_exports = ["postgresql"]
  enable_performance_insights      = true
  performance_insights_retention_period = 7

  tags = {
    Name = "${var.project_name}-postgres"
  }

  depends_on = [aws_security_group.rds]
}

# ═════════════════════════════════════════════════════════════════════════════
# ELASTICACHE REDIS
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.project_name}-redis-subnet"
  subnet_ids = aws_subnet.database[*].id

  tags = {
    Name = "${var.project_name}-redis-subnet"
  }
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.project_name}-redis"
  engine               = "redis"
  engine_version       = var.redis_version
  node_type            = var.redis_node_type
  num_cache_nodes      = var.redis_num_nodes
  parameter_group_name = "default.redis7"
  port                 = 6379
  security_group_ids   = [aws_security_group.elasticache.id]
  subnet_group_name    = aws_elasticache_subnet_group.redis.name

  at_rest_encryption_enabled = true
  auth_token                 = var.redis_auth_token
  transit_encryption_enabled = true

  snapshot_retention_limit = var.redis_snapshot_retention
  snapshot_window          = var.redis_snapshot_window

  automatic_failover_enabled = true

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    enabled          = true
  }

  tags = {
    Name = "${var.project_name}-redis"
  }

  depends_on = [aws_security_group.elasticache]
}

# ═════════════════════════════════════════════════════════════════════════════
# S3 BUCKETS
# ═════════════════════════════════════════════════════════════════════════════

# Application Uploads Bucket
resource "aws_s3_bucket" "uploads" {
  bucket = "${var.project_name}-prod-uploads-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-uploads"
  }
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
  }
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ALB Logs Bucket
resource "aws_s3_bucket" "alb_logs" {
  bucket = "${var.project_name}-alb-logs-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-alb-logs"
  }
}

resource "aws_s3_bucket_public_access_block" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ═════════════════════════════════════════════════════════════════════════════
# CLOUDWATCH
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_cloudwatch_log_group" "application" {
  name              = "/aws/dropkey/application"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.project_name}-app-logs"
  }
}

resource "aws_cloudwatch_log_group" "redis" {
  name              = "/aws/dropkey/redis"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.project_name}-redis-logs"
  }
}

# ═════════════════════════════════════════════════════════════════════════════
# KMS ENCRYPTION KEYS
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_kms_key" "ebs" {
  description             = "KMS key for EBS encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-ebs-key"
  }
}

resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-rds-key"
  }
}

resource "aws_kms_key" "s3" {
  description             = "KMS key for S3 encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-s3-key"
  }
}

# ═════════════════════════════════════════════════════════════════════════════
# DATA SOURCES
# ═════════════════════════════════════════════════════════════════════════════

data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}
