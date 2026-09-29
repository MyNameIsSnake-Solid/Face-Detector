import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", 1))

MAX_ATTEMPTS = int (os.getenv("MAX_LOGIN_ATTEMPTS", 3))
LOCKOUT_MINUTES = int(os.getenv("LOCKOUT_MINUTES", 15))


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def issue_jwt (user_id: int, username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "usr": username, 
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=JWT_EXPIRY_HOURS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError as e:
        print(f"  [DEBUG] Invalid token: {e}")
        return None
    

# ---------------------------------------------------------------------------
# Lockout
# ---------------------------------------------------------------------------

def is_locked_out(conn, user_id: int) -> bool:

    cutoff = datetime.now(timezone.utc) - timedelta(minutes = LOCKOUT_MINUTES)
    with conn.cursor() as cur:
        cur.execute(
        """
        SELECT COUNT(*) FROM login_attempts
        WHERE user_id = %s
        AND success = FALSE
        AND attempted_at > %s
        """,
            (user_id, cutoff),
        )
        count = cur.fetchone()[0]
    return count >= MAX_ATTEMPTS

def record_attempt(conn, user_id: int, success: bool):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO login_attempts (user_id, success) VALUES (%s, %s)",
            (user_id, success),
        )
    conn.commit()

# ---------------------------------------------------------------------------
# Recovery tokens
# ---------------------------------------------------------------------------

def generate_recovery_token() -> tuple[str, str]:
    
    plaintext = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    return plaintext, token_hash

def store_recovery_token(conn, user_id: int, token_hash: str):
    
    expiry = datetime.now(timezone.utc) + timedelta(
        minutes=int(os.getenv("RECOVERY_TOKEN_EXPIRY_MINUTES", 15))
    )
    with conn.cursor() as cur:
        cur.execute (
        "UPDATE recovery_tokens SET used = TRUE WHERE user_id = %s AND used = FALSE",
            (user_id, ),
        )
        cur.execute (
            "INSERT INTO recovery_tokens (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
            (user_id, token_hash, expiry),
        )
    conn.commit()

def validate_recovery_token(conn, token_hash: str) -> int | None:

   with conn.cursor() as cur:
        cur.execute (
            "SELECT id, user_id, expires_at, used FROM recovery_tokens WHERE token_hash = %s",
            (token_hash, ),
        )
        row = cur.fetchone()

   if row is None:
        return None
   
   token_id, user_id, expires_at, used = row

   if used:
       return None

   if datetime.now(timezone.utc) > expires_at:
       return None
   
   with conn.cursor() as cur:
       cur.execute(
        "UPDATE recovery_tokens SET used = TRUE WHERE id = %s",
        (token_id,),    
                   )
   conn.commit()
   
   return user_id
   