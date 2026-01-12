# student.py
import os
import json
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from backboard import BackboardClient
import sqlite3
from .accounts import get_current_user, User, oauth2_scheme, DB_PATH as ACCOUNTS_DB_PATH
from .teacher import get_active_instructions
from jose import JWTError, jwt
from typing import Optional

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

# System prompt for the educational story AI
SYSTEM_PROMPT = """You are an educational storyteller for children. Your job is to teach math through engaging stories.

IMPORTANT RULES:
1. Tell a short, engaging story that naturally leads to a SPECIFIC math question
2. The story should be 2-3 short paragraphs maximum
3. At the END of your response, you MUST ask exactly ONE clear math question for the student to answer
4. Format your question on its own line starting with "QUESTION:" like this: QUESTION: What is 7 + 5?
5. Wait for the student's answer - do NOT give the answer yourself
6. Keep the math appropriate for elementary school children (ages 6-12)
7. Make the story fun and relatable with characters and adventure

Example format:
[Short engaging story...]

QUESTION: What is 3 x 4?"""

# Store the last full bot response per thread for validation
last_bot_responses = {}

def get_student_id_from_token(token: str) -> int | None:
    """Extract student_id from JWT token. Returns None if not authenticated."""
    if not token:
        return None
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            return None
        # Look up student_id from accounts DB
        conn = sqlite3.connect(ACCOUNTS_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM accounts WHERE username = ? AND account_type = 'student'", (username,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
    except JWTError:
        return None

def save_message_to_conversation(conversation_id: int, role: str, content: str, is_wrong: bool = False):
    """Save a message to the conversation_messages table."""
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute(
            "INSERT INTO conversation_messages (conversation_id, role, content, is_wrong) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, 1 if is_wrong else 0)
        )
        # Update last_message_at timestamp
        c.execute(
            "UPDATE student_conversations SET last_message_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,)
        )
        # If wrong answer, update has_wrong_answers flag
        if is_wrong:
            c.execute(
                "UPDATE student_conversations SET has_wrong_answers = 1 WHERE id = ?",
                (conversation_id,)
            )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving message to conversation: {e}")

def create_conversation(student_id: int, thread_id: str) -> int:
    """Create a new conversation for a student and return its ID."""
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()
    c.execute(
        "INSERT INTO student_conversations (student_id, thread_id) VALUES (?, ?)",
        (student_id, thread_id)
    )
    conversation_id = c.lastrowid
    conn.commit()
    conn.close()
    return conversation_id

def get_conversation_by_id(conversation_id: int) -> dict | None:
    """Get conversation details by ID."""
    conn = sqlite3.connect('chat_history.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM student_conversations WHERE id = ?", (conversation_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_student_assistant_id(student_id: int) -> str | None:
    """Fetch the unique assistant_id for a given student from the accounts table."""
    if not student_id:
        return None
        
    conn = sqlite3.connect(ACCOUNTS_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT assistant_id FROM accounts WHERE id = ?", (student_id,))
    row = c.fetchone()
    conn.close()
    
    return row["assistant_id"] if row else None

@router.post("/chat")
async def chat(request: ChatRequest, authorization: Optional[str] = Header(None)):
    # Get student_id from token (optional - works without auth too)
    student_id = get_student_id_from_token(authorization) if authorization else None

    user_assistant_id = get_student_assistant_id(student_id) if student_id else None

    if not user_assistant_id:
        raise HTTPException(
            status_code=401, 
            detail="Please log in to start your learning adventure!"
        )

    async def generate_stream():
        nonlocal student_id
        conversation_id = request.conversation_id
        is_wrong_answer = False

        try:
            # 1. Create a new thread if one doesn't exist
            current_thread_id = request.thread_id
            is_first_message = False
            if not current_thread_id:
                print("Creating new thread...")
                thread = await client.create_thread(user_assistant_id)
                current_thread_id = str(thread.thread_id)
                is_first_message = True

                # Create conversation record if student is logged in
                if student_id:
                    conversation_id = create_conversation(student_id, current_thread_id)

                # Send thread_id and conversation_id first
                yield f"data: {json.dumps({'type': 'thread_id', 'thread_id': current_thread_id, 'conversation_id': conversation_id})}\n\n"

            print(f"Student message to thread {current_thread_id}: {request.message}")

            # Save user message to conversation if we have one
            if conversation_id:
                save_message_to_conversation(conversation_id, 'user', request.message, is_wrong=False)

            # Get teacher's custom instructions
            teacher_instructions = get_active_instructions()

            # 2. If this is the first message, start the story with proper system prompt
            if is_first_message:
                # Build the initial prompt with system instructions
                initial_prompt = f"""{SYSTEM_PROMPT}
{teacher_instructions}

The student wants to learn about: {request.message}

Now create a short engaging story with a math question at the end. Remember: ask exactly ONE question and wait for the answer."""

                story_stream = await client.add_message(
                    thread_id=current_thread_id,
                    content=initial_prompt,
                    llm_provider="openai",
                    model_name="gpt-4.1-mini",
                    stream=True
                )
            else:
                # 3. Validate student's answer with the stored story context
                # Get the last bot response (the story with the question)
                last_story = last_bot_responses.get(current_thread_id, "")

                # Build clear validation prompt with:
                # A) The full story/question
                # B) The student's answer
                validation_prompt = f"""You are validating a student's math answer.

=== PART A: THE STORY AND QUESTION ===
{last_story}

=== PART B: STUDENT'S ANSWER ===
{request.message}

=== YOUR TASK ===
Is the student's answer correct for the math question in the story above?

Respond with ONLY one letter:
Y = correct answer
N = incorrect answer"""

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

                # 4. Continue based on validation
                if 'Y' in validation_result:
                    # Answer is correct - continue the story with a new question
                    continuation_prompt = f"""The student answered correctly! Their answer was: {request.message}

{SYSTEM_PROMPT}
{teacher_instructions}

Congratulate them briefly (1 sentence), then continue the story with a NEW math question.
Remember: Keep it short, and end with exactly ONE clear math question."""
                    is_wrong_answer = False
                else:
                    # Answer is incorrect - give feedback and re-ask
                    continuation_prompt = f"""The student's answer "{request.message}" was incorrect.

Give them a gentle hint without revealing the answer. Encourage them to try again.
Keep your response short (2-3 sentences max) and re-ask the SAME question."""
                    is_wrong_answer = True

                    # Update the user message to mark it as wrong
                    if conversation_id:
                        try:
                            conn = sqlite3.connect('chat_history.db')
                            c = conn.cursor()
                            # Mark the last user message in this conversation as wrong
                            # SQLite doesn't support ORDER BY in UPDATE, so use subquery
                            c.execute("""
                                UPDATE conversation_messages
                                SET is_wrong = 1
                                WHERE id = (
                                    SELECT id FROM conversation_messages
                                    WHERE conversation_id = ? AND role = 'user'
                                    ORDER BY id DESC LIMIT 1
                                )
                            """, (conversation_id,))
                            print(f"Marked message as wrong, rows affected: {c.rowcount}")
                            # Also flag the conversation
                            c.execute(
                                "UPDATE student_conversations SET has_wrong_answers = 1 WHERE id = ?",
                                (conversation_id,)
                            )
                            conn.commit()
                            conn.close()
                        except Exception as e:
                            print(f"Error marking wrong answer: {e}")

                # 5. Stream the response
                story_stream = await client.add_message(
                    thread_id=current_thread_id,
                    content=continuation_prompt,
                    llm_provider="openai",
                    model_name="gpt-4.1-mini",  # Use mini for better quality responses
                    stream=True
                )

            # Variable to accumulate bot response for DB
            full_bot_response = ""

            async for chunk in story_stream:
                if chunk.get('type') == 'content_streaming' and chunk.get('content'):
                    content = chunk['content']
                    full_bot_response += content  # Accumulate content
                    yield f"data: {json.dumps({'type': 'content', 'content': content, 'thread_id': str(current_thread_id), 'conversation_id': conversation_id})}\n\n"
                elif chunk.get('type') == 'message_complete':
                    break

            # Store the full bot response for next validation
            last_bot_responses[current_thread_id] = full_bot_response
            print(f"Stored bot response for thread {current_thread_id}: {full_bot_response[:100]}...")

            # Save bot message to conversation
            if conversation_id:
                save_message_to_conversation(conversation_id, 'bot', full_bot_response, is_wrong=False)

            # Send done signal with wrong answer indicator
            yield f"data: {json.dumps({'type': 'done', 'thread_id': str(current_thread_id), 'conversation_id': conversation_id, 'was_wrong': is_wrong_answer})}\n\n"

        except Exception as e:
            print(f"Error in chat: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")

@router.get("/conversations")
async def get_my_conversations(current_user: User = Depends(get_current_user)):
    """Get all conversations for the logged-in student."""
    if current_user.account_type != "student":
        raise HTTPException(status_code=403, detail="Only students can view their conversations")

    # Get student_id
    conn = sqlite3.connect(ACCOUNTS_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM accounts WHERE username = ?", (current_user.username,))
    row = c.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Student not found")

    student_id = row[0]

    # Get conversations
    conn = sqlite3.connect('chat_history.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, thread_id, started_at, last_message_at, has_wrong_answers
        FROM student_conversations
        WHERE student_id = ?
        ORDER BY last_message_at DESC
    """, (student_id,))
    rows = c.fetchall()
    conn.close()

    return {"conversations": [dict(row) for row in rows]}
