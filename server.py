import asyncio
import os
import uvicorn
from fastapi import FastAPI
from main import main as bot_main

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = FastAPI()

# -------------------------------
# Google Drive setup
# -------------------------------
SERVICE_ACCOUNT_FILE = "angelic-cat-469803-c8-7ec9cc0a6674.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build("drive", "v3", credentials=credentials)

# Private uploads folder (keep hidden)
FOLDER_ID = "17P1q50Wp-2NzXJEiBQOA0HZxuoC4Vpei"  # Replace with your BotUploads folder ID


def upload_to_drive(filepath: str):
    """
    Upload file to Google Drive and return:
      1) direct download link
      2) file ID for future deletion
    """
    file_metadata = {
        "name": os.path.basename(filepath),
        "parents": [FOLDER_ID],
    }
    media = MediaFileUpload(filepath, resumable=True)
    uploaded_file = drive_service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()

    file_id = uploaded_file.get("id")

    # Make only this file shareable
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


# -------------------------------
# FastAPI endpoints
# -------------------------------
@app.get("/")
async def home():
    return {"status": "Bot + Google Drive uploader running!"}


# -------------------------------
# Run Discord bot + FastAPI together
# -------------------------------
async def start_fastapi():
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    """Run Discord bot and FastAPI at the same time"""
    await asyncio.gather(
        bot_main(),       # your Discord bot
        start_fastapi()   # FastAPI server
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down...")
