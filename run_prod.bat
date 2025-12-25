@echo off
setlocal

echo 🍌 Building Nano Banana Studio for Production...

REM 1. 构建前端
echo 🏗️  Building Frontend...
cd frontend
call npm install
call npm run build
if %errorlevel% neq 0 (
    echo ❌ Frontend build failed!
    pause
    exit /b %errorlevel%
)
cd ..

REM 2. 准备后端环境
echo 🐍 Preparing Backend...
cd backend
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt

REM 3. 启动服务
echo 🚀 Starting Server...
echo 👉 Access via: http://localhost:6060
echo (To access from other devices, use your IP address: http://YOUR_IP:6060)

uvicorn main:app --host 0.0.0.0 --port 6060

endlocal
