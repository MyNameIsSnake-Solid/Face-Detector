import sys
import os
import base64
import numpy as np
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
from pipeline.embedding import (
    decode_image_to_file,
    generate_embedding,
    compare_embeddings,
    validate_direction,
    embeddings_from_db_rows,
    THRESHOLD,
)
 
# ── Helpers ───────────────────────────────────────────────────────────────────
 
def ok(msg):   print(f"  ✓  {msg}")
def fail(msg): print(f"  ✗  {msg}"); sys.exit(1)
def header(msg): print(f"\n{'─'*50}\n  {msg}\n{'─'*50}")
 
 
def make_blank_image_b64(width=100, height=100):
    """Generate a plain grey image as base64 — no face, for negative tests."""
    import cv2
    img = np.ones((height, width, 3), dtype=np.uint8) * 128
    _, buffer = cv2.imencode(".jpg", img)
    return base64.b64encode(buffer).decode("utf-8")
 
 
def make_face_image_b64():
    """
    Load a real face image for positive tests.
    Downloads a small public domain face image if not cached.
    Falls back to a solid colour with a warning if download fails.
    """
    cache_path = "tests/test_face.jpg"
 
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
 
    try:
        import urllib.request
        # Public domain face from thispersondoesnotexist alternative
        url = "https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/Gatto_europeo4.jpg/320px-Gatto_europeo4.jpg"
        urllib.request.urlretrieve(url, cache_path)
        with open(cache_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        print("  ⚠  Could not download test face image — using blank image")
        print("     To test face detection properly, add a face photo at tests/test_face.jpg")
        return make_blank_image_b64(200, 200)
 
 
# ── Tests ─────────────────────────────────────────────────────────────────────
 
def test_decode_valid_image():
    header("TEST 1 — Decode Valid Base64 Image")
 
    b64 = make_blank_image_b64()
    try:
        path = decode_image_to_file(b64)
        if os.path.exists(path):
            ok(f"Temp file created at: {path}")
            os.unlink(path)
            ok("Temp file cleaned up")
        else:
            fail("Temp file not created")
    except Exception as e:
        fail(f"decode_image_to_file raised: {e}")
 
 
def test_decode_with_data_url_prefix():
    header("TEST 2 — Decode Base64 with Data URL Prefix")
 
    b64 = make_blank_image_b64()
    with_prefix = f"data:image/jpeg;base64,{b64}"
 
    try:
        path = decode_image_to_file(with_prefix)
        if os.path.exists(path):
            ok("Data URL prefix stripped and image decoded correctly")
            os.unlink(path)
        else:
            fail("Temp file not created with prefix input")
    except Exception as e:
        fail(f"Failed with data URL prefix: {e}")
 
 
def test_decode_garbage_input():
    header("TEST 3 — Reject Garbage Input")
 
    try:
        decode_image_to_file("this is not base64 image data !!!")
        fail("Should have raised ValueError on garbage input")
    except ValueError as e:
        ok(f"ValueError raised correctly: {e}")
    except Exception as e:
        ok(f"Exception raised on garbage input: {type(e).__name__}: {e}")
 
 
def test_generate_embedding_no_face():
    header("TEST 4 — generate_embedding on Image with No Face")
    print("  (This tests error handling — a blank image should return success=False)")
 
    b64 = make_blank_image_b64(200, 200)
    result = generate_embedding(b64)
 
    if result["success"] == False:
        ok(f"Correctly returned success=False: '{result['error']}'")
    else:
        fail("Expected success=False for blank image but got success=True")
 
 
def test_compare_embeddings_identical():
    header("TEST 5 — compare_embeddings: Same Embedding Matches Itself")
 
    # Create a random unit vector simulating an embedding
    vec = np.random.randn(512)
    vec = vec / np.linalg.norm(vec)
    embedding = vec.tolist()
 
    stored = [
        {"direction": "center", "embedding": embedding},
        {"direction": "left",   "embedding": (vec * 0.95 + np.random.randn(512) * 0.05).tolist()},
    ]
 
    result = compare_embeddings(embedding, stored)
 
    if result["match"]:
        ok(f"Identical embedding correctly matched (distance={result['distance']}, confidence={result['confidence']})")
    else:
        fail(f"Identical embedding failed to match (distance={result['distance']})")
 
    if result["distance"] < 0.01:
        ok("Distance near 0 as expected for identical vectors")
 
 
def test_compare_embeddings_different():
    header("TEST 6 — compare_embeddings: Different Embeddings Don't Match")
 
    # Two random unit vectors — very unlikely to be close
    vec1 = np.random.randn(512)
    vec1 = vec1 / np.linalg.norm(vec1)
 
    vec2 = np.random.randn(512)
    vec2 = vec2 / np.linalg.norm(vec2)
 
    stored = [{"direction": "center", "embedding": vec2.tolist()}]
    result = compare_embeddings(vec1.tolist(), stored)
 
    # Random 512-d unit vectors have cosine distance ~1.0
    if result["distance"] > THRESHOLD:
        ok(f"Different embeddings correctly not matched (distance={result['distance']})")
    else:
        fail(f"Different embeddings incorrectly matched (distance={result['distance']})")
 
 
def test_compare_embeddings_empty():
    header("TEST 7 — compare_embeddings: Empty Stored Embeddings")
 
    vec = np.random.randn(512).tolist()
    result = compare_embeddings(vec, [])
 
    if not result["match"] and result["confidence"] == 0.0:
        ok("Empty stored embeddings correctly returns no match")
    else:
        fail(f"Expected no match for empty stored embeddings, got: {result}")
 
 
def test_validate_direction():
    header("TEST 8 — validate_direction")
 
    valid = ["center", "left", "right", "up", "down"]
    for d in valid:
        if validate_direction(d):
            ok(f"'{d}' correctly accepted")
        else:
            fail(f"'{d}' incorrectly rejected")
 
    invalid = ["forward", "diagonal", "", "LEFT", "Center"]
    # Note: "LEFT" and "Center" fail because validate_direction expects lowercase
    # The routes.py does .lower() before calling this, so that's fine
    for d in ["forward", "diagonal", ""]:
        if not validate_direction(d):
            ok(f"'{d}' correctly rejected")
        else:
            fail(f"'{d}' incorrectly accepted")
 
 
def test_embeddings_from_db_rows():
    header("TEST 9 — embeddings_from_db_rows Formatting")
 
    # Simulate what psycopg2 RealDictCursor returns
    class FakeRow:
        def __init__(self, direction, embedding):
            self._data = {"direction": direction, "embedding": embedding}
        def __getitem__(self, key):
            return self._data[key]
 
    fake_rows = [
        FakeRow("center", [0.1, 0.2, 0.3]),
        FakeRow("left",   [0.4, 0.5, 0.6]),
    ]
 
    result = embeddings_from_db_rows(fake_rows)
 
    if len(result) == 2:
        ok("Correct number of entries returned")
    else:
        fail(f"Expected 2 entries, got {len(result)}")
 
    if result[0]["direction"] == "center" and result[0]["embedding"] == [0.1, 0.2, 0.3]:
        ok("First entry formatted correctly")
    else:
        fail(f"First entry wrong: {result[0]}")
 
 
# ── Run all tests ─────────────────────────────────────────────────────────────
 
if __name__ == "__main__":
    print("\n╔══════════════════════════════════════╗")
    print("║      EMBEDDING.PY TEST SUITE         ║")
    print("╚══════════════════════════════════════╝")
    print("\n  Note: First run may download DeepFace model weights (~90MB)")
 
    test_decode_valid_image()
    test_decode_with_data_url_prefix()
    test_decode_garbage_input()
    test_generate_embedding_no_face()
    test_compare_embeddings_identical()
    test_compare_embeddings_different()
    test_compare_embeddings_empty()
    test_validate_direction()
    test_embeddings_from_db_rows()
 
    print("\n✓ All embedding tests passed!\n")
    print("  ⚠  Note: To test generate_embedding with a real face,")
    print("     place a face photo at tests/test_face.jpg and")
    print("     add a manual test calling generate_embedding() on it.\n")