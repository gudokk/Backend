from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from .db import get_db_connection

router = APIRouter()

@router.get("/api/resorts/selector")
def get_resorts_for_selector(
    snow_last_3_days: Optional[bool] = Query(None),
    snow_expected: Optional[bool] = Query(None),
    slopes: Optional[str] = Query(None),
    visa: Optional[str] = Query(None)
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        filters = []
        params = []

        if snow_last_3_days is not None:
            filters.append("rwth.snow_last_3_days = %s")
            params.append(snow_last_3_days)

        if snow_expected is not None:
            filters.append("rwth.snow_expected = %s")
            params.append(snow_expected)

        # Фильтрация по трассам с ненулевой длиной
        if slopes:
            if slopes == "Зелёная":
                filters.append("trails.trail_green > 0")
            elif slopes == "Синяя":
                filters.append("trails.trail_blue > 0")
            elif slopes == "Красная":
                filters.append("trails.trail_red > 0")
            elif slopes == "Чёрная":
                filters.append("trails.trail_black > 0")
        if visa:
            if visa == "no":
                filters.append("sr.visa = false")
            elif visa == "yes":
                filters.append("sr.visa = true")

        where_clause = "WHERE " + " AND ".join(filters) if filters else ""

        query = f"""
            SELECT 
                sr.id,
                sr.name,
                sr.country,
                sr.trail_length,
                sr.changes,
                sr.max_height,
                COALESCE(sp.price_day, 0),
                COALESCE(lifts.lift_info, ''),
                COALESCE(rw.num_reviews, 0),
                COALESCE(rw.avg_rating, 0),
                rw.latest_review,
                COALESCE(trails.trail_green, 0),
                COALESCE(trails.trail_blue, 0),
                COALESCE(trails.trail_red, 0),
                COALESCE(trails.trail_black, 0)
            FROM ski_resort sr
            LEFT JOIN ski_pass sp ON sr.id = sp.resort_id
            LEFT JOIN (
                SELECT resort_id, 
                       COUNT(*) AS num_reviews,
                       ROUND(AVG((
                           rating_skiing + rating_lifts + rating_prices + 
                           rating_snow_weather + rating_accommodation + 
                           rating_people + rating_apres_ski) / 7.0), 1) AS avg_rating,
                       MAX(overall_comment) FILTER (WHERE created_at = (
                           SELECT MAX(created_at) 
                           FROM resort_reviews r2 
                           WHERE r1.resort_id = r2.resort_id
                       )) AS latest_review
                FROM resort_reviews r1
                GROUP BY resort_id
            ) rw ON sr.id = rw.resort_id
            LEFT JOIN (
                SELECT resort_id, STRING_AGG(lift_type || ' ' || lift_count, ', ') AS lift_info
                FROM lifts
                GROUP BY resort_id
            ) lifts ON sr.id = lifts.resort_id
            LEFT JOIN (
                SELECT 
                    resort_id,
                    ROUND(SUM(CASE WHEN trail_type = 'Зелёная' THEN trail_length ELSE 0 END)::numeric, 1) AS trail_green,
                    ROUND(SUM(CASE WHEN trail_type = 'Синяя' THEN trail_length ELSE 0 END)::numeric, 1) AS trail_blue,
                    ROUND(SUM(CASE WHEN trail_type = 'Красная' THEN trail_length ELSE 0 END)::numeric, 1) AS trail_red,
                    ROUND(SUM(CASE WHEN trail_type = 'Чёрная' THEN trail_length ELSE 0 END)::numeric, 1) AS trail_black
                FROM tracks
                GROUP BY resort_id
            ) trails ON sr.id = trails.resort_id
            LEFT JOIN resort_weather rwth ON sr.id = rwth.resort_id
            {where_clause}
        """

        cursor.execute(query, tuple(params))

        resorts = []
        for row in cursor.fetchall():
            resorts.append({
                "id": row[0],
                "name": row[1],
                "country": row[2],
                "trail_length": row[3],
                "changes": row[4],
                "max_height": row[5],
                "price_day": row[6],
                "lifts": row[7],
                "num_reviews": row[8],
                "average_rating": row[9],
                "latest_review": row[10],
                "trail_green": float(row[11]),
                "trail_blue": float(row[12]),
                "trail_red": float(row[13]),
                "trail_black": float(row[14]),
            })

        cursor.close()
        conn.close()
        return resorts
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))