# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands
- Start server: `uvicorn server:app --reload` or `./service.sh start`
- Stop server: `./service.sh stop`
- Check server status: `./service.sh status`
- Generate documentation: `./generate_docs.sh generate`
- Serve documentation: `./generate_docs.sh serve`

## Style Guidelines
- Language: Python 3.8+
- Imports: Group standard library, third-party, then local imports
- Naming: snake_case for variables/functions, PascalCase for classes
- Error handling: Use custom exception classes (DatabaseError, ConnectionError, QueryError)
- Documentation: Use docstrings for all functions and classes
- Type hints: Use Python's typing module for parameter and return types
- Config: Use YAML for configuration
- Database: Use pyodbc with proper connection cleanup
- Exception handling: Catch specific exceptions, avoid bare except
- Logging: Use print statements with clear prefixes for now