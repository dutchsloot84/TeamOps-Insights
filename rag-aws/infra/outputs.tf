output "bucket_name" {
  description = "S3 bucket storing Jira artifacts and Lambda package"
  value       = aws_s3_bucket.artifacts.bucket
}

output "lambda_name" {
  description = "Name of the Jira ingestion Lambda function"
  value       = aws_lambda_function.jira_ingestor.function_name
}

output "event_rule" {
  description = "CloudWatch Events rule triggering the ingestion Lambda"
  value       = aws_cloudwatch_event_rule.hourly.name
}
