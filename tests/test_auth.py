import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
from database.database import get_connection, init_schema
from utils.auth import (
    issue_jwt,
    verify_jwt,
    is_locked_out,
    record_attempt,
    generate_recovery_token,
    store_recovery_token,
    validate_recovery_token,
)
 
# ── Helpers ───────────────────────────────────────────────────────────────────
 
def ok(msg):   print(f"  ✓  {msg}")
def fail(msg): print(f"  ✗  {msg}"); sys.exit(1)
def header(msg): print(f"\n{'─'*50}\n  {msg}\n{'─'*50}")
 
def create_test_user(conn):
    """Create a throwaway user for auth tests. Returns user_id."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE username = 'auth_test_user'")
        cur.execute(
            "INSERT INTO users (username, email) VALUES (%s, %s) RETURNING id",
            ("auth_test_user", "auth_test@example.com")
        )
        user_id = cur.fetchone()[0]
    conn.commit()
    return user_id
 
def cleanup_test_user(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE username = 'auth_test_user'")
    conn.commit()
 
# ── Tests ─────────────────────────────────────────────────────────────────────
 
def test_jwt_issue_and_verify():
    header("TEST 1 — JWT Issue and Verify")
 
    token = issue_jwt(user_id=1, username="alice")
    ok(f"Token issued: {token[:40]}...")
 
    payload = verify_jwt(token)
    if payload is None:
        fail("verify_jwt returned None for a valid token")
 
    if payload["sub"] == "1" and payload["usr"] == "alice":
        ok(f"Payload correct: sub={payload['sub']} usr={payload['usr']}")
    else:
        fail(f"Payload wrong: {payload}")
 
 
def test_jwt_tampered():
    header("TEST 2 — Tampered JWT Rejected")
 
    token = issue_jwt(user_id=1, username="alice")
 
    # Flip one character in the signature (last segment)
    parts = token.split(".")
    tampered = parts[0] + "." + parts[1] + "." + parts[2][:-1] + "X"
 
    result = verify_jwt(tampered)
    if result is None:
        ok("Tampered token correctly rejected")
    else:
        fail("Tampered token was incorrectly accepted")
 
 
def test_jwt_expired():
    header("TEST 3 — Expired JWT Rejected")
 
    # Temporarily patch expiry to 0 hours to force immediate expiry
    import utils.auth as auth_module
    original = auth_module.JWT_EXPIRY_HOURS
    auth_module.JWT_EXPIRY_HOURS = 0
 
    from datetime import datetime, timedelta, timezone
    import jwt as pyjwt
 
    # Manually create an already-expired token
    now = datetime.now(timezone.utc)
    payload = {
        "sub": 1,
        "usr": "alice",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),   # expired 1 hour ago
    }
    expired_token = pyjwt.encode(
        payload,
        auth_module.JWT_SECRET,
        algorithm=auth_module.JWT_ALGORITHM
    )
 
    result = verify_jwt(expired_token)
    if result is None:
        ok("Expired token correctly rejected")
    else:
        fail("Expired token was incorrectly accepted")
 
    auth_module.JWT_EXPIRY_HOURS = original
 
 
def test_lockout():
    header("TEST 4 — Lockout After Failed Attempts")
 
    init_schema()
    conn = get_connection()
    try:
        user_id = create_test_user(conn)
 
        # Should not be locked out initially
        if not is_locked_out(conn, user_id):
            ok("User not locked out initially")
        else:
            fail("User incorrectly locked out before any attempts")
 
        # Record MAX_ATTEMPTS - 1 failures (should not lock yet)
        for i in range(2):
            record_attempt(conn, user_id, success=False)
        
        if not is_locked_out(conn, user_id):
            ok("User not locked out after 2 failures (threshold is 3)")
        else:
            fail("User locked out too early after only 2 failures")
 
        # Record one more failure — should now be locked
        record_attempt(conn, user_id, success=False)
 
        if is_locked_out(conn, user_id):
            ok("User correctly locked out after 3 failures")
        else:
            fail("User NOT locked out after 3 failures — lockout broken")
 
        # A successful login does NOT clear the lockout
        # (lockout is time-based, not reset by success)
        record_attempt(conn, user_id, success=True)
 
        if is_locked_out(conn, user_id):
            ok("Lockout persists correctly despite successful attempt")
        else:
            fail("Lockout was incorrectly cleared by successful attempt")
 
    finally:
        cleanup_test_user(conn)
        conn.close()
 
 
def test_recovery_token():
    header("TEST 5 — Recovery Token Full Flow")
 
    init_schema()
    conn = get_connection()
    try:
        user_id = create_test_user(conn)
 
        # Generate token
        plaintext, token_hash = generate_recovery_token()
        ok(f"Generated token: {plaintext[:20]}...")
        ok(f"Token hash:      {token_hash[:20]}...")
 
        if plaintext != token_hash:
            ok("Plaintext and hash are different (correct)")
        else:
            fail("Plaintext and hash are identical — hashing not working")
 
        # Store token
        store_recovery_token(conn, user_id, token_hash)
        ok("Token stored in DB")
 
        # Validate token — should succeed
        returned_user_id = validate_recovery_token(conn, token_hash)
        if returned_user_id == user_id:
            ok(f"Token validated — returned user_id={returned_user_id}")
        else:
            fail(f"validate_recovery_token returned {returned_user_id}, expected {user_id}")
 
        # Replay attempt — should fail (token already used)
        replay_result = validate_recovery_token(conn, token_hash)
        if replay_result is None:
            ok("Replay attack correctly rejected — token already used")
        else:
            fail("Replay attack succeeded — token reuse not prevented")
 
        # Wrong token — should fail
        wrong_result = validate_recovery_token(conn, "wrong_hash_value")
        if wrong_result is None:
            ok("Wrong token correctly rejected")
        else:
            fail("Wrong token was incorrectly accepted")
 
    finally:
        cleanup_test_user(conn)
        conn.close()
 
 
def test_recovery_token_expiry():
    header("TEST 6 — Expired Recovery Token Rejected")
 
    init_schema()
    conn = get_connection()
    try:
        user_id = create_test_user(conn)
 
        # Manually insert an already-expired token
        import hashlib
        from datetime import datetime, timedelta, timezone
 
        plaintext = "expired_test_token_12345"
        token_hash = hashlib.sha256(plaintext.encode()).hexdigest()
 
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO recovery_tokens (user_id, token_hash, expires_at, used)
                VALUES (%s, %s, %s, FALSE)
                """,
                (
                    user_id,
                    token_hash,
                    datetime.now(timezone.utc) - timedelta(hours=1)  # expired 1hr ago
                )
            )
        conn.commit()
 
        result = validate_recovery_token(conn, token_hash)
        if result is None:
            ok("Expired recovery token correctly rejected")
        else:
            fail("Expired recovery token was incorrectly accepted")
 
    finally:
        cleanup_test_user(conn)
        conn.close()
 
 
# ── Run all tests ─────────────────────────────────────────────────────────────
 
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════╗")
    print("║        AUTH.PY TEST SUITE            ║")
    print("╚══════════════════════════════════════╝")
 
    test_jwt_issue_and_verify()
    test_jwt_tampered()
    test_jwt_expired()
    test_lockout()
    test_recovery_token()
    test_recovery_token_expiry()
 
    print("\n✓ All auth tests passed!\n")
