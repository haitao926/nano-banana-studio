#!/bin/bash

echo "🍌 Building Nano Banana Studio for Production..."

# 1. 构建前端
echo "🏗️  Building Frontend..."
cd frontend
npm install
npm run build
if [ $? -ne 0 ]; then
    echo "❌ Frontend build failed!"
    exit 1
fi
cd ..

# 2. 准备后端环境
echo "🐍 Preparing Backend..."
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt

# 3. 启动服务 (监听 0.0.0.0 以便局域网访问)
echo "🚀 Starting Server..."
echo "👉 Local:   http://localhost:6060"
echo "👉 Network: http://$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -n 1):6060"

# 使用生产级配置启动
uvicorn main:app --host 0.0.0.0 --port 6060
