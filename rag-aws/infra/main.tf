terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

resource "aws_kms_key" "s3" {
  description             = "KMS key for Jira ingestion bucket encryption"
  deletion_window_in_days = 7
}

resource "aws_s3_bucket" "artifacts" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.s3.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_object" "lambda_package" {
  bucket = aws_s3_bucket.artifacts.id
  key    = var.lambda_zip_key
  source = var.lambda_local_zip_path
  etag   = filemd5(var.lambda_local_zip_path)
}

resource "aws_ssm_parameter" "cursor" {
  name  = var.cursor_param_name
  type  = "String"
  value = ""

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_iam_role" "lambda" {
  name = "${var.lambda_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "basic_execution" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_inline" {
  name = "${var.lambda_name}-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = var.jira_secret_arn
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:PutParameter"
        ]
        Resource = aws_ssm_parameter.cursor.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:PutObjectAcl"
        ]
        Resource = "${aws_s3_bucket.artifacts.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Encrypt",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.s3.arn
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.lambda_name}"
  retention_in_days = 30
}

resource "aws_lambda_function" "jira_ingestor" {
  function_name = var.lambda_name
  role          = aws_iam_role.lambda.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.12"
  timeout       = 300
  memory_size   = 512

  s3_bucket = aws_s3_bucket.artifacts.id
  s3_key    = aws_s3_object.lambda_package.key

  source_code_hash = filebase64sha256(var.lambda_local_zip_path)

  environment {
    variables = {
      S3_BUCKET        = aws_s3_bucket.artifacts.bucket
      JIRA_OAUTH_SECRET = var.jira_secret_arn
      CURSOR_PARAM     = var.cursor_param_name
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_inline,
    aws_iam_role_policy_attachment.basic_execution
  ]
}

resource "aws_cloudwatch_event_rule" "hourly" {
  name                = "${var.lambda_name}-schedule"
  description         = "Hourly trigger for Jira ingestion"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "lambda" {
  rule      = aws_cloudwatch_event_rule.hourly.name
  target_id = "jira-ingestor"
  arn       = aws_lambda_function.jira_ingestor.arn
}

resource "aws_lambda_permission" "allow_events" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.jira_ingestor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.hourly.arn
}
