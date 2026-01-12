from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pathlib import Path
import shutil
from datetime import datetime
import sqlite3
from pydantic import BaseModel
from .accounts import get_current_user, User, DB_PATH as ACCOUNTS_DB_PATH
import httpx
import os
from dotenv import load_dotenv
from utils import convert_document_to_markdown, can_convert

load_dotenv()

router = APIRouter(prefix="/teacher", tags=["Teacher"])

# Backboard API configuration
BACKBOARD_API_KEY = os.getenv("BACKBOARD_API_KEY")
BACKBOARD_BASE_URL = "https://app.backboard.io/api"
ASSISTANT_ID = "610acc47-b81b-4234-bda9-8a8a102ebca1"  # Same as in student.py

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
    Saves files locally AND uploads to Backboard assistant for RAG.
    """
    try:
        uploaded_files = []
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()

        for file in files:
            # Create a unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            safe_filename = f"{timestamp}_{file.filename}"
            file_path = UPLOAD_DIR / safe_filename

            # Read file content for Backboard upload
            file_content = await file.read()

            # Save locally
            with file_path.open("wb") as buffer:
                buffer.write(file_content)

            file_size = file_path.stat().st_size

            # Upload to Backboard assistant for RAG
            backboard_doc_id = None
            backboard_status = "not_uploaded"
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{BACKBOARD_BASE_URL}/assistants/{ASSISTANT_ID}/documents",
                        headers={"X-API-Key": BACKBOARD_API_KEY},
                        files={"file": (file.filename, file_content)},
                        timeout=60.0
                    )
                    if response.status_code == 200:
                        doc_data = response.json()
                        backboard_doc_id = doc_data.get("document_id")
                        backboard_status = doc_data.get("status", "pending")
                        print(f"Uploaded to Backboard: {backboard_doc_id} - {backboard_status}")
                    else:
                        print(f"Backboard upload failed: {response.status_code} - {response.text}")
                        backboard_status = "upload_failed"
            except Exception as e:
                print(f"Backboard upload error: {e}")
                backboard_status = "upload_error"

            # Save to database with Backboard document ID
            c.execute(
                """INSERT INTO files
                   (filename, original_filename, file_path, file_size, backboard_doc_id, backboard_status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (safe_filename, file.filename, str(file_path), file_size, backboard_doc_id, backboard_status)
            )
            file_id = c.lastrowid

            uploaded_files.append({
                "id": file_id,
                "filename": safe_filename,
                "original_filename": file.filename,
                "size": file_size,
                "path": str(file_path),
                "backboard_doc_id": backboard_doc_id,
                "backboard_status": backboard_status
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
    List all uploaded files with category and Backboard status information.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT f.id, f.filename, f.original_filename, f.file_size,
                   f.uploaded_at, f.is_active, f.category_id, c.name as category_name,
                   f.backboard_doc_id, f.backboard_status
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


@router.get("/files/{file_id}/backboard-status")
async def get_backboard_status(file_id: int):
    """
    Get the current Backboard processing status for a file.
    Fetches fresh status from Backboard API.
    If status is 'error', automatically converts with LlamaIndex and re-uploads.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, file_path, original_filename, backboard_doc_id, backboard_status FROM files WHERE id = ?", (file_id,))
        row = c.fetchone()

        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="File not found")

        backboard_doc_id = row['backboard_doc_id']
        if not backboard_doc_id:
            conn.close()
            return {"status": "not_uploaded", "message": "File not uploaded to Backboard"}

        # Fetch fresh status from Backboard
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BACKBOARD_BASE_URL}/documents/{backboard_doc_id}/status",
                headers={"X-API-Key": BACKBOARD_API_KEY},
                timeout=30.0
            )

            if response.status_code == 200:
                status_data = response.json()
                new_status = status_data.get("status", "unknown")

                # If error, auto-retry with LlamaIndex conversion
                # Skip if already retrying or already converted (status contains our markers)
                current_status = row['backboard_status']
                if new_status == "error" and can_convert(row['original_filename']) and current_status not in ('converting', 'retrying', 'conversion_failed'):
                    print(f"Auto-retrying file {file_id} with LlamaIndex conversion...")

                    # Update status immediately to prevent duplicate retries
                    c.execute("UPDATE files SET backboard_status = 'retrying' WHERE id = ?", (file_id,))
                    conn.commit()

                    try:
                        # Convert to markdown
                        new_filename, md_content = convert_document_to_markdown(
                            row['file_path'],
                            row['original_filename']
                        )

                        # Re-upload to Backboard
                        retry_response = await client.post(
                            f"{BACKBOARD_BASE_URL}/assistants/{ASSISTANT_ID}/documents",
                            headers={"X-API-Key": BACKBOARD_API_KEY},
                            files={"file": (new_filename, md_content, "text/markdown")},
                            timeout=60.0
                        )

                        if retry_response.status_code == 200:
                            doc_data = retry_response.json()
                            new_doc_id = doc_data.get("document_id")
                            new_status = doc_data.get("status", "pending")

                            c.execute(
                                "UPDATE files SET backboard_doc_id = ?, backboard_status = ? WHERE id = ?",
                                (new_doc_id, new_status, file_id)
                            )
                            conn.commit()
                            print(f"Auto-retry successful: {new_doc_id} - {new_status}")

                            conn.close()
                            return {
                                "file_id": file_id,
                                "backboard_doc_id": new_doc_id,
                                "status": new_status,
                                "auto_converted": True,
                                "converted_filename": new_filename
                            }
                        else:
                            new_status = "conversion_failed"
                            print(f"Auto-retry upload failed: {retry_response.text}")
                    except Exception as e:
                        new_status = "conversion_failed"
                        print(f"Auto-retry conversion error: {e}")

                # Update local database
                c.execute(
                    "UPDATE files SET backboard_status = ? WHERE id = ?",
                    (new_status, file_id)
                )
                conn.commit()
                conn.close()

                return {
                    "file_id": file_id,
                    "backboard_doc_id": backboard_doc_id,
                    "status": new_status,
                    "details": status_data
                }
            else:
                conn.close()
                return {
                    "file_id": file_id,
                    "backboard_doc_id": backboard_doc_id,
                    "status": "error",
                    "message": f"Failed to fetch status: {response.status_code}"
                }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backboard/documents")
async def list_backboard_documents():
    """
    List all documents attached to the Backboard assistant.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BACKBOARD_BASE_URL}/assistants/{ASSISTANT_ID}/documents",
                headers={"X-API-Key": BACKBOARD_API_KEY},
                timeout=30.0
            )

            if response.status_code == 200:
                documents = response.json()
                return {"documents": documents, "count": len(documents)}
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to fetch documents: {response.text}"
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/files/{file_id}/retry-backboard")
async def retry_backboard_upload(file_id: int):
    """
    Retry uploading a failed document to Backboard.
    If the original upload failed, converts PDF to markdown and re-uploads.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Get file info
        c.execute("""
            SELECT id, file_path, original_filename, backboard_doc_id, backboard_status
            FROM files WHERE id = ?
        """, (file_id,))
        row = c.fetchone()

        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="File not found")

        file_path = row['file_path']
        original_filename = row['original_filename']
        old_doc_id = row['backboard_doc_id']

        # Check if file can be converted
        if not can_convert(original_filename):
            conn.close()
            raise HTTPException(
                status_code=400,
                detail=f"Cannot convert {original_filename} - unsupported file type"
            )

        # Convert to markdown
        try:
            new_filename, md_content = convert_document_to_markdown(file_path, original_filename)
        except Exception as e:
            conn.close()
            raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")

        # Upload markdown to Backboard
        backboard_doc_id = None
        backboard_status = "not_uploaded"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BACKBOARD_BASE_URL}/assistants/{ASSISTANT_ID}/documents",
                    headers={"X-API-Key": BACKBOARD_API_KEY},
                    files={"file": (new_filename, md_content, "text/markdown")},
                    timeout=60.0
                )
                if response.status_code == 200:
                    doc_data = response.json()
                    backboard_doc_id = doc_data.get("document_id")
                    backboard_status = doc_data.get("status", "pending")
                    print(f"Retry upload to Backboard: {backboard_doc_id} - {backboard_status}")
                else:
                    print(f"Retry upload failed: {response.status_code} - {response.text}")
                    conn.close()
                    raise HTTPException(
                        status_code=500,
                        detail=f"Backboard upload failed: {response.text}"
                    )
        except HTTPException:
            raise
        except Exception as e:
            conn.close()
            raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")

        # Update database with new document ID
        c.execute("""
            UPDATE files
            SET backboard_doc_id = ?, backboard_status = ?
            WHERE id = ?
        """, (backboard_doc_id, backboard_status, file_id))
        conn.commit()
        conn.close()

        return {
            "message": "Document converted and re-uploaded successfully",
            "file_id": file_id,
            "converted_filename": new_filename,
            "backboard_doc_id": backboard_doc_id,
            "backboard_status": backboard_status,
            "old_doc_id": old_doc_id
        }

    except HTTPException:
        raise
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
    Delete a file from database, filesystem, AND Backboard.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Get file info before deleting
        c.execute("SELECT file_path, backboard_doc_id FROM files WHERE id = ?", (file_id,))
        row = c.fetchone()

        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="File not found")

        file_path = Path(row["file_path"])
        backboard_doc_id = row["backboard_doc_id"]

        # Delete from Backboard if it exists there
        if backboard_doc_id:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.delete(
                        f"{BACKBOARD_BASE_URL}/documents/{backboard_doc_id}",
                        headers={"X-API-Key": BACKBOARD_API_KEY},
                        timeout=30.0
                    )
                    if response.status_code == 200:
                        print(f"Deleted from Backboard: {backboard_doc_id}")
                    else:
                        print(f"Backboard delete failed: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Backboard delete error: {e}")

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
    Mark a file as active for AI context. Uploads to Backboard if not already there.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Get file info
        c.execute("""
            SELECT file_path, original_filename, backboard_doc_id
            FROM files WHERE id = ?
        """, (file_id,))
        row = c.fetchone()

        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="File not found")

        file_path = Path(row["file_path"])
        original_filename = row["original_filename"]
        backboard_doc_id = row["backboard_doc_id"]

        # Upload to Backboard if not already there
        if not backboard_doc_id:
            if not file_path.exists():
                conn.close()
                raise HTTPException(status_code=404, detail="File not found on disk")

            # Read file content
            with open(file_path, "rb") as f:
                file_content = f.read()

            backboard_status = "not_uploaded"
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{BACKBOARD_BASE_URL}/assistants/{ASSISTANT_ID}/documents",
                        headers={"X-API-Key": BACKBOARD_API_KEY},
                        files={"file": (original_filename, file_content)},
                        timeout=60.0
                    )
                    if response.status_code == 200:
                        doc_data = response.json()
                        backboard_doc_id = doc_data.get("document_id")
                        backboard_status = doc_data.get("status", "pending")
                        print(f"Uploaded to Backboard on activate: {backboard_doc_id} - {backboard_status}")
                    else:
                        print(f"Backboard upload failed on activate: {response.status_code} - {response.text}")
                        backboard_status = "upload_failed"
            except Exception as e:
                print(f"Backboard upload error on activate: {e}")
                backboard_status = "upload_error"

            # Update with backboard info
            c.execute("""
                UPDATE files
                SET is_active = 1, backboard_doc_id = ?, backboard_status = ?
                WHERE id = ?
            """, (backboard_doc_id, backboard_status, file_id))
        else:
            # Already on Backboard, just activate
            c.execute("UPDATE files SET is_active = 1 WHERE id = ?", (file_id,))

        conn.commit()
        conn.close()

        return {"message": "File activated successfully", "backboard_doc_id": backboard_doc_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/files/{file_id}/deactivate")
async def deactivate_file(file_id: int):
    """
    Remove a file from AI context. Also removes from Backboard so AI can't use it.
    """
    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Get backboard_doc_id before updating
        c.execute("SELECT backboard_doc_id FROM files WHERE id = ?", (file_id,))
        row = c.fetchone()

        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="File not found")

        backboard_doc_id = row["backboard_doc_id"]

        # Delete from Backboard if it exists there
        if backboard_doc_id:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.delete(
                        f"{BACKBOARD_BASE_URL}/documents/{backboard_doc_id}",
                        headers={"X-API-Key": BACKBOARD_API_KEY},
                        timeout=30.0
                    )
                    if response.status_code == 200:
                        print(f"Removed from Backboard: {backboard_doc_id}")
                    else:
                        print(f"Backboard remove failed: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"Backboard remove error: {e}")

        # Update database - clear backboard info since it's no longer there
        c.execute("""
            UPDATE files
            SET is_active = 0, backboard_doc_id = NULL, backboard_status = 'not_uploaded'
            WHERE id = ?
        """, (file_id,))
        conn.commit()
        conn.close()

        return {"message": "File deactivated and removed from AI"}
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


# ===== STUDENT CONVERSATION VIEWING ENDPOINTS =====

@router.get("/students/conversations")
async def get_all_student_conversations(current_user: User = Depends(get_current_user)):
    """
    Get all student conversations with student info. Teachers only.
    """
    if current_user.account_type != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can view student conversations")

    try:
        # Get all conversations with student info
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT id, student_id, thread_id, started_at, last_message_at, has_wrong_answers
            FROM student_conversations
            ORDER BY last_message_at DESC
        """)
        conversations = [dict(row) for row in c.fetchall()]
        conn.close()

        # Get student info for each conversation
        accounts_conn = sqlite3.connect(ACCOUNTS_DB_PATH)
        accounts_conn.row_factory = sqlite3.Row
        ac = accounts_conn.cursor()

        for conv in conversations:
            ac.execute(
                "SELECT username, full_name FROM accounts WHERE id = ?",
                (conv['student_id'],)
            )
            student = ac.fetchone()
            if student:
                conv['student_username'] = student['username']
                conv['student_name'] = student['full_name']
            else:
                conv['student_username'] = 'Unknown'
                conv['student_name'] = 'Unknown Student'

        accounts_conn.close()

        return {"conversations": conversations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/students/{student_id}/conversations")
async def get_student_conversations(student_id: int, current_user: User = Depends(get_current_user)):
    """
    Get all conversations for a specific student. Teachers only.
    """
    if current_user.account_type != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can view student conversations")

    try:
        # Get student info
        accounts_conn = sqlite3.connect(ACCOUNTS_DB_PATH)
        accounts_conn.row_factory = sqlite3.Row
        ac = accounts_conn.cursor()
        ac.execute("SELECT username, full_name FROM accounts WHERE id = ? AND account_type = 'student'", (student_id,))
        student = ac.fetchone()
        accounts_conn.close()

        if not student:
            raise HTTPException(status_code=404, detail="Student not found")

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
        conversations = [dict(row) for row in c.fetchall()]
        conn.close()

        return {
            "student": {
                "id": student_id,
                "username": student['username'],
                "full_name": student['full_name']
            },
            "conversations": conversations
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: int, current_user: User = Depends(get_current_user)):
    """
    Get all messages in a conversation. Teachers only.
    """
    if current_user.account_type != "teacher":
        raise HTTPException(status_code=403, detail="Only teachers can view conversation messages")

    try:
        conn = sqlite3.connect('chat_history.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Get conversation info
        c.execute("SELECT * FROM student_conversations WHERE id = ?", (conversation_id,))
        conversation = c.fetchone()

        if not conversation:
            conn.close()
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Get messages
        c.execute("""
            SELECT id, role, content, is_wrong, created_at
            FROM conversation_messages
            WHERE conversation_id = ?
            ORDER BY id ASC
        """, (conversation_id,))
        messages = [dict(row) for row in c.fetchall()]
        conn.close()

        # Get student info
        accounts_conn = sqlite3.connect(ACCOUNTS_DB_PATH)
        accounts_conn.row_factory = sqlite3.Row
        ac = accounts_conn.cursor()
        ac.execute("SELECT username, full_name FROM accounts WHERE id = ?", (conversation['student_id'],))
        student = ac.fetchone()
        accounts_conn.close()

        return {
            "conversation": {
                "id": conversation['id'],
                "student_id": conversation['student_id'],
                "student_username": student['username'] if student else 'Unknown',
                "student_name": student['full_name'] if student else 'Unknown',
                "thread_id": conversation['thread_id'],
                "started_at": conversation['started_at'],
                "last_message_at": conversation['last_message_at'],
                "has_wrong_answers": bool(conversation['has_wrong_answers'])
            },
            "messages": messages
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
