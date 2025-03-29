#!/bin/bash

# Database documentation generator
# Usage: ./generate_docs.sh {generate|serve|clean}

# Configuration
DOC_DIR="public/docs"
PYTHON_PATH=$(which python3)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to generate documentation
generate_docs() {
    echo -e "${YELLOW}Generating database documentation...${NC}"
    
    # Create documentation directory
    mkdir -p "$DOC_DIR"
    
    # Generate documentation using Python script
    $PYTHON_PATH -m doc_generator
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Documentation generated successfully${NC}"
        echo -e "${YELLOW}Documentation location: ${DOC_DIR}${NC}"
    else
        echo -e "${RED}Failed to generate documentation${NC}"
        exit 1
    fi
}

# Function to serve documentation
serve_docs() {
    echo -e "${YELLOW}Starting documentation server...${NC}"
    echo -e "${YELLOW}Documentation available at: http://localhost:8001${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
    
    # Start Python's built-in HTTP server
    cd "$DOC_DIR" && $PYTHON_PATH -m http.server 8001
}

# Function to clean documentation
clean_docs() {
    echo -e "${YELLOW}Cleaning documentation...${NC}"
    rm -rf "$DOC_DIR"
    echo -e "${GREEN}Documentation cleaned successfully${NC}"
}

# Main script logic
case "$1" in
    generate)
        generate_docs
        ;;
    serve)
        serve_docs
        ;;
    clean)
        clean_docs
        ;;
    *)
        echo "Usage: $0 {generate|serve|clean}"
        exit 1
        ;;
esac

exit 0 