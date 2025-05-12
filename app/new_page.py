from fastapi import APIRouter, HTTPException
from .db import get_db_connection

router = APIRouter()
@router.get("/api/newsPage/{article_id}")
def get_article_by_id(article_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT a.id, a.title, a.content, a.publication_date, u.username, ai.image_path
            FROM articles a
            JOIN users u ON a.author_id = u.id
            LEFT JOIN article_images ai ON a.id = ai.article_id
            WHERE a.id = %s
        """, (article_id,))
        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Article not found")

        # Получаем теги отдельно
        cursor.execute("""
            SELECT t.name
            FROM tag t
            JOIN article_tag at ON t.id = at.tag_id
            WHERE at.article_id = %s
        """, (article_id,))
        tag_rows = cursor.fetchall()
        tags = [tag[0] for tag in tag_rows]

        return {
            "id": row[0],
            "title": row[1],
            "content": row[2],
            "publication_date": row[3].isoformat(),
            "author": row[4],
            "image": row[5],
            "tags": tags
        }

    except Exception as e:
        print(f"[ERROR] {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    finally:
        cursor.close()
        conn.close()
