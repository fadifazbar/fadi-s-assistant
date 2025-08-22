import os
import json
import asyncio
from fastapi import FastAPI
import uvicorn

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ✅ Read from environment variables
SERVICE_JSON = os.environ.get("SERVICE_JSON")
FOLDER_ID = os.environ.get("FOLDER_ID")

if not SERVICE_JSON:
    raise ValueError("SERVICE_JSON environment variable not set!")
if not FOLDER_ID:
    raise ValueError("FOLDER_ID environment variable not set!")

credentials = service_account.Credentials.from_service_account_info(
    json.loads(SERVICE_JSON),
    scopes=["https://www.googleapis.com/auth/drive.file"]
)

drive_service = build("drive", "v3", credentials=credentials)

app = FastAPI()


def upload_to_drive(filepath: str):
    """Upload a file to Google Drive and make it publicly downloadable."""
    file_metadata = {
        "name": os.path.basename(filepath),
        "parents": [FOLDER_ID],
    }
    media = MediaFileUpload(filepath, resumable=True)
    uploaded_file = drive_service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()

    file_id = uploaded_file.get("id")

    # Make file shareable by anyone with the link
    drive_service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()

    # Return direct download link + file ID
    link = f"https://drive.google.com/uc?export=download&id={file_id}"
    return link, file_id


def delete_from_drive(file_id: str):
    """Delete a file from Google Drive."""
    try:
        drive_service.files().delete(fileId=file_id).execute()
    except Exception as e:
        print(f"[!] Failed to delete file {file_id}: {e}")


async def delete_after_48h(file_id: str):
    """Wait 48 hours then delete the file."""
    await asyncio.sleep(48 * 3600)  # 48 hours
    delete_from_drive(file_id)


@app.get("/")
async def home():
    return {"status": "Bot + Google Drive uploader running!"}


async def start_fastapi():
    config = uvicorn.Config(app=app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


# ✅ Import your bot's main function (make sure main.py exists)
from main import main as bot_main


async def main():
    """Run Discord bot + FastAPI concurrently."""
    await asyncio.gather(
        bot_main(),
        start_fastapi()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down...")
