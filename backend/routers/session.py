from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3

router = APIRouter(prefix="/sessions", tags=["Sessions"])

class SessionCreate(BaseModel):
    name: str

class SessionAddFiles(BaseModel):
    file_ids: list[int]

@router.get("")
async def list_sessions():
    """
    List all sessions.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM sessions ORDER BY created_at DESC")
        rows = c.fetchall()
        conn.close()

        sessions = [dict(row) for row in rows]
        return {"sessions": sessions, "count": len(sessions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
async def create_session(session: SessionCreate):
    """
    Create a new session.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute("INSERT INTO sessions (name) VALUES (?)", (session.name,))
        session_id = c.lastrowid
        conn.commit()
        conn.close()

        return {
            "message": "Session created successfully",
            "id": session_id,
            "name": session.name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{session_id}")
async def get_session(session_id: int):
    """
    Get session details including all files in the session.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Get session info
        c.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session_row = c.fetchone()

        if not session_row:
            conn.close()
            raise HTTPException(status_code=404, detail="Session not found")

        # Get files in this session
        c.execute("""
            SELECT f.id, f.filename, f.original_filename, f.file_size,
                   sf.added_at, c.name as category_name
            FROM session_files sf
            JOIN files f ON sf.file_id = f.id
            LEFT JOIN categories c ON f.category_id = c.id
            WHERE sf.session_id = ?
            ORDER BY sf.added_at ASC
        """, (session_id,))
        file_rows = c.fetchall()
        conn.close()

        session = dict(session_row)
        session["files"] = [dict(row) for row in file_rows]

        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{session_id}/activate")
async def activate_session(session_id: int):
    """
    Set a session as active (deactivates all other sessions).
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()

        # Deactivate all sessions
        c.execute("UPDATE sessions SET is_active = 0")

        # Activate this session
        c.execute("UPDATE sessions SET is_active = 1 WHERE id = ?", (session_id,))

        if c.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Session not found")

        conn.commit()
        conn.close()

        return {"message": "Session activated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{session_id}/files")
async def add_files_to_session(session_id: int, data: SessionAddFiles):
    """
    Add files to a session with duplicate prevention.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()

        # Check if session exists
        c.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
        if not c.fetchone():
            conn.close()
            raise HTTPException(status_code=404, detail="Session not found")

        added = []
        skipped = []

        for file_id in data.file_ids:
            # Check if file exists
            c.execute("SELECT id FROM files WHERE id = ?", (file_id,))
            if not c.fetchone():
                skipped.append({"file_id": file_id, "reason": "File not found"})
                continue

            # Check if already in session
            c.execute("SELECT 1 FROM session_files WHERE session_id = ? AND file_id = ?",
                      (session_id, file_id))
            if c.fetchone():
                skipped.append({"file_id": file_id, "reason": "Already in session"})
                continue

            # Add to session
            c.execute("INSERT INTO session_files (session_id, file_id) VALUES (?, ?)",
                      (session_id, file_id))
            added.append(file_id)

        conn.commit()
        conn.close()

        return {
            "message": f"Added {len(added)} file(s) to session",
            "added": added,
            "skipped": skipped
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{session_id}/files/{file_id}")
async def remove_file_from_session(session_id: int, file_id: int):
    """
    Remove a file from a session.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute("DELETE FROM session_files WHERE session_id = ? AND file_id = ?",
                  (session_id, file_id))

        if c.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="File not found in session")

        conn.commit()
        conn.close()

        return {"message": "File removed from session successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active/current")
async def get_active_session():
    """
    Get the currently active session with all its files.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Get active session
        c.execute("SELECT * FROM sessions WHERE is_active = 1 LIMIT 1")
        session_row = c.fetchone()

        if not session_row:
            conn.close()
            return {"session": None, "files": []}

        session_id = session_row["id"]

        # Get files in active session
        c.execute("""
            SELECT f.id, f.filename, f.original_filename, f.file_path, f.file_size
            FROM session_files sf
            JOIN files f ON sf.file_id = f.id
            WHERE sf.session_id = ?
            ORDER BY sf.added_at ASC
        """, (session_id,))
        file_rows = c.fetchall()
        conn.close()

        session = dict(session_row)
        session["files"] = [dict(row) for row in file_rows]

        return session
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
