from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from routers import student, teacher, session, accounts
import sqlite3

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(student.router)
app.include_router(teacher.router)
app.include_router(session.router)
app.include_router(accounts.router)

class MessageInput(BaseModel):
    text: str

def init_db():
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()

    # Chat messages table
    c.execute('''CREATE TABLE IF NOT EXISTS messages
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  role TEXT,
                  content TEXT)''')

    # Categories table
    c.execute('''CREATE TABLE IF NOT EXISTS categories
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  is_active BOOLEAN DEFAULT 1)''')

    # Files table
    c.execute('''CREATE TABLE IF NOT EXISTS files
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT NOT NULL,
                  original_filename TEXT NOT NULL,
                  file_path TEXT NOT NULL,
                  file_size INTEGER NOT NULL,
                  category_id INTEGER,
                  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  is_active BOOLEAN DEFAULT 0,
                  FOREIGN KEY (category_id) REFERENCES categories(id))''')

    # Sessions table
    c.execute('''CREATE TABLE IF NOT EXISTS sessions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  is_active BOOLEAN DEFAULT 0)''')

    # Session files junction table
    c.execute('''CREATE TABLE IF NOT EXISTS session_files
                 (session_id INTEGER NOT NULL,
                  file_id INTEGER NOT NULL,
                  added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (session_id, file_id),
                  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                  FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE)''')

    conn.commit()
    conn.close()

init_db()

@app.get("/chat")
async def get_chat_history():
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row  # Allows accessing columns by name
        c = conn.cursor()
        c.execute("SELECT role, content FROM messages ORDER BY id ASC")
        rows = c.fetchall()
        conn.close()
        
        # Convert to list of dicts for JSON response
        return [{"role": row["role"], "content": row["content"]} for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def save_chat(message: MessageInput):
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        
        # 1. Save User Message
        c.execute("INSERT INTO messages (role, content) VALUES (?, ?)", 
                  ('user', message.text))
        
        # 2. Generate Bot Reply (Mock logic for now)
        bot_reply = f"Story continues: You said '{message.text}'..."
        
        # 3. Save Bot Message
        c.execute("INSERT INTO messages (role, content) VALUES (?, ?)", 
                  ('bot', bot_reply))
        
        conn.commit()
        conn.close()

        return {"reply": bot_reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
