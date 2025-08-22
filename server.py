import os
import json
import base64
import threading
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# =========================
# Config / Env
# =========================
FOLDER_ID = os.environ.get("FOLDER_ID")  # Optional; if None, uploads to My Drive
SERVICE_JSON_ENV = os.environ.get("SERVICE_JSON")
if not SERVICE_JSON_ENV:
    raise ValueError("SERVICE_JSON environment variable is not set!")

def _load_service_json(value: str) -> dict:
    """
    Accepts either raw JSON or base64-encoded JSON.
    Also fixes private_key newlines if needed.
    """
    data = None

    # Try plain JSON first
    try:
        data = json.loads(value)
    except Exception:
        # Fallback: try base64 -> JSON
        try:
            decoded = base64.b64decode(value).decode("utf-8")
            data = json.loads(decoded)
        except Exception as e:
            raise ValueError(f"SERVICE_JSON is neither valid JSON nor valid base64 JSON: {e}")

    # Normalize private_key newlines if they are escaped
    pk = data.get("private_key")
    if isinstance(pk, str):
        # If it looks like a single line with literal \n, convert to real newlines
        if "\\n" in pk and "-----BEGIN" in pk and "-----END" in pk:
            data["private_key"] = pk.replace("\\n", "\n")

    return data

service_account_info = _load_service_json(SERVICE_JSON_ENV)

# =========================
# Google Drive client
# =========================
credentials = service_account.Credentials.from_service_account_info(service_account_info)
drive_service = build("drive", "v3", credentials=credentials)

# =========================
# Upload / Delete functions (unchanged behavior)
# =========================
def upload_to_drive(file_path: str):
    """
    Uploads a file to Google Drive and makes it publicly viewable.
    Returns (public_link, file_id)
    """
    file_name = os.path.basename(file_path)
    media = MediaFileUpload(file_path, resumable=True)
    metadata = {"name": file_name}

    # Only set parents when FOLDER_ID is provided
    if FOLDER_ID:
        metadata["parents"] = [FOLDER_ID]

    # Upload file
    file = drive_service.files().create(body=metadata, media_body=media, fields="id").execute()
    file_id = file.get("id")

    # Make file public
    drive_service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"}
    ).execute()

    # Direct download link
    link = f"https://drive.google.com/uc?export=download&id={file_id}"
    return link, file_id

def delete_from_drive(file_id: str):
    """
    Deletes a file from Google Drive.
    """
    drive_service.files().delete(fileId=file_id).execute()

# =========================
# Tiny health server for Railway
# =========================
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        # Keep logs clean
        return

def _start_health_server():
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    print(f"[server] Health server listening on :{port}")
    server.serve_forever()

# =========================
# Start Discord bot (main.py)
# =========================
def _start_bot():
    # Launch your Discord bot script
    # If your runtime needs "python3", change it below.
    print("[server] Starting main.py (Discord bot)...")
    proc = subprocess.Popen(["python", "main.py"])
    return proc

if __name__ == "__main__":
    # Start health server in a background thread
    t = threading.Thread(target=_start_health_server, daemon=True)
    t.start()

    # Start the bot and keep this process alive while it runs
    bot_proc = _start_bot()
    exit_code = bot_proc.wait()
    print(f"[server] main.py exited with code {exit_code}")
    # If the bot exits, also exit this process (Railway will restart it based on your settings)
    raise SystemExit(exit_code)
