from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
from typing import List, Dict, Optional, Tuple
import os
from data_manager import DataManager
import asyncio
import traceback
import json
import gzip
from base64 import b64encode
import time

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CORS_ALLOWED_ORIGINS", "https://frontendurl")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Data Models
class UserPrompt(BaseModel):
    user: str
    prompt: str

class Response(BaseModel):
    queue: int
    response: str
    is_complete: bool

class QueueResponse(BaseModel):
    queue: int
    responses: List[Response]

class ChatRequest(BaseModel):
    user: str
    prompt: str

class ChatResponse(BaseModel):
    response: str
    context: str
    compressed: bool = False
    encoding: str = "utf-8"

# Initialize data manager
data_manager = None

# In-memory storage for user contexts and queue counters
user_contexts: Dict[str, List[int]] = {}
queue_counters: Dict[str, int] = {}
conversation_history: Dict[str, List[Dict[str, str]]] = {}  # Store conversation history per user
MAX_HISTORY_LENGTH = 10  # Maximum number of messages to keep in history
RECENT_MESSAGES = 3  # Number of recent messages to include verbatim
MAX_SUMMARY_LENGTH = 500  # Maximum length of conversation summary

# Ollama API configuration
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5-coder:latest"

async def initialize_data_manager():
    """Initialize the data manager asynchronously."""
    global data_manager
    data_manager = DataManager()
    await data_manager._initialize_data_sources()

def initialize_user(username: str):
    """Initialize user context if not exists."""
    if username not in user_contexts:
        user_contexts[username] = []
    if username not in queue_counters:
        queue_counters[username] = 0
    if username not in conversation_history:
        conversation_history[username] = []

def add_to_history(username: str, role: str, content: str):
    """Add a message to the user's conversation history."""
    if username not in conversation_history:
        conversation_history[username] = []
    
    conversation_history[username].append({
        "role": role,
        "content": content,
        "timestamp": time.time()  # Add timestamp for sorting
    })
    
    # Keep only the last MAX_HISTORY_LENGTH messages
    if len(conversation_history[username]) > MAX_HISTORY_LENGTH:
        conversation_history[username] = conversation_history[username][-MAX_HISTORY_LENGTH:]

def get_conversation_context(username: str) -> str:
    """Get a context-aware summary of the conversation history."""
    if username not in conversation_history or not conversation_history[username]:
        return ""
    
    messages = conversation_history[username]
    
    # Get recent messages (verbatim)
    recent_messages = messages[-RECENT_MESSAGES:]
    recent_context = "\n".join([
        f"{msg['role']}: {msg['content']}"
        for msg in recent_messages
    ])
    
    # If we have older messages, create a summary
    if len(messages) > RECENT_MESSAGES:
        older_messages = messages[:-RECENT_MESSAGES]
        summary = f"Earlier in the conversation, we discussed: {', '.join([msg['content'][:50] + '...' for msg in older_messages])}"
        return f"{summary}\n\nRecent messages:\n{recent_context}"
    
    return f"Recent messages:\n{recent_context}"

def clear_history(username: str):
    """Clear the conversation history for a user."""
    if username in conversation_history:
        conversation_history[username] = []

def get_queue_number(username: str) -> int:
    """Get the next queue number for a user."""
    if username not in queue_counters:
        queue_counters[username] = 0
    queue_counters[username] += 1
    return queue_counters[username]

def classify_query_type(prompt: str) -> str:
    """
    Classify the query type to determine which data source to prioritize.
    Uses weighted keyword matching and prioritization rules.
    
    Returns:
        str: One of "policy", "database", "data", "documentation", or "general"
    """
    prompt_lower = prompt.lower()
    
    # Policy-related keywords with weights
    policy_keywords = {
        # High priority keywords (weight 3)
        "policy": 3, "policies": 3, "handbook": 3, "guideline": 3, "hr policy": 3,
        "vacation policy": 3, "leave policy": 3, "sick leave": 3,
        # Medium priority keywords (weight 2)
        "procedure": 2, "regulation": 2, "compliance": 2, "protocol": 2, 
        "standard": 2, "vacation": 2, "time off": 2, "leave": 2, "benefit": 2,
        # Lower priority keywords (weight 1)
        "hr": 1, "human resources": 1, "holiday": 1, "rule": 1
    }
    
    # Database-related keywords with weights (schema/structure questions)
    database_keywords = {
        # High priority keywords (weight 3)
        "database schema": 3, "table structure": 3, "database design": 3, "schema": 3,
        "stored procedure": 3, "database view": 3, "sql": 3, "primary key": 3,
        # Medium priority keywords (weight 2)
        "table": 2, "column": 2, "field": 2, "foreign key": 2, "entity": 2,
        "relationship": 2, "data model": 2, "data structure": 2, "etl": 2,
        # Lower priority keywords (weight 1)
        "database": 1, "report": 1, "query": 1, "view": 1
    }
    
    # Data-related keywords (for SQL query execution/data retrieval)
    data_keywords = {
        # High priority keywords (weight 3)
        "show me data": 3, "get data": 3, "retrieve data": 3, "run query": 3, "execute query": 3,
        "select from": 3, "query data": 3, "data from": 3, "show records": 3, "find records": 3,
        # Medium priority keywords (weight 2)
        "how many": 2, "count of": 2, "list all": 2, "search for": 2, "find all": 2, 
        "look up": 2, "recent entries": 2, "last updated": 2, "fetch": 2,
        # Lower priority keywords (weight 1)
        "records": 1, "entries": 1, "rows": 1, "data": 1, "information": 1
    }
    
    # Documentation-related keywords with weights
    documentation_keywords = {
        # High priority keywords (weight 3)
        "documentation": 3, "user guide": 3, "reference manual": 3, "technical guide": 3,
        "process document": 3, "system documentation": 3, 
        # Medium priority keywords (weight 2)
        "guide": 2, "manual": 2, "instruction": 2, "process": 2, "workflow": 2,
        "how to": 2, "steps": 2, "tutorial": 2,
        # Lower priority keywords (weight 1)
        "document": 1, "reference": 1, "help": 1
    }
    
    # Calculate weighted scores using partial matching
    policy_score = 0
    database_score = 0
    data_score = 0
    documentation_score = 0
    
    # Check for policy keywords
    for keyword, weight in policy_keywords.items():
        if keyword in prompt_lower:
            policy_score += weight
    
    # Check for database keywords
    for keyword, weight in database_keywords.items():
        if keyword in prompt_lower:
            database_score += weight
    
    # Check for data query keywords
    for keyword, weight in data_keywords.items():
        if keyword in prompt_lower:
            data_score += weight
    
    # Check for documentation keywords
    for keyword, weight in documentation_keywords.items():
        if keyword in prompt_lower:
            documentation_score += weight
    
    # Common SQL query patterns that strongly indicate a data query
    sql_patterns = [
        r"select.*from", r"count.*from", r"sum.*from", r"avg.*from", 
        r"where.*=", r"group by", r"order by", r"having", r"join"
    ]
    
    # Check for SQL patterns that strongly indicate a data query
    for pattern in sql_patterns:
        if re.search(pattern, prompt_lower):
            data_score += 4  # Very high weight for SQL-like syntax
    
    # Natural language indicators of data queries
    nl_patterns = [
        r"show me all", r"list the", r"display all", r"how many .* are there",
        r"what is the count of", r"what are the", r"who has the", r"which .* have"
    ]
    
    # Check for natural language patterns that indicate a data query
    for pattern in nl_patterns:
        if re.search(pattern, prompt_lower):
            data_score += 2  # Medium weight for natural language data requests
    
    print(f"Query scores - Policy: {policy_score}, Database: {database_score}, Data: {data_score}, Documentation: {documentation_score}")
    
    # Apply threshold and prioritization rules
    threshold = 2  # Minimum score required to classify as a specific type
    
    # Determine the query type based on the highest score above threshold
    all_scores = [policy_score, database_score, data_score, documentation_score]
    max_score = max(all_scores)
    
    # If no category meets the threshold, it's a general query
    if max_score < threshold:
        return "general"
    
    # Data queries take precedence if they have a substantial score
    if data_score >= 4 or (data_score == max_score and data_score >= threshold):
        return "data"
    
    # Handle tie-breaking with priority rules for other categories
    if policy_score == database_score and policy_score == max_score:
        # If tied between policy and database, prefer policy
        return "policy"
    
    if policy_score == documentation_score and policy_score == max_score:
        # If tied between policy and documentation, prefer policy
        return "policy"
    
    if database_score == documentation_score and database_score == max_score:
        # If tied between database and documentation, prefer database
        return "database"
    
    # Return the type with the highest score
    if policy_score == max_score:
        return "policy"
    elif database_score == max_score:
        return "database"
    elif data_score == max_score:
        return "data"
    else:
        return "documentation"

async def process_prompt(prompt: str, context: str = "", username: str = "") -> Tuple[str, str]:
    """Process a prompt and return the response and updated context."""
    try:
        print("Processing prompt...")
        
        # Classify the query type
        query_type = classify_query_type(prompt)
        print(f"Query classified as: {query_type}")
        
        # Get appropriate context based on query type
        print(f"Getting context for {query_type} query...")
        
        # Flag to indicate if we're returning SQL results directly
        is_direct_sql_response = False
        sql_response = ""
        
        if query_type == "policy":
            policy_results = data_manager.search_policy_documents(prompt)
            context_data = ""
            if policy_results:
                context_parts = ["Relevant Policy Documents:"]
                for result in policy_results[:3]:  # Limit to top 3 most relevant
                    context_parts.append(f"- {result['name']}")
                    context_parts.append(f"  Category: {result['category']}")
                    context_parts.append(f"  Author: {result['author']}")
                    context_parts.append(f"  Applicability: {result['applicability_group']}")
                    context_parts.append(f"  Preview: {result['preview']}")
                    if result.get('urls', {}).get('direct'):
                        context_parts.append(f"  URL: {result['urls']['direct']}")
                context_data = "\n".join(context_parts)
        elif query_type == "database":
            db_results = data_manager.get_relevant_database_info(prompt)
            context_data = ""
            if db_results:
                context_parts = ["Relevant Database Information:"]
                for result in db_results[:5]:  # Limit to top 5 most relevant
                    if result['type'] == 'table':
                        context_parts.append(f"- Database: {result['database']}")
                        context_parts.append(f"  Table: {result['schema']}.{result['name']}")
                        context_parts.append("  Columns:")
                        for col in result['columns']:
                            desc = f" ({col['description']})" if col.get('description') else ""
                            context_parts.append(f"    - {col['name']}: {col['type']}{desc}")
                    elif result['type'] == 'view':
                        context_parts.append(f"- Database: {result['database']}")
                        context_parts.append(f"  View: {result['schema']}.{result['name']}")
                        context_parts.append("  Columns:")
                        for col in result['columns']:
                            desc = f" ({col['description']})" if col.get('description') else ""
                            context_parts.append(f"    - {col['name']}: {col['type']}{desc}")
                    elif result['type'] == 'stored_procedure':
                        context_parts.append(f"- Database: {result['database']}")
                        context_parts.append(f"  Stored Procedure: {result['schema']}.{result['name']}")
                        if result.get('comment'):
                            context_parts.append(f"  Description: {result['comment']}")
                        context_parts.append(f"  Definition: {result['definition'][:200]}...")
                context_data = "\n".join(context_parts)
        elif query_type == "data":
            # Handle data query - attempt to generate and run SQL
            try:
                # Check if the feature is enabled in configuration
                if not data_manager.config.get('sql_server', {}).get('allow_data_queries', False):
                    context_data = """Data queries are disabled in the system configuration. 
Please contact your administrator if you need this feature enabled."""
                else:
                    # First, see if user directly provided a SQL query
                    sql_query = None
                    
                    # Try to extract SQL query from the prompt
                    sql_pattern = r"```sql\s*(.*?)\s*```"
                    sql_matches = re.findall(sql_pattern, prompt, re.DOTALL)
                    
                    if sql_matches:
                        # User provided SQL in code block
                        sql_query = sql_matches[0].strip()
                    else:
                        # Check for obvious SQL statements
                        if "SELECT " in prompt.upper() and " FROM " in prompt.upper():
                            # Extract the entire line containing SELECT ... FROM
                            lines = prompt.split('\n')
                            for line in lines:
                                if "SELECT " in line.upper() and " FROM " in line.upper():
                                    sql_query = line.strip()
                                    break
                    
                    # If no direct SQL found, proceed with normal processing
                    if sql_query:
                        # User provided a SQL query directly - execute it
                        print(f"Executing user-provided SQL query: {sql_query}")
                        
                        try:
                            # Execute the SQL query
                            results, table_string = data_manager.execute_sql_query(sql_query)
                            
                            # Create response with query results
                            sql_response = f"""I executed your SQL query:
```sql
{sql_query}
```

Here are the results:

{table_string}
"""
                            # Set flag to return SQL results directly
                            is_direct_sql_response = True
                            context_data = ""
                        except PermissionError as e:
                            context_data = f"SQL Query Error: {str(e)}\n\nPlease modify your query to comply with the system's security restrictions."
                        except Exception as e:
                            context_data = f"Error executing SQL query: {str(e)}"
                    else:
                        # No direct SQL provided, gather context for the AI to generate a query
                        db_results = data_manager.get_relevant_database_info(prompt)
                        
                        if db_results:
                            context_parts = ["To answer this data query, I need database information:"]
                            # Include relevant tables and columns for SQL generation
                            for result in db_results[:5]:
                                if result['type'] == 'table':
                                    context_parts.append(f"- Database: {result['database']}")
                                    context_parts.append(f"  Table: {result['schema']}.{result['name']}")
                                    context_parts.append("  Columns:")
                                    for col in result['columns']:
                                        desc = f" ({col['description']})" if col.get('description') else ""
                                        context_parts.append(f"    - {col['name']}: {col['type']}{desc}")
                            
                            # Add instruction for the AI to generate SQL
                            context_parts.append("\nBased on the user query, generate a SQL SELECT statement to retrieve the requested data. Use only the tables and columns listed above.")
                            context_parts.append("The SQL should be simple, secure, and limited to retrieving data only (SELECT statements only).")
                            context_parts.append("Ensure the query complies with these security restrictions:")
                            context_parts.append("- Only use SELECT statements")
                            context_parts.append("- Do not use DROP, DELETE, INSERT, UPDATE, ALTER, or CREATE commands")
                            context_parts.append("- Do not use comments (--) or statement terminators (;)")
                            context_parts.append("- Limit results with TOP or LIMIT clause")
                            
                            context_data = "\n".join(context_parts)
                        else:
                            context_data = "I couldn't find relevant database tables for your query. Please provide more specific information about the data you're looking for."
            except Exception as e:
                context_data = f"Error processing data query: {str(e)}"
                
        elif query_type == "documentation":
            doc_results = data_manager.search_documentation(prompt)
            context_data = ""
            if doc_results:
                context_parts = ["Relevant Documentation:"]
                for result in doc_results[:3]:  # Limit to top 3 most relevant
                    context_parts.append(f"- File: {result['file']}")
                    context_parts.append(f"  Context: {result['context']}")
                context_data = "\n".join(context_parts)
        else:
            # General query - don't use specific context
            context_data = ""
        
        print(f"Context retrieved: {context_data[:100]}...")
        
        # If we have a direct SQL response, return it without going to the LLM
        if is_direct_sql_response:
            print("Returning direct SQL response")
            # Add assistant's response to history
            if username:
                add_to_history(username, "assistant", sql_response)
            return sql_response, context_data
        
        # Add user's prompt to history
        if username:
            add_to_history(username, "user", prompt)
        
        # Get conversation context
        conversation_context = get_conversation_context(username) if username else ""
        
        # Prepare special instruction for data queries that need SQL generation
        sql_instruction = ""
        if query_type == "data" and data_manager.config.get('sql_server', {}).get('allow_data_queries', False):
            sql_instruction = """
If this is a request for data and you need to execute a SQL query:
1. Generate a valid SQL SELECT statement based on the user's request and the database context
2. Format the SQL as a code block with ```sql and ```
3. Explain what the query will do
"""
        
        # Prepare the prompt with context and conversation history
        full_prompt = f"""Previous conversation context:
{conversation_context}

{context_data}

{sql_instruction}

User: {prompt}

A: Let me help you with that."""
        
        # Send request to Ollama
        print("Sending request to Ollama...")
        async with httpx.AsyncClient(timeout=300.0) as client:
            data = {
                "model": MODEL,
                "prompt": full_prompt,
                "stream": False,
                "raw": True,
                "num_ctx": 8192,
                "num_thread": 4,
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 8192
            }
            try:
                response = await client.post(OLLAMA_URL.replace("/chat", "/generate"), json=data)
                if response.status_code != 200:
                    raise HTTPException(status_code=500, detail=f"Ollama API error: {response.text}")
                
                result = response.json()
                response_text = result.get("response", "")
                
                # For data queries, check if the model generated SQL that needs to be executed
                if query_type == "data" and data_manager.config.get('sql_server', {}).get('allow_data_queries', False):
                    # Try to extract SQL query from the response
                    sql_pattern = r"```sql\s*(.*?)\s*```"
                    sql_matches = re.findall(sql_pattern, response_text, re.DOTALL)
                    
                    if sql_matches:
                        # Model generated SQL - try to execute it
                        sql_query = sql_matches[0].strip()
                        print(f"Executing AI-generated SQL query: {sql_query}")
                        
                        try:
                            # Execute the SQL query
                            results, table_string = data_manager.execute_sql_query(sql_query)
                            
                            # Replace the SQL code block with results
                            response_with_results = response_text.replace(
                                f"```sql\n{sql_query}\n```", 
                                f"```sql\n{sql_query}\n```\n\nHere are the results:\n\n{table_string}"
                            )
                            
                            # Use the enhanced response
                            response_text = response_with_results
                        except Exception as e:
                            # Append error message but don't replace the original response
                            response_text += f"\n\nI couldn't execute the SQL query: {str(e)}"
                
                # Add assistant's response to history
                if username:
                    add_to_history(username, "assistant", response_text)
                
                # Log response length
                print(f"Response length: {len(response_text)} characters")
                
                # Validate response
                if not response_text:
                    raise HTTPException(status_code=500, detail="Empty response from Ollama")
                if len(response_text) < 10:
                    raise HTTPException(status_code=500, detail="Response too short")
                    
                print("Prompt processed successfully")
                return response_text, context_data
            except httpx.TimeoutException as e:
                print(f"Timeout while communicating with Ollama: {str(e)}")
                raise HTTPException(status_code=504, detail="Request to Ollama timed out. Please try again.")
            except httpx.RequestError as e:
                print(f"Error communicating with Ollama: {str(e)}")
                raise HTTPException(status_code=503, detail=f"Error communicating with Ollama: {str(e)}")
    except Exception as e:
        print(f"Error in process_prompt: \nTraceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """Handle chat requests."""
    try:
        if data_manager is None:
            print("Initializing data manager...")
            await initialize_data_manager()
            print("Data manager initialized")
            
        # Initialize user context if needed
        initialize_user(request.user)
            
        print(f"Processing request for user {request.user} with prompt: {request.prompt}")
        response_text, new_context = await process_prompt(request.prompt, username=request.user)
        
        # Ensure the response is complete
        if not response_text or len(response_text) < 10:  # Basic validation
            raise HTTPException(status_code=500, detail="Incomplete response from model")
        
        # If response is large, compress it
        if len(response_text) > 1000:
            compressed = gzip.compress(response_text.encode('utf-8'))
            response_text = b64encode(compressed).decode('utf-8')
            return ChatResponse(
                response=response_text,
                context=new_context,
                compressed=True,
                encoding="gzip+base64"
            )
            
        return ChatResponse(
            response=response_text,
            context=new_context
        )
    except HTTPException as e:
        print(f"HTTP error in chat_endpoint: {e.detail}")
        raise e
    except Exception as e:
        print(f"Error in chat_endpoint: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {str(e)}"
        )

@app.post("/chat/clear")
async def clear_chat_history(request: ChatRequest):
    """Clear the conversation history for a user."""
    try:
        clear_history(request.user)
        return {"status": "success", "message": "Conversation history cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing history: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """Initialize data manager on startup."""
    await initialize_data_manager()

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    if data_manager:
        data_manager.close()

if __name__ == "__main__":
    import uvicorn
    print("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
