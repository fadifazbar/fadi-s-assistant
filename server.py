from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os, uuid, aiofiles

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Discord File Host")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload")
async def upload(file: UploadFile, expires_in: int = Form(3600)):
    ext = os.path.splitext(file.filename)[-1]
    file_id = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, file_id)

    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            await f.write(chunk)

    return JSONResponse({
        "status": "success",
        "file_url": f"/files/{file_id}"
    })

@app.get("/files/{file_id}")
async def get_file(file_id: str):
    file_path = os.path.join(UPLOAD_DIR, file_id)
    if not os.path.exists(file_path):
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(file_path, filename=file_id)
