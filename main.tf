data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/script.py"
  output_path = "${path.module}/caching-setup.zip"
}

# Create IAM role for the Lambda function
resource "aws_iam_role" "lambda_role" {
  name = "caching-setup-lambda-role"

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
}

# Attach CloudFront permissions to the Lambda role
resource "aws_iam_role_policy" "lambda_cloudfront_policy" {
  name = "cloudfront-management-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudfront:GetDistribution",
          "cloudfront:GetDistributionConfig",
          "cloudfront:UpdateDistribution",
          "cloudfront:CreateInvalidation"
        ]
        Resource = "*"
      }
    ]
  })
}

# Attach basic Lambda execution permissions
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda_role.name
}

# Create Lambda function
resource "aws_lambda_function" "caching_setup" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "caching-setup"
  role            = aws_iam_role.lambda_role.arn
  handler         = "script.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime         = "python3.12"
  timeout         = 30

  environment {
    variables = {
      # Add any environment variables your Lambda might need
    }
  }
}
