# app/news_page.py

from fastapi import APIRouter, HTTPException
from .db import get_db_connection

router = APIRouter()
@router.get("/api/newsPage")
def get_all_articles_with_tags():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.id, a.title, a.content, a.publication_date, u.username, ai.image_path
        FROM articles a
        JOIN users u ON a.author_id = u.id
        LEFT JOIN article_images ai ON a.id = ai.article_id
        ORDER BY a.publication_date DESC
    """)
    articles = cursor.fetchall()

    result = []
    for article in articles:
        article_id = article[0]
        cursor.execute("""
            SELECT t.name
            FROM tag t
            JOIN article_tag at ON t.id = at.tag_id
            WHERE at.article_id = %s
        """, (article_id,))
        tag_rows = cursor.fetchall()
        tags = [tag[0] for tag in tag_rows]

        result.append({
            "id": article[0],
            "title": article[1],
            "content": article[2],
            "publication_date": article[3].isoformat(),
            "author": article[4],
            "image": article[5],
            "tags": tags
        })

    cursor.close()
    conn.close()
    return result
