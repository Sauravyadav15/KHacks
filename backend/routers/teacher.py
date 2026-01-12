from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import shutil
from datetime import datetime
import sqlite3
from pydantic import BaseModel

router = APIRouter(prefix="/teacher", tags=["Teacher"])

class CategoryCreate(BaseModel):
    name: str

class FileCategoryUpdate(BaseModel):
    category_id: int | None

class InstructionCreate(BaseModel):
    name: str
    value: str

# Create uploads directory relative to backend folder
UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

@router.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    """
    Upload one or more lesson files.
    Saves the files to the uploads directory with timestamps and records in database.
    """
    try:
        uploaded_files = []
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()

        for file in files:
            # Create a unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")  # Added microseconds for uniqueness
            safe_filename = f"{timestamp}_{file.filename}"
            file_path = UPLOAD_DIR / safe_filename

            # Save the file
            with file_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            file_size = file_path.stat().st_size

            # Save to database
            c.execute(
                "INSERT INTO files (filename, original_filename, file_path, file_size) VALUES (?, ?, ?, ?)",
                (safe_filename, file.filename, str(file_path), file_size)
            )
            file_id = c.lastrowid

            uploaded_files.append({
                "id": file_id,
                "filename": safe_filename,
                "original_filename": file.filename,
                "size": file_size,
                "path": str(file_path)
            })

        conn.commit()
        conn.close()

        return {
            "message": f"{len(uploaded_files)} file(s) uploaded successfully",
            "files": uploaded_files,
            "count": len(uploaded_files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/files")
async def list_files():
    """
    List all uploaded files with category information.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT f.id, f.filename, f.original_filename, f.file_size,
                   f.uploaded_at, f.is_active, f.category_id, c.name as category_name
            FROM files f
            LEFT JOIN categories c ON f.category_id = c.id
            ORDER BY f.uploaded_at DESC
        """)
        rows = c.fetchall()
        conn.close()

        files = [dict(row) for row in rows]
        return {"files": files, "count": len(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories")
async def list_categories():
    """
    List all categories.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM categories ORDER BY created_at ASC")
        rows = c.fetchall()
        conn.close()

        categories = [dict(row) for row in rows]
        return {"categories": categories, "count": len(categories)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/categories")
async def create_category(category: CategoryCreate):
    """
    Create a new category.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute("INSERT INTO categories (name) VALUES (?)", (category.name,))
        category_id = c.lastrowid
        conn.commit()
        conn.close()

        return {
            "message": "Category created successfully",
            "id": category_id,
            "name": category.name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/categories/{category_id}")
async def delete_category(category_id: int):
    """
    Delete a category. Files in this category will become uncategorized.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()

        # Set category_id to NULL for all files in this category
        c.execute("UPDATE files SET category_id = NULL WHERE category_id = ?", (category_id,))

        # Delete the category
        c.execute("DELETE FROM categories WHERE id = ?", (category_id,))

        if c.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Category not found")

        conn.commit()
        conn.close()

        return {"message": "Category deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/categories/{category_id}/activate")
async def activate_category(category_id: int):
    """
    Activate a category.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute("UPDATE categories SET is_active = 1 WHERE id = ?", (category_id,))

        if c.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Category not found")

        conn.commit()
        conn.close()

        return {"message": "Category activated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/categories/{category_id}/deactivate")
async def deactivate_category(category_id: int):
    """
    Deactivate a category.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute("UPDATE categories SET is_active = 0 WHERE id = ?", (category_id,))

        if c.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Category not found")

        conn.commit()
        conn.close()

        return {"message": "Category deactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/files/{file_id}/category")
async def update_file_category(file_id: int, update: FileCategoryUpdate):
    """
    Move a file to a category (or remove from category if category_id is None).
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute("UPDATE files SET category_id = ? WHERE id = ?", (update.category_id, file_id))

        if c.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="File not found")

        conn.commit()
        conn.close()

        return {"message": "File category updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/files/{file_id}")
async def delete_file(file_id: int):
    """
    Delete a file from database and filesystem.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Get file path before deleting
        c.execute("SELECT file_path FROM files WHERE id = ?", (file_id,))
        row = c.fetchone()

        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="File not found")

        file_path = Path(row["file_path"])

        # Delete from database
        c.execute("DELETE FROM files WHERE id = ?", (file_id,))
        conn.commit()
        conn.close()

        # Delete physical file
        if file_path.exists():
            file_path.unlink()

        return {"message": "File deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/files/{file_id}/activate")
async def activate_file(file_id: int):
    """
    Mark a file as active for AI context.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute("UPDATE files SET is_active = 1 WHERE id = ?", (file_id,))

        if c.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="File not found")

        conn.commit()
        conn.close()

        return {"message": "File activated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/files/{file_id}/deactivate")
async def deactivate_file(file_id: int):
    """
    Remove a file from AI context.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute("UPDATE files SET is_active = 0 WHERE id = ?", (file_id,))

        if c.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="File not found")

        conn.commit()
        conn.close()

        return {"message": "File deactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files/active")
async def get_active_files():
    """
    Get all files marked as active for AI context.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT f.id, f.filename, f.original_filename, f.file_path, f.file_size
            FROM files f
            WHERE f.is_active = 1
            ORDER BY f.uploaded_at ASC
        """)
        rows = c.fetchall()
        conn.close()

        files = [dict(row) for row in rows]
        return {"files": files, "count": len(files)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Helper functions for student.py
def get_active_file_paths() -> list[str]:
    """
    Get list of file paths for all active files.
    This is used by student.py to upload files to new threads.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT file_path
            FROM files
            WHERE is_active = 1
            ORDER BY uploaded_at ASC
        """)
        rows = c.fetchall()
        conn.close()
        return [row['file_path'] for row in rows]
    except Exception as e:
        print(f"Error getting active file paths: {e}")
        return []

def get_active_instructions() -> str:
    """
    Get all active custom instructions formatted for prompt injection.
    This is used by student.py to add teacher rules to AI prompts.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT instruction_value
            FROM assistant_config
            WHERE is_active = 1
            ORDER BY created_at ASC
        """)
        rows = c.fetchall()
        conn.close()

        if not rows:
            return ""

        instruction_text = "\n".join([f"- {row['instruction_value']}" for row in rows])
        return f"\n\nADDITIONAL TEACHER INSTRUCTIONS:\n{instruction_text}"
    except Exception as e:
        print(f"Error getting active instructions: {e}")
        return ""

# ===== CONFIGURATION ENDPOINTS =====

@router.get("/config/instructions")
async def get_instructions():
    """
    Get all custom instructions for the assistant.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT id, instruction_name, instruction_value, is_active, created_at
            FROM assistant_config
            ORDER BY created_at DESC
        """)
        rows = c.fetchall()
        conn.close()
        instructions = [dict(row) for row in rows]
        return {"instructions": instructions, "count": len(instructions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config/instructions")
async def create_instruction(instruction: InstructionCreate):
    """
    Create a new custom instruction.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute("""
            INSERT INTO assistant_config (instruction_name, instruction_value)
            VALUES (?, ?)
        """, (instruction.name, instruction.value))
        instruction_id = c.lastrowid
        conn.commit()
        conn.close()
        return {
            "message": "Instruction created successfully",
            "id": instruction_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config/instructions/{instruction_id}/toggle")
async def toggle_instruction(instruction_id: int):
    """
    Toggle an instruction's active status.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute("""
            UPDATE assistant_config
            SET is_active = NOT is_active
            WHERE id = ?
        """, (instruction_id,))

        if c.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Instruction not found")

        conn.commit()
        conn.close()
        return {"message": "Instruction toggled successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/config/instructions/{instruction_id}")
async def delete_instruction(instruction_id: int):
    """
    Delete a custom instruction.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute("DELETE FROM assistant_config WHERE id = ?", (instruction_id,))

        if c.rowcount == 0:
            conn.close()
            raise HTTPException(status_code=404, detail="Instruction not found")

        conn.commit()
        conn.close()
        return {"message": "Instruction deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
