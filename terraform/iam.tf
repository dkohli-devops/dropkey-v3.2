# ═════════════════════════════════════════════════════════════════════════════
# iam.tf — IAM Roles and Policies for DropKey AWS Deployment
#
# Implements principle of least privilege
# ═════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════
# EC2 Instance Role
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_iam_role" "ec2_role" {
  name_prefix = "${var.project_name}-ec2-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-ec2-role"
  }
}

resource "aws_iam_instance_profile" "ec2" {
  name_prefix = "${var.project_name}-ec2-"
  role        = aws_iam_role.ec2_role.name
}

# ═════════════════════════════════════════════════════════════════════════════
# EC2 - S3 Access Policy
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_iam_role_policy" "ec2_s3_access" {
  name_prefix = "${var.project_name}-ec2-s3-"
  role        = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3UploadsBucket"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.uploads.arn}/*"
      },
      {
        Sid    = "S3UploadsList"
        Effect = "Allow"
        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = aws_s3_bucket.uploads.arn
      }
    ]
  })
}

# ═════════════════════════════════════════════════════════════════════════════
# EC2 - CloudWatch Access Policy
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_iam_role_policy" "ec2_cloudwatch" {
  name_prefix = "${var.project_name}-ec2-cloudwatch-"
  role        = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "PutMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "ec2:DescribeVolumes",
          "ec2:DescribeTags",
          "logs:PutLogEvents",
          "logs:CreateLogStream",
          "logs:CreateLogGroup"
        ]
        Resource = "*"
      },
      {
        Sid    = "GetSSMParameter"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:*:parameter/${var.project_name}/*"
      }
    ]
  })
}

# ═════════════════════════════════════════════════════════════════════════════
# EC2 - Secrets Manager Access Policy
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_iam_role_policy" "ec2_secrets" {
  name_prefix = "${var.project_name}-ec2-secrets-"
  role        = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GetDatabaseSecret"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:*:secret:${var.project_name}/db/*"
      },
      {
        Sid    = "GetRedisSecret"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${var.aws_region}:*:secret:${var.project_name}/redis/*"
      }
    ]
  })
}

# ═════════════════════════════════════════════════════════════════════════════
# EC2 - KMS Decryption Policy
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_iam_role_policy" "ec2_kms" {
  name_prefix = "${var.project_name}-ec2-kms-"
  role        = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DecryptEBS"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = aws_kms_key.ebs.arn
      },
      {
        Sid    = "DecryptS3"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = aws_kms_key.s3.arn
      }
    ]
  })
}

# ═════════════════════════════════════════════════════════════════════════════
# EC2 - SSM Session Manager Policy
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# ═════════════════════════════════════════════════════════════════════════════
# RDS Enhanced Monitoring Role
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_iam_role" "rds_monitoring" {
  name_prefix = "${var.project_name}-rds-monitoring-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-rds-monitoring-role"
  }
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# ═════════════════════════════════════════════════════════════════════════════
# CloudWatch Logs Policy for RDS
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_iam_role_policy" "rds_logs" {
  name_prefix = "${var.project_name}-rds-logs-"
  role        = aws_iam_role.rds_monitoring.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowRDSLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:CreateLogGroup"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:log-group:/aws/rds/*"
      }
    ]
  })
}

# ═════════════════════════════════════════════════════════════════════════════
# Lambda Execution Role (for automation tasks)
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_iam_role" "lambda_role" {
  name_prefix = "${var.project_name}-lambda-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-lambda-role"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_rds" {
  name_prefix = "${var.project_name}-lambda-rds-"
  role        = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "RDSAccess"
        Effect = "Allow"
        Action = [
          "rds:DescribeDBInstances",
          "rds:CreateDBSnapshot",
          "rds:DescribeDBSnapshots",
          "rds-db:connect"
        ]
        Resource = "arn:aws:rds:${var.aws_region}:*:db/${var.project_name}*"
      }
    ]
  })
}

# ═════════════════════════════════════════════════════════════════════════════
# Backup Role for Cross-Region Backup
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_iam_role" "backup_role" {
  name_prefix = "${var.project_name}-backup-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "backup.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-backup-role"
  }
}

resource "aws_iam_role_policy_attachment" "backup_default" {
  role       = aws_iam_role.backup_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

resource "aws_iam_role_policy_attachment" "backup_restore" {
  role       = aws_iam_role.backup_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores"
}

# ═════════════════════════════════════════════════════════════════════════════
# KMS Key Policies
# ═════════════════════════════════════════════════════════════════════════════

resource "aws_kms_key_policy" "ebs" {
  key_id = aws_kms_key.ebs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow EC2 Use"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_kms_key_policy" "rds" {
  key_id = aws_kms_key.rds.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow RDS Use"
        Effect = "Allow"
        Principal = {
          Service = "rds.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:GenerateDataKey",
          "kms:CreateGrant"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_kms_key_policy" "s3" {
  key_id = aws_kms_key.s3.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow S3 Use"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })
}
