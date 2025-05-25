from fastapi import APIRouter, HTTPException
from .db import get_db_connection
from fastapi import Depends
from .auth import get_current_user



router = APIRouter()

@router.post("/api/newsPage/{article_id}/vote")
def vote_article(article_id: int, user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Проверка: уже голосовал?
    cursor.execute("SELECT 1 FROM article_votes WHERE user_id = %s AND article_id = %s", (user_id, article_id))
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Вы уже голосовали за эту статью")

    # Обновляем рейтинг
    cursor.execute("UPDATE articles SET rating = COALESCE(rating, 0) + 1 WHERE id = %s", (article_id,))
    # Сохраняем, что пользователь проголосовал
    cursor.execute("INSERT INTO article_votes (user_id, article_id) VALUES (%s, %s)", (user_id, article_id))

    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Голос засчитан"}
@router.get("/api/newsPage/{article_id}")
def get_article_by_id(article_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT a.id, a.title, a.content, a.publication_date, u.username, ai.image_path, a.rating
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
            "rating": float(row[6]) if row[6] is not None else 0.0,
            "tags": tags
        }

    except Exception as e:
        print(f"[ERROR] {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

    finally:
        cursor.close()
        conn.close()
