# app/news.py

from fastapi import APIRouter, HTTPException
from .db import get_db_connection

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
