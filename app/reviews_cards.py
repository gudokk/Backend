from fastapi import APIRouter, HTTPException
from .db import get_db_connection

router = APIRouter()

@router.get("/api/resorts/{resort_id}/reviews")
def get_reviews_by_resort(resort_id: int):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                r.id,
                r.user_id,
                u.username,
                r.stay_month,
                r.stay_year,

                r.rating_skiing,
                r.comment_skiing,
                r.rating_lifts,
                r.comment_lifts,
                r.rating_prices,
                r.comment_prices,
                r.rating_snow_weather,
                r.comment_snow_weather,
                r.rating_accommodation,
                r.comment_accommodation,
                r.rating_people,
                r.comment_people,
                r.rating_apres_ski,
                r.comment_apres_ski,
                r.overall_comment,
                r.created_at,

                ROUND((
                    COALESCE(r.rating_skiing, 0) +
                    COALESCE(r.rating_lifts, 0) +
                    COALESCE(r.rating_prices, 0) +
                    COALESCE(r.rating_snow_weather, 0) +
                    COALESCE(r.rating_accommodation, 0) +
                    COALESCE(r.rating_people, 0) +
                    COALESCE(r.rating_apres_ski, 0)
                )::numeric / 7, 1) AS average_rating

            FROM resort_reviews r
            JOIN users u ON r.user_id = u.id
            WHERE r.resort_id = %s
            ORDER BY r.created_at DESC
        """, (resort_id,))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        reviews = []
        for row in rows:
            reviews.append({
                "id": row[0],
                "user_id": row[1],
                "username": row[2],
                "stay_month": row[3],
                "stay_year": row[4],

                "rating_skiing": row[5],
                "comment_skiing": row[6],
                "rating_lifts": row[7],
                "comment_lifts": row[8],
                "rating_prices": row[9],
                "comment_prices": row[10],
                "rating_snow_weather": row[11],
                "comment_snow_weather": row[12],
                "rating_accommodation": row[13],
                "comment_accommodation": row[14],
                "rating_people": row[15],
                "comment_people": row[16],
                "rating_apres_ski": row[17],
                "comment_apres_ski": row[18],

                "overall_comment": row[19],
                "created_at": row[20],
                "average_rating": float(row[21])
            })

        return reviews

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
