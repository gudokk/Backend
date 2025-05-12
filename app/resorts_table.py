# app/resorts_table.py
from fastapi import APIRouter
from .db import get_db_connection

router = APIRouter()

@router.get("/api/resorts-table")
def get_resorts_table():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
SELECT
    sr.id,
    sr.name,
    sr.trail_length,
    sr.changes,
    sr.max_height,

    -- Длина зелёной трассы
    (SELECT t.trail_length FROM tracks t WHERE t.resort_id = sr.id AND t.trail_type = 'Зелёная' LIMIT 1) AS green,
    -- Длина синей трассы
    (SELECT t.trail_length FROM tracks t WHERE t.resort_id = sr.id AND t.trail_type = 'Синяя' LIMIT 1) AS blue,
    -- Длина красной трассы
    (SELECT t.trail_length FROM tracks t WHERE t.resort_id = sr.id AND t.trail_type = 'Красная' LIMIT 1) AS red,
    -- Длина чёрной трассы
    (SELECT t.trail_length FROM tracks t WHERE t.resort_id = sr.id AND t.trail_type = 'Чёрная' LIMIT 1) AS black,

    -- Подъёмники
    STRING_AGG(CONCAT(tl.lift_type, ': ', tl.lift_count), ', ') AS lifts

FROM ski_resort sr
LEFT JOIN lifts tl ON sr.id = tl.resort_id
GROUP BY sr.id, sr.name, sr.trail_length, sr.changes, sr.max_height
ORDER BY sr.name;

    """)
    resorts = cursor.fetchall()
    cursor.close()
    conn.close()

    return [
        {
            "id": row[0],
            "name": row[1],
            "total_km": row[2],
            "min_height": row[3] or 0,
            "max_height": row[4],
            "green": row[5],
            "blue": row[6],
            "red": row[7],
            "black": row[8],
            "lifts": row[9] or "нет данных"
        }
        for row in resorts
    ]
