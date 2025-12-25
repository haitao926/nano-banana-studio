@echo off
setlocal

echo 🍌 Building ReOpenInnoLab-教学绘画 (Windows EXE) ...

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

REM 2. 准备后端打包环境
echo 🐍 Preparing Backend Environment...
cd backend
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

REM 3. 开始打包 (PyInstaller)
echo 📦 Packaging EXE...
REM --add-data 语法: 源路径;目标路径 (Windows 分隔符是 ;)
REM 我们把前端构建产物放入 exe 内部的 'dist' 目录
REM main.py 是入口
pyinstaller --noconfirm --onefile --windowed ^
    --name "ReOpenInnoLab" ^
    --add-data "../frontend/dist;dist" ^
    --hidden-import "uvicorn.logging" ^
    --hidden-import "uvicorn.loops" ^
    --hidden-import "uvicorn.loops.auto" ^
    --hidden-import "uvicorn.protocols" ^
    --hidden-import "uvicorn.protocols.http" ^
    --hidden-import "uvicorn.protocols.http.auto" ^
    --hidden-import "uvicorn.lifespan" ^
    --hidden-import "uvicorn.lifespan.on" ^
    main.py

if %errorlevel% neq 0 (
    echo ❌ PyInstaller failed!
    pause
    exit /b %errorlevel%
)

REM 4. 移动成品
echo ✅ Build Success!
echo Moving executable to root...
move dist\ReOpenInnoLab.exe ..\ReOpenInnoLab.exe

REM 清理
echo Cleaning up...
rmdir /s /q build
rmdir /s /q dist
del ReOpenInnoLab.spec

echo.
echo ========================================================
echo 🎉 DONE! 
echo Portable executable is ready: ReOpenInnoLab.exe
echo.
echo IMPORTANT: 
echo This EXE expects 'static' and 'data' folders to exist next to it 
echo for storing your images and logs.
echo ========================================================
pause

endlocal
