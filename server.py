import os
import time
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTasks
from pathlib import Path
import shutil
import asyncio

app = FastAPI()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_AGE = 48 * 3600  # 48 hours in seconds


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Save uploaded file and return public URL."""
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"file_url": f"/files/{file.filename}"}


@app.get("/files/{filename}")
async def get_file(filename: str):
    """Serve uploaded file."""
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(file_path)


async def cleanup_old_files():
    """Delete files older than 48 hours."""
    while True:
        now = time.time()
        for file in UPLOAD_DIR.iterdir():
            if file.is_file():
                if now - file.stat().st_mtime > MAX_FILE_AGE:
                    try:
                        file.unlink()
                        print(f"🗑️ Deleted old file: {file}")
                    except Exception as e:
                        print(f"⚠️ Error deleting {file}: {e}")
        await asyncio.sleep(3600)  # Run cleanup every 1 hour


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_old_files())
