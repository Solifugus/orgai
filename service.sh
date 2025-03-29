#!/bin/bash

# Service management script for AI Assistant
# Usage: ./service.sh {start|stop|restart|status|install}

# Configuration
SERVICE_NAME="ai-assistant"
PID_FILE="/tmp/${SERVICE_NAME}.pid"
LOG_FILE="/tmp/${SERVICE_NAME}.log"
PYTHON_PATH=$(which python3)
UVICORN_PATH=$(which uvicorn)
OLLAMA_PATH=$(which ollama)

# Ubuntu-specific paths
SERVICE_DIR="/etc/systemd/system"
SERVICE_FILE="${SERVICE_DIR}/${SERVICE_NAME}.service"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check Ubuntu dependencies
check_dependencies() {
    echo -e "${YELLOW}Checking dependencies...${NC}"
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python 3 is not installed. Installing...${NC}"
        sudo apt-get update && sudo apt-get install -y python3 python3-pip
    fi
    
    # Check Ollama
    if ! command -v ollama &> /dev/null; then
        echo -e "${RED}Ollama is not installed. Installing...${NC}"
        curl -fsSL https://ollama.com/install.sh | sudo sh
    fi
    
    # Check required Python packages
    if ! pip3 list | grep -q "fastapi"; then
        echo -e "${RED}Installing required Python packages...${NC}"
        pip3 install -r requirements.txt
    fi
    
    # Check SQL Server driver
    if ! dpkg -l | grep -q "unixodbc-dev"; then
        echo -e "${RED}Installing SQL Server dependencies...${NC}"
        sudo apt-get install -y unixodbc-dev
    fi
}

# Function to check if a process is running
is_running() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Function to start the service
start_service() {
    echo -e "${YELLOW}Starting ${SERVICE_NAME}...${NC}"
    
    # Check dependencies first
    check_dependencies
    
    # Check if Ollama is running
    if ! pgrep -f "ollama" > /dev/null; then
        echo -e "${YELLOW}Starting Ollama...${NC}"
        $OLLAMA_PATH serve &
        sleep 2
        $OLLAMA_PATH run qwen2.5-coder &
        sleep 2
    fi
    
    # Start the FastAPI server
    nohup $PYTHON_PATH -m $UVICORN_PATH server:app --host 0.0.0.0 --port 8000 --reload > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    # Wait for the server to start
    sleep 3
    
    if is_running; then
        echo -e "${GREEN}${SERVICE_NAME} started successfully${NC}"
        echo -e "${YELLOW}Logs available at: ${LOG_FILE}${NC}"
    else
        echo -e "${RED}Failed to start ${SERVICE_NAME}${NC}"
        echo -e "${YELLOW}Check logs at: ${LOG_FILE}${NC}"
        exit 1
    fi
}

# Function to stop the service
stop_service() {
    echo -e "${YELLOW}Stopping ${SERVICE_NAME}...${NC}"
    
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            kill "$pid"
            rm "$PID_FILE"
            echo -e "${GREEN}${SERVICE_NAME} stopped successfully${NC}"
        else
            echo -e "${YELLOW}${SERVICE_NAME} is not running${NC}"
        fi
    else
        echo -e "${YELLOW}${SERVICE_NAME} is not running${NC}"
    fi
}

# Function to restart the service
restart_service() {
    echo -e "${YELLOW}Restarting ${SERVICE_NAME}...${NC}"
    stop_service
    sleep 2
    start_service
}

# Function to check service status
check_status() {
    if is_running; then
        echo -e "${GREEN}${SERVICE_NAME} is running${NC}"
        pid=$(cat "$PID_FILE")
        echo -e "${YELLOW}Process ID: ${pid}${NC}"
        echo -e "${YELLOW}Logs available at: ${LOG_FILE}${NC}"
        
        # Check system resources
        echo -e "\n${YELLOW}System Resources:${NC}"
        echo -e "Memory Usage:"
        free -h
        echo -e "\nDisk Usage:"
        df -h /
    else
        echo -e "${RED}${SERVICE_NAME} is not running${NC}"
    fi
}

# Function to install as systemd service
install_service() {
    echo -e "${YELLOW}Installing ${SERVICE_NAME} as systemd service...${NC}"
    
    # Create systemd service file
    sudo tee "$SERVICE_FILE" > /dev/null << EOL
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
    sudo systemctl enable "$SERVICE_NAME"
    echo -e "${GREEN}Service installed successfully${NC}"
    echo -e "${YELLOW}You can now use:${NC}"
    echo -e "  sudo systemctl start ${SERVICE_NAME}"
    echo -e "  sudo systemctl stop ${SERVICE_NAME}"
    echo -e "  sudo systemctl status ${SERVICE_NAME}"
}

# Main script logic
case "$1" in
    start)
        start_service
        ;;
    stop)
        stop_service
        ;;
    restart)
        restart_service
        ;;
    status)
        check_status
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