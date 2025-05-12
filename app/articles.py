from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List
import shutil
import os
from .db import get_db_connection

router = APIRouter()

UPLOAD_DIR = "static/uploads"

@router.post("/api/articles")
async def create_article(
    title: str = Form(...),
    content: str = Form(...),
    author_id: int = Form(...),
    files: List[UploadFile] = File(default=[])
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Вставка статьи
        cursor.execute("""
            INSERT INTO articles (title, content, author_id)
            VALUES (%s, %s, %s) RETURNING id
        """, (title, content, author_id))
        article_id = cursor.fetchone()[0]

        # 2. Сохранение изображений
        image_paths = []
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        for file in files:
            filename = f"{article_id}_{file.filename}"
            file_path = os.path.join(UPLOAD_DIR, filename)

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Сохранение в БД
            cursor.execute("""
                INSERT INTO article_images (article_id, image_path)
                VALUES (%s, %s)
            """, (article_id, file_path))
            image_paths.append(file_path)

        conn.commit()
        cursor.close()
        conn.close()

        return JSONResponse(content={
            "message": "Article created successfully",
            "article_id": article_id,
            "images": image_paths
        })

    except Exception as e:
        print(f"Ошибка: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при создании статьи")
