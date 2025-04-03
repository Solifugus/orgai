#!/bin/bash

# Service management script for AI Assistant
# Usage: ./service.sh {start|stop|restart|status|install}

# Configuration
APP_NAME="ai-assistant"
APP_DIR="$(pwd)"
LOG_FILE="/tmp/${APP_NAME}.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to detect Python environment
detect_python_env() {
    # Check if we're in a Conda environment
    if [ -n "$CONDA_DEFAULT_ENV" ]; then
        echo "conda"
        return 0
    fi
    
    # Check if we're in a venv
    if [ -n "$VIRTUAL_ENV" ]; then
        echo "venv"
        return 0
    fi
    
    # Check if we're in the base Conda environment
    if command -v conda &> /dev/null && [ "$(conda info --base)" = "$CONDA_PREFIX" ]; then
        echo "conda_base"
        return 0
    fi
    
    echo "system"
    return 0
}

# Function to check dependencies
check_dependencies() {
    echo "Checking dependencies..."
    
    PYTHON_ENV=$(detect_python_env)
    
    case $PYTHON_ENV in
        "conda"|"conda_base")
            # Check if uvicorn is installed in the Conda environment
            if ! conda run -n $CONDA_DEFAULT_ENV python -c "import uvicorn" &> /dev/null; then
                echo "ERROR: uvicorn is not installed in the Conda environment"
                echo "Please install it using: conda install -n $CONDA_DEFAULT_ENV uvicorn"
                return 1
            fi
            ;;
        "venv")
            # Check if uvicorn is installed in the venv
            if ! "$VIRTUAL_ENV/bin/python" -c "import uvicorn" &> /dev/null; then
                echo "ERROR: uvicorn is not installed in the virtual environment"
                echo "Please install it using: pip install uvicorn"
                return 1
            fi
            ;;
        "system")
            # Check if uvicorn is installed system-wide
            if ! python3 -c "import uvicorn" &> /dev/null; then
                echo "ERROR: uvicorn is not installed"
                echo "Please install it using: pip3 install uvicorn"
                return 1
            fi
            ;;
    esac
    
    return 0
}

# Function to start the application
start() {
    echo "Starting ${APP_NAME}..."
    
    if ! check_dependencies; then
        echo "Failed to start ${APP_NAME}"
        return 1
    fi
    
    PYTHON_ENV=$(detect_python_env)
    
    case $PYTHON_ENV in
        "conda"|"conda_base")
            # Start using Conda
            nohup conda run -n $CONDA_DEFAULT_ENV uvicorn server:app --host 0.0.0.0 --port 8000 --reload > "${LOG_FILE}" 2>&1 &
            ;;
        "venv")
            # Start using venv
            nohup "$VIRTUAL_ENV/bin/uvicorn" server:app --host 0.0.0.0 --port 8000 --reload > "${LOG_FILE}" 2>&1 &
            ;;
        "system")
            # Start using system Python
            nohup python3 -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload > "${LOG_FILE}" 2>&1 &
            ;;
    esac
    
    if [ $? -eq 0 ]; then
        echo "${APP_NAME} started successfully"
        echo "Logs available at: ${LOG_FILE}"
    else
        echo "Failed to start ${APP_NAME}"
        echo "Check logs at: ${LOG_FILE}"
    fi
}

# Function to stop the application
stop() {
    echo "Stopping ${APP_NAME}..."
    pkill -f "uvicorn server:app"
    echo "${APP_NAME} stopped"
}

# Function to check status
status() {
    if pgrep -f "uvicorn server:app" > /dev/null; then
        echo "${APP_NAME} is running"
    else
        echo "${APP_NAME} is not running"
    fi
}

# Function to install as systemd service
install_service() {
    echo -e "${YELLOW}Installing ${APP_NAME} as systemd service...${NC}"
    
    # Create systemd service file
    sudo tee "/etc/systemd/system/${APP_NAME}.service" > /dev/null << EOL
[Unit]
Description=AI Assistant Service
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=/bin/bash -c 'source $(pwd)/service.sh start'
ExecStop=/bin/bash -c 'source $(pwd)/service.sh stop'
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOL
    
    # Reload systemd and enable service
    sudo systemctl daemon-reload
    sudo systemctl enable "${APP_NAME}"
    echo -e "${GREEN}Service installed successfully${NC}"
    echo -e "${YELLOW}You can now use:${NC}"
    echo -e "  sudo systemctl start ${APP_NAME}"
    echo -e "  sudo systemctl stop ${APP_NAME}"
    echo -e "  sudo systemctl status ${APP_NAME}"
}

# Main script
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 2
        start
        ;;
    status)
        status
        ;;
    install)
        install_service
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|install}"
        exit 1
        ;;
esac

exit 0 