# app/auth.py

from fastapi import APIRouter, HTTPException, Header
from .models import UserCreate, UserLogin
from .db import get_db_connection
from .config import SECRET_KEY, ALGORITHM
from jose import jwt
import bcrypt
import datetime
from fastapi.responses import JSONResponse

router = APIRouter()

def create_access_token(data: dict, expires_delta: datetime.timedelta = None):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + (expires_delta or datetime.timedelta(minutes=30))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except Exception:
        return None

@router.post("/api/register")
async def register_user(user: UserCreate):
    try:
        hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM Users WHERE username = %s", (user.username,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(status_code=400, detail="Username already exists.")

        registration_date = datetime.date.today()
        cursor.execute(
            "INSERT INTO Users (username, email, password, registration_date) VALUES (%s, %s, %s, %s) RETURNING id",
            (user.username, user.email, hashed_password.decode('utf-8'), registration_date)
        )

        user_id = cursor.fetchone()[0]

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "User registered successfully", "userId": user_id}

    except Exception as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/api/login")
async def login_user(user: UserLogin):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, password FROM Users WHERE username = %s", (user.username,))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=400, detail="Пользователь не найден.")

        user_id, stored_password = result

        if not bcrypt.checkpw(user.password.encode('utf-8'), stored_password.encode('utf-8')):
            raise HTTPException(status_code=400, detail="Неверный пароль.")

        token = create_access_token(data={"sub": str(user_id)})

        cursor.close()
        conn.close()

        return {"access_token": token, "token_type": "bearer"}

    except Exception as e:
        print(f"Database error during login: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

@router.get("/api/profile")
async def get_profile(Authorization: str = Header(...)):
    token = Authorization.split(" ")[1]
    user_id = decode_access_token(token)

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT username, email FROM Users WHERE id = %s", (user_id,))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="User not found")

        username, email = result

        cursor.close()
        conn.close()

        return {"username": username, "email": email}

    except Exception as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

