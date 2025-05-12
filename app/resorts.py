# app/resorts.py
from fastapi import APIRouter
from .db import get_db_connection

router = APIRouter()

@router.get("/api/resorts")
def get_resorts():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sr.id, sr.name, cr.latitude, cr.longitude
        FROM ski_resort sr
        JOIN coordinates_resort cr ON sr.id = cr.resort_id
    """)
    resorts = cursor.fetchall()
    cursor.close()
    conn.close()

    return [
        {"id": r[0], "name": r[1], "latitude": r[2], "longitude": r[3]}
        for r in resorts
    ]
