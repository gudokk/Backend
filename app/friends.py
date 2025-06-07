from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import date
from .db import get_db_connection
from .auth import get_current_user

router = APIRouter()


class UserPublic(BaseModel):
    id: int
    username: str
    photo: Optional[str] = None
    is_friend: Optional[bool] = False

class TripOut(BaseModel):
    id: int
    resort_name: str
    trip_start_date: date
    trip_end_date: date

def normalize_pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)

@router.get("/api/friends/list", response_model=List[UserPublic])
def get_friends(user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT u.id, u.username, u.photo
        FROM friendships f
        JOIN users u ON u.id = CASE
            WHEN f.user_id1 = %s THEN f.user_id2
            ELSE f.user_id1
        END
        WHERE f.status = 'accepted'
        AND (%s = f.user_id1 OR %s = f.user_id2)
    """, (user_id, user_id, user_id))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [UserPublic(id=r[0], username=r[1], photo=r[2]) for r in rows]

@router.get("/api/friends/requests", response_model=List[UserPublic])
def get_incoming_requests(user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT u.id, u.username, u.photo
        FROM friendships f
        JOIN users u ON u.id = CASE
            WHEN f.user_id1 = %s THEN f.user_id2
            ELSE f.user_id1
        END
        WHERE f.status = 'pending'
        AND f.requester_id != %s
        AND (%s = f.user_id1 OR %s = f.user_id2)
    """, (user_id, user_id, user_id, user_id))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [UserPublic(id=r[0], username=r[1], photo=r[2]) for r in rows]

@router.get("/api/friends/outgoing", response_model=List[UserPublic])
def get_outgoing_requests(user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT u.id, u.username, u.photo
        FROM friendships f
        JOIN users u ON u.id = CASE
            WHEN f.user_id1 = %s THEN f.user_id2
            ELSE f.user_id1
        END
        WHERE f.status = 'pending'
        AND f.requester_id = %s
        AND (%s = f.user_id1 OR %s = f.user_id2)
    """, (user_id, user_id, user_id, user_id))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [UserPublic(id=r[0], username=r[1], photo=r[2]) for r in rows]

@router.post("/api/friends/add/{target_id}")
def send_friend_request(target_id: int, user_id: int = Depends(get_current_user)):
    if target_id == user_id:
        raise HTTPException(400, detail="Нельзя добавить себя")

    uid1, uid2 = normalize_pair(user_id, target_id)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT 1 FROM friendships WHERE user_id1 = %s AND user_id2 = %s
    """, (uid1, uid2))

    if cur.fetchone():
        raise HTTPException(400, detail="Уже есть заявка или дружба")

    cur.execute("""
        INSERT INTO friendships (user_id1, user_id2, status, requester_id)
        VALUES (%s, %s, 'pending', %s)
    """, (uid1, uid2, user_id))

    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Заявка отправлена"}

@router.post("/api/friends/accept/{requester_id}")
def accept_friend(requester_id: int, user_id: int = Depends(get_current_user)):
    uid1, uid2 = normalize_pair(user_id, requester_id)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE friendships SET status = 'accepted'
        WHERE user_id1 = %s AND user_id2 = %s
          AND requester_id = %s AND status = 'pending'
    """, (uid1, uid2, requester_id))

    if cur.rowcount == 0:
        raise HTTPException(404, detail="Заявка не найдена")

    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Принято"}

@router.post("/api/friends/decline/{requester_id}")
def decline_friend(requester_id: int, user_id: int = Depends(get_current_user)):
    uid1, uid2 = normalize_pair(user_id, requester_id)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM friendships
        WHERE user_id1 = %s AND user_id2 = %s
          AND status = 'pending'
    """, (uid1, uid2))

    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Отклонено"}

@router.delete("/api/friends/remove/{friend_id}")
def remove_friend(friend_id: int, user_id: int = Depends(get_current_user)):
    uid1, uid2 = normalize_pair(user_id, friend_id)

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM friendships
        WHERE user_id1 = %s AND user_id2 = %s
    """, (uid1, uid2))

    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Удалено из друзей"}

@router.get("/api/users/search", response_model=List[UserPublic])
def search_users(
    query: str = Query(...),
    user_id: int = Depends(get_current_user)
):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT u.id, u.username, u.photo,
            EXISTS (
                SELECT 1 FROM friendships f
                WHERE f.status = 'accepted'
                  AND ((f.user_id1 = %s AND f.user_id2 = u.id)
                    OR (f.user_id2 = %s AND f.user_id1 = u.id))
            ) AS is_friend
        FROM users u
        WHERE u.username ILIKE %s AND u.id != %s
        LIMIT 20
    """, (user_id, user_id, f"%{query}%", user_id))

    users = [
        {
            "id": row[0],
            "username": row[1],
            "photo": row[2],
            "is_friend": row[3],
        }
        for row in cur.fetchall()
    ]

    cur.close()
    conn.close()
    return users

@router.get("/api/users/{user_id}")
def get_user_by_id(user_id: int, current_user: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            u.id, u.username, u.photo, u.description, u.email,
            CASE
                WHEN EXISTS (
                    SELECT 1 FROM friendships f
                    WHERE f.status = 'accepted'
                      AND ((f.user_id1 = %s AND f.user_id2 = u.id)
                        OR (f.user_id2 = %s AND f.user_id1 = u.id))
                ) THEN 'friend'
                WHEN EXISTS (
                    SELECT 1 FROM friendships f
                    WHERE f.status = 'pending'
                      AND ((f.user_id1 = %s AND f.user_id2 = u.id)
                        OR (f.user_id2 = %s AND f.user_id1 = u.id))
                ) THEN 'pending'
                ELSE 'none'
            END AS friend_status
        FROM users u
        WHERE u.id = %s
    """, (current_user, current_user, current_user, current_user, user_id))

    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        raise HTTPException(404, detail="Пользователь не найден")

    return {
        "id": row[0],
        "username": row[1],
        "photo": row[2],
        "description": row[3],
        "email": row[4],
        "friend_status": row[5],  # "friend", "pending", "none"
    }


@router.get("/api/trips/{user_id}", response_model=List[TripOut])
def get_trips_for_user(user_id: int, current_user: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    # Проверка, являются ли друзьями
    cur.execute("""
        SELECT f.status
        FROM friendships f
        WHERE ((f.user_id1 = %s AND f.user_id2 = %s) OR (f.user_id2 = %s AND f.user_id1 = %s))
          AND f.status = 'accepted'
    """, (current_user, user_id, current_user, user_id))

    if not cur.fetchone():
        raise HTTPException(403, detail="Нет доступа к поездкам пользователя")

    # Получение поездок пользователя
    cur.execute("""
        SELECT t.id, t.resort_name, t.trip_start_date, t.trip_end_date, t.description
        FROM trips t
        JOIN trip_participants tp ON tp.trip_id = t.id
        WHERE tp.user_id = %s
        ORDER BY t.trip_start_date
    """, (user_id,))

    trips = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "id": row[0],
            "resort_name": row[1],
            "trip_start_date": row[2],
            "trip_end_date": row[3],
            "description": row[4],
        }
        for row in trips
    ]
