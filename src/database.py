import json
import psycopg
from src.config import DATABASE_URL

def initialize_database():
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector;") # create vector extension if not exists
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS curricula (
                    id SERIAL PRIMARY KEY,
                    file_reference TEXT,
                    raw_text TEXT,
                    llm_data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

# adds a new CV entry to the database and returns the generated ID
def insert_cv_data(file_path: str, raw_text: str, llm_data: dict) -> int:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO curricula (file_reference, raw_text, llm_data)
                VALUES (%s, %s, %s)
                RETURNING id;
            """,(file_path, raw_text, json.dumps(llm_data)))
            cv_id = cur.fetchone()[0]
            conn.commit()
    return cv_id