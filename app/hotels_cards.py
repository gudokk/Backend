# --- FastAPI backend endpoint ---
from fastapi import APIRouter, HTTPException
from .db import get_db_connection

router = APIRouter()

@router.get("/api/resorts/{resort_id}/hotels")
def get_hotels_by_resort(resort_id: int):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT 
                h.id, h.name, h.hotel_type, h.stars, h.reviews_count,
                h.rating, h.yandex_link, h.distance_to_lift, h.price_per_night,
                ARRAY_AGG(hi.image_path) AS images
            FROM hotels h
            LEFT JOIN hotels_images hi ON h.id = hi.hotel_id
            WHERE h.resort_id = %s
            GROUP BY h.id
        """, (resort_id,))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        result = []
        for row in rows:
            result.append({
                "id": row[0],
                "name": row[1],
                "hotel_type": row[2],
                "stars": row[3],
                "reviews_count": row[4],
                "rating": float(row[5]),
                "yandex_link": row[6],
                "distance_to_lift": row[7],
                "price_per_night": row[8],
                "images": row[9] if row[9] else []
            })

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
