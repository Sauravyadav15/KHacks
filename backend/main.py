from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from routers import student, teacher, session
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
