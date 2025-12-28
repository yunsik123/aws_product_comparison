# 🚀 실행 가이드

## 방법 1: 간단한 실행 (권장)

### 1단계: 백엔드 실행
새 PowerShell 창을 열고:
```powershell
cd c:\Users\신윤식\Desktop\aws_product_comparison\backend
$env:PYTHONPATH=".."
uvicorn app.main:app --reload --port 8000
```

**확인**: `http://localhost:8000/docs` 접속 시 API 문서가 보이면 성공

### 2단계: Streamlit 실행
또 다른 PowerShell 창을 열고:
```powershell
cd c:\Users\신윤식\Desktop\aws_product_comparison\streamlit_app
$env:BACKEND_URL="http://localhost:8000"
streamlit run app.py
```

**확인**: 자동으로 브라우저가 열리거나 `http://localhost:8501` 접속

---

## 방법 2: 한 번에 실행 (스크립트)

### start.ps1 파일 생성 후 실행
```powershell
# 프로젝트 루트에서
.\start.ps1
```

---

## 테스트 방법

### API 직접 테스트
```powershell
# PowerShell에서
Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get
```

### 제품 비교 테스트
```powershell
$body = @{
    product_a = "신라면"
    product_b = "진라면 매운맛"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/compare" -Method Post -Body $body -ContentType "application/json"
```

---

## 문제 해결

### 포트가 이미 사용 중인 경우
```powershell
# 8000번 포트 사용 중인 프로세스 확인
netstat -ano | findstr :8000

# 프로세스 종료 (PID는 위 명령어 결과에서 확인)
taskkill /PID <PID> /F
```

### 의존성 설치 필요 시
```powershell
cd c:\Users\신윤식\Desktop\aws_product_comparison\backend
pip install -r requirements.txt

cd ..\streamlit_app
pip install -r requirements.txt
```
