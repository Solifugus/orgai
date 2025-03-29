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