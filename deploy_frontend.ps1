# S3 정적 웹사이트 배포 스크립트
param(
    [string]$Region = "ap-northeast-2",
    [string]$BucketName = "nongshim-compare-web"
)

$ErrorActionPreference = "Continue"

Write-Host "Deploying Frontend to S3..." -ForegroundColor Green
Write-Host ""

# Check AWS CLI
$AccountId = (aws sts get-caller-identity --query Account --output text 2>$null)
if (-not $AccountId) {
    Write-Host "AWS CLI not configured" -ForegroundColor Red
    exit 1
}
Write-Host "AWS Account: $AccountId" -ForegroundColor Cyan

# Check if bucket exists
Write-Host "`nChecking S3 bucket..." -ForegroundColor Yellow
$BucketExists = aws s3api head-bucket --bucket $BucketName 2>$null
$LASTEXITCODE_BUCKET = $LASTEXITCODE

if ($LASTEXITCODE_BUCKET -ne 0) {
    Write-Host "Creating S3 bucket: $BucketName" -ForegroundColor Yellow

    # Create bucket (ap-northeast-2 requires LocationConstraint)
    aws s3api create-bucket `
        --bucket $BucketName `
        --region $Region `
        --create-bucket-configuration LocationConstraint=$Region 2>$null

    Start-Sleep -Seconds 2
}

Write-Host "Bucket ready: $BucketName" -ForegroundColor Green

# Disable block public access
Write-Host "`nConfiguring public access..." -ForegroundColor Yellow
aws s3api put-public-access-block `
    --bucket $BucketName `
    --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false" `
    --region $Region 2>$null

Start-Sleep -Seconds 2

# Configure static website hosting
Write-Host "Enabling static website hosting..." -ForegroundColor Yellow
aws s3 website "s3://$BucketName" --index-document index.html --error-document index.html --region $Region 2>$null

# Set bucket policy for public read
Write-Host "Setting bucket policy..." -ForegroundColor Yellow
$BucketPolicy = @"
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::$BucketName/*"
        }
    ]
}
"@

$PolicyFile = Join-Path $env:TEMP "bucket-policy.json"
$BucketPolicy | Out-File -FilePath $PolicyFile -Encoding ascii

aws s3api put-bucket-policy --bucket $BucketName --policy "file://$PolicyFile" --region $Region 2>$null

# Upload files
Write-Host "`nUploading frontend files..." -ForegroundColor Yellow
aws s3 sync frontend/ "s3://$BucketName/" --delete --region $Region

# Get website URL
$WebsiteUrl = "http://$BucketName.s3-website.$Region.amazonaws.com"

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Website URL:" -ForegroundColor White
Write-Host "   $WebsiteUrl" -ForegroundColor Cyan
Write-Host ""

# Save URL to file
$WebsiteUrl | Out-File -FilePath "WEBSITE_URL.txt" -Encoding utf8
Write-Host "URL saved to WEBSITE_URL.txt" -ForegroundColor Yellow

# Cleanup
Remove-Item -Force $PolicyFile -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Open in browser: $WebsiteUrl" -ForegroundColor Green
