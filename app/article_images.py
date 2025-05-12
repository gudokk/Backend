# app/article_images.py
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
import shutil
import os
from app.db import get_db_connection

router = APIRouter()

UPLOAD_DIR = "static/images/articles"

@router.post("/api/upload_image")
async def upload_article_image(article_id: int = Form(...), file: UploadFile = File(...)):
    try:
        # Убедись, что папка существует
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        relative_path = f"/static/images/articles/{file.filename}"
        file_path = os.path.join("static/images/articles", file.filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Сохраняем путь в базу
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO article_images (article_id, image_path) VALUES (%s, %s)",
            (article_id, relative_path)
        )

        conn.commit()
        cursor.close()
        conn.close()

        return JSONResponse({"status": "ok", "path": file_path})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
