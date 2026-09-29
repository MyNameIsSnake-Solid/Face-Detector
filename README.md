# Face Detection Login

Passwordless authentication using facial recognition. Users register by capturing their face from five directions through the webcam, then log in by simply looking at the camera. The backend is a Flask API that generates face embeddings with DeepFace (ArcFace) and stores them in PostgreSQL.

## Features

- **Face registration**: captures five angles (center, left, right, up, down) and checks that the photos are consistent before the account is activated.
- **Face login**: compares a live capture against the stored embeddings using cosine distance and issues a JWT on a match.
- **Brute-force protection**: accounts are temporarily locked after repeated failed login attempts.
- **Account recovery**: single-use, time-limited recovery tokens (stored hashed) allow users to re-register their face.
- **Single-face enforcement**: rejects images with no face or more than one face.

## Tech stack

| Layer     | Technology                                   |
|-----------|----------------------------------------------|
| Backend   | Python, Flask, Flask-CORS                    |
| Face AI   | DeepFace (ArcFace model, OpenCV detector), TensorFlow |
| Database  | PostgreSQL (psycopg2)                        |
| Auth      | PyJWT                                        |
| Frontend  | Plain HTML, CSS, JavaScript (webcam via `getUserMedia`) |

## Project structure

```
├── app.py                 # Flask entry point (creates schema, serves API on :5000)
├── api/routes.py          # REST endpoints: register, login, recovery
├── database/database.py   # PostgreSQL connection and schema setup
├── pipeline/embedding.py  # Face detection, embedding and comparison logic
├── utils/auth.py          # JWT, login lockout, recovery tokens
├── frontend/              # login, register, recovery and dashboard pages
├── tests/                 # Test suites and runner
└── requirements.txt
```

## Getting started

### Prerequisites

- Python 3.10 or 3.11 (TensorFlow 2.15 does not support newer versions)
- PostgreSQL running locally
- A webcam

### 1. Clone and install

```bash
git clone <your-repo-url>
cd <repo-folder>
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

The first run downloads the ArcFace model weights, which may take a moment.

### 2. Create the database

```sql
CREATE DATABASE face_auth;
```

Tables are created automatically when the app starts.

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=face_auth
DB_USER=postgres
DB_PASSWORD=your_password

# JWT
JWT_SECRET=replace-with-a-long-random-string
JWT_EXPIRY_HOURS=1

# Face recognition
FACE_DISTANCE_THRESHOLD=0.68
MAX_LOGIN_ATTEMPTS=3
LOCKOUT_MINUTES=15

# Recovery
RECOVERY_TOKEN_EXPIRY_MINUTES=15
```

### 4. Run the backend

```bash
python app.py
```

The API runs at `http://127.0.0.1:5000`. Check it with `GET /health`.

### 5. Open the frontend

Serve the `frontend/` folder with any static server, for example:

```bash
cd frontend
python -m http.server 8000
```

Then open `http://localhost:8000/register.html` to create an account, or `login.html` to sign in. Serving over `localhost` is required for the browser to allow webcam access.

## API reference

All endpoints are under `/api`, accept JSON, and take images as base64-encoded JPEG or PNG strings (data URLs are accepted).

| Method | Endpoint                 | Body                               | Description |
|--------|--------------------------|------------------------------------|-------------|
| POST   | `/register/init`         | `username`, `email`                | Create a user account |
| POST   | `/register/photo`        | `username`, `direction`, `image`   | Save the face embedding for one direction |
| POST   | `/register/verify`       | `username`, `image`                | Confirm registration once all 5 directions are saved |
| POST   | `/login`                 | `username`, `image`                | Log in; returns a JWT on success |
| POST   | `/recovery/request`      | `username`                         | Issue a recovery token |
| POST   | `/recovery/re-register`  | `token`, `direction`, `image`      | Replace face data using a recovery token |

`direction` must be one of `center`, `left`, `right`, `up`, `down`.

> **Note:** Recovery emails are not implemented yet. In development, the recovery link is printed to the server console.

## Running tests

With PostgreSQL running and `.env` configured:

```bash
python tests/run_all_tests.py
```

This runs the database, auth, embedding and route suites in order and stops at the first failure.

## Security notes

- Never commit your `.env` file. It is excluded by `.gitignore`.
- Always set a strong `JWT_SECRET`; the code falls back to an insecure default if it is missing.
- `app.py` runs Flask in debug mode, which is meant for local development only.
