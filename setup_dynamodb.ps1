# DynamoDB 테이블 생성 스크립트
param(
    [string]$Region = "ap-northeast-2",
    [string]$TableName = "nongshim-product-cache"
)

Write-Host "Creating DynamoDB table: $TableName" -ForegroundColor Green

# Check if table exists
$TableExists = aws dynamodb describe-table --table-name $TableName --region $Region 2>$null

if ($TableExists) {
    Write-Host "Table already exists!" -ForegroundColor Yellow
} else {
    # Create table
    aws dynamodb create-table `
        --table-name $TableName `
        --attribute-definitions `
            AttributeName=pk,AttributeType=S `
            AttributeName=sk,AttributeType=S `
        --key-schema `
            AttributeName=pk,KeyType=HASH `
            AttributeName=sk,KeyType=RANGE `
        --billing-mode PAY_PER_REQUEST `
        --region $Region

    Write-Host "Waiting for table to be active..." -ForegroundColor Yellow
    aws dynamodb wait table-exists --table-name $TableName --region $Region

    Write-Host "Table created successfully!" -ForegroundColor Green
}

# Enable TTL
Write-Host "Enabling TTL on 'ttl' attribute..." -ForegroundColor Yellow
aws dynamodb update-time-to-live `
    --table-name $TableName `
    --time-to-live-specification "Enabled=true,AttributeName=ttl" `
    --region $Region 2>$null

Write-Host ""
Write-Host "DynamoDB Setup Complete!" -ForegroundColor Green
Write-Host "Table: $TableName" -ForegroundColor Cyan
Write-Host "Region: $Region" -ForegroundColor Cyan
