import os
import json
import threading
import subprocess
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# =========================
# Config / Env
# =========================
FOLDER_ID = os.environ.get("FOLDER_ID")
CLIENT_SECRET_FILE = os.environ.get("CLIENT_SECRET_FILE")  # Path to downloaded OAuth JSON
TOKEN_FILE = os.environ.get("TOKEN_FILE", "token.json")  # Will store OAuth token

if not CLIENT_SECRET_FILE:
    raise ValueError("CLIENT_SECRET_FILE environment variable is not set!")

# =========================
# Google Drive client (OAuth)
# =========================
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

creds = None
if os.path.exists(TOKEN_FILE):
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

if not creds or not creds.valid:
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    # Save the credentials for next run
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

drive_service = build("drive", "v3", credentials=creds)

# =========================
# Upload / Delete functions
# =========================
def upload_to_drive(file_path: str):
    file_name = os.path.basename(file_path)
    media = MediaFileUpload(file_path, resumable=True)
    metadata = {"name": file_name}
    if FOLDER_ID:
        metadata["parents"] = [FOLDER_ID]

    file = drive_service.files().create(body=metadata, media_body=media, fields="id").execute()
    file_id = file.get("id")

    drive_service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"}
    ).execute()

    link = f"https://drive.google.com/uc?export=download&id={file_id}"
    return link, file_id

def delete_from_drive(file_id: str):
    drive_service.files().delete(fileId=file_id).execute()

def delete_after_48h(file_id: str):
    """
    Schedules a Google Drive file to be deleted after 48 hours.
    """
    def _worker():
        print(f"[server] ⏳ File {file_id} scheduled for deletion in 48h")
        time.sleep(48 * 3600)  # wait 48 hours
        try:
            delete_from_drive(file_id)
            print(f"[server] ✅ File {file_id} deleted after 48h")
        except Exception as e:
            print(f"[server] ❌ Failed to delete {file_id}: {e}")

    threading.Thread(target=_worker, daemon=True).start()

# =========================
# Tiny health server
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
        return

def _start_health_server():
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    print(f"[server] Health server listening on :{port}")
    server.serve_forever()

# =========================
# Start Discord bot
# =========================
def _start_bot():
    print("[server] Starting main.py (Discord bot)...")
    proc = subprocess.Popen(["python", "main.py"])
    return proc

if __name__ == "__main__":
    t = threading.Thread(target=_start_health_server, daemon=True)
    t.start()

    bot_proc = _start_bot()
    exit_code = bot_proc.wait()
    print(f"[server] main.py exited with code {exit_code}")
    raise SystemExit(exit_code)
