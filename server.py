import asyncio
import os
import shutil
import uvicorn
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from main import main as bot_main

app = FastAPI()

# Make sure downloads folder exists
DOWNLOADS_DIR = "downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Save file into downloads/ and return its public URL"""
    file_path = os.path.join(DOWNLOADS_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    base_url = os.environ.get("RAILWAY_STATIC_URL", "localhost:8080")
    return {
        "file_url": f"https://{base_url}/files/{file.filename}"
    }

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Force download instead of just serving the file"""
    file_path = os.path.join(DOWNLOADS_DIR, filename)
    if not os.path.exists(file_path):
        return {"detail": "File not found"}
    return FileResponse(
        file_path,
        filename=filename,
        media_type="application/octet-stream",  # forces "Save As"
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/files/{filename}")
async def get_file(filename: str):
    """Serve files normally (view in browser)"""
    file_path = os.path.join(DOWNLOADS_DIR, filename)
    if not os.path.exists(file_path):
        return {"detail": "File not found"}
    return FileResponse(file_path, filename=filename)

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
