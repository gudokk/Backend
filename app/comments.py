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
        WHERE c.article_id = %s AND c.is_published = TRUE

        ORDER BY c.date ASC
    """, (article_id,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    return [
        {"text": row[0], "date": row[1].isoformat(), "author": row[2]}
        for row in rows
    ]

@router.get("/api/admin/comments")
def get_pending_comments(current_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Проверка прав администратора
    cursor.execute("SELECT is_admin FROM users WHERE id = %s", (current_id,))
    is_admin = cursor.fetchone()
    if not is_admin or not is_admin[0]:
        raise HTTPException(status_code=403, detail="Access denied")

    cursor.execute("""
        SELECT c.id, c.text, c.date, u.username, a.title
        FROM comments c
        JOIN users u ON c.user_id = u.id
        JOIN articles a ON c.article_id = a.id
        WHERE c.is_published = FALSE
        ORDER BY c.date ASC
    """)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return [
        {
            "id": r[0],
            "text": r[1],
            "date": r[2].isoformat(),
            "author": r[3],
            "article_title": r[4]
        }
        for r in rows
    ]
@router.delete("/api/admin/comments/{comment_id}")
def delete_comment(comment_id: int, current_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT is_admin FROM users WHERE id = %s", (current_id,))
    is_admin = cursor.fetchone()
    if not is_admin or not is_admin[0]:
        raise HTTPException(status_code=403, detail="Access denied")

    cursor.execute("DELETE FROM comments WHERE id = %s", (comment_id,))
    conn.commit()

    cursor.close()
    conn.close()

    return {"message": "Комментарий удалён"}