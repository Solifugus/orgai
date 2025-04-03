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

async def process_prompt(prompt: str, context: str = "", username: str = "") -> Tuple[str, str]:
    """Process a prompt and return the response and updated context."""
    try:
        print("Processing prompt...")
        
        # Get context from data sources
        print("Getting context from data sources...")
        context_data = data_manager.format_context_for_prompt(prompt)
        print(f"Context retrieved: {context_data[:100]}...")
        
        # Add user's prompt to history
        if username:
            add_to_history(username, "user", prompt)
        
        # Get conversation context
        conversation_context = get_conversation_context(username) if username else ""
        
        # Prepare the prompt with context and conversation history
        full_prompt = f"""Previous conversation context:
{conversation_context}

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
