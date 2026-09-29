import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

def get_connection():

    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME", "face_auth"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )

def init_schema():

    schema = """ 
    CREATE TABLE IF NOT EXISTS users (
        id  SERIAL PRIMARY KEY,
        username    VARCHAR(64) UNIQUE NOT NULL,
        email   VARCHAR(255) UNIQUE NOT NULL,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS face_embeddings (
        id  SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) on DELETE CASCADE,
        direction   VARCHAR(64) NOT NULL,
        embedding   JSONB NOT NULL,
        created_at  TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (user_id, direction)
    );

    CREATE TABLE IF NOT EXISTS login_attempts (
        id  SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) on DELETE CASCADE,
        attempted_at  TIMESTAMPTZ DEFAULT NOW(),
        success BOOLEAN NOT NULL DEFAULT FALSE
    );

    CREATE TABLE IF NOT EXISTS recovery_tokens (
        id  SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) on DELETE CASCADE,
        token_hash   VARCHAR(64) NOT NULL,
        expires_at  TIMESTAMPTZ NOT NULL,
        used BOOLEAN NOT NULL DEFAULT FALSE,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    );
    
    """

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(schema)
        conn.commit()
        print("[DB] Schema initalised successfully.")
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"[DB] Schema init failed: {e}")
    finally:
        conn.close()