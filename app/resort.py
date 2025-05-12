from fastapi import APIRouter, HTTPException
from .db import get_db_connection

router = APIRouter()

@router.get("/api/resorts/{resort_id}")
def get_resort(resort_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                sr.id, sr.name, sr.information, sr.trail_length, sr.changes, sr.max_height, sr.season,
                STRING_AGG(tl.lift_type || ': ' || tl.lift_count, ', ') AS lifts,
                rei.how_to_get_there, rei.nearby_cities, rei.related_ski_areas
            FROM ski_resort sr
            LEFT JOIN lifts tl ON sr.id = tl.resort_id
            LEFT JOIN resort_extra_info rei ON sr.id = rei.resort_id
            WHERE sr.id = %s
            GROUP BY sr.id, rei.how_to_get_there, rei.nearby_cities, rei.related_ski_areas
        """, (resort_id,))

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Resort not found")

        return {
            "id": row[0],
            "name": row[1],
            "information": row[2],
            "trail_length": row[3],
            "changes": row[4],
            "max_height": row[5],
            "season": row[6],
            "lifts": row[7] or "нет данных",
            "how_to_get_there": row[8],
            "nearby_cities": row[9],
            "related_ski_areas": row[10]
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

