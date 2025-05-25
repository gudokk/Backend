# app/auth.py

from fastapi import APIRouter, HTTPException, Header, Depends, File, UploadFile, Form, status
from .models import UserCreate, UserLogin
import os
from fastapi.responses import JSONResponse
from .db import get_db_connection
from .config import SECRET_KEY, ALGORITHM
from jose import jwt, JWTError
import bcrypt
import datetime

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
async def get_profile(user_id: int = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, username, email, registration_date, description, gender, photo, is_admin
            FROM users
            WHERE id = %s
        """, (user_id,))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="User not found")

        (
            user_id,
            username,
            email,
            registration_date,
            description,
            gender,
            photo,
            is_admin
        ) = result

        cursor.close()
        conn.close()

        return {
            "id": user_id,
            "username": username,
            "email": email,
            "registration_date": registration_date.isoformat() if registration_date else None,
            "description": description,
            "gender": gender,
            "photo": photo,
            "is_admin": is_admin
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/profile/update")
async def update_profile(
        user_id: int = Depends(get_current_user),
        username: str = Form(...),
        email: str = Form(...),
        description: str = Form(""),
        gender: str = Form(""),
        photo: UploadFile = File(None)
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        photo_path = None
        if photo:
            # Создаём папку для пользователя
            user_folder = f"app/static/images/user_photo/{user_id}"
            os.makedirs(user_folder, exist_ok=True)

            # Безопасное имя файла
            filename = photo.filename.replace(" ", "_")
            file_path = os.path.join(user_folder, filename)

            # Сохраняем файл
            with open(file_path, "wb") as f:
                f.write(await photo.read())

            # Сохраняемый путь относительно сервера
            photo_path = f"/static/images/user_photo/{user_id}/{filename}"

        # Составляем запрос
        if photo_path:
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

