import sqlite3
import os
from contextlib import contextmanager

# The database file will be stored in the project root by default
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "app.db")

@contextmanager
def get_db_connection():
    """Yields a database connection and closes it automatically."""
    conn = sqlite3.connect(DB_PATH)
    # Enable row factory to access columns by name
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initializes the database and creates the required tables if they don't exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. User Profile Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT,
                email TEXT,
                phone TEXT,
                location TEXT,
                portfolio_url TEXT,
                github_url TEXT,
                years_experience INTEGER,
                work_authorization TEXT,
                custom_qa TEXT, -- Stored as JSON string
                resume_text TEXT,
                resume_parsed_data TEXT, -- Stored as JSON string
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 2. LLM Config Table (For Provider Failover)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS llm_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL, -- 'ollama', 'gemini', 'openrouter', 'omniroute'
                api_key TEXT,
                base_url TEXT,
                model_name TEXT NOT NULL,
                priority INTEGER DEFAULT 1, -- Fallback order (1 is highest)
                is_active BOOLEAN DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 3. Job Applications Table (For Tracking)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS job_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL, -- 'linkedin', 'indeed', etc.
                job_id TEXT NOT NULL, -- Platform specific job ID to prevent duplicates
                job_title TEXT,
                company TEXT,
                job_url TEXT,
                status TEXT DEFAULT 'scraped', -- 'scraped', 'matched', 'applied', 'skipped', 'failed', 'pending_approval'
                match_score INTEGER,
                applied_at TIMESTAMP,
                logs TEXT, -- Execution logs or JSON
                email_alias TEXT, -- Which email alias received updates
                UNIQUE(platform, job_id) -- Ensures we don't apply to the exact same job twice
            )
        ''')
        
        # 4. Email Credentials Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                imap_server TEXT NOT NULL,
                imap_port INTEGER DEFAULT 993,
                alias TEXT DEFAULT 'Main',
                email_address TEXT NOT NULL,
                app_password TEXT NOT NULL,
                last_scanned_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()

if __name__ == "__main__":
    init_db()
    print(f"Database initialized successfully at {DB_PATH}")
