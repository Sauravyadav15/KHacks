import os
import json
import sqlite3
import asyncio
from typing import Optional, Dict, List, AsyncGenerator, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from backboard import BackboardClient
from jose import JWTError, jwt
from .accounts import get_current_user, oauth2_scheme, DB_PATH as ACCOUNTS_DB_PATH

load_dotenv()

router = APIRouter(prefix="/student", tags=["Student"])

# --- CONFIGURATION ---
API_KEY = os.getenv("BACKBOARD_API_KEY")
client = BackboardClient(API_KEY)
CHAT_DB_PATH = 'chat_history.db'
SECRET_KEY = "07491e256c50c40b71a9ddc14d90e0dd438d8863fe00ae90abc3b72878bb0741"
ALGORITHM = "HS256"

MODELS = {
    "architect": "gpt-4o",
    "renderer": "anthropic/claude-3.5-sonnet",
    "tutor": "gpt-4o-mini"
}

# --- DATA MODELS ---
class GraphNode(BaseModel):
    id: str
    type: str
    content_goal: str
    problem_data: Optional[Dict[str, str]] = None
    next_success: Optional[str] = None
    next_failure: Optional[str] = None
    next_node: Optional[str] = None

class StoryGraphState(BaseModel):
    current_node_id: str
    nodes: Dict[str, GraphNode]

class ChatRequest(BaseModel):
    thread_id: str | None = None
    conversation_id: int | None = None
    message: str

# --- DATABASE HELPERS ---
def get_user_id_from_token(token: str) -> int | None:
    if not token: return None
    try:
        if token.startswith('Bearer '): token = token[7:]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username: return None
        
        conn = sqlite3.connect(ACCOUNTS_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM accounts WHERE username = ?", (username,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
    except JWTError:
        return None

def get_user_assistant_id(user_id: int) -> str:
    if not user_id: return None
    conn = sqlite3.connect(ACCOUNTS_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT assistant_id FROM accounts WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row["assistant_id"] if row and row["assistant_id"] else None

def get_graph_state(thread_id: str) -> Optional[StoryGraphState]:
    conn = sqlite3.connect(CHAT_DB_PATH)
    c = conn.cursor()
    try:
        t_id_str = str(thread_id)
        c.execute("SELECT graph_state FROM student_conversations WHERE thread_id = ?", (t_id_str,))
        row = c.fetchone()
        if row and row[0]: 
            return StoryGraphState(**json.loads(row[0]))
    except Exception: 
        pass
    finally: 
        conn.close()
    return None

def save_graph_state(thread_id: str, state: StoryGraphState):
    conn = sqlite3.connect(CHAT_DB_PATH)
    c = conn.cursor()
    t_id_str = str(thread_id)
    
    # Check if exists
    c.execute("SELECT 1 FROM student_conversations WHERE thread_id = ?", (t_id_str,))
    exists = c.fetchone()
    
    if exists:
        c.execute("UPDATE student_conversations SET graph_state = ? WHERE thread_id = ?",
                  (json.dumps(state.model_dump()), t_id_str))
    else:
        # If not exists, insert new record (requires user_id in real app, defaulting for now or skipping)
        pass
    
    conn.commit()
    conn.close()

# --- ROBUST CONTENT EXTRACTOR ---
def extract_content_string(response_obj: Any) -> str:
    """
    Final robust extractor that handles objects, dicts, lists, and strings.
    Guarantees a string return value.
    """
    if response_obj is None:
        return ""
    
    # Immediate list handling (recursive)
    if isinstance(response_obj, list):
        return "".join(extract_content_string(x) for x in response_obj)
    
    content = response_obj
    
    # Resolve attributes - Check 'content' BEFORE 'message'
    if hasattr(content, 'latest_message'):
        content = content.latest_message
    if hasattr(content, 'content'):
        content = content.content
    elif hasattr(content, 'message'):
        content = content.message
    elif isinstance(content, dict):
        content = content.get('content') or content.get('text') or ""
    
    # Check if we unwrapped another layer of container OR if it's a list
    if content != response_obj or isinstance(content, list):
        return extract_content_string(content)
    
    # Base case: convert to string
    return str(content)

def parse_json_from_text(text: str) -> Dict[str, Any]:
    """Extracts JSON from markdown text."""
    original_text = text
    
    if isinstance(text, list):
        text = "".join(str(item) for item in text)
    
    if not isinstance(text, str):
        text = str(text)
    
    text = text.strip()
    
    if "```json" in text:
        parts = text.split("```json")
        if len(parts) > 1:
            text = parts[1].split("```")[0]  # Get content between markers
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]  # FIX: Changed from 'text = parts'
        elif len(parts) > 1:
            text = parts[1]
    
    # Fallback for raw JSON without markdown blocks
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end+1]
    
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"JSON Parse Failed. Error: {e}")
        print(f"Original text type: {type(original_text)}")
        print(f"Original text (first 500 chars): {str(original_text)[:500]}")
        print(f"Attempted to parse: {text[:500]}")
        raise

# --- REPAIR MECHANISM ---
async def repair_json_content(thread_id: str, broken_content: str) -> str:
    prompt = f"""
SYSTEM ALERT: The previous output failed to parse as JSON.
Your task is to fix the following text so it becomes valid JSON.
Do NOT add any explanations. Return ONLY the JSON object.

BROKEN TEXT:
{broken_content[:4000]}
"""
    try:
        response = await client.add_message(
            thread_id=thread_id,
            content=prompt,
            model_name=MODELS["tutor"]
        )
        return extract_content_string(response)
    except Exception:
        return "{}"

# --- STREAMING GENERATORS ---
async def generate_graph_expansion(thread_id: str, context: str, difficulty: str) -> Dict[str, GraphNode]:
    prompt = f"""
You are the Level Designer for an educational RPG.

Context: {context}
Current Difficulty: {difficulty}

Generate a JSON object representing 3 connected nodes:
1. A 'story_white' node (Plot progression).
2. A 'problem_red' node (A challenge requiring the user to solve a math problem).
3. A 'story_white' node (Resolution/Reward).

Structure:
{{
  "node_A": {{ "id": "node_A", "type": "story_white", "content_goal": "...", "next_node": "node_B" }},
  "node_B": {{ "id": "node_B", "type": "problem_red", "content_goal": "...", "problem_data": {{ "question": "...", "answer": "..." }}, "next_success": "node_C", "next_failure": "node_B_hint" }},
  "node_C": {{ "id": "node_C", "type": "story_white", "content_goal": "...", "next_node": "END_OF_BATCH" }}
}}

IMPORTANT: Output valid JSON only.
"""
    try:
        response = await client.add_message(
            thread_id=thread_id,
            content=prompt,
            model_name=MODELS["architect"],
            stream=False
        )
        
        print(f"DEBUG - Raw response type: {type(response)}")
        
        # 1. Robust Extraction (now with fixed order)
        content_str = extract_content_string(response)
        print(f"DEBUG - Extracted content (first 500 chars): {content_str[:500]}")
        
        # 2. Parse & Validate
        try:
            raw = parse_json_from_text(content_str)
            # Validate structure
            if not isinstance(raw, dict):
                raise ValueError(f"Expected dict, got {type(raw)}")
            
            # Validate we have actual nodes, not just a success message
            if len(raw) == 0 or not any(isinstance(v, dict) and 'id' in v for v in raw.values()):
                raise ValueError("No valid graph nodes found in response")
            
            return {k: GraphNode(**v) for k, v in raw.items()}
        except (json.JSONDecodeError, ValueError) as e:
            print(f"JSON PARSE ERROR: {e}")
            print(f"Content (first 1000 chars): {content_str[:1000]}")
            print("Attempting repair...")
            
            fixed_content = await repair_json_content(thread_id, content_str)
            try:
                # Re-extract if repair returns wrapped content
                fixed_str = extract_content_string(fixed_content)
                raw = parse_json_from_text(fixed_str)
                if not isinstance(raw, dict):
                    raise ValueError(f"Repaired content is not a dict: {type(raw)}")
                return {k: GraphNode(**v) for k, v in raw.items()}
            except Exception as repair_error:
                print(f"Repair also failed: {repair_error}")
                return {}
                
    except Exception as e:
        print(f"GRAPH GEN ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {}

async def render_node_stream(thread_id: str, node: GraphNode) -> AsyncGenerator[str, None]:
    prompt = f"""
You are the Storyteller.
Current Goal: {node.content_goal}

Write the narrative text for this moment.
Do NOT output JSON. Output the story text only.
"""
    print("NOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOODE")
    print(node.type)
    if node.type == "problem_red" and node.problem_data:
        prompt += f"\nMOST IMPORTANT: Integrate this problem naturally: {node.problem_data['question']}"
    
    try:
        stream = await client.add_message(
            thread_id=thread_id,
            content=prompt,
            llm_provider="openrouter",
            model_name=MODELS["renderer"],
            stream=True
        )
        
        async for event in stream:
            content = extract_content_string(event)
            if content:  # Only yield if there is actual content
                yield content
    except Exception as e:
        print(f"STREAM ERROR: {e}")
        yield f"[System Error: {str(e)}]"

async def check_answer_semantic(thread_id: str, user_input: str, correct_answer: str, question: str) -> bool:
    try:
        response = await client.add_message(
            thread_id=thread_id,
            content=f"Q:{question} A:{correct_answer} Student:{user_input}. Is correct? JSON {{'is_correct': bool}}",
            model_name=MODELS["tutor"]
        )
        content_str = extract_content_string(response)
        data = parse_json_from_text(content_str)
        return data.get("is_correct", False)
    except Exception as e:
        print(f"Semantic check failed: {e}, falling back to exact match")
        return str(user_input).strip().lower() == str(correct_answer).strip().lower()

# --- ENDPOINTS ---
@router.post("/chat")
async def chat_endpoint(request: ChatRequest, token: str = Depends(oauth2_scheme)):
    user_id = get_user_id_from_token(token)
    if not user_id: 
        raise HTTPException(status_code=401, detail="Invalid token")
    
    async def response_generator():
        # 1. Thread Initialization
        thread_id = request.thread_id
        if not thread_id:
            assistant_id = get_user_assistant_id(user_id)
            res = client.create_thread(assistant_id=assistant_id)
            
            if asyncio.iscoroutine(res):
                thread = await res
            else:
                thread = res
            
            # Extract thread_id from various response formats
            if isinstance(thread, dict):
                thread_id = thread.get('thread_id') or thread.get('id')
            elif hasattr(thread, 'thread_id'):
                thread_id = thread.thread_id
            elif hasattr(thread, 'id'):
                thread_id = thread.id
            else:
                try:
                    dump = thread.model_dump()
                    thread_id = dump.get('thread_id') or dump.get('id')
                except:
                    thread_id = str(thread)
            
            thread_id = str(thread_id).strip()
            
            # Validate thread_id
            if not thread_id or thread_id == "None":
                yield f"data: {json.dumps({'type': 'error', 'content': 'Failed to initialize session'})}\n\n"
                return
            
            # Yield thread_id so frontend receives it
            yield f"data: {json.dumps({'type': 'thread_id', 'thread_id': thread_id})}\n\n"
        
        # 2. Load Existing State
        state = get_graph_state(thread_id)
        if not state:
            state = StoryGraphState(
                current_node_id="START",
                nodes={"START": GraphNode(id="START", type="story_white", content_goal="Start of adventure", next_node="node_A")}
            )
        
        current_node = state.nodes.get(state.current_node_id)
        if not current_node:
            current_node = state.nodes.get("START")
            state.current_node_id = "START"
        
        if not current_node:
            yield f"data: {json.dumps({'type': 'error', 'content': 'State corrupted'})}\n\n"
            return
        
        # 3. Story Logic
        next_id = None
        if current_node.type == "problem_red":
            is_correct = await check_answer_semantic(
                thread_id,
                request.message,
                current_node.problem_data['answer'],
                current_node.problem_data['question']
            )
            
            if is_correct:
                yield f"data: {json.dumps({'type': 'content', 'is_correct': True, 'content': 'Correct! '})}\n\n"
                next_id = current_node.next_success
            else:
                yield f"data: {json.dumps({'type': 'content', 'is_correct': False, 'content': 'Not quite. '})}\n\n"
                
                try:
                    hint_stream = await client.add_message(
                        thread_id=thread_id,
                        content=f"Hint for: {current_node.problem_data['question']}",
                        model_name=MODELS["tutor"],
                        stream=True
                    )
                    
                    async for chunk in hint_stream:
                        content = extract_content_string(chunk)
                        if content:
                            yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'content', 'content': f'Error generating hint: {e}'})}\n\n"
                return
        else:
            next_id = current_node.next_node
        
        # 4. Graph Expansion
        if next_id == "END_OF_BATCH" or next_id not in state.nodes:
            yield f"data: {json.dumps({'type': 'status', 'content': 'Generating new path...'})}\\n\\n"
            new_nodes = await generate_graph_expansion(thread_id, f"After {current_node.id}", "medium")
            if new_nodes:
                state.nodes.update(new_nodes)
                next_id = list(new_nodes.keys())[0]  # FIX: Get first key only
            else:
                yield f"data: {json.dumps({'type': 'error', 'content': 'Failed to generate story nodes.'})}\\n\\n"
                return

        
        # 5. Save & Stream Next Node
        state.current_node_id = next_id
        save_graph_state(thread_id, state)
        
        next_node = state.nodes[next_id]
        
        async for chunk in render_node_stream(thread_id, next_node):
            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
    
    return StreamingResponse(response_generator(), media_type="text/event-stream")
