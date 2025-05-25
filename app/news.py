# app/news.py

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from .db import get_db_connection
from .auth import get_current_user
import os
import uuid
import json


router = APIRouter()

@router.get("/api/news")
async def get_latest_news():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT a.id, a.title, a.content, a.publication_date, ai.image_path
            FROM articles a
             LEFT JOIN article_images ai ON a.id = ai.article_id
             WHERE a.is_published = TRUE
            ORDER BY a.publication_date DESC
            LIMIT 4
        """)
        news = cursor.fetchall()

        cursor.close()
        conn.close()

        news_list = []
        for item in news:
            news_list.append({
                "id": item[0],
                "title": item[1],
                "content": item[2],
                "publication_date": item[3].isoformat(),  # чтобы дата шла в формате строки
                "image": item[4]
            })

        return news_list

    except Exception as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")



@router.post("/api/news/create")
async def create_article(
    title: str = Form(...),
    content: str = Form(...),
    tags: str = Form(""),  # JSON-строка со списком тегов
    image: UploadFile = File(None),
    user_id: int = Depends(get_current_user)
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Сохранение статьи
        cursor.execute("""
            INSERT INTO articles (author_id, title, content, publication_date, is_published)
            VALUES (%s, %s, %s, NOW(), FALSE)
            RETURNING id
        """, (user_id, title, content))
        article_id = cursor.fetchone()[0]

        # Загрузка изображения
        if image:
            folder = f"app/static/images/articles/{article_id}"
            os.makedirs(folder, exist_ok=True)
            filename = f"{uuid.uuid4().hex}_{image.filename}"
            full_path = os.path.join(folder, filename)
            with open(full_path, "wb") as f:
                f.write(await image.read())
            rel_path = f"/static/images/articles/{article_id}/{filename}"
            cursor.execute("""
                INSERT INTO article_images (article_id, image_path)
                VALUES (%s, %s)
            """, (article_id, rel_path))

        # Обработка тегов
        if tags:
            tag_list = json.loads(tags)  # ожидаем JSON-строку: ["снег", "спорт"]
            for tag_name in tag_list:
                # если тега нет — добавить
                cursor.execute("SELECT id FROM tag WHERE name = %s", (tag_name,))
                tag = cursor.fetchone()
                if not tag:
                    cursor.execute("INSERT INTO tag (name) VALUES (%s) RETURNING id", (tag_name,))
                    tag_id = cursor.fetchone()[0]
                else:
                    tag_id = tag[0]
                # добавляем в article_tag
                cursor.execute("""
                    INSERT INTO article_tag (article_id, tag_id)
                    VALUES (%s, %s)
                """, (article_id, tag_id))

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Черновик отправлен на модерацию"}

    except Exception as e:
        print("Ошибка при создании статьи:", e)
        raise HTTPException(status_code=500, detail="Ошибка сервера")


@router.get("/api/news/unpublished")
async def get_unpublished_articles(user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Проверка прав
    cursor.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    is_admin = cursor.fetchone()
    if not is_admin or not is_admin[0]:
        raise HTTPException(status_code=403, detail="Access denied")

    cursor.execute("""
        SELECT a.id, a.title, a.content, a.publication_date, u.username,
               (SELECT image_path FROM article_images ai WHERE ai.article_id = a.id LIMIT 1)
        FROM articles a
        JOIN users u ON a.author_id = u.id
        WHERE a.is_published = FALSE
        ORDER BY a.publication_date DESC
    """)
    articles = cursor.fetchall()

    cursor.close()
    conn.close()

    return [
        {
            "id": a[0],
            "title": a[1],
            "content": a[2],
            "date": a[3].isoformat(),
            "author": a[4],
            "image": a[5]
        }
        for a in articles
    ]

@router.post("/api/news/publish/{article_id}")
async def publish_article(article_id: int, user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    if not cursor.fetchone()[0]:
        raise HTTPException(status_code=403, detail="Access denied")

    cursor.execute("UPDATE articles SET is_published = TRUE WHERE id = %s", (article_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"message": "Статья опубликована"}

@router.delete("/api/news/delete/{article_id}")
async def delete_article(article_id: int, user_id: int = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Проверка: пользователь должен быть админом
        cursor.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
        result = cursor.fetchone()
        if not result or not result[0]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Удаление изображений из файловой системы
        cursor.execute("SELECT image_path FROM article_images WHERE article_id = %s", (article_id,))
        images = cursor.fetchall()
        for (path,) in images:
            try:
                abs_path = os.path.join("app", path.lstrip("/"))
                if os.path.exists(abs_path):
                    os.remove(abs_path)
            except Exception as file_err:
                print(f"Ошибка при удалении файла: {file_err}")

        # Удаление папки, если пустая
        folder_path = os.path.join("app/static/images/articles", str(article_id))
        if os.path.exists(folder_path):
            try:
                os.rmdir(folder_path)
            except OSError:
                pass  # папка не пуста

        # Удаление записей из article_images
        cursor.execute("DELETE FROM article_images WHERE article_id = %s", (article_id,))
        # Удаление самой статьи
        cursor.execute("DELETE FROM articles WHERE id = %s", (article_id,))

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Статья и связанные изображения удалены"}

    except Exception as e:
        print("Ошибка при удалении статьи:", e)
        raise HTTPException(status_code=500, detail="Ошибка сервера")