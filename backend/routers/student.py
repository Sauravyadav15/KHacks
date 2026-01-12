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
from pathlib import Path
import httpx

# Initialize router
router = APIRouter(prefix="/student", tags=["Student"])

# For token decoding
SECRET_KEY = "07491e256c50c40b71a9ddc14d90e0dd438d8863fe00ae90abc3b72878bb0741"
ALGORITHM = "HS256"

# ===== STRUCTURED OUTPUT MODELS =====

class StoryResponse(BaseModel):
    """Structured response for story generation"""
    story: str  # The narrative/story text
    question: str  # The math question to ask
    expected_answer: str  # The correct answer (e.g., "12", "3.5", "seven")
    difficulty: str  # "easy", "medium", "hard"
    hint: str  # A hint to give if the student gets it wrong

class FeedbackResponse(BaseModel):
    """Structured response for feedback after wrong answer"""
    encouragement: str  # Encouraging message
    hint: str  # Hint without giving away the answer
    question_repeated: str  # The same question asked again

# JSON schemas for Backboard response_format
STORY_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "story_response",
        "strict": True,
        "schema": StoryResponse.model_json_schema()
    }
}

FEEDBACK_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "feedback_response",
        "strict": True,
        "schema": FeedbackResponse.model_json_schema()
    }
}

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

# System prompt for the educational story AI (structured output version)
SYSTEM_PROMPT = """You are an educational storyteller for children. Your job is to teach using engaging stories.

CRITICAL RULES - FOLLOW EXACTLY:
1. ONLY teach concepts EXPLICITLY covered in the uploaded teaching materials
2. DO NOT introduce new operations, concepts, or topics not in the materials
3. If materials teach subtraction, ask ONLY subtraction questions - NO division, multiplication, fractions, etc.
4. If materials teach multiplication, ask ONLY multiplication questions - NO other operations
5. Stay STRICTLY within the scope of what the teacher uploaded
6. Create a short, engaging story (2-3 paragraphs) that teaches concepts FROM THE MATERIALS ONLY
7. Ask exactly ONE clear question using ONLY concepts and operations from the teaching materials
8. Adjust difficulty within the material's scope BUT never add new concepts

ADAPTIVE DIFFICULTY (within the same topic ONLY):
- "easy": Basic problems from early sections of the materials (e.g., single-digit subtraction if materials teach subtraction)
- "medium": Intermediate problems from middle sections (e.g., two-digit subtraction if materials teach that)
- "hard": Advanced problems from later sections (e.g., regrouping if materials teach that)
- NEVER add operations or concepts not explicitly taught in the materials

QUESTION STYLE ADAPTATION:
- If a student struggles with a format, give MORE practice with that exact format
- Vary how you ask questions BUT only use concepts from the uploaded materials
- Pay attention to WHAT the student gets wrong and practice that specific skill

STRICT EXAMPLES:
✓ CORRECT (if materials teach subtraction): "What is 15 - 8?"
✓ CORRECT (if materials teach subtraction): "If you have 20 apples and give away 13, how many are left?"
✗ WRONG: "What is (20 - 11) / 2?" - Division is NOT in subtraction materials
✗ WRONG: "What is 5 × 3?" - Multiplication is NOT in subtraction materials
✗ WRONG: "What is 1/2 of 10?" - Fractions are NOT in subtraction materials

Your response will be parsed as JSON with these fields:
- story: The narrative text using ONLY concepts from teaching materials
- question: A question testing ONLY what's explicitly in the materials
- expected_answer: The correct answer (just the value)
- difficulty: "easy", "medium", or "hard" (within material's scope)
- hint: A helpful clue referencing the materials"""

# Store the expected answer per thread for validation
thread_expected_answers = {}

def get_user_id_from_token(token: str) -> int | None:
    """Extract user_id from JWT token. Returns None if not authenticated."""
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
        # Look up user_id from accounts DB (any account type)
        conn = sqlite3.connect(ACCOUNTS_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM accounts WHERE username = ?", (username,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
    except JWTError:
        return None

def save_message_to_conversation(conversation_id: int, role: str, content: str, is_wrong: bool = False, difficulty: str = None):
    """Save a message to the conversation_messages table."""
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute(
            "INSERT INTO conversation_messages (conversation_id, role, content, is_wrong, difficulty) VALUES (?, ?, ?, ?, ?)",
            (conversation_id, role, content, 1 if is_wrong else 0, difficulty)
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

def get_performance_stats(conversation_id: int) -> dict:
    """Get performance statistics for a conversation to inform difficulty adjustment."""
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()

        # Get counts of correct/wrong answers
        c.execute("""
            SELECT
                COUNT(*) as total_answers,
                SUM(CASE WHEN is_wrong = 1 THEN 1 ELSE 0 END) as wrong_count,
                SUM(CASE WHEN is_wrong = 0 THEN 1 ELSE 0 END) as correct_count
            FROM conversation_messages
            WHERE conversation_id = ? AND role = 'user'
        """, (conversation_id,))
        row = c.fetchone()

        # Get recent performance (last 5 answers)
        c.execute("""
            SELECT is_wrong, difficulty FROM conversation_messages
            WHERE conversation_id = ? AND role = 'user'
            ORDER BY id DESC LIMIT 5
        """, (conversation_id,))
        recent = c.fetchall()

        # Get difficulty distribution
        c.execute("""
            SELECT difficulty, COUNT(*) as count
            FROM conversation_messages
            WHERE conversation_id = ? AND role = 'bot' AND difficulty IS NOT NULL
            GROUP BY difficulty
        """, (conversation_id,))
        difficulty_dist = {r[0]: r[1] for r in c.fetchall()}

        conn.close()

        total = row[0] or 0
        wrong = row[1] or 0
        correct = row[2] or 0

        # Calculate recent streak
        recent_correct_streak = 0
        recent_wrong_streak = 0
        for r in recent:
            if r[0] == 0:  # correct
                recent_correct_streak += 1
            else:
                break
        for r in recent:
            if r[0] == 1:  # wrong
                recent_wrong_streak += 1
            else:
                break

        return {
            'total_answers': total,
            'correct_count': correct,
            'wrong_count': wrong,
            'accuracy': (correct / total * 100) if total > 0 else 0,
            'recent_correct_streak': recent_correct_streak,
            'recent_wrong_streak': recent_wrong_streak,
            'difficulty_distribution': difficulty_dist
        }
    except Exception as e:
        print(f"Error getting performance stats: {e}")
        return {
            'total_answers': 0,
            'correct_count': 0,
            'wrong_count': 0,
            'accuracy': 0,
            'recent_correct_streak': 0,
            'recent_wrong_streak': 0,
            'difficulty_distribution': {}
        }

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

def get_user_assistant_id(user_id: int) -> str | None:
    """Fetch the unique assistant_id for a given user from the accounts table."""
    if not user_id:
        return None

    conn = sqlite3.connect(ACCOUNTS_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT assistant_id FROM accounts WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()

    return row["assistant_id"] if row and row["assistant_id"] else None

def normalize_answer(answer: str) -> str:
    """Normalize an answer for comparison (lowercase, strip, handle number words)"""
    answer = answer.lower().strip()
    # Common number words to digits
    word_to_num = {
        'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
        'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
        'ten': '10', 'eleven': '11', 'twelve': '12', 'thirteen': '13',
        'fourteen': '14', 'fifteen': '15', 'sixteen': '16', 'seventeen': '17',
        'eighteen': '18', 'nineteen': '19', 'twenty': '20'
    }
    if answer in word_to_num:
        return word_to_num[answer]
    # Remove common extra characters
    answer = answer.replace('$', '').replace('%', '').replace(',', '')
    return answer

def check_answer(student_answer: str, expected_answer: str) -> bool:
    """Check if student's answer matches expected answer"""
    student_norm = normalize_answer(student_answer)
    expected_norm = normalize_answer(expected_answer)

    # Direct match
    if student_norm == expected_norm:
        return True

    # Try numeric comparison (handles "12" vs "12.0")
    try:
        return float(student_norm) == float(expected_norm)
    except ValueError:
        pass

    # Check if expected is contained in student answer (e.g., "The answer is 12" contains "12")
    if expected_norm in student_norm:
        return True

    return False

async def auto_sync_lessons_to_student(student_id: int, student_assistant_id: str):
    """Automatically sync all active lessons to the student's assistant on first chat"""
    try:
        # Get all active files
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT f.id, f.file_path, f.original_filename
            FROM files f
            WHERE f.is_active = 1 AND f.backboard_status = 'indexed'
            AND NOT EXISTS (
                SELECT 1 FROM student_lessons sl
                WHERE sl.student_id = ? AND sl.file_id = f.id
            )
        """, (student_id,))
        files = c.fetchall()

        print(f"Found {len(files)} lessons to sync for student {student_id}")

        # Upload each file to student's assistant
        for file_row in files:
            file_path = Path(file_row["file_path"])
            if not file_path.exists():
                print(f"File not found: {file_path}")
                continue

            # Read file content
            with open(file_path, "rb") as f:
                file_content = f.read()

            # Upload to Backboard
            try:
                async with httpx.AsyncClient() as http_client:
                    response = await http_client.post(
                        f"{BACKBOARD_BASE_URL}/assistants/{student_assistant_id}/documents",
                        headers={"X-API-Key": BACKBOARD_API_KEY},
                        files={"file": (file_row["original_filename"], file_content)},
                        timeout=60.0
                    )
                    if response.status_code == 200:
                        doc_data = response.json()
                        backboard_doc_id = doc_data.get("document_id")

                        # Record in database
                        c.execute("""
                            INSERT INTO student_lessons (student_id, file_id, backboard_doc_id)
                            VALUES (?, ?, ?)
                        """, (student_id, file_row["id"], backboard_doc_id))
                        print(f"Synced lesson: {file_row['original_filename']} -> {backboard_doc_id}")
                    else:
                        print(f"Failed to sync {file_row['original_filename']}: {response.status_code}")
            except Exception as e:
                print(f"Error syncing {file_row['original_filename']}: {e}")

        conn.commit()
        conn.close()
        print(f"Auto-sync complete for student {student_id}")
    except Exception as e:
        print(f"Error in auto_sync_lessons_to_student: {e}")

@router.post("/chat")
async def chat(request: ChatRequest, authorization: Optional[str] = Header(None)):
    # Get user_id from token (works for both students and teachers)
    user_id = get_user_id_from_token(authorization) if authorization else None

    user_assistant_id = get_user_assistant_id(user_id) if user_id else None

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Please log in to start your learning adventure!"
        )

    if not user_assistant_id:
        raise HTTPException(
            status_code=400,
            detail="Your account needs to be set up. Please contact support or re-register."
        )

    async def generate_stream():
        nonlocal user_id
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

                # Create conversation record if user is logged in
                if user_id:
                    conversation_id = create_conversation(user_id, current_thread_id)

                # AUTO-SYNC ALL ACTIVE LESSONS TO STUDENT'S ASSISTANT
                print(f"Auto-syncing active lessons to student {user_id}'s assistant...")
                await auto_sync_lessons_to_student(user_id, user_assistant_id)

                # Send thread_id and conversation_id first
                yield f"data: {json.dumps({'type': 'thread_id', 'thread_id': current_thread_id, 'conversation_id': conversation_id})}\n\n"

            print(f"Student message to thread {current_thread_id}: {request.message}")

            # Save user message to conversation if we have one
            if conversation_id:
                save_message_to_conversation(conversation_id, 'user', request.message, is_wrong=False)

            # Get teacher's custom instructions
            teacher_instructions = get_active_instructions()

            # 2. If this is the first message, generate a new story with structured output
            if is_first_message:
                initial_prompt = f"""{SYSTEM_PROMPT}
{teacher_instructions}

The student wants to learn about: {request.message}

This is the START of the session, so begin with an "easy" question to warm up.

REMINDER: Only use concepts and operations explicitly taught in the uploaded materials. Do NOT introduce operations not covered in the materials.

IMPORTANT: You MUST respond with ONLY valid JSON in this exact format (no other text):
{{"story": "your story here", "question": "your question here", "expected_answer": "the answer", "difficulty": "easy", "hint": "a helpful hint"}}"""

                # Collect full response (no streaming for JSON)
                full_response = ""
                response_stream = await client.add_message(
                    thread_id=current_thread_id,
                    content=initial_prompt,
                    llm_provider="openai",
                    model_name="gpt-4o",
                    stream=True
                )
                async for chunk in response_stream:
                    if chunk.get('type') == 'content_streaming' and chunk.get('content'):
                        full_response += chunk['content']
                    elif chunk.get('type') == 'message_complete':
                        break

                # Parse the JSON response
                try:
                    # Try to extract JSON from the response (in case there's extra text)
                    json_start = full_response.find('{')
                    json_end = full_response.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = full_response[json_start:json_end]
                        story_data = json.loads(json_str)
                    else:
                        story_data = json.loads(full_response)
                    story_response = StoryResponse(**story_data)
                except json.JSONDecodeError as e:
                    print(f"JSON parse error: {e}")
                    print(f"Raw response: {full_response}")
                    # Fallback: treat as plain text story
                    story_response = StoryResponse(
                        story=full_response,
                        question="What did you learn from the story?",
                        expected_answer="",
                        difficulty="easy",
                        hint="Think about the story!"
                    )

                # Store expected answer for this thread
                thread_expected_answers[current_thread_id] = {
                    'expected_answer': story_response.expected_answer,
                    'hint': story_response.hint,
                    'question': story_response.question,
                    'difficulty': story_response.difficulty
                }
                print(f"Stored expected answer for thread {current_thread_id}: {story_response.expected_answer} (difficulty: {story_response.difficulty})")

                # Format the response for the student (story + question, NOT the answer)
                display_text = f"{story_response.story}\n\n{story_response.question}"

                # Stream the display text to the frontend
                yield f"data: {json.dumps({'type': 'content', 'content': display_text, 'thread_id': str(current_thread_id), 'conversation_id': conversation_id, 'difficulty': story_response.difficulty})}\n\n"

                # Save bot message to conversation WITH difficulty
                if conversation_id:
                    save_message_to_conversation(conversation_id, 'bot', display_text, is_wrong=False, difficulty=story_response.difficulty)

            else:
                # 3. Validate student's answer using stored expected_answer
                stored_data = thread_expected_answers.get(current_thread_id)

                if stored_data:
                    expected = stored_data['expected_answer']
                    is_correct = check_answer(request.message, expected)
                    print(f"Answer check: '{request.message}' vs expected '{expected}' = {is_correct}")
                else:
                    # No stored answer, assume correct to continue
                    is_correct = True
                    print("No stored answer found, assuming correct")

                if is_correct:
                    # Answer is correct - generate new story
                    last_difficulty = stored_data.get('difficulty', 'easy') if stored_data else 'easy'

                    continuation_prompt = f"""Great job! The student answered correctly with: {request.message}

{SYSTEM_PROMPT}
{teacher_instructions}

The last question was "{last_difficulty}" difficulty. Consider increasing difficulty if appropriate BUT stay within the material's scope.

REMINDER: Only use concepts and operations explicitly taught in the materials. Do NOT introduce division, multiplication, fractions, or any other operations not covered.

Congratulate them briefly, then continue with a NEW story and a NEW question using ONLY concepts from the teaching materials.

IMPORTANT: You MUST respond with ONLY valid JSON in this exact format (no other text):
{{"story": "your story here", "question": "your question here", "expected_answer": "the answer", "difficulty": "easy/medium/hard", "hint": "a helpful hint"}}"""

                    # Collect full response
                    full_response = ""
                    response_stream = await client.add_message(
                        thread_id=current_thread_id,
                        content=continuation_prompt,
                        llm_provider="openai",
                        model_name="gpt-4o",
                        stream=True
                    )
                    async for chunk in response_stream:
                        if chunk.get('type') == 'content_streaming' and chunk.get('content'):
                            full_response += chunk['content']
                        elif chunk.get('type') == 'message_complete':
                            break

                    # Parse the JSON response
                    try:
                        json_start = full_response.find('{')
                        json_end = full_response.rfind('}') + 1
                        if json_start >= 0 and json_end > json_start:
                            json_str = full_response[json_start:json_end]
                            story_data = json.loads(json_str)
                        else:
                            story_data = json.loads(full_response)
                        story_response = StoryResponse(**story_data)
                    except json.JSONDecodeError as e:
                        print(f"JSON parse error on continuation: {e}")
                        print(f"Raw response: {full_response}")
                        story_response = StoryResponse(
                            story=full_response,
                            question="What did you learn?",
                            expected_answer="",
                            difficulty="easy",
                            hint="Think about it!"
                        )

                    # Store new expected answer with difficulty
                    thread_expected_answers[current_thread_id] = {
                        'expected_answer': story_response.expected_answer,
                        'hint': story_response.hint,
                        'question': story_response.question,
                        'difficulty': story_response.difficulty
                    }

                    print(f"New question difficulty: {story_response.difficulty} (was {last_difficulty})")
                    display_text = f"Correct! 🎉\n\n{story_response.story}\n\n{story_response.question}"
                    is_wrong_answer = False

                else:
                    # Answer is incorrect - give hint and repeat question
                    is_wrong_answer = True
                    hint = stored_data.get('hint', 'Think about it carefully!')
                    question = stored_data.get('question', 'Try the question again.')
                    current_difficulty = stored_data.get('difficulty', 'easy')

                    display_text = f"Not quite! 🤔\n\n**Hint:** {hint}\n\n**Try again:** {question}"

                    # Mark the user message as wrong
                    if conversation_id:
                        try:
                            conn = sqlite3.connect('chat_history.db')
                            c = conn.cursor()
                            c.execute("""
                                UPDATE conversation_messages
                                SET is_wrong = 1
                                WHERE id = (
                                    SELECT id FROM conversation_messages
                                    WHERE conversation_id = ? AND role = 'user'
                                    ORDER BY id DESC LIMIT 1
                                )
                            """, (conversation_id,))
                            c.execute(
                                "UPDATE student_conversations SET has_wrong_answers = 1 WHERE id = ?",
                                (conversation_id,)
                            )
                            conn.commit()
                            conn.close()
                        except Exception as e:
                            print(f"Error marking wrong answer: {e}")

                # Get difficulty for saving (from correct branch or wrong branch)
                save_difficulty = story_response.difficulty if is_correct else current_difficulty

                # Stream the response with difficulty info
                yield f"data: {json.dumps({'type': 'content', 'content': display_text, 'thread_id': str(current_thread_id), 'conversation_id': conversation_id, 'difficulty': save_difficulty})}\n\n"

                # Save bot message to conversation with difficulty
                if conversation_id:
                    save_message_to_conversation(conversation_id, 'bot', display_text, is_wrong=False, difficulty=save_difficulty)

            # Send done signal
            yield f"data: {json.dumps({'type': 'done', 'thread_id': str(current_thread_id), 'conversation_id': conversation_id, 'was_wrong': is_wrong_answer})}\n\n"

        except Exception as e:
            print(f"Error in chat: {str(e)}")
            import traceback
            traceback.print_exc()
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


# ===== LESSON MANAGEMENT ENDPOINTS =====

BACKBOARD_API_KEY = os.getenv("BACKBOARD_API_KEY")
BACKBOARD_BASE_URL = "https://app.backboard.io/api"

@router.get("/available-lessons")
async def get_available_lessons(current_user: User = Depends(get_current_user)):
    """Get all lessons available to the student (active files from teacher)."""
    if current_user.account_type != "student":
        raise HTTPException(status_code=403, detail="Only students can view lessons")

    # Get student_id
    conn = sqlite3.connect(ACCOUNTS_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM accounts WHERE username = ?", (current_user.username,))
    row = c.fetchone()
    student_id = row[0] if row else None
    conn.close()

    if not student_id:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get all active files (available lessons)
    conn = sqlite3.connect('chat_history.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT f.id, f.original_filename, f.uploaded_at, f.backboard_status,
               c.name as category_name,
               sl.id as lesson_id, sl.started_at as lesson_started_at
        FROM files f
        LEFT JOIN categories c ON f.category_id = c.id
        LEFT JOIN student_lessons sl ON f.id = sl.file_id AND sl.student_id = ?
        WHERE f.is_active = 1 AND f.backboard_status = 'indexed'
        ORDER BY f.uploaded_at DESC
    """, (student_id,))
    files = c.fetchall()
    conn.close()

    lessons = []
    for f in files:
        lessons.append({
            "id": f["id"],
            "name": f["original_filename"],
            "category": f["category_name"],
            "uploaded_at": f["uploaded_at"],
            "started": f["lesson_id"] is not None,
            "started_at": f["lesson_started_at"]
        })

    return {"lessons": lessons}


@router.get("/my-lessons")
async def get_my_lessons(current_user: User = Depends(get_current_user)):
    """Get lessons the student has already started."""
    if current_user.account_type != "student":
        raise HTTPException(status_code=403, detail="Only students can view their lessons")

    # Get student_id
    conn = sqlite3.connect(ACCOUNTS_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM accounts WHERE username = ?", (current_user.username,))
    row = c.fetchone()
    student_id = row[0] if row else None
    conn.close()

    if not student_id:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get started lessons
    conn = sqlite3.connect('chat_history.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT sl.id, sl.file_id, sl.started_at, sl.last_accessed_at,
               f.original_filename, c.name as category_name
        FROM student_lessons sl
        JOIN files f ON sl.file_id = f.id
        LEFT JOIN categories c ON f.category_id = c.id
        WHERE sl.student_id = ?
        ORDER BY sl.last_accessed_at DESC
    """, (student_id,))
    lessons = [dict(row) for row in c.fetchall()]
    conn.close()

    return {"lessons": lessons}


@router.post("/start-lesson/{file_id}")
async def start_lesson(file_id: int, current_user: User = Depends(get_current_user)):
    """Start a lesson - syncs the document to the student's assistant."""
    if current_user.account_type != "student":
        raise HTTPException(status_code=403, detail="Only students can start lessons")

    # Get student info
    conn = sqlite3.connect(ACCOUNTS_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, assistant_id FROM accounts WHERE username = ?", (current_user.username,))
    row = c.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Student not found")

    student_id = row["id"]
    student_assistant_id = row["assistant_id"]

    if not student_assistant_id:
        raise HTTPException(status_code=400, detail="Student doesn't have an assistant. Please re-login.")

    # Get file info
    conn = sqlite3.connect('chat_history.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id, file_path, original_filename, backboard_status
        FROM files WHERE id = ? AND is_active = 1
    """, (file_id,))
    file_row = c.fetchone()

    if not file_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Lesson not found or not available")

    # Check if already started
    c.execute("SELECT id FROM student_lessons WHERE student_id = ? AND file_id = ?", (student_id, file_id))
    existing = c.fetchone()

    if existing:
        # Already started, just update last_accessed
        c.execute("UPDATE student_lessons SET last_accessed_at = CURRENT_TIMESTAMP WHERE id = ?", (existing["id"],))
        conn.commit()
        conn.close()
        return {"message": "Lesson already started", "lesson_id": existing["id"]}

    # Upload document to student's assistant
    file_path = Path(file_row["file_path"])
    if not file_path.exists():
        conn.close()
        raise HTTPException(status_code=404, detail="Lesson file not found on server")

    # Read file content
    with open(file_path, "rb") as f:
        file_content = f.read()

    # Upload to student's assistant
    backboard_doc_id = None
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                f"{BACKBOARD_BASE_URL}/assistants/{student_assistant_id}/documents",
                headers={"X-API-Key": BACKBOARD_API_KEY},
                files={"file": (file_row["original_filename"], file_content)},
                timeout=60.0
            )
            if response.status_code == 200:
                doc_data = response.json()
                backboard_doc_id = doc_data.get("document_id")
                print(f"Uploaded lesson to student {student_id}'s assistant: {backboard_doc_id}")
            else:
                print(f"Failed to upload lesson: {response.status_code} - {response.text}")
                conn.close()
                raise HTTPException(status_code=500, detail="Failed to sync lesson to your learning assistant")
    except httpx.RequestError as e:
        conn.close()
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")

    # Record the started lesson
    c.execute("""
        INSERT INTO student_lessons (student_id, file_id, backboard_doc_id)
        VALUES (?, ?, ?)
    """, (student_id, file_id, backboard_doc_id))
    lesson_id = c.lastrowid
    conn.commit()
    conn.close()

    return {
        "message": "Lesson started successfully!",
        "lesson_id": lesson_id,
        "backboard_doc_id": backboard_doc_id
    }
