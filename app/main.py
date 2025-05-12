# app/main.py
from fastapi import FastAPI
from starlette.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from app.auth import router as auth_router
from app.auth_middleware import AuthMiddleware
from app.news import router as news_router
from app.articles import router as articles_router
from app.news_page import router as news_page_router
from app.new_page import router as new_page_router
from app.resorts import router as resorts_router
from app.resorts_table import router as resorts_table_router
from fastapi.staticfiles import StaticFiles
from app.article_images import router as article_images_router
from app.resort import router as resort_router
from app.resort_images import router as resort_images_router


import os

app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory=os.path.join("app", "static")),
    name="static"
)


# app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS настройка
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

# Добавляем свое промежуточное ПО (middleware)
app.add_middleware(AuthMiddleware)


# Подключение роутов
app.include_router(auth_router)
app.include_router(news_router)
app.include_router(articles_router)
app.include_router(news_page_router)
app.include_router(new_page_router)
app.include_router(article_images_router)
app.include_router(resorts_router)
app.include_router(resorts_table_router)
app.include_router(resort_router)
app.include_router(resort_images_router)