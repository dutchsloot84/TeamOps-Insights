variable "region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-west-2"
}

variable "bucket_name" {
  description = "Unique name for the ingestion artifact bucket"
  type        = string
}

variable "jira_secret_arn" {
  description = "ARN of the Secrets Manager secret containing Jira OAuth credentials"
  type        = string
}

variable "lambda_zip_key" {
  description = "S3 key where the Lambda deployment package will be uploaded"
  type        = string
  default     = "lambda/jira_ingestor.zip"
}

variable "lambda_local_zip_path" {
  description = "Path to the local Lambda deployment package"
  type        = string
  default     = "../../services/ingest/jira_ingestor/jira_ingestor.zip"
}

variable "lambda_name" {
  description = "Lambda function name"
  type        = string
  default     = "rag-jira-ingestor"
}

variable "cursor_param_name" {
  description = "SSM Parameter name used to store the Jira sync cursor"
  type        = string
  default     = "/rag/jira/last_sync"
}
