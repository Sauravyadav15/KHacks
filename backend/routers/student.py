# student.py
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backboard import BackboardClient

# Initialize router
router = APIRouter(prefix="/student", tags=["Student"])

# Request model
class ChatRequest(BaseModel):
    thread_id: str | None = None
    message: str

# Initialize Backboard Client
# BEST PRACTICE: Use environment variable for API Key
API_KEY = os.getenv("BACKBOARD_API_KEY", "put api key here")
client = BackboardClient(api_key=API_KEY)

# Store assistant ID (create one once and reuse it, or store in DB)
ASSISTANT_ID = "put assistant id here" 

@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        # 1. Create a new thread if one doesn't exist
        current_thread_id = request.thread_id
        if not current_thread_id:
            print("Creating new thread...")
            thread = await client.create_thread(ASSISTANT_ID)
            current_thread_id = thread.thread_id
        
        # 2. Send message to Backboard
        print(f"Sending message to thread {current_thread_id}: {request.message}")
        response = await client.add_message(
            thread_id=current_thread_id,
            content=request.message,
            llm_provider="openai",  # Or your preferred provider
            model_name="gpt-4o",    # Or "cheap model" like gpt-3.5-turbo
            stream=False
        )

        # 3. Return the response and the thread_id so frontend can maintain context
        return {
            "reply": response.content,
            "thread_id": current_thread_id
        }

    except Exception as e:
        print(f"Error in chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
