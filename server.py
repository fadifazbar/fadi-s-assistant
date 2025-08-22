import asyncio
import os
import uvicorn
from fastapi import FastAPI
from main import main as bot_main
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = FastAPI()

# ----------------------------
# Google Drive setup
# ----------------------------
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# Load JSON from environment variable
SERVICE_JSON = os.environ.get("GOOGLE_SERVICE_JSON")
if not SERVICE_JSON:
    raise ValueError("Environment variable GOOGLE_SERVICE_JSON is not set!")

credentials = service_account.Credentials.from_service_account_info(
    json.loads(SERVICE_JSON),
    scopes=SCOPES
)

drive_service = build("drive", "v3", credentials=credentials)

# Folder ID in Google Drive (private folder, just for bot uploads)
FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID")
if not FOLDER_ID:
    raise ValueError("Environment variable GOOGLE_DRIVE_FOLDER_ID is not set!")


# ----------------------------
# Google Drive file functions
# ----------------------------
def upload_to_drive(filepath: str):
    """Upload file to Google Drive, make it public, and return link + file_id"""
    file_metadata = {
        "name": os.path.basename(filepath),
        "parents": [FOLDER_ID],
    }
    media = MediaFileUpload(filepath, resumable=True)
    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    file_id = uploaded_file.get("id")

    # Make file public (anyone with link can download)
    drive_service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()

    # Direct download link
    link = f"https://drive.google.com/uc?export=download&id={file_id}"
    return link, file_id


def delete_from_drive(file_id: str):
    """Delete file from Google Drive"""
    drive_service.files().delete(fileId=file_id).execute()


# ----------------------------
# FastAPI endpoints
# ----------------------------
@app.get("/")
async def home():
    return {"status": "Bot + Google Drive uploader running!"}


# ----------------------------
# Run FastAPI + Discord bot together
# ----------------------------
async def start_fastapi():
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    await asyncio.gather(
        bot_main(),       # Run Discord bot
        start_fastapi()   # Run FastAPI server
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down...")
