# Start Backend and Streamlit
Write-Host "🚀 Starting Nongshim Competitor Compare..." -ForegroundColor Green
Write-Host ""

# Start Backend
Write-Host "Starting Backend API on port 8000..." -ForegroundColor Cyan
$backendPath = Join-Path $PSScriptRoot "backend"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$backendPath'; `$env:PYTHONPATH='..'; Write-Host '🔧 Backend starting...' -ForegroundColor Yellow; uvicorn app.main:app --reload --port 8000"
)

Start-Sleep -Seconds 3

# Start Streamlit
Write-Host "Starting Streamlit UI on port 8501..." -ForegroundColor Cyan
$streamlitPath = Join-Path $PSScriptRoot "streamlit_app"
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$streamlitPath'; `$env:BACKEND_URL='http://localhost:8000'; Write-Host '🎨 Streamlit starting...' -ForegroundColor Yellow; streamlit run app.py --server.port 8501"
)

Write-Host ""
Write-Host "✅ Services starting in separate windows..." -ForegroundColor Green
Write-Host ""
Write-Host "📍 URLs:" -ForegroundColor White
Write-Host "   - Backend API: http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "   - Streamlit UI: http://localhost:8501" -ForegroundColor Gray
Write-Host ""
Write-Host "⏳ Wait a few seconds, then open http://localhost:8501 in your browser" -ForegroundColor Yellow
Write-Host ""
