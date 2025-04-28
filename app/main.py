from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
import psycopg2
from psycopg2 import sql
from fastapi.middleware.cors import CORSMiddleware
import bcrypt
from jose import jwt
import datetime

# Секретный ключ (должен быть спрятан в реальном проекте)
SECRET_KEY = "my_super_secret_key"
ALGORITHM = "HS256"

def create_access_token(data: dict, expires_delta: datetime.timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Инициализация FastAPI
app = FastAPI()

# CORS настройка
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Можно ограничить доменом фронтенда, например: ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Класс для валидации данных (Pydantic модель)
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    # confirmPassword: str


# Настройки подключения к базе данных
db_params = {
    "dbname": "ski_portal",
    "user": "postgres",
    "password": "nikita",
    "host": "localhost",
    "port": "5432"
}


# Маршрут для регистрации пользователя
@app.post("/api/register")
async def register_user(user: UserCreate):
    # if user.password != user.confirmPassword:
    #     raise HTTPException(status_code=400, detail="Passwords do not match.")

    try:

        hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())

        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()

        # Проверяем, есть ли уже такой username
        cursor.execute("SELECT id FROM Users WHERE username = %s", (user.username,))
        existing_user = cursor.fetchone()
        if existing_user:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=400, detail="Username already exists.")

        # SQL запрос
        query = sql.SQL(
            "INSERT INTO Users (username, email, password) VALUES (%s, %s, %s) RETURNING id"
        )
        cursor.execute(query, (user.username, user.email, hashed_password.decode('utf-8')))
        user_id = cursor.fetchone()[0]

        conn.commit()
        cursor.close()
        conn.close()

        return {"message": "User registered successfully", "userId": user_id}

    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


class UserLogin(BaseModel):
    username: str
    password: str

@app.post("/api/login")
async def login_user(user: UserLogin):
    try:
        conn = psycopg2.connect(**db_params)
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
