from fastapi import APIRouter, HTTPException
from .db import get_db_connection

router = APIRouter()

@router.get("/api/resort-features/{resort_id}")
def get_resort_features(resort_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT panoramic_trails_above_2500m, guaranteed_snow, snowboard_friendly,
                   night_skiing, kiting_available, snowparks_count, halfpipes_count,
                   artificial_snow, forest_trails, glacier_available, summer_skiing,
                   freeride_opportunities, official_freeride_zones, backcountry_routes,
                   heliski_available, official_freeride_guides, kids_ski_schools,
                   fis_certified_trails_count
            FROM resort_features
            WHERE resort_id = %s
        """, (resort_id,))

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Features not found")

        columns = [
            "panoramic_trails_above_2500m", "guaranteed_snow", "snowboard_friendly",
            "night_skiing", "kiting_available", "snowparks_count", "halfpipes_count",
            "artificial_snow", "forest_trails", "glacier_available", "summer_skiing",
            "freeride_opportunities", "official_freeride_zones", "backcountry_routes",
            "heliski_available", "official_freeride_guides", "kids_ski_schools",
            "fis_certified_trails_count"
        ]

        return dict(zip(columns, row))

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
