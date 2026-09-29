import base64
import os
import tempfile

import cv2
import numpy as np
from deepface import DeepFace

THRESHOLD = float(os.getenv("FACE_DISTANCE_THRESHOLD", 0.68))

MODEL_NAME = "ArcFace"
DETECTOR_BACKEND = "opencv"

VALID_DIRECTIONS = {"center", "left", "right", "up", "down"}

# ---------------------------------------------------------------------------
# Image decoding
# ---------------------------------------------------------------------------

def decode_image_to_file(b64_string: str) -> str:

    if "," in b64_string:
        b64_string =  b64_string.split(",", 1)[1]

    image_bytes = base64.b64decode(b64_string)
    np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError("Could not decode image — ensure JPEG or PNG is sent.")
    
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    cv2.imwrite(tmp.name, img)
    return tmp.name

# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------

def generate_embedding(b64_image: str) -> dict:
    
    try:
        img_path = decode_image_to_file(b64_image)

    except ValueError as e:
        return {"success": False, "embeddings": None, "error": str(e), "face_count": 0}
    
    try:
        faces = DeepFace.extract_faces(
            img_path=img_path,
            detector_backend=DETECTOR_BACKEND,
            enforce_detection=True,
        )

        face_count = len(faces)

        if face_count == 0:
            return {
                "success": False, 
                "embeddings": None,
                "error": "No face detected. Ensure your face is well-lit and centred.",
                "face_count": 0,
            }
        
        if face_count > 1:
            return {
                "success": False, 
                "embeddings": None,
                "error": f"{face_count} faces detected. Only one face should be visible.",
                "face_count": face_count,
            }
        
        result = DeepFace.represent(
            img_path=img_path,
            model_name=MODEL_NAME,
            detector_backend=DETECTOR_BACKEND,
            enforce_detection=True,
        )

        embedding = result[0]["embedding"]

        return {
            "success": True,
            "embedding": embedding,
            "error": None,
            "face_count": 1,
        }
    
    except Exception as e:
        error_msg = str(e)
        if "Face could not be detected" in error_msg or "No face" in error_msg:
            return {
                "success": False,
                "embeddings": None,
                "error": "No face detected. Ensure your face is well-lit and centered.",
                "face_count": 0,
            }
        return {
            "success": False,
            "embeddings": None,
            "error": f"Face processing error: {error_msg}",
            "face_count": 0,
        }

    finally:
        try:
            os.unlink(img_path)
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Embedding comparison
# ---------------------------------------------------------------------------

def compare_embeddings (query_embedding: list, stored_embeddings: list[dict]) -> dict:
    if not stored_embeddings:
        return {
            "match": False,
            "confidence": 0.0, 
            "best_direction": None,
            "distance": float("inf"),
        }
    
    query_vec = np.array(query_embedding)
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)

    best_distance = float("inf")
    best_direction = None

    for entry in stored_embeddings:
        stored_vec = np.array(entry["embedding"])
        stored_norm = stored_vec / (np.linalg.norm(stored_vec))

        cosine_distance = 1.0 - float(np.dot(query_norm, stored_norm))

        if cosine_distance < best_distance:
            best_distance = cosine_distance
            best_direction = entry["direction"]

    confidence = max(0.0, 1.0 - (best_distance / (THRESHOLD + 1e-10)))
    confidence = min(confidence, 1.0)

    return {
        "match": best_distance < THRESHOLD,
        "confidence": round(confidence, 4),
        "best_direction": best_direction,
        "distance": round(float(best_distance), 6),
    }

# ---------------------------------------------------------------------------
# Registration quality check
# ---------------------------------------------------------------------------

def validate_registration_quality(embeddings: list[list]) -> dict:
    if len(embeddings) < 2:
        return {"valid": True, "message": "Not enough embeddings to validate.", "max_spread": 0.0}
    
    vecs = [np.array(e) / (np.linalg.norm(np.array(e) + 1e-10)) for e in embeddings]

    max_spread = 0.0 
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            dist = 1.0 - float(np.dot(vecs[i], vecs[j]))
            if dist > max_spread:
                max_spread = dist

    SPREAD_LIMIT = 1.2

    if max_spread > SPREAD_LIMIT:
        return {
            "valid": False,
            "message": (
                "Registration photos are inconsistent. "
                "Try re-taking in better lighting with your face clearly visible."
            ),
            "max_spread": round(max_spread, 4),
        }
    
    return {
        "valid": True,
        "message": "Registration embeddings are consistent.",
        "max_spread": round(max_spread, 4),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def validate_direction(direction: str) -> bool:
    return direction.lower() in VALID_DIRECTIONS

def embeddings_from_db_rows(rows) -> list[dict]:
    return [{"direction": row["direction"], "embedding": row["embedding"]} for row in rows]

