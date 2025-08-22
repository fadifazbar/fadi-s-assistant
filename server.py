import asyncio
import os
import uvicorn
from fastapi import FastAPI
from main import main as bot_main

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = FastAPI()

# Google Drive setup
SERVICE_ACCOUNT_FILE = "angelic-cat-469803-c8-7ec9cc0a6674.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build("drive", "v3", credentials=credentials)

# Your uploads folder in Google Drive (you created it already)
FOLDER_ID = "YOUR_FOLDER_ID_HERE"  # <-- replace with actual BotUploads folder ID


def upload_to_drive(filepath: str) -> str:
    """Upload file to Google Drive and return direct download link"""
    file_metadata = {
        "name": os.path.basename(filepath),
        "parents": [FOLDER_ID],
    }
    media = MediaFileUpload(filepath, resumable=True)
    uploaded_file = drive_service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()

    file_id = uploaded_file.get("id")

    # Make file shareable
    drive_service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()

    # Return direct download link
    return f"https://drive.google.com/uc?export=download&id={file_id}"


@app.get("/")
async def home():
    return {"status": "Bot + Google Drive uploader running!"}


async def start_fastapi():
    """Run FastAPI inside asyncio"""
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
