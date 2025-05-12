from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError
import re

SECRET_KEY = "my_super_secret_key"
ALGORITHM = "HS256"

# Список публичных маршрутов (как обычные строки или шаблоны)
PUBLIC_PATH_PATTERNS = [
    r"^/api/login$",
    r"^/api/resorts-table$",
    r"^/api/register$",
    r"^/api/news$",
    r"^/api/newsPage/{article_id}",
    r"^/api/newsPage$",
    r"^/api/newsPage/\d+$",
    r"^/api/resorts$",
    r"^/api/resorts/\d+$",
    r"^/api/resort-images/[^/]+$",
    r"^/api/article_images.*$",
    r"^/docs$",
    r"^/openapi.json$"
]

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path.startswith("/static"):
            # Для статических файлов не требуем авторизации
            return await call_next(request)

        # Разрешаем доступ к публичным маршрутам
        for pattern in PUBLIC_PATH_PATTERNS:
            if re.match(pattern, path):
                return await call_next(request)

        # Проверка заголовка авторизации
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if user_id is None:
                raise HTTPException(status_code=401, detail="Invalid token payload")
            request.state.user_id = user_id
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

        # Всё хорошо — передаём дальше
        return await call_next(request)
