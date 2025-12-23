@echo off
setlocal

echo [INFO] Starting Nano Banana System...

echo.
echo [INFO] Step 1: Checking Backend Dependencies...
python -m pip install -r backend/requirements.txt

echo.
echo [INFO] Step 2: Checking Frontend Dependencies...
cd frontend
call npm install
cd ..

echo.
echo [INFO] Step 3: Launching Backend Server...
:: Using a simple title without spaces to avoid parsing errors
start "NanoBananaBackend" cmd /k "python backend/main.py"

echo.
echo [INFO] Step 4: Launching Frontend Server...
echo [INFO] The browser should open automatically at http://localhost:5173
cd frontend
npm run dev