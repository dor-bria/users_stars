from flask import Flask, redirect, request, jsonify
import requests
import datetime
import os
import psycopg

app = Flask(__name__)

# OAuth settings
CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET")
REDIRECT_URI = "https://users-git-stars.onrender.com/callback"   # חייב להיות תואם ב־GitHub OAuth App
REPO_URL = "https://github.com/Bria-AI/RMBG-2.0"

# Database connection
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_connection():
    return psycopg.connect(DATABASE_URL)

# Create table if it does not exist
with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                username TEXT,
                source TEXT,
                timestamp TIMESTAMP
            );
        """)
    conn.commit()

def save_log(username, source):
    timestamp = datetime.datetime.utcnow()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO logs (username, source, timestamp) VALUES (%s, %s, %s)",
                (username, source, timestamp)
            )
        conn.commit()

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

    if not code:
        return "Error: Missing code from GitHub", 400

    try:
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
            timeout=10,
        )

        print("TOKEN RESPONSE:", token_res.text)  # Debug log

        if token_res.status_code != 200:
            return f"Error fetching token: {token_res.text}", 500

        token_data = token_res.json()
        access_token = token_data.get("access_token")

        if not access_token:
            return f"Error: No access token returned. Response: {token_res.text}", 500

        # Get user details from GitHub
        user_res = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {access_token}"},
            timeout=10,
        )

        print("USER RESPONSE:", user_res.text)  # Debug log

        if user_res.status_code != 200:
            return f"Error fetching user info: {user_res.text}", 500

        user_data = user_res.json()
        username = user_data.get("login")

        if not username:
            return f"Error: No username found in GitHub response: {user_res.text}", 500

        # Save log to DB
        save_log(username, source or "unknown")

        # Redirect back to the repo
        return redirect(REPO_URL)

    except Exception as e:
        print("CALLBACK ERROR:", str(e))
        return f"Internal error: {str(e)}", 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
