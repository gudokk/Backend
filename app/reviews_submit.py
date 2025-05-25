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
    user_id: int = Depends(get_current_user)  # ✅ добавить обратно
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
                overall_comment, created_at
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s
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
            data.overall_comment, datetime.now()
        ))

        conn.commit()
        cur.close()
        conn.close()

        return {"message": "Отзыв успешно добавлен"}

    except Exception as e:
        print("Ошибка при добавлении отзыва:", e)
        raise HTTPException(status_code=500, detail="Ошибка сервера")
