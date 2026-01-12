"""
Migration script to add Backboard columns to the files table.
Run this once if you have an existing database.
"""
import sqlite3

def migrate():
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()

    # Check if columns exist
    c.execute("PRAGMA table_info(files)")
    columns = [col[1] for col in c.fetchall()]

    if 'backboard_doc_id' not in columns:
        print("Adding backboard_doc_id column...")
        c.execute("ALTER TABLE files ADD COLUMN backboard_doc_id TEXT")

    if 'backboard_status' not in columns:
        print("Adding backboard_status column...")
        c.execute("ALTER TABLE files ADD COLUMN backboard_status TEXT DEFAULT 'not_uploaded'")

    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
