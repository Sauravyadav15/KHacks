# student.py
import os
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backboard import BackboardClient

# Initialize router
router = APIRouter(prefix="/student", tags=["Student"])

# Request model
class ChatRequest(BaseModel):
    thread_id: str | None = None
    message: str

# Initialize Backboard Client
API_KEY = os.getenv("BACKBOARD_API_KEY", "Add key here")
client = BackboardClient(api_key="here")

# Store assistant ID (create one once and reuse it, or store in DB)
ASSISTANT_ID = "877cd681-6c8f-41df-af98-6d8e81459cb1"

@router.post("/chat")
async def chat(request: ChatRequest):
    async def generate_stream():
        try:
            # 1. Create a new thread if one doesn't exist
            current_thread_id = request.thread_id
            if not current_thread_id:
                print("Creating new thread...")
                thread = await client.create_thread(ASSISTANT_ID)
                current_thread_id = str(thread.thread_id)
                # Send thread_id first
                yield f"data: {json.dumps({'type': 'thread_id', 'thread_id': current_thread_id})}\n\n"

            # 2. Send message to Backboard with streaming
            print(f"Sending message to thread {current_thread_id}: {request.message}")
            stream = await client.add_message(
                thread_id=current_thread_id,
                content=request.message,
                llm_provider="openai",
                model_name="gpt-4.1-mini",
                stream=True
            )

            # 3. Stream the response chunks
            async for chunk in stream:
                # Backboard returns dict chunks with 'type' and 'content' keys
                if chunk.get('type') == 'content_streaming' and chunk.get('content'):
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk['content'], 'thread_id': str(current_thread_id)})}\n\n"
                elif chunk.get('type') == 'message_complete':
                    break

            # Send done signal
            yield f"data: {json.dumps({'type': 'done', 'thread_id': str(current_thread_id)})}\n\n"

        except Exception as e:
            print(f"Error in chat: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")
