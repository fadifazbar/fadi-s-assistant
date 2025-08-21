import os
import time
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
import shutil
import asyncio
import uvicorn
from contextlib import asynccontextmanager

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_AGE = 48 * 3600  # 48 hours in seconds


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    asyncio.create_task(cleanup_old_files())
    yield
    # Shutdown (nothing needed here, but you could cancel tasks if wanted)


app = FastAPI(lifespan=lifespan)


@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """Save uploaded file and return public URL."""
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    base_url = str(request.base_url).rstrip("/")
    return {"file_url": f"{base_url}/files/{file.filename}"}


@app.get("/files/{filename}")
async def get_file(filename: str):
    """Serve uploaded file."""
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(file_path)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
