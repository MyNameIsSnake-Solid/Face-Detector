from flask import Flask
from flask_cors import CORS

from api.routes import bp
from database.database import init_schema

app = Flask(__name__)

CORS(app, supports_credentials=True)

app.register_blueprint(bp, url_prefix="/api")

@app.route("/health")
def health():
    return {"status": "ok"}, 200

if __name__ == "__main__":
    init_schema()
    app.run(debug=True, port=5000)

    