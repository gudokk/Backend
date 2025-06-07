from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from typing import List
from pydantic import BaseModel
from .auth import get_current_user
import os, shutil
from datetime import datetime
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

@router.get("/api/blogger-reviews")
def get_approved_reviews():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT br.id, br.title, br.content, u.username, br.created_at
        FROM blogger_reviews br
        JOIN users u ON br.user_id = u.id
        WHERE br.status = 'approved'
        ORDER BY br.created_at DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "id": r[0],
            "title": r[1],
            "content": r[2],
            "author": r[3],
            "created_at": r[4]
        } for r in rows
    ]

@router.post("/api/blogger-reviews")
async def create_blogger_review(
    title: str = Form(...),
    content: str = Form(...),  # HTML-формат
    images: List[UploadFile] = File([]),
    user_id: int = Depends(get_current_user)
):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO blogger_reviews (user_id, title, content, status)
        VALUES (%s, %s, %s, 'pending') RETURNING id
    """, (user_id, title, content))

    review_id = cur.fetchone()[0]

    image_dir = f"app/static/images/blogger_reviews/{review_id}"
    os.makedirs(image_dir, exist_ok=True)

    for idx, image in enumerate(images, 1):
        ext = os.path.splitext(image.filename)[1]
        filename = f"img{idx}{ext}"
        server_path = os.path.join(image_dir, filename)
        web_path = f"/static/images/blogger_reviews/{review_id}/{filename}"

        with open(server_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        cur.execute("""
            INSERT INTO blogger_review_images (review_id, image_path)
            VALUES (%s, %s)
        """, (review_id, web_path))

    conn.commit()
    cur.close()
    conn.close()

    return {"message": "Обзор успешно опубликован"}

@router.get("/api/blogger-reviews/moderation")
def get_pending_reviews(user_id=Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    if not cur.fetchone()[0]:
        raise HTTPException(status_code=403, detail="Access denied")

    cur.execute("""
        SELECT br.id, br.title, br.content, u.username, br.created_at, br.status
        FROM blogger_reviews br
        JOIN users u ON br.user_id = u.id
        WHERE br.status = 'pending'
        ORDER BY br.created_at DESC
    """)
    reviews = cur.fetchall()

    result = []
    for r in reviews:
        cur.execute(
            "SELECT image_path FROM blogger_review_images WHERE review_id = %s",
            (r[0],)
        )
        images = [img[0] for img in cur.fetchall()]
        result.append({
            "id": r[0],
            "title": r[1],
            "content": r[2],
            "author": r[3],
            "created_at": r[4],
            "status": r[5],
            "images": images
        })

    cur.close()
    conn.close()
    return result

@router.post("/api/blogger-reviews/{review_id}/{action}")
def moderate_blogger_review(
    review_id: int,
    action: str,
    comment: str = Form(""),
    user_id=Depends(get_current_user)
):
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    is_admin = cur.fetchone()
    if not is_admin or not is_admin[0]:
        raise HTTPException(status_code=403, detail="Access denied")

    status = "approved" if action == "approve" else "rejected"
    cur.execute("""
        UPDATE blogger_reviews
        SET status = %s, moderation_comment = %s
        WHERE id = %s
    """, (status, comment, review_id))

    conn.commit()
    cur.close()
    conn.close()

    return {"message": f"Обзор {status}"}

@router.get("/api/blogger-reviews/{review_id}/images")
def get_review_images(review_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT image_path FROM blogger_review_images WHERE review_id = %s", (review_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]
