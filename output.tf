output "lambda_function_arn" {
  description = "ARN of the created Lambda function"
  value       = aws_lambda_function.caching_setup.arn
}

output "lambda_function_name" {
  description = "Name of the created Lambda function"
  value       = aws_lambda_function.caching_setup.function_name
}

output "lambda_role_arn" {
  description = "ARN of the Lambda IAM role"
  value       = aws_iam_role.lambda_role.arn
}