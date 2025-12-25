#!/bin/bash

# Nano Banana Studio Development Startup Script

# Function to kill child processes on exit
cleanup() {
    echo "Stopping services..."
    kill $(jobs -p)
    exit
}

trap cleanup SIGINT SIGTERM

echo "🍌 Starting Nano Banana Studio..."

# 1. Start Backend
echo "Starting Backend..."
cd backend
# Ensure dependencies are installed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt

# Start uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to initialize
sleep 2

# 2. Start Frontend
echo "Starting Frontend..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi
npm run dev &
FRONTEND_PID=$!
cd ..

echo "✅ Services started!"
echo "Backend running on http://localhost:8000"
echo "Frontend running on http://localhost:5173"
echo "Press Ctrl+C to stop."

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID