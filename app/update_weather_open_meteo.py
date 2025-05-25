import requests
import psycopg2
from datetime import datetime

# Настройки подключения к БД
conn = psycopg2.connect(
    dbname="ski_portal",
    user="postgres",
    password="nikita",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

# Получение координат всех курортов
cur.execute("""
    SELECT sr.id, cr.latitude, cr.longitude
    FROM ski_resort sr
    JOIN coordinates_resort cr ON sr.id = cr.resort_id
""")
resorts = cur.fetchall()

for resort_id, latitude, longitude in resorts:
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": "latitude",
                "longitude": "longitude",
                "daily": "snowfall",
                "timezone": "auto"
            },
            timeout=10
        )
        data = response.json()

        snow_values = data.get("daily", {}).get("snowfall", [])
        dates = data.get("daily", {}).get("time", [])

        snow_last_3_days = False
        snow_expected = False

        for i in range(min(3, len(snow_values))):
            if snow_values[i] and snow_values[i] > 0:
                snow_last_3_days = True

        for i in range(1, min(4, len(snow_values))):
            if snow_values[i] and snow_values[i] > 0:
                snow_expected = True

        # Обновляем таблицу resort_weather
        cur.execute("""
            INSERT INTO resort_weather (resort_id, snow_last_3_days, snow_expected, updated_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (resort_id) DO UPDATE
            SET snow_last_3_days = EXCLUDED.snow_last_3_days,
                snow_expected = EXCLUDED.snow_expected,
                updated_at = now()
        """, (resort_id, snow_last_3_days, snow_expected))

        print(f"[✓] Обновлено: курорт {resort_id}")

    except Exception as e:
        print(f"[!] Ошибка для курорта {resort_id}: {e}")

conn.commit()
cur.close()
conn.close()
