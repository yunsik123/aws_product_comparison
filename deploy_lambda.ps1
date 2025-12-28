# Lambda deployment script for Windows PowerShell
param(
    [string]$Region = "ap-northeast-2",
    [string]$FunctionName = "nongshim-compare-api",
    [string]$RoleName = "nongshim-lambda-role"
)

$ErrorActionPreference = "Continue"

Write-Host "Deploying Nongshim Compare API to AWS Lambda..." -ForegroundColor Green
Write-Host ""

# Check AWS CLI
$AccountId = (aws sts get-caller-identity --query Account --output text 2>$null)
if (-not $AccountId) {
    Write-Host "AWS CLI not configured" -ForegroundColor Red
    exit 1
}
$AccountId = $AccountId.Trim()
Write-Host "AWS Account: $AccountId" -ForegroundColor Cyan

# Create IAM Role if not exists
Write-Host "`nSetting up IAM Role..." -ForegroundColor Yellow

$TrustPolicy = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
$TrustPolicyFile = Join-Path $env:TEMP "lambda-trust-policy.json"
$TrustPolicy | Out-File -FilePath $TrustPolicyFile -Encoding ascii -NoNewline

$RoleExists = aws iam get-role --role-name $RoleName 2>$null
if (-not $RoleExists) {
    Write-Host "Creating IAM Role..." -ForegroundColor Yellow
    aws iam create-role --role-name $RoleName --assume-role-policy-document "file://$TrustPolicyFile" --region $Region 2>$null
    aws iam attach-role-policy --role-name $RoleName --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>$null
    Write-Host "Waiting for role propagation..." -ForegroundColor Gray
    Start-Sleep -Seconds 15
} else {
    Write-Host "Role already exists" -ForegroundColor Green
}

# Add DynamoDB permissions
Write-Host "Adding DynamoDB permissions..." -ForegroundColor Yellow
$DynamoDBPolicy = @"
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:Scan",
                "dynamodb:Query"
            ],
            "Resource": "arn:aws:dynamodb:${Region}:${AccountId}:table/nongshim-product-cache"
        }
    ]
}
"@
$DynamoPolicyFile = Join-Path $env:TEMP "dynamodb-policy.json"
$DynamoDBPolicy | Out-File -FilePath $DynamoPolicyFile -Encoding ascii

# Create inline policy for DynamoDB
aws iam put-role-policy --role-name $RoleName --policy-name "DynamoDBReadAccess" --policy-document "file://$DynamoPolicyFile" 2>$null

$RoleArn = (aws iam get-role --role-name $RoleName --query "Role.Arn" --output text 2>$null)
if ($RoleArn) { $RoleArn = $RoleArn.Trim() }
Write-Host "Role ARN: $RoleArn" -ForegroundColor Cyan

# Create deployment package
Write-Host "`nCreating deployment package..." -ForegroundColor Yellow

$PackageDir = Join-Path $env:TEMP "lambda_package"
$ZipFile = Join-Path $env:TEMP "lambda_function.zip"

# Clean up
if (Test-Path $PackageDir) { Remove-Item -Recurse -Force $PackageDir }
if (Test-Path $ZipFile) { Remove-Item -Force $ZipFile }

New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null

# Install dependencies (Lambda compatible - Linux x86_64)
Write-Host "Installing dependencies (this may take a minute)..." -ForegroundColor Gray
pip install -r backend\requirements.txt -t $PackageDir --quiet --upgrade --platform manylinux2014_x86_64 --only-binary=:all: --implementation cp --python-version 3.11 2>$null

# Copy application code
Write-Host "Copying application code..." -ForegroundColor Gray
Copy-Item -Recurse -Force "backend\app" "$PackageDir\app"
Copy-Item -Force "backend\lambda_handler.py" "$PackageDir\lambda_handler.py"

# Create zip
Write-Host "Creating ZIP file..." -ForegroundColor Gray
Push-Location $PackageDir
Compress-Archive -Path * -DestinationPath $ZipFile -Force
Pop-Location

$ZipSize = [math]::Round((Get-Item $ZipFile).Length / 1MB, 2)
Write-Host "Package size: $ZipSize MB" -ForegroundColor Cyan

# Check if function exists
$FunctionExists = aws lambda get-function --function-name $FunctionName --region $Region 2>$null

# Create or update Lambda function
Write-Host "`nDeploying Lambda function..." -ForegroundColor Yellow

$EnvVars = "Variables={DYNAMODB_TABLE=nongshim-product-cache,AWS_REGION=$Region}"

if ($FunctionExists) {
    Write-Host "Updating existing function..." -ForegroundColor Gray
    aws lambda update-function-code --function-name $FunctionName --zip-file "fileb://$ZipFile" --region $Region 2>$null | Out-Null
    Start-Sleep -Seconds 5
    aws lambda update-function-configuration --function-name $FunctionName --timeout 30 --memory-size 512 --environment $EnvVars --region $Region 2>$null | Out-Null
} else {
    Write-Host "Creating new function..." -ForegroundColor Gray
    aws lambda create-function --function-name $FunctionName --runtime python3.11 --role $RoleArn --handler lambda_handler.handler --zip-file "fileb://$ZipFile" --timeout 30 --memory-size 512 --environment $EnvVars --region $Region 2>$null | Out-Null
}

Write-Host "Lambda function deployed" -ForegroundColor Green

# Create/Get API Gateway
Write-Host "`nSetting up API Gateway..." -ForegroundColor Yellow

# Check for existing API
$ApiId = $null
$ExistingApisJson = aws apigatewayv2 get-apis --region $Region --output json 2>$null
if ($ExistingApisJson) {
    $ExistingApis = $ExistingApisJson | ConvertFrom-Json
    foreach ($api in $ExistingApis.Items) {
        if ($api.Name -eq "$FunctionName-api") {
            $ApiId = $api.ApiId
            break
        }
    }
}

if (-not $ApiId) {
    Write-Host "Creating HTTP API..." -ForegroundColor Gray
    $ApiResultJson = aws apigatewayv2 create-api --name "$FunctionName-api" --protocol-type HTTP --region $Region --output json 2>$null
    if ($ApiResultJson) {
        $ApiResult = $ApiResultJson | ConvertFrom-Json
        $ApiId = $ApiResult.ApiId
    }
    
    # Create Lambda integration
    if ($ApiId) {
        $IntegrationJson = aws apigatewayv2 create-integration --api-id $ApiId --integration-type AWS_PROXY --integration-uri "arn:aws:lambda:${Region}:${AccountId}:function:$FunctionName" --payload-format-version 2.0 --region $Region --output json 2>$null
        if ($IntegrationJson) {
            $Integration = $IntegrationJson | ConvertFrom-Json
            $IntegrationId = $Integration.IntegrationId
            
            # Create route
            aws apigatewayv2 create-route --api-id $ApiId --route-key 'ANY /{proxy+}' --target "integrations/$IntegrationId" --region $Region 2>$null | Out-Null
            aws apigatewayv2 create-route --api-id $ApiId --route-key 'ANY /' --target "integrations/$IntegrationId" --region $Region 2>$null | Out-Null
            
            # Create stage
            aws apigatewayv2 create-stage --api-id $ApiId --stage-name '$default' --auto-deploy --region $Region 2>$null | Out-Null
        }
        
        # Add Lambda permission
        aws lambda add-permission --function-name $FunctionName --statement-id "apigateway-invoke-$ApiId" --action lambda:InvokeFunction --principal apigateway.amazonaws.com --source-arn "arn:aws:execute-api:${Region}:${AccountId}:$ApiId/*" --region $Region 2>$null | Out-Null
    }
}

if ($ApiId) {
    $ApiEndpoint = (aws apigatewayv2 get-api --api-id $ApiId --region $Region --query "ApiEndpoint" --output text 2>$null)
    if ($ApiEndpoint) { $ApiEndpoint = $ApiEndpoint.Trim() }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "API Endpoint:" -ForegroundColor White
Write-Host "   $ApiEndpoint" -ForegroundColor Cyan
Write-Host ""
Write-Host "API Documentation:" -ForegroundColor White
Write-Host "   $ApiEndpoint/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Health Check:" -ForegroundColor White
Write-Host "   $ApiEndpoint/health" -ForegroundColor Cyan
Write-Host ""

# Save endpoint to file
if ($ApiEndpoint) {
    $ApiEndpoint | Out-File -FilePath "API_ENDPOINT.txt" -Encoding utf8
    Write-Host "Endpoint saved to API_ENDPOINT.txt" -ForegroundColor Yellow
}

# Cleanup
Remove-Item -Recurse -Force $PackageDir -ErrorAction SilentlyContinue
Remove-Item -Force $ZipFile -ErrorAction SilentlyContinue
Remove-Item -Force $TrustPolicyFile -ErrorAction SilentlyContinue
Remove-Item -Force $DynamoPolicyFile -ErrorAction SilentlyContinue
