# app/db.py

import psycopg2
from .config import db_params

def get_db_connection():
    conn = psycopg2.connect(**db_params)
    return conn
