from fastapi import APIRouter, HTTPException
from backboard import BackboardClient
from pydantic import BaseModel

router = APIRouter(prefix="/student", tags=["Student"])

client = BackboardClient(api_key="YOUR_API_KEY")
ASSISTANT_ID = "your_assistant_id"

class ChatRequest(BaseModel):
    thread_id: str | None = None
    message: str

@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        # 1. Start or resume a persistent thread
        thread_id = request.thread_id
        if not thread_id:
            thread = await client.create_thread(assistant_id=ASSISTANT_ID)
            thread_id = thread.thread_id

        # 2. Send message with "Auto" memory for adaptive tuning
        response = await client.add_message(
            thread_id=thread_id,
            content=request.message,
            memory="Auto", # Automatically uses context to tune story difficulty
            stream=False
        )

        return {
            "reply": response.latest_message.content,
            "thread_id": thread_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))