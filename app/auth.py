# app/auth.py

from fastapi import APIRouter, HTTPException, Header, Depends, File, UploadFile, Form, status
from .models import UserCreate, UserLogin
import os, shutil, json
from fastapi.responses import JSONResponse
from .db import get_db_connection
from .config import SECRET_KEY, ALGORITHM
from jose import jwt, JWTError
import bcrypt
import datetime
import requests

router = APIRouter()

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_token(data: dict, expires_delta: datetime.timedelta):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: int):
    return create_token({"sub": str(user_id)}, datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(user_id: int):
    return create_token({"sub": str(user_id)}, datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))


def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload.get("sub"))
    except JWTError:
        return None


def get_current_user(Authorization: str = Header(...)):
    token = Authorization.split(" ")[1]
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return int(user_id)


@router.post("/api/register")
async def register_user(user: UserCreate):
    if len(user.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )

    hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Проверка username
        cursor.execute("SELECT id FROM Users WHERE username = %s", (user.username,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists."
            )

        # Проверка email
        cursor.execute("SELECT id FROM Users WHERE email = %s", (user.email,))
        if cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered."
            )

        registration_date = datetime.date.today()
        cursor.execute(
            """
            INSERT INTO Users (username, email, password, registration_date)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (user.username, user.email, hashed_password.decode('utf-8'), registration_date)
        )
        user_id = cursor.fetchone()[0]

        conn.commit()
        return {"message": "User registered successfully", "userId": user_id}

    except HTTPException:
        raise  # пробрасываем специально выброшенные HTTP ошибки

    except Exception as e:
        print(f"Unexpected registration error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@router.post("/api/login")
async def login_user(user: UserLogin):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, password, is_active FROM Users WHERE username = %s", (user.username,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if not result:
            raise HTTPException(status_code=401, detail="Неверный логин или пароль.")

        user_id, stored_password, is_active = result

        if not is_active:
            raise HTTPException(status_code=403, detail="Пользователь заблокирован.")

        if not bcrypt.checkpw(user.password.encode(), stored_password.encode()):
            raise HTTPException(status_code=401, detail="Неверный логин или пароль.")

        return {
            "access_token": create_access_token(user_id),
            "refresh_token": create_refresh_token(user_id),
            "token_type": "bearer"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error during login: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.post("/api/refresh")
async def refresh_token(refresh_token: str = Header(...)):
    user_id = decode_access_token(refresh_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    return {
        "access_token": create_access_token(user_id),
        "token_type": "bearer"
    }


@router.get("/api/profile")
def get_profile(user_id=Depends(get_current_user)):
    conn = get_db_connection()
    cur = conn.cursor()

    # Получаем данные пользователя
    cur.execute("""
        SELECT id, username, email, registration_date, description, gender, photo, is_admin, is_blogger
        FROM users
        WHERE id = %s
    """, (user_id,))
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Проверяем наличие ожидающей заявки блогера
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM blogger_requests
            WHERE user_id = %s AND status = 'pending'
        )
    """, (user_id,))
    has_pending = cur.fetchone()[0]

    # Считаем количество друзей (принятые заявки)
    cur.execute("""
        SELECT COUNT(*) FROM friendships
        WHERE (user_id1 = %s OR user_id2 = %s)
          AND status = 'accepted'
    """, (user_id, user_id))
    friends_count = cur.fetchone()[0]

    cur.close()
    conn.close()

    return {
        "id": row[0],
        "username": row[1],
        "email": row[2],
        "registration_date": row[3],
        "description": row[4],
        "gender": row[5],
        "photo": row[6],
        "is_admin": row[7],
        "is_blogger": row[8],
        "has_pending_blogger_request": has_pending,
        "friends_count": friends_count
    }



@router.post("/api/profile/update")
async def update_profile(
    user_id: int = Depends(get_current_user),
    username: str = Form(...),
    email: str = Form(...),
    description: str = Form(""),
    gender: str = Form(""),
    photo: UploadFile = File(None),
    photo_delete: bool = Form(False)
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        photo_path = None

        # Если пользователь запросил удаление фото
        if photo_delete:
            # Получим текущий путь фото
            cursor.execute("SELECT photo FROM users WHERE id = %s", (user_id,))
            current_photo = cursor.fetchone()[0]
            if current_photo:
                full_path = f"app/{current_photo}"
                if os.path.exists(full_path):
                    os.remove(full_path)
            photo_path = None  # явно указываем, что поле должно быть пустым

        # Если загружено новое фото
        if photo:
            user_folder = f"app/static/images/user_photo/{user_id}"
            os.makedirs(user_folder, exist_ok=True)
            filename = photo.filename.replace(" ", "_")
            file_path = os.path.join(user_folder, filename)

            with open(file_path, "wb") as f:
                f.write(await photo.read())

            photo_path = f"/static/images/user_photo/{user_id}/{filename}"

        # Обновляем пользователя
        if photo_path is not None or photo_delete:
            cursor.execute("""
                UPDATE users 
                SET username = %s, email = %s, description = %s, gender = %s, photo = %s
                WHERE id = %s
            """, (username, email, description, gender, photo_path, user_id))
        else:
            cursor.execute("""
                UPDATE users 
                SET username = %s, email = %s, description = %s, gender = %s
                WHERE id = %s
            """, (username, email, description, gender, user_id))

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "Profile updated successfully"}

    except Exception as e:
        print("Ошибка при обновлении профиля:", e)
        return JSONResponse(status_code=500, content={"detail": "Ошибка сервера"})


@router.get("/api/admin/users")
async def get_all_users(current_id: int = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT is_admin FROM users WHERE id = %s", (current_id,))
        is_admin = cursor.fetchone()
        if not is_admin or not is_admin[0]:
            raise HTTPException(status_code=403, detail="Access denied")

        cursor.execute("""
            SELECT id, username, email, is_active, registration_date, description, gender, is_blogger 
            FROM users WHERE is_admin = false
        """)
        users = cursor.fetchall()
        cursor.close()
        conn.close()

        return [
            {
                "id": row[0],
                "username": row[1],
                "email": row[2],
                "is_active": row[3],
                "registration_date": row[4],
                "description": row[5],
                "gender": row[6],
                "is_blogger": row[7]
            } for row in users
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail="Ошибка получения списка пользователей")
@router.post("/api/admin/users/{user_id}/block")
async def block_user(user_id: int, current_id: int = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT is_admin FROM users WHERE id = %s", (current_id,))
        is_admin = cursor.fetchone()
        if not is_admin or not is_admin[0]:
            raise HTTPException(status_code=403, detail="Access denied")

        cursor.execute("UPDATE users SET is_active = false WHERE id = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "User blocked"}

    except Exception as e:
        raise HTTPException(status_code=500, detail="Ошибка блокировки пользователя")


@router.post("/api/admin/users/{user_id}/unblock")
async def unblock_user(user_id: int, current_id: int = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT is_admin FROM users WHERE id = %s", (current_id,))
        is_admin = cursor.fetchone()
        if not is_admin or not is_admin[0]:
            raise HTTPException(status_code=403, detail="Access denied")

        cursor.execute("UPDATE users SET is_active = true WHERE id = %s", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "User unblocked"}

    except Exception as e:
        raise HTTPException(status_code=500, detail="Ошибка разблокировки пользователя")


@router.post("/api/admin/comments/{comment_id}/approve")
def approve_comment(comment_id: int, current_id: int = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT is_admin FROM users WHERE id = %s", (current_id,))
    is_admin = cursor.fetchone()
    if not is_admin or not is_admin[0]:
        raise HTTPException(status_code=403, detail="Access denied")

    cursor.execute("UPDATE comments SET is_published = TRUE WHERE id = %s", (comment_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return {"message": "Комментарий одобрен"}

YANDEX_API_KEY = os.getenv("df26c33f-b6e4-4442-bc85-0c1c3461ed2a")

@router.post("/api/admin/resorts")
async def create_resort(
    name: str = Form(...),
    information: str = Form(...),
    trail_length: int = Form(...),
    max_height: int = Form(...),
    season: str = Form(...),
    country: str = Form(...),
    visa: bool = Form(...),
    tracks: str = Form(...),
    how_to_get_there: str = Form(...),
    nearby_cities: str = Form(...),
    related_ski_areas: str = Form(...),
    features: str = Form(...),
    ski_pass: str = Form(...),
    latitude: float = Form(None),
    longitude: float = Form(None),
    images: list[UploadFile] = File(...),
    user_id: int = Depends(get_current_user)
):
    conn = get_db_connection()
    cur = conn.cursor()

    # Проверка админа
    cur.execute("SELECT is_admin FROM users WHERE id = %s", (user_id,))
    if not cur.fetchone()[0]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Добавление курорта
    cur.execute("""
        INSERT INTO ski_resort (name, information, trail_length, changes, max_height, num_reviews, season, country)
        VALUES (%s, %s, %s, 0, %s, 0, %s, %s) RETURNING id
    """, (name, information, trail_length, max_height, season, country))
    resort_id = cur.fetchone()[0]

    # Трассы
    for t in json.loads(tracks):
        cur.execute("""
            INSERT INTO tracks (resort_id, trail_type, trail_length)
            VALUES (%s, %s, %s)
        """, (resort_id, t["trail_type"], t["trail_length"]))

    # Ски-пасс
    prices = json.loads(ski_pass)
    cur.execute("""
        INSERT INTO ski_pass (
            resort_id, price_day, price_child, price_2_days, price_3_days,
            price_4_days, price_5_days, price_6_days, price_7_days, season_pass
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        resort_id, prices["price_day"], prices["price_child"],
        prices["price_2_days"], prices["price_3_days"], prices["price_4_days"],
        prices["price_5_days"], prices["price_6_days"], prices["price_7_days"],
        prices["season_pass"]
    ))

    # Изображения
    # Изображения
    save_dir = f"app/static/images/resorts/{resort_id}"
    os.makedirs(save_dir, exist_ok=True)

    url_path = f"/static/images/resorts/{resort_id}"

    for idx, image in enumerate(images, 1):
        ext = os.path.splitext(image.filename)[1]
        save_path = f"{save_dir}/img{idx}{ext}"  # абсолютный путь для сохранения
        url = f"{url_path}/img{idx}{ext}"  # относительный URL

        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

        cur.execute("""
            INSERT INTO resort_images (resort_id, image_path)
            VALUES (%s, %s)
        """, (resort_id, url))

    # Координаты (если не указаны — получить через Яндекс)
    if latitude is None or longitude is None:
        address = f"{country}, {name}"
        geo_url = f"https://geocode-maps.yandex.ru/1.x/?apikey={YANDEX_API_KEY}&geocode={address}&format=json"
        response = requests.get(geo_url)
        try:
            pos = response.json()["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["Point"]["pos"]
            longitude, latitude = map(float, pos.split())
        except Exception:
            latitude = longitude = None

    if latitude is not None and longitude is not None:
        cur.execute("""
            INSERT INTO coordinates_resort (resort_id, latitude, longitude)
            VALUES (%s, %s, %s)
        """, (resort_id, latitude, longitude))

    # Начальная запись о погоде
    cur.execute("""
        INSERT INTO resort_weather (resort_id, snow_last_3_days, snow_expected, has_glacier, updated_at)
        VALUES (%s,False, False, False, %s)
    """, (resort_id, datetime.datetime.utcnow()))

    cur.execute("""
        INSERT INTO resort_extra_info (resort_id, how_to_get_there, nearby_cities, related_ski_areas)
        VALUES (%s, %s, %s, %s)
    """, (resort_id, how_to_get_there, nearby_cities, related_ski_areas))

    f = json.loads(features)
    cur.execute("""
        INSERT INTO resort_features (
            resort_id, panoramic_trails_above_2500m, guaranteed_snow, snowboard_friendly,
            night_skiing, kiting_available, snowparks_count, halfpipes_count, artificial_snow,
            forest_trails, glacier_available, summer_skiing, freeride_opportunities,
            official_freeride_zones, backcountry_routes, heliski_available,
            official_freeride_guides, kids_ski_schools, fis_certified_trails_count
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """, (
        resort_id, f["panoramic_trails_above_2500m"], f["guaranteed_snow"], f["snowboard_friendly"],
        f["night_skiing"], f["kiting_available"], f["snowparks_count"], f["halfpipes_count"],
        f["artificial_snow"], f["forest_trails"], f["glacier_available"], f["summer_skiing"],
        f["freeride_opportunities"], f["official_freeride_zones"], f["backcountry_routes"],
        f["heliski_available"], f["official_freeride_guides"], f["kids_ski_schools"],
        f["fis_certified_trails_count"]
    ))

    conn.commit()
    cur.close()
    conn.close()
    return {"message": "Курорт успешно добавлен"}

