from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from typing import List, Dict, Optional
import os
from data_manager import DataManager

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

# Initialize data manager
data_manager = DataManager()

# In-memory storage for user contexts and queue counters
user_contexts: Dict[str, List[int]] = {}
queue_counters: Dict[str, int] = {}

# Ollama API configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:latest"

async def process_prompt(prompt: str, context: Optional[List[int]] = None) -> tuple[str, List[int]]:
    """Process a single prompt through Ollama with optional context."""
    # Get relevant context from data sources
    data_context = data_manager.format_context_for_prompt(prompt)
    
    # Combine user prompt with data context
    full_prompt = f"""Context from available data sources:
{data_context}

User question: {prompt}

Please provide a comprehensive answer based on the available information."""

    data = {
        "model": MODEL,
        "prompt": full_prompt,
        "stream": False,
        "raw": False
    }
    if context is not None:
        data["context"] = context

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(OLLAMA_URL, json=data)
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Ollama API error: {response.text}")
            
            response_data = response.json()
            return response_data.get("response", "").strip(), response_data.get("context", [])
    except Exception as e:
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

@app.post("/chat", response_model=QueueResponse)
async def chat_endpoint(user_prompt: UserPrompt):
    """Main chat endpoint that processes requests sequentially while maintaining frontend compatibility."""
    username = user_prompt.user
    prompt = user_prompt.prompt
    queue_num = get_queue_number(username)
    
    # Initialize user context if needed
    initialize_user(username)
    
    try:
        # Get existing context for user
        context = user_contexts.get(username)
        
        # Process the prompt
        response_text, new_context = await process_prompt(prompt, context)
        
        # Update user context
        user_contexts[username] = new_context
        
        # Create response in the format expected by the frontend
        response = Response(
            queue=queue_num,
            response=response_text,
            is_complete=True
        )
        
        return QueueResponse(
            queue=queue_num,
            responses=[response]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    data_manager.close()

if __name__ == "__main__":
    import uvicorn
    print("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
