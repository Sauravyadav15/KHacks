# student.py
import os
import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from backboard import BackboardClient
from pathlib import Path

# Initialize router
router = APIRouter(prefix="/student", tags=["Student"])

# Request model
class ChatRequest(BaseModel):
    thread_id: str | None = None
    message: str

#Load .env file
load_dotenv() 

# Initialize Backboard Client
API_KEY = os.getenv("BACKBOARD_API_KEY")
client = BackboardClient(API_KEY)

# Store assistant ID (create one once and reuse it, or store in DB)
ASSISTANT_ID = "6881a3e7-40cb-484e-bb99-f6e07ff0644f"

@router.post("/chat")
async def chat(request: ChatRequest):
    async def generate_stream():
        try:
            # 1. Create a new thread if one doesn't exist
            current_thread_id = request.thread_id
            is_first_message = False
            if not current_thread_id:
                print("Creating new thread...")
                thread = await client.create_thread(ASSISTANT_ID)
                current_thread_id = str(thread.thread_id)
                is_first_message = True

                # Upload active files to the thread for context
                from routers.teacher import get_active_file_paths
                active_files = get_active_file_paths()

                if active_files:
                    print(f"Uploading {len(active_files)} active files to thread {current_thread_id}...")
                    for file_path in active_files:
                        try:
                            await client.upload_document_to_thread(
                                thread_id=current_thread_id,
                                file_path=file_path
                            )
                            print(f"✓ Uploaded {Path(file_path).name} to thread")
                        except Exception as e:
                            print(f"✗ Error uploading {file_path}: {e}")

                # Send thread_id first
                yield f"data: {json.dumps({'type': 'thread_id', 'thread_id': current_thread_id})}\n\n"

            print(f"Student message to thread {current_thread_id}: {request.message}")

            # 2. If this is the first message, just start the story (no validation)
            if is_first_message:
                # Get custom teacher instructions
                from routers.teacher import get_active_instructions
                teacher_instructions = get_active_instructions()

                # Add instruction to use uploaded materials
                initial_prompt = request.message
                if active_files:
                    initial_prompt = f"{request.message}\n\nIMPORTANT: Use the uploaded lesson materials to create problems that match those examples and difficulty levels. Base your questions on the content provided in the documents."

                # Append teacher instructions
                initial_prompt += teacher_instructions

                story_stream = await client.add_message(
                    thread_id=current_thread_id,
                    content=initial_prompt,
                    llm_provider="openai",
                    model_name="gpt-4.1-mini",
                    stream=True
                )
            else:
                # Get custom teacher instructions for continuation
                from routers.teacher import get_active_instructions
                teacher_instructions = get_active_instructions()

                # 3. Validate student's answer with big model
                validation_prompt = f"""You are validating a student's answer in an educational story.

Student's answer: {request.message}

Based on the conversation context, is this answer correct? Respond with ONLY:
- Y (if correct)
- N (if incorrect){teacher_instructions}"""

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
                    continuation_prompt = f"The student's answer is correct. Continue the story and ask the next question.{teacher_instructions}"
                else:
                    # Answer is incorrect - give feedback and re-ask
                    continuation_prompt = f"The student's answer needs improvement. Provide a hint or explanation and ask the question again.{teacher_instructions}"

                # 5. Stream small model's response
                story_stream = await client.add_message(
                    thread_id=current_thread_id,
                    content=continuation_prompt,
                    llm_provider="openai",
                    model_name="gpt-4.1-nano",  # Small model continues story
                    stream=True
                )

            async for chunk in story_stream:
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
