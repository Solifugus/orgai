# AI Assistant for Organizational Data

## Overview

This AI Assistant is designed to provide intelligent responses to organizational queries by leveraging multiple data sources and maintaining context-aware conversations. The system integrates policy documents, organizational data, and technical documentation to provide comprehensive answers to user questions.

## Deployment Environments

The system is designed for flexible deployment:

1. **Enterprise Environment**
   - Linux server within organization network
   - Direct connection to SQL Server database
   - Full access to policy documents and organizational data
   - Can be deployed with Conda or other environment managers

2. **Development/Testing Environments**
   - Compatible with various Linux distributions
   - Python virtual environment (venv) support
   - Mock data capabilities when database isn't available
   - Local caching of policy documents

## Data Sources

### 1. Policy Documents
- Source: Policy repository API (JSON format)
- Content: Organizational policies, procedures, and guidelines
- Update Frequency: As needed via API refresh

### 2. Organizational Data
- Source: SQL Server Databases
- Content: 
  - Database schemas
  - Table structures
  - View definitions
  - Data derivation logic
  - Field relationships
- Access: Read-only access to specific databases
- Future Enhancement: Direct query execution capability

### 3. Additional Documentation
- Location: `indexables/` directory
- Content: 
  - Technical documentation
  - Process documentation
  - System documentation
  - Other organizational documents

## System Architecture

### 1. API Layer
- Framework: FastAPI
- Single Endpoint:
  - `/chat`: Main conversation endpoint
    - Accepts user prompts
    - Processes requests sequentially
    - Returns responses in order
    - Handles all types of queries (policies, data, documentation)

### 2. Processing Layer
- LLM Integration: Ollama with qwen2.5-coder:latest model
- Features:
  - Sequential request processing
  - Single GPU resource utilization
  - Simple response queue
  - Basic user session management
- Processing Flow:
  1. Request received and added to processing queue
  2. Previous request completion awaited
  3. Context maintained between sequential requests
  4. Response returned to user
  5. Next request processed
- Query Types:
  1. Policy Queries
     - Search policy documents
     - Extract relevant sections
     - Format response with citations
  2. Database Schema Queries
     - Access schema information
     - Explain relationships
     - Describe data derivations
  3. Documentation Queries
     - Search indexed documents
     - Extract relevant information
     - Provide context and references

### 3. Data Integration Layer
- Policy Document Integration
  - JSON parsing and indexing
  - Policy content extraction
  - Search functionality
- Database Integration
  - Schema analysis
  - Metadata extraction
  - Relationship mapping
- Document Processing
  - Text extraction
  - Content indexing
  - Search optimization

## Features

### 1. Policy Understanding
- Answer questions about organizational policies
- Explain policy requirements and implications
- Provide policy references and citations
- Track policy updates and changes

### 2. Data Knowledge
- Explain database structures and relationships
- Describe data field derivations
- Identify relevant tables and views
- Future: Execute and explain queries

### 3. Documentation Access
- Answer questions about technical documentation
- Explain processes and procedures
- Provide context from multiple documents
- Cross-reference related information

### 4. Conversation Management
- Maintain context across interactions
- Support multi-turn conversations
- Process requests sequentially
- Handle large document processing

## Security Considerations

1. Data Access
   - Read-only database access
   - No direct query execution (future feature)
   - Policy document access controls

2. API Security
   - CORS configuration
   - Input validation
   - Rate limiting
   - Error handling

## Future Enhancements

1. Query Execution
   - Safe query execution framework
   - Result formatting and explanation
   - Query validation and security

2. Enhanced Document Processing
   - Advanced text analysis
   - Document relationship mapping
   - Automated document updates

3. Improved Context Management
   - Long-term context storage
   - Context summarization
   - Multi-document context integration

## Technical Implementation

### Environment Management
- Automatic detection of Python environment (Conda/venv)
- Adapts paths and commands based on environment type
- Environment-agnostic service management script

### Database Integration
- Uses pyodbc for SQL Server connectivity
- Graceful fallback to mock data when database unavailable
- Schema caching to reduce database load
- Exclusion of system schemas to focus on relevant objects

### Documentation Generation
- HTML-based documentation for database objects
- Cross-linked resources for navigation
- Search functionality for quick reference
- Automatic updates with schema changes

## Development Guidelines

1. Code Organization
   - Modular architecture
   - Clear separation of concerns
   - Comprehensive documentation

2. Testing Requirements
   - Unit tests for core functionality
   - Integration tests for API endpoints
   - Security testing
   - Performance testing

3. Deployment
   - Containerization support
   - Environment configuration
   - Monitoring and logging
   - Health checks