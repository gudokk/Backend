from fastapi import APIRouter, HTTPException, Depends, Form
from .db import get_db_connection
from .auth import get_current_user
from datetime import datetime

router = APIRouter()

@router.post("/api/comments/{article_id}")
def post_comment(article_id: int, text: str = Form(...), user_id: int = Depends(get_current_user)):
    if not text.strip():
        raise HTTPException(status_code=400, detail="Комментарий не может быть пустым")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO comments (article_id, user_id, text, date)
        VALUES (%s, %s, %s, %s)
    """, (article_id, user_id, text, datetime.utcnow()))

    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Комментарий добавлен"}

@router.get("/api/comments/{article_id}")
def get_comments(article_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.text, c.date, u.username
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.article_id = %s
        ORDER BY c.date ASC
    """, (article_id,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return [
        {"text": row[0], "date": row[1].isoformat(), "author": row[2]}
        for row in rows
    ]
