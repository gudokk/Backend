from typing import List, Optional
from pydantic import BaseModel
from datetime import date as dt
from fastapi import APIRouter, HTTPException, Depends, Path, Body
from .db import get_db_connection
from .auth import get_current_user

router = APIRouter()


class TripCreate(BaseModel):
    resort_name: str
    trip_start_date: dt
    trip_end_date: dt
    description: Optional[str] = None

class TripOut(BaseModel):
    id: int
    resort_name: str
    trip_start_date: dt
    trip_end_date: dt
    description: Optional[str]

@router.get("/api/trips", response_model=List[TripOut])
def get_user_trips(user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.id, t.resort_name, t.trip_start_date, t.trip_end_date, t.description
        FROM trips t
        JOIN trip_participants tp ON tp.trip_id = t.id
        WHERE tp.user_id = %s
        ORDER BY t.trip_start_date
    """, (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "id": r[0],
            "resort_name": r[1],
            "trip_start_date": r[2],
            "trip_end_date": r[3],
            "description": r[4],
        } for r in rows
    ]


@router.post("/api/trips", response_model=TripOut)
def create_trip(trip: TripCreate, user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO trips (resort_name, trip_start_date, trip_end_date, description, created_by)
        VALUES (%s, %s, %s, %s, %s) RETURNING id
    """, (trip.resort_name, trip.trip_start_date, trip.trip_end_date, trip.description, user_id))
    trip_id = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO trip_participants (trip_id, user_id)
        VALUES (%s, %s)
    """, (trip_id, user_id))

    conn.commit()

    cur.execute("""
        SELECT id, resort_name, trip_start_date, trip_end_date, description
        FROM trips WHERE id = %s
    """, (trip_id,))
    row = cur.fetchone()

    cur.close()
    conn.close()
    return {
        "id": row[0],
        "resort_name": row[1],
        "trip_start_date": row[2],
        "trip_end_date": row[3],
        "description": row[4],
    }


@router.delete("/api/trips/{trip_id}")
def delete_trip(trip_id: int, user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT created_by FROM trips WHERE id = %s", (trip_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Поездка не найдена")
    if row[0] != user_id:
        raise HTTPException(403, "Вы не можете удалить чужую поездку")

    cur.execute("DELETE FROM trips WHERE id = %s", (trip_id,))
    conn.commit()
    cur.close()
    conn.close()

    return {"message": "Поездка удалена"}


@router.post("/api/trips/join_user/{trip_id}")
def join_trip(trip_id: int, user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT trip_end_date FROM trips WHERE id = %s", (trip_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Поездка не найдена")

    if row[0] < dt.today():
        raise HTTPException(400, "Поездка уже завершена")

    cur.execute("SELECT 1 FROM trip_participants WHERE trip_id = %s AND user_id = %s", (trip_id, user_id))
    if cur.fetchone():
        raise HTTPException(400, "Вы уже участвуете в этой поездке")

    cur.execute("INSERT INTO trip_participants (trip_id, user_id) VALUES (%s, %s)", (trip_id, user_id))
    conn.commit()
    cur.close()
    conn.close()

    return {"message": "Вы присоединились к поездке"}


@router.get("/api/trips/{trip_id}/participants")
def get_participants(trip_id: int, user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT u.id, u.username, u.photo
        FROM trip_participants tp
        JOIN users u ON tp.user_id = u.id
        WHERE tp.trip_id = %s
    """, (trip_id,))

    users = [
        {"id": r[0], "username": r[1], "photo": r[2]}
        for r in cur.fetchall()
    ]

    cur.close()
    conn.close()
    return users

@router.post("/api/trips/leave/{trip_id}")
def leave_trip(trip_id: int, user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    # Проверяем, участвует ли пользователь в поездке
    cur.execute("SELECT 1 FROM trip_participants WHERE trip_id = %s AND user_id = %s", (trip_id, user_id))
    if not cur.fetchone():
        raise HTTPException(400, "Вы не участвуете в этой поездке")

    # Удаляем участие
    cur.execute("DELETE FROM trip_participants WHERE trip_id = %s AND user_id = %s", (trip_id, user_id))
    conn.commit()
    cur.close()
    conn.close()

    return {"message": "Вы покинули поездку"}
