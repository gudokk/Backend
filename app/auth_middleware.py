from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from jose import jwt, JWTError
import re

from .config import SECRET_KEY, ALGORITHM

PUBLIC_PATH_PATTERNS = [
    r"^/api/login$",
    r"^/api/register$",
    r"^/api/news$",
    r"^/api/newsPage$",
    r"^/api/newsPage/\d+$",
    r"^/api/resorts$",
    r"^/api/resorts-table$",
    r"^/api/resort-features/\d+$",
    r"^/api/resorts/selector$",
    r"^/api/resorts/\d+$",
    r"^/api/resorts/\d+/hotels$",
    r"^/api/resorts/\d+/reviews$",
    r"^/api/resort-images/[^/]+$",
    r"^/api/hotels-images/\d+/\d+$",
    r"^/api/article_images.*$",
    r"^/docs$",
    r"^/openapi.json$"
]

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Разрешаем доступ к статике и публичным маршрутам
        if path.startswith("/static") or any(re.match(pattern, path) for pattern in PUBLIC_PATH_PATTERNS):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing or invalid Authorization header"})

        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if user_id is None:
                return JSONResponse(status_code=401, content={"detail": "Invalid token payload"})
            request.state.user_id = user_id
        except JWTError as e:
            return JSONResponse(status_code=401, content={"detail": f"Invalid or expired token: {str(e)}"})

        return await call_next(request)
