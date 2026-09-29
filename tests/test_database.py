import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
from database.database import get_connection, init_schema
 
# ── Helpers ──────────────────────────────────────────────────────────────────
 
def ok(msg):
    print(f"  ✓  {msg}")
 
def fail(msg):
    print(f"  ✗  {msg}")
    sys.exit(1)
 
def header(msg):
    print(f"\n{'─'*50}\n  {msg}\n{'─'*50}")
 
# ── Tests ─────────────────────────────────────────────────────────────────────
 
def test_connection():
    header("TEST 1 — Database Connection")
    try:
        conn = get_connection()
        conn.close()
        ok("Connected to database successfully")
    except Exception as e:
        fail(f"Could not connect: {e}")
 
 
def test_schema():
    header("TEST 2 — Schema Initialisation")
    try:
        init_schema()
        ok("init_schema() ran without errors")
    except Exception as e:
        fail(f"Schema init failed: {e}")
 
    # Verify all 4 tables actually exist
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for table in ["users", "face_embeddings", "login_attempts", "recovery_tokens"]:
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s)",
                    (table,)
                )
                exists = cur.fetchone()[0]
                if exists:
                    ok(f"Table '{table}' exists")
                else:
                    fail(f"Table '{table}' was NOT created")
    finally:
        conn.close()
 
 
def test_insert_and_read():
    header("TEST 3 — Insert and Read User")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Clean up any leftover test data first
            cur.execute("DELETE FROM users WHERE username = 'test_debug_user'")
 
            # Insert a test user
            cur.execute(
                "INSERT INTO users (username, email) VALUES (%s, %s) RETURNING id",
                ("test_debug_user", "test_debug@example.com")
            )
            user_id = cur.fetchone()[0]
            ok(f"Inserted test user with id={user_id}")
 
            # Read it back
            cur.execute("SELECT username, email FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
 
            if row[0] == "test_debug_user" and row[1] == "test_debug@example.com":
                ok(f"Read back username='{row[0]}' email='{row[1]}'")
            else:
                fail(f"Read back wrong data: {row}")
 
        conn.commit()
    except Exception as e:
        conn.rollback()
        fail(f"Insert/read failed: {e}")
    finally:
        conn.close()
 
 
def test_cascade_delete():
    header("TEST 4 — ON DELETE CASCADE")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Get test user id
            cur.execute("SELECT id FROM users WHERE username = 'test_debug_user'")
            row = cur.fetchone()
            if not row:
                fail("Test user not found — run test_insert_and_read first")
            user_id = row[0]
 
            # Insert a login attempt linked to that user
            cur.execute(
                "INSERT INTO login_attempts (user_id, success) VALUES (%s, FALSE)",
                (user_id,)
            )
            ok(f"Inserted login attempt for user_id={user_id}")
 
            # Delete the user
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            ok(f"Deleted user id={user_id}")
 
            # Check the login attempt was auto-deleted
            cur.execute(
                "SELECT COUNT(*) FROM login_attempts WHERE user_id = %s",
                (user_id,)
            )
            count = cur.fetchone()[0]
            if count == 0:
                ok("login_attempts CASCADE deleted successfully")
            else:
                fail(f"Expected 0 login_attempts, found {count}")
 
        conn.commit()
    except Exception as e:
        conn.rollback()
        fail(f"Cascade delete test failed: {e}")
    finally:
        conn.close()
 
 
def test_unique_constraint():
    header("TEST 5 — UNIQUE Constraint")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Clean up first
            cur.execute("DELETE FROM users WHERE username = 'unique_test_user'")
            cur.execute(
                "INSERT INTO users (username, email) VALUES (%s, %s)",
                ("unique_test_user", "unique_test@example.com")
            )
        conn.commit()
        ok("First insert succeeded")
 
        # Try inserting duplicate username
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username, email) VALUES (%s, %s)",
                    ("unique_test_user", "different@example.com")
                )
            conn.commit()
            fail("Duplicate username should have been rejected")
        except Exception:
            conn.rollback()
            ok("Duplicate username correctly rejected by UNIQUE constraint")
 
        # Cleanup
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username = 'unique_test_user'")
        conn.commit()
 
    finally:
        conn.close()
 
 
# ── Run all tests ─────────────────────────────────────────────────────────────
 
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════╗")
    print("║       DATABASE.PY TEST SUITE         ║")
    print("╚══════════════════════════════════════╝")
 
    test_connection()
    test_schema()
    test_insert_and_read()
    test_cascade_delete()
    test_unique_constraint()
 
    print("\n✓ All database tests passed!\n")