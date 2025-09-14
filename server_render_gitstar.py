from flask import Flask, redirect, request
import requests
import datetime
import os
from sqlalchemy import create_engine, text

app = Flask(__name__)

# OAuth settings
CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET")
REDIRECT_URI = "https://your-app.onrender.com/callback"   # update with your Render domain
REPO_URL = "https://github.com/Bria-AI/RMBG-2.0"

# Database connection
DATABASE_URL = os.environ.get("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# Create table if it does not exist
with engine.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            username TEXT,
            source TEXT,
            timestamp TIMESTAMP
        );
    """))

def save_log(username, source):
    timestamp = datetime.datetime.utcnow().isoformat()
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO logs (username, source, timestamp) VALUES (:u, :s, :t)"),
            {"u": username, "s": source, "t": timestamp}
        )

# Step 1: Page with "Continue with GitHub" button
@app.route("/")
def home():
    source = request.args.get("src", "unknown")
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&state={source}"
    )
    return f"""
    <h2>Confirm your GitHub account</h2>
    <a href="{github_auth_url}">
        <button>Continue with GitHub</button>
    </a>
    """

# Step 2: Callback after GitHub authorization
@app.route("/callback")
def callback():
    code = request.args.get("code")
    source = request.args.get("state")

    # Exchange code for access_token
    token_res = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        json={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
    )
    token_data = token_res.json()
    access_token = token_data.get("access_token")

    # Get user details from GitHub
    user_res = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"token {access_token}"},
    )
    user_data = user_res.json()

    # Save log to DB
    save_log(user_data.get("login"), source)

    # Redirect back to the repo
    return redirect(REPO_URL)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
