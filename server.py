import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# === CONFIG ===
# Folder ID on Google Drive where files will be uploaded
FOLDER_ID = os.environ.get("FOLDER_ID")  # e.g., '17P1q50Wp-2NzXJEiBQOA0HZxuoC4Vpei'

# SERVICE_JSON should be the raw JSON content of your service account
SERVICE_JSON_RAW = os.environ.get("SERVICE_JSON")
if not SERVICE_JSON_RAW:
    raise ValueError("SERVICE_JSON environment variable is not set!")

# Parse JSON directly
try:
    service_account_info = json.loads(SERVICE_JSON_RAW)
except Exception as e:
    raise ValueError(f"Invalid SERVICE_JSON (not valid JSON): {e}")

# Authenticate
credentials = service_account.Credentials.from_service_account_info(service_account_info)
drive_service = build("drive", "v3", credentials=credentials)

# === UPLOAD FUNCTION ===
def upload_to_drive(file_path: str):
    """
    Uploads a file to Google Drive and makes it publicly viewable.
    Returns (public_link, file_id)
    """
    file_name = os.path.basename(file_path)
    media = MediaFileUpload(file_path, resumable=True)
    file_metadata = {
        "name": file_name,
        "parents": [FOLDER_ID]
    }

    # Upload file
    file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_id = file.get("id")

    # Make file public
    drive_service.permissions().create(
        fileId=file_id,
        body={"role": "reader", "type": "anyone"}
    ).execute()

    # Direct download link
    link = f"https://drive.google.com/uc?export=download&id={file_id}"
    return link, file_id

# === DELETE FUNCTION ===
def delete_from_drive(file_id: str):
    """
    Deletes a file from Google Drive.
    """
    drive_service.files().delete(fileId=file_id).execute()
