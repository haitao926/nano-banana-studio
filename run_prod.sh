#!/bin/bash

# Ensure we are in the script's directory
cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"

# Parse arguments
SKIP_BUILD=false
if [[ "$*" == *"--no-build"* ]]; then
    SKIP_BUILD=true
fi

# Function to setup Linux auto-start (Systemd)
setup_linux_autostart() {
    SERVICE_NAME="nano-banana.service"
    SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"
    
    # Determine the user to run the service as (handle sudo)
    TARGET_USER="${SUDO_USER:-$(whoami)}"
    
    echo "🐧 Configuring Linux auto-start (Systemd)..."
    echo "   Service will run as user: $TARGET_USER"
    echo "   Project root: $PROJECT_ROOT"
    
    # Check for root privileges (required for systemd file creation)
    if [ "$EUID" -ne 0 ]; then
        echo "⚠️  This operation requires root privileges to write to /etc/systemd/system/"
        echo "   Please run: sudo $0 --install-startup"
        exit 1
    fi

    # Ensure the script is executable
    chmod +x "$PROJECT_ROOT/run_prod.sh"

    # Create the systemd service file
    cat <<EOF > "$SERVICE_PATH"
[Unit]
Description=Nano Banana Studio (AI Teaching Platform)
After=network.target

[Service]
Type=simple
User=$TARGET_USER
WorkingDirectory=$PROJECT_ROOT
# Use bash -lc to load the user's profile/bashrc (important for nvm/node/python paths)
# We use --no-build to skip frontend compilation on startup for speed and stability
ExecStart=/bin/bash -lc 'exec $PROJECT_ROOT/run_prod.sh --no-build'
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    echo "📄 Created Service: $SERVICE_PATH"
    
    # Reload systemd, enable and start the service
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    systemctl restart "$SERVICE_NAME"
    
    echo "✅ Auto-start enabled! Service '$SERVICE_NAME' has been configured and started."
    echo "   Check status: systemctl status $SERVICE_NAME"
    echo "   View logs:    journalctl -u $SERVICE_NAME -f"
}

# Check for --install-startup argument
if [ "$1" == "--install-startup" ]; then
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        setup_linux_autostart
    else
        echo "⚠️  It looks like you are not on Linux ($OSTYPE)."
        echo "   Do you still want to proceed with Linux systemd setup? (y/n)"
        read -r response
        if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            setup_linux_autostart
        else
            echo "❌ Setup cancelled."
        fi
    fi
    exit 0
fi

echo "🍌 Building ReOpenInnoLab-教学绘画 for Production..."

# 1. 构建前端
if [ "$SKIP_BUILD" != "true" ]; then
    echo "🏗️  Building Frontend..."
    cd frontend
    npm install
    npm run build
    if [ $? -ne 0 ]; then
        echo "❌ Frontend build failed!"
        exit 1
    fi
    cd ..
else
    echo "⏩ Skipping Frontend build (--no-build)..."
fi

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

# Detect IP Address
LOCAL_IP=""

# Method 1: ip route (Best for Linux - gets the IP used for internet traffic)
if [ -z "$LOCAL_IP" ] && command -v ip >/dev/null 2>&1; then
    LOCAL_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i=="src") print $(i+1)}')
fi

# Method 2: hostname -I (Linux) - takes the first one
if [ -z "$LOCAL_IP" ] && command -v hostname >/dev/null 2>&1; then
    LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
fi

# Method 3: ifconfig (macOS / older Linux)
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -n 1)
fi

echo "👉 Network: http://${LOCAL_IP}:6060"

# 使用生产级配置启动
uvicorn main:app --host 0.0.0.0 --port 6060
