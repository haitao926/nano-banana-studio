#!/bin/bash

# Nano Banana Studio Development Startup Script

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE="${NBS_ENV_FILE:-$SCRIPT_DIR/.env.nbs}"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
fi

# Function to kill child processes on exit
cleanup() {
    echo "Stopping services..."
    kill $(jobs -p)
    exit
}

trap cleanup SIGINT SIGTERM

echo "🍌 Starting ReOpenInnoLab-智绘工坊..."

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

# Start uvicorn (workers for concurrency; disable reload when workers > 1)
DEV_WORKERS="${NBS_DEV_WORKERS:-2}"
if [ "$DEV_WORKERS" -gt 1 ]; then
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers "$DEV_WORKERS" &
else
    uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
fi
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
npm run dev -- --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!
cd ..

echo "✅ Services started!"
echo "Backend running on http://localhost:8000"
echo "Frontend running on http://localhost:5173"
echo "Press Ctrl+C to stop."

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
