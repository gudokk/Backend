# friends_routes.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from .db import get_db_connection
from .auth import get_current_user

router = APIRouter()

class UserPublic(BaseModel):
    id: int
    username: str
    photo: Optional[str] = None

# Получить список друзей
@router.get("/api/friends/list", response_model=List[UserPublic])
def get_friends(user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT u.id, u.username, u.photo
        FROM users u
        JOIN friendships f ON (f.user_id = %s AND f.friend_id = u.id)
                             OR (f.friend_id = %s AND f.user_id = u.id)
                             WHERE f.status = 'accepted'

    """, (user_id, user_id))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [UserPublic(id=r[0], username=r[1], photo=r[2]) for r in rows]

# Получить входящие заявки
@router.get("/api/friends/requests", response_model=List[UserPublic])
def get_incoming_requests(user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT u.id, u.username, u.photo
        FROM users u
        JOIN friendships f ON f.user_id = u.id
        WHERE f.friend_id = %s AND f.status = 'pending'
    """, (user_id,))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [UserPublic(id=r[0], username=r[1], photo=r[2]) for r in rows]

# Получить исходящие заявки
@router.get("/api/friends/outgoing", response_model=List[UserPublic])
def get_outgoing_requests(user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT u.id, u.username, u.photo
        FROM users u
        JOIN friendships f ON f.friend_id = u.id
        WHERE f.user_id = %s AND f.status = 'pending'
    """, (user_id,))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [UserPublic(id=r[0], username=r[1], photo=r[2]) for r in rows]

# Принять заявку
@router.post("/api/friends/accept/{requester_id}")
def accept_friend(requester_id: int, user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE friendships SET status = 'accepted'
        WHERE user_id = %s AND friend_id = %s AND status = 'pending'
    """, (requester_id, user_id))

    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Запрос не найден")

    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Принято"}

# Отклонить заявку
@router.post("/api/friends/decline/{requester_id}")
def decline_friend(requester_id: int, user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM friendships
        WHERE user_id = %s AND friend_id = %s AND status = 'pending'
    """, (requester_id, user_id))

    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Отклонено"}

# Удалить друга
@router.delete("/api/friends/remove/{friend_id}")
def remove_friend(friend_id: int, user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM friendships
        WHERE (user_id = %s AND friend_id = %s)
           OR (user_id = %s AND friend_id = %s)
    """, (user_id, friend_id, friend_id, user_id))

    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Удалено из друзей"}

@router.post("/api/friends/add/{target_id}")
def send_friend_request(target_id: int, user_id: int = Depends(get_current_user)):
    if target_id == user_id:
        raise HTTPException(status_code=400, detail="Нельзя добавить себя")

    conn = get_db_connection()
    cur = conn.cursor()

    # Проверим, не существует ли уже заявка или дружба
    cur.execute("""
        SELECT 1 FROM friendships
        WHERE (user_id = %s AND friend_id = %s)
           OR (user_id = %s AND friend_id = %s)
    """, (user_id, target_id, target_id, user_id))
    if cur.fetchone():
        raise HTTPException(status_code=400, detail="Уже есть заявка или дружба")

    # Отправим заявку
    cur.execute("""
        INSERT INTO friendships (user_id, friend_id, status)
        VALUES (%s, %s, 'pending')
    """, (user_id, target_id))

    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Заявка отправлена"}

@router.get("/api/users/search", response_model=List[UserPublic])
def search_users(query: str, user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, username, photo
        FROM users
        WHERE username ILIKE %s AND id != %s
        LIMIT 20
    """, (f"%{query}%", user_id))

    users = [UserPublic(id=row[0], username=row[1], photo=row[2]) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return users
