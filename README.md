# AI Assistant for Organizational Data

This AI Assistant provides intelligent responses to organizational queries by leveraging multiple data sources including policy documents, database structures, and technical documentation.

## Prerequisites

- Python 3.8 or higher
- SQL Server with appropriate databases and permissions
- Ollama installed and running with the qwen2.5-coder model

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure the system:
   - Update `config.yaml` with your SQL Server connection details
   - Ensure policy documents are available in `policies.json`
   - Place documentation files in the `indexables/` directory

3. Start Ollama with the required model:
```bash
ollama run qwen2.5-coder
```

## Running the Server

### Using the Service Script

The service can be managed using the `service.sh` script:

```bash
# Start the service
./service.sh start

# Stop the service
./service.sh stop

# Restart the service
./service.sh restart

# Check service status
./service.sh status
```

The script will:
- Manage both the Ollama service and the FastAPI server
- Store logs in `/tmp/ai-assistant.log`
- Handle process management and cleanup
- Provide colored output for better visibility

### Manual Start

Alternatively, you can start the server manually:
```bash
uvicorn server:app --reload
```

The server will be available at `http://localhost:8000`

## Database Documentation

The system includes a comprehensive database documentation generator that creates interlinked HTML pages for all database objects.

### Generating Documentation

To generate the documentation:

```bash
# Generate documentation
./generate_docs.sh generate

# Serve the documentation
./generate_docs.sh serve

# Clean generated documentation
./generate_docs.sh clean
```

The documentation will be available at `http://localhost:8001` when served.

Features:
- Complete database schema documentation
- Table structures with column details
- View definitions
- Stored procedure definitions
- Cross-referenced documentation
- Modern, responsive design
- Searchable content
- Easy navigation between objects

The documentation includes:
1. Main index page with all databases
2. Database-specific pages with:
   - Tables
   - Views
   - Stored Procedures
3. Detailed pages for each object with:
   - Full definitions
   - Column information
   - Descriptions
   - Relationships

## Testing the System

You can test the system using curl or any HTTP client:

```bash
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{"prompt": "What is our vacation policy?"}'
```

Example questions to test:
1. Policy questions:
   - "What is our vacation policy?"
   - "Who wrote the employee handbook?"
   - "What policies apply to managers?"

2. Database questions:
   - "What tables are in the CoreDB database?"
   - "What is the structure of the Employee table?"
   - "What stored procedures are related to payroll?"

3. Documentation questions:
   - "How do I submit an expense report?"
   - "What is the process for requesting time off?"

## API Documentation

Once the server is running, you can access the API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Troubleshooting

1. Database Connection Issues:
   - Verify SQL Server is running
   - Check connection string in config.yaml
   - Ensure proper permissions are set

2. Policy Document Issues:
   - Verify policies.json exists and is valid JSON
   - Check file permissions

3. Documentation Issues:
   - Ensure files are in the indexables/ directory
   - Check file permissions

4. Ollama Issues:
   - Verify Ollama is running
   - Check if qwen2.5-coder model is installed

5. Service Management Issues:
   - Check logs at `/tmp/ai-assistant.log`
   - Verify process status with `./service.sh status`
   - Ensure proper permissions on service.sh

6. Documentation Generation Issues:
   - Check database connectivity
   - Verify SQL Server permissions
   - Check generated files in public/docs/
   - Review error messages in console output

# OrgAI Setup Instructions

## Local Development (Linux)

### 1. Virtual Environment Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. SQL Server Integration
The application supports both real SQL Server connections and mock data fallback:

#### With SQL Server (Work Environment)
```bash
# Add Microsoft repository
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list

# Update and install
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

#### Without SQL Server (Local Development)
The application will automatically use mock data when the ODBC driver is not available.

### 3. Configuration
Update `config.yaml` with appropriate settings:

```yaml
sql_server:
  enabled: true
  # For work environment
  connection_string: "DRIVER={ODBC Driver 18 for SQL Server};SERVER=your_work_server;DATABASE=CoreDB;UID=your_username;PWD=your_password"
  # For local development (mock data)
  # connection_string: "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;UID=test;PWD=test"
```

### 4. Running the Application
```bash
# Start the server
uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# If port is in use, kill existing process first
pkill -f "uvicorn server:app"
```

## Features

### SQL Server Integration
- Automatically detects SQL Server ODBC driver availability
- Falls back to mock data when driver is not available
- Supports multiple databases (CoreDB, ReportingDB, AnalyticsDB)
- Caches database schema for improved performance

### Policy Documents
- Fetches policy documents from remote URL
- Caches documents locally
- Updates daily or as configured

### Local Documentation
- Supports local documentation integration
- Configurable through config.yaml

## Troubleshooting

### Port Already in Use
If you see the error `[Errno 98] Address already in use`:
```bash
# Kill existing server process
pkill -f "uvicorn server:app"
```

### SQL Server Connection Issues
- Verify ODBC driver installation
- Check connection string in config.yaml
- Ensure database server is accessible
- Application will fall back to mock data if connection fails

### Policy Documents
- Check internet connectivity for remote URL access
- Verify local cache directory permissions
- Monitor update frequency in config.yaml 