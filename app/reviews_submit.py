from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime
from .db import get_db_connection
from .auth import get_current_user
router = APIRouter()

class ReviewInput(BaseModel):
    stay_month: str
    stay_year: int
    rating_skiing: int
    comment_skiing: str
    rating_lifts: int
    comment_lifts: str
    rating_prices: int
    comment_prices: str
    rating_snow_weather: int
    comment_snow_weather: str
    rating_accommodation: int
    comment_accommodation: str
    rating_people: int
    comment_people: str
    rating_apres_ski: int
    comment_apres_ski: str
    overall_comment: str
@router.post("/api/resorts/{resort_id}/submit-review")
async def submit_review(
    resort_id: int,
    data: ReviewInput,
    user_id: int = Depends(get_current_user)
):
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO resort_reviews (
                resort_id, user_id, stay_month, stay_year,
                rating_skiing, comment_skiing,
                rating_lifts, comment_lifts,
                rating_prices, comment_prices,
                rating_snow_weather, comment_snow_weather,
                rating_accommodation, comment_accommodation,
                rating_people, comment_people,
                rating_apres_ski, comment_apres_ski,
                overall_comment, created_at, status
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s
            )
        """, (
            resort_id, user_id, data.stay_month, data.stay_year,
            data.rating_skiing, data.comment_skiing,
            data.rating_lifts, data.comment_lifts,
            data.rating_prices, data.comment_prices,
            data.rating_snow_weather, data.comment_snow_weather,
            data.rating_accommodation, data.comment_accommodation,
            data.rating_people, data.comment_people,
            data.rating_apres_ski, data.comment_apres_ski,
            data.overall_comment, datetime.now(), "pending"
        ))

        conn.commit()
        cur.close()
        conn.close()

        return {"message": "Отзыв отправлен на модерацию"}

    except Exception as e:
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.get("/api/reviews/pending")
def get_pending_reviews(user_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    is_admin = cur.fetchone()
    if not is_admin or not is_admin[0]:
        raise HTTPException(status_code=403, detail="Access denied")

    cur.execute("""
SELECT rr.id, u.username, r.name,
       rr.stay_month, rr.stay_year, rr.overall_comment,
       rr.comment_skiing, rr.rating_skiing,
       rr.comment_lifts, rr.rating_lifts,
       rr.comment_prices, rr.rating_prices,
       rr.comment_snow_weather, rr.rating_snow_weather,
       rr.comment_accommodation, rr.rating_accommodation,
       rr.comment_people, rr.rating_people,
       rr.comment_apres_ski, rr.rating_apres_ski
FROM resort_reviews rr
JOIN users u ON rr.user_id = u.id
JOIN ski_resort r ON rr.resort_id = r.id
WHERE rr.status = 'pending'
ORDER BY rr.created_at DESC

    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [
        {
            "id": r[0], "username": r[1], "resort": r[2],
            "stay_month": r[3], "stay_year": r[4], "overall_comment": r[5],
            "comment_skiing": r[6], "rating_skiing": r[7],
            "comment_lifts": r[8], "rating_lifts": r[9],
            "comment_prices": r[10], "rating_prices": r[11],
            "comment_snow_weather": r[12], "rating_snow_weather": r[13],
            "comment_accommodation": r[14], "rating_accommodation": r[15],
            "comment_people": r[16], "rating_people": r[17],
            "comment_apres_ski": r[18], "rating_apres_ski": r[19],
        } for r in rows
    ]


@router.post("/api/reviews/{review_id}/{action}")
def moderate_review(review_id: int, action: str, user_id: int = Depends(get_current_user)):
    if action not in ["approve", "reject"]:
        raise HTTPException(status_code=400, detail="Invalid action")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    is_admin = cur.fetchone()
    if not is_admin or not is_admin[0]:
        raise HTTPException(status_code=403, detail="Access denied")

    cur.execute("""
        UPDATE resort_reviews
        SET status = %s
        WHERE id = %s
    """, (action, review_id))

    conn.commit()
    cur.close()
    conn.close()

    return {"message": f"Review {action}d successfully"}
