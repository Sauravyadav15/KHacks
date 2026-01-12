# student.py
import os
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from backboard import BackboardClient
import sqlite3
from .accounts import get_current_user, User, oauth2_scheme
from jose import JWTError, jwt

# Initialize router
router = APIRouter(prefix="/student", tags=["Student"])

# For token decoding
SECRET_KEY = "07491e256c50c40b71a9ddc14d90e0dd438d8863fe00ae90abc3b72878bb0741"
ALGORITHM = "HS256"

# Request model
class ChatRequest(BaseModel):
    thread_id: str | None = None
    conversation_id: int | None = None
    message: str

#Load .env file
load_dotenv() 

# Initialize Backboard Client
API_KEY = os.getenv("BACKBOARD_API_KEY")
client = BackboardClient(API_KEY)

# Store assistant ID (create one once and reuse it, or store in DB)
ASSISTANT_ID = "775e3763-4000-4cc3-bee9-898f96cae91c"

@router.post("/chat")
async def chat(request: ChatRequest):
    async def generate_stream():
        try:
            #SAVE USER MESSAGE
            try:
                conn = sqlite3.connect('chat_history.db')
                c = conn.cursor()
                c.execute("INSERT INTO messages (role, content) VALUES (?, ?)",
                          ('user', request.message))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"Error saving user message to DB: {e}")

            # 1. Create a new thread if one doesn't exist
            current_thread_id = request.thread_id
            is_first_message = False
            if not current_thread_id:
                print("Creating new thread...")
                thread = await client.create_thread(ASSISTANT_ID)
                current_thread_id = str(thread.thread_id)
                is_first_message = True
                # Send thread_id first
                yield f"data: {json.dumps({'type': 'thread_id', 'thread_id': current_thread_id})}\n\n"

            print(f"Student message to thread {current_thread_id}: {request.message}")

            # 2. If this is the first message, just start the story (no validation)
            if is_first_message:
                story_stream = await client.add_message(
                    thread_id=current_thread_id,
                    content=request.message,
                    llm_provider="openai",
                    model_name="gpt-4.1-mini",
                    stream=True
                )
            else:
                # 3. Validate student's answer with big model
                validation_prompt = f"""You are validating a student's answer in an educational story.

Student's answer: {request.message}

Based on the conversation context, is this answer correct? Respond with ONLY:
- Y (if correct)
- N (if incorrect)"""

                validation_stream = await client.add_message(
                    thread_id=current_thread_id,
                    content=validation_prompt,
                    llm_provider="openai",
                    model_name="gpt-4o",  # Big model validates
                    stream=True
                )

                # Collect validation result
                validation_response = []
                async for chunk in validation_stream:
                    if chunk.get('type') == 'content_streaming' and chunk.get('content'):
                        validation_response.append(chunk['content'])
                    elif chunk.get('type') == 'message_complete':
                        break

                validation_result = ''.join(validation_response).strip().upper()
                print(f"Validation result: {validation_result}")

                # 4. Small model continues based on validation
                if 'Y' in validation_result:
                    # Answer is correct - continue the story
                    continuation_prompt = "The student's answer is correct. Continue the story and ask the next question."
                else:
                    # Answer is incorrect - give feedback and re-ask
                    continuation_prompt = "The student's answer needs improvement. Provide a hint or explanation and ask the question again."

                # 5. Stream small model's response
                story_stream = await client.add_message(
                    thread_id=current_thread_id,
                    content=continuation_prompt,
                    llm_provider="openai",
                    model_name="gpt-4.1-nano",  # Small model continues story
                    stream=True
                )

            # Variable to accumulate bot response for DB
            full_bot_response = ""

            async for chunk in story_stream:
                if chunk.get('type') == 'content_streaming' and chunk.get('content'):
                    content = chunk['content']
                    full_bot_response += content  # Accumulate content
                    yield f"data: {json.dumps({'type': 'content', 'content': content, 'thread_id': str(current_thread_id)})}\n\n"
                elif chunk.get('type') == 'message_complete':
                    break
            
            #SAVE BOT MESSAGE
            try:
                conn = sqlite3.connect('chat_history.db')
                c = conn.cursor()
                c.execute("INSERT INTO messages (role, content) VALUES (?, ?)",
                          ('bot', full_bot_response))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"Error saving bot message to DB: {e}")

            # Send done signal
            yield f"data: {json.dumps({'type': 'done', 'thread_id': str(current_thread_id)})}\n\n"

        except Exception as e:
            print(f"Error in chat: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")
