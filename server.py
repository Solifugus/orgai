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

# Ollama API configuration
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5-coder:latest"

async def initialize_data_manager():
    """Initialize the data manager asynchronously."""
    global data_manager
    data_manager = DataManager()
    await data_manager._initialize_data_sources()

async def process_prompt(prompt: str, context: str = "") -> Tuple[str, str]:
    """Process a prompt and return the response and updated context."""
    try:
        print("Processing prompt...")
        
        # Get context from data sources
        print("Getting context from data sources...")
        context_data = data_manager.format_context_for_prompt(prompt)
        print(f"Context retrieved: {context_data[:100]}...")
        
        # Prepare the prompt with context
        full_prompt = f"""User: {prompt}

A: Let me help you with that."""
        
        # Send request to Ollama
        print("Sending request to Ollama...")
        async with httpx.AsyncClient(timeout=300.0) as client:
            data = {
                "model": MODEL,
                "prompt": full_prompt,  # Use simple prompt format
                "stream": False,  # Disable streaming for now
                "raw": True,  # Use raw format
                "num_ctx": 8192,  # Increase context window
                "num_thread": 4,
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 8192  # Increase max tokens
            }
            try:
                response = await client.post(OLLAMA_URL.replace("/chat", "/generate"), json=data)
                if response.status_code != 200:
                    raise HTTPException(status_code=500, detail=f"Ollama API error: {response.text}")
                
                result = response.json()
                response_text = result.get("response", "")
                
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

def initialize_user(username: str):
    """Initialize user context if not exists."""
    if username not in user_contexts:
        user_contexts[username] = []
    if username not in queue_counters:
        queue_counters[username] = 0

def get_queue_number(username: str) -> int:
    """Get the next queue number for a user."""
    if username not in queue_counters:
        queue_counters[username] = 0
    queue_counters[username] += 1
    return queue_counters[username]

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """Handle chat requests."""
    try:
        if data_manager is None:
            print("Initializing data manager...")
            await initialize_data_manager()
            print("Data manager initialized")
            
        print(f"Processing request for user {request.user} with prompt: {request.prompt}")
        response_text, new_context = await process_prompt(request.prompt)
        
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
