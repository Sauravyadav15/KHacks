"""
Database migration to add assistant_config table for custom teacher instructions
"""
import sqlite3

def migrate():
    conn = sqlite3.connect('chat_history.db')
    c = conn.cursor()

    # Create assistant_config table
    c.execute('''
        CREATE TABLE IF NOT EXISTS assistant_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instruction_name TEXT NOT NULL,
            instruction_value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')

    # Also add thread_id column to messages table if it doesn't exist
    try:
        c.execute('ALTER TABLE messages ADD COLUMN thread_id TEXT')
        print("Added thread_id column to messages table")
    except sqlite3.OperationalError:
        print("thread_id column already exists in messages table")

    try:
        c.execute('ALTER TABLE messages ADD COLUMN timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        print("Added timestamp column to messages table")
    except sqlite3.OperationalError:
        print("timestamp column already exists in messages table")

    conn.commit()
    conn.close()

    print("Migration completed successfully!")
    print("assistant_config table created")

if __name__ == "__main__":
    migrate()
