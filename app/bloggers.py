from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from .auth import get_current_user  # или ваша система авторизации
from .db import get_db_connection

router = APIRouter()

class BloggerRequestCreate(BaseModel):
    comment: str

@router.post("/api/blogger-requests")
def submit_blogger_request(data: BloggerRequestCreate, user=Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    # Проверка: есть ли уже заявка
    cur.execute("SELECT id FROM blogger_requests WHERE user_id = %s AND status = 'pending'", (user,))
    if cur.fetchone():
        raise HTTPException(status_code=400, detail="Заявка уже отправлена")

    cur.execute(
        "INSERT INTO blogger_requests (user_id, comment) VALUES (%s, %s)",
        (user, data.comment)
    )
    conn.commit()
    cur.close()
    conn.close()

    return {"message": "Заявка отправлена"}

@router.get("/api/blogger-requests")
def get_blogger_requests(user_id=Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    is_admin = cur.fetchone()
    if not is_admin or not is_admin[0]:
        raise HTTPException(status_code=403, detail="Access denied")

    cur.execute("""
        SELECT br.id, u.username, u.email, br.comment, br.status, br.created_at
        FROM blogger_requests br
        JOIN users u ON br.user_id = u.id
        ORDER BY br.created_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "id": r[0],
            "username": r[1],
            "email": r[2],
            "comment": r[3],
            "status": r[4],
            "created_at": r[5]
        } for r in rows
    ]


@router.post("/api/blogger-requests/{request_id}/{action}")
def handle_request(request_id: int, action: str, user_id=Depends(get_current_user)):
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    is_admin = cur.fetchone()
    if not is_admin or not is_admin[0]:
        raise HTTPException(status_code=403, detail="Access denied")

    cur.execute("UPDATE blogger_requests SET status = %s WHERE id = %s", (action, request_id))

    if action == "approve":
        cur.execute("""
            UPDATE users
            SET is_blogger = TRUE
            WHERE id = (SELECT user_id FROM blogger_requests WHERE id = %s)
        """, (request_id,))

    conn.commit()
    cur.close()
    conn.close()

    return {"message": "Заявка обновлена"}

