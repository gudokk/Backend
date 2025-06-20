# app/main.py
from fastapi import FastAPI
from starlette.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from app.auth import router as auth_router
from app.auth_middleware import AuthMiddleware
from app.news import router as news_router
from app.hotels_cards import router as hotels_cards_router
from app.reviews_cards import router as reviews_cards_router
from app.resorts_selector import router as resorts_selector_router
from app.articles import router as articles_router
from app.news_page import router as news_page_router
from app.new_page import router as new_page_router
from app.resorts import router as resorts_router
from app.resorts_table import router as resorts_table_router
from fastapi.staticfiles import StaticFiles
from app.article_images import router as article_images_router
from app.resort import router as resort_router
from app.reviews_submit import router as resort_submit_router
from app.resort_images import router as resort_images_router
from app.hotels_images import router as hotels_images_router
from app.resort_features import router as resort_features_router
from app.comments import router as comments_router
from app.bloggers import router as bloggers_router
from app.friends import router as friends_router
from app.trips import router as trips_router
from dotenv import load_dotenv
import os

app = FastAPI()

app.mount(
    "/static",
    StaticFiles(directory=os.path.join("app", "static")),
    name="static"
)

load_dotenv()

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
# print("API KEY:", YANDEX_API_KEY)

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
app.include_router(resorts_selector_router)
app.include_router(articles_router)
app.include_router(news_page_router)
app.include_router(new_page_router)
app.include_router(hotels_cards_router)
app.include_router(reviews_cards_router)
app.include_router(article_images_router)
app.include_router(resorts_router)
app.include_router(resorts_table_router)
app.include_router(resort_router)
app.include_router(resort_images_router)
app.include_router(resort_submit_router)
app.include_router(hotels_images_router)
app.include_router(comments_router)
app.include_router(resort_features_router)
app.include_router(bloggers_router)
app.include_router(friends_router)
app.include_router(trips_router)