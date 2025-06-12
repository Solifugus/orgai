#!/usr/bin/env python3
import argparse
import asyncio
import httpx
import json
import base64
import gzip
import os
import sys
from typing import Optional, Dict, Any
import yaml

class OrgAIClient:
    """Console client for testing the OrgAI Assistant."""
    
    def __init__(self, server_url: str = "http://localhost:8000", username: str = "console_user", mode: str = "auto"):
        """Initialize the client with server URL, username, and mode."""
        self.server_url = server_url
        self.username = username
        self.mode = mode
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from config.yaml if it exists."""
        config_path = "config.yaml"
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                print(f"Warning: Error loading config file: {e}")
        
        # Return default config
        return {
            "client": {
                "server_url": "http://localhost:8000",
                "username": "console_user"
            }
        }
        
    async def chat(self, prompt: str) -> str:
        """Send a chat message to the server and return the response."""
        url = f"{self.server_url}/chat"
        data = {
            "user": self.username,
            "prompt": prompt,
            "mode": self.mode
        }
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                print("Sending request to server...")
                response = await client.post(url, json=data)
                
                if response.status_code != 200:
                    return f"Error: Server returned status code {response.status_code}\n{response.text}"
                
                result = response.json()
                response_text = result.get("response", "")
                is_compressed = result.get("compressed", False)
                encoding = result.get("encoding", "utf-8")
                context = result.get("context", "")
                
                # Handle compressed responses
                if is_compressed and encoding == "gzip+base64":
                    try:
                        compressed_data = base64.b64decode(response_text)
                        response_text = gzip.decompress(compressed_data).decode('utf-8')
                    except Exception as e:
                        return f"Error decompressing response: {e}"
                
                return response_text
                
            except httpx.RequestError as e:
                return f"Error communicating with server: {e}"
            except Exception as e:
                return f"Unexpected error: {e}"
                
    async def clear_history(self) -> str:
        """Clear the conversation history."""
        url = f"{self.server_url}/chat/clear"
        data = {
            "user": self.username,
            "prompt": ""  # Empty prompt
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=data)
                
                if response.status_code != 200:
                    return f"Error clearing history: {response.status_code}\n{response.text}"
                
                return "Conversation history cleared."
                
            except httpx.RequestError as e:
                return f"Error communicating with server: {e}"
            except Exception as e:
                return f"Unexpected error: {e}"
                
    async def interactive_mode(self):
        """Run the client in interactive mode."""
        mode_names = {
            "policy": "HR Policies & Procedures",
            "etl": "Data Analysis & Metadata", 
            "auto": "Smart Assistant (Auto-routing)"
        }
        print(f"OrgAI Console Client - Connected to {self.server_url}")
        print(f"Mode: {mode_names.get(self.mode, self.mode)}")
        print("Type 'exit', 'quit', or 'q' to exit, 'clear' to clear conversation history")
        print("-----------------------------------------------------------------------")
        
        while True:
            try:
                # Get user input
                prompt = input("\nYou: ")
                
                # Check for exit commands
                if prompt.lower() in ('exit', 'quit', 'q'):
                    print("Exiting...")
                    break
                    
                # Check for clear command
                if prompt.lower() == 'clear':
                    result = await self.clear_history()
                    print(result)
                    continue
                    
                # Skip empty prompts
                if not prompt.strip():
                    continue
                    
                # Process the prompt
                print("\nAssistant: ", end="")
                sys.stdout.flush()  # Ensure the prompt is displayed before the response
                
                response = await self.chat(prompt)
                print(response)
                
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")

def main():
    """Main entry point for the console client."""
    parser = argparse.ArgumentParser(description="OrgAI Console Client")
    parser.add_argument("--server", "-s", help="Server URL (default: http://localhost:8000)", default="http://localhost:8000")
    parser.add_argument("--user", "-u", help="Username (default: console_user)", default="console_user")
    parser.add_argument("--mode", "-m", help="Mode: policy, etl, or auto (default: auto)", choices=["policy", "etl", "auto"], default="auto")
    parser.add_argument("--prompt", "-p", help="Single prompt to process (non-interactive mode)")
    
    args = parser.parse_args()
    
    client = OrgAIClient(server_url=args.server, username=args.user, mode=args.mode)
    
    if args.prompt:
        # Single prompt mode
        response = asyncio.run(client.chat(args.prompt))
        print(response)
    else:
        # Interactive mode
        try:
            asyncio.run(client.interactive_mode())
        except KeyboardInterrupt:
            print("\nExiting...")

if __name__ == "__main__":
    main()