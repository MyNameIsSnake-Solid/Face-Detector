import hashlib
import json

import psycopg2.extras
from flask import Blueprint, jsonify, request

from database.database import get_connection

from pipeline.embedding import (
    VALID_DIRECTIONS,
    compare_embeddings,
    embeddings_from_db_rows, 
    generate_embedding,
    validate_direction,
    validate_registration_quality,
)

from utils.auth import (
    generate_recovery_token,
    is_locked_out,
    issue_jwt,
    record_attempt,
    store_recovery_token,
    validate_recovery_token,
)

bp  = Blueprint("auth", __name__)

# ---------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _get_user_by_username(cur, username: str):
    cur.execute(
        "SELECT id, username, email FROM users WHERE username = %s", (username, )
    )
    return cur.fetchone()

def _get_embeddings(cur, user_id: int):
    cur.execute(
        "SELECT direction, embedding FROM face_embeddings WHERE user_id = %s", (user_id, )
    )
    return cur.fetchall()

def _error(message: str, code: int = 400):
    return jsonify({"success": False, "error": message}), code

def _ok(payload: dict):
    return jsonify({"success": True, **payload}), 200

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@bp.route("/register/init", methods=["POST"])
def register_init():

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower()
    email = (data.get("email") or "").strip().lower()

    if not username or not email:
        return _error("username and email are required.")
    
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            existing = _get_user_by_username(cur, username)
            if existing:
                return _error("Username already taken")
            
            cur.execute(
                "INSERT INTO users (username, email) VALUES (%s, %s) RETURNING id",
                (username, email),
            )
            user_id = cur.fetchone()["id"]
        conn.commit()
    finally:
        conn.close()

    return _ok({
        "user_id": user_id,
        "message": "Account created. Please submit photos for all 5 directions.",
        "directions_required": sorted(VALID_DIRECTIONS),
    })
    
@bp.route("/register/photo", methods=["POST"])
def register_photo():

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower()
    direction = (data.get("direction") or "").strip().lower()
    image = data.get("image")

    if not all ([username, direction, image]):
        return _error("username, direction, and images are required.")
    
    if not validate_direction(direction):
        return _error(f"Invalid direction. Must be one of: {sorted(VALID_DIRECTIONS)}")
    
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            user = _get_user_by_username(cur, username)
            if not user: 
                return _error("User not found.", 404)
            
            result = generate_embedding(image)
            if not result["success"]:
                return _error(result["error"])
            
            cur.execute(
                """
                INSERT INTO face_embeddings (user_id, direction, embedding)
                VALUES (%s, %s, %s::jsonb)
                ON CONFLICT (user_id, direction)
                DO UPDATE SET embedding = EXCLUDED.embedding, created_at = NOW()
                """,
                (user["id"], direction, json.dumps(result["embedding"])),
            )

            cur.execute(
                "SELECT direction FROM face_embeddings WHERE user_id = %s",
                (user["id"],),
            )
            submitted = {row["direction"] for row in cur.fetchall()}
            remaining = sorted(VALID_DIRECTIONS - submitted)

        conn.commit()
    finally:
        conn.close()

    return _ok({
        "direction_saved": direction,
        "directions_remaining": remaining,
        "registration_complete": len(remaining) == 0,
    })

@bp.route ("/register/verify", methods = ["POST"])
def register_verify():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower()
    image = data.get("image")

    if not username or not image:
        return _error("username and image are required.")
    
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            user = _get_user_by_username(cur, username)

            if not user:
                return _error("User not found.", 404)
            rows = _get_embeddings(cur, user["id"])

            if len(rows) < 5:
                return _error("Not all 5 direction photos have been submitted yet.")
            
            all_embeddings = [row["embedding"] for row in rows]
            quality = validate_registration_quality(all_embeddings)
            if not quality["valid"]:
                return _error(quality["message"])
            
            result = generate_embedding(image)
            if not result["success"]:
                return _error(result["error"])
            
            stored = embeddings_from_db_rows(rows)
            comparison = compare_embeddings(result["embedding"], stored)
    finally:
        conn.close()
    
    if not comparison ["match"]:
        return _error(
            f"Verification failed (confidence: {comparison['confidence']:.0%})."
            "Try re-submitting your photo in better lighting."
        )
    
    return _ok({
        "message": "Registration verified. You can now log in.",
        "confidence": comparison["confidence"],
    })

# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@bp.route ("/login", methods = ["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower()
    image = data.get("image")

    if not username or not image:
        return _error("username and image are required.")
    
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            user = _get_user_by_username(cur, username)
            if not user:
                return _error("Face not recognised. Please try again.", 401)
            
            if is_locked_out(conn, user["id"]):
                return _error(
                    "Account temporarily locked due to too many failed attempts. "
                    "Please use account recovery or try again later.",
                    429,
                )
            
            rows = _get_embeddings(cur, user["id"])

        if not rows:
            return _error("No face data registered for this account.", 401)
        
        result = generate_embedding(image)
        if not result ["success"]:
            return _error(result["error"])
        
        stored = embeddings_from_db_rows(rows)
        comparison = compare_embeddings(result["embedding"], stored)

        if comparison["match"]:
            record_attempt(conn, user["id"], success=True)
            token = issue_jwt(user["id"], user["username"])

            return _ok({
                "token": token,
                "username": user["username"],
                "confidence": comparison["confidence"],
            })
        else:
            record_attempt(conn, user["id"], success=False)
            return jsonify({
                "success": False,
                "error": "Face not recognised. Please try again.", 
                "confidence": comparison["confidence"], 
            }), 401
        
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Account recovery
# ---------------------------------------------------------------------------

@bp.route ("/recovery/request", methods = ["POST"])
def recovery_request():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip().lower()

    if not username:
        return _error("username is required.")
    
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            user = _get_user_by_username(cur, username)

        if user:
            plaintext, token_hash = generate_recovery_token()
            store_recovery_token(conn, user["id"], token_hash)

            print(f"[DEV] Recovery link: /recovery/re-register?token={plaintext}")
        
    finally: 
        conn.close()

    return  _ok({
        "message": "If that username exists, a recovery email has been sent."
    })
    
@bp.route ("/recovery/re-register", methods = ["POST"])
def recovery_re_register():
    data = request.get_json(silent=True) or {}
    token_plaintext = data.get("token")
    direction = (data.get("direction") or "").strip().lower()
    image = data.get("image")

    if not all([token_plaintext, direction, image]):
        return _error("token, direction, and image are required.")
    
    if not validate_direction(direction):
        return _error(f"Invalid direction. Must be one of: {sorted(VALID_DIRECTIONS)}")
    
    token_hash = hashlib.sha256(token_plaintext.encode()).hexdigest()

    conn = get_connection()
    try: 
        user_id = validate_recovery_token(conn, token_hash)
        if not user_id:
            return _error("Recovery token is invalid or has expired.", 401)
        
        result = generate_embedding(image)
        if not result["success"]:
            return _error(result["error"])
        
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO face_embeddings (user_id, direction, embedding)
                VALUES (%s, %s, %s::jsonb)
                ON CONFLICT (user_id, direction)
                DO UPDATE SET embedding = EXCLUDED.embedding, created_at = NOW()
                """,
                (user_id, direction, json.dumps(result["embedding"])),
            )
            cur.execute(
                "SELECT direction FROM face_embeddings WHERE user_id = %s", (user_id,)
            )
            submitted = {row["direction"] for row in cur.fetchall()}
            remaining = sorted(VALID_DIRECTIONS - submitted)

        conn.commit()
    finally:
        conn.close()
        
    return _ok ({
        "direction_saved": direction,
        "directions_remaining": remaining,
        "registration_complete": len(remaining) == 0,
        })