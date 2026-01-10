from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/student", tags=["Student"])

class ChatRequest(BaseModel):
    thread_id: str | None = None
    message: str

@router.post("/chat")
async def chat(request: ChatRequest):
    # Simple response for now
    return {
        "reply": "I got this",
        "thread_id": request.thread_id or "new_thread_123"
    }