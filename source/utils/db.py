import psycopg2
import psycopg2.extras
import os
from config import settings

def get_conn():
    return psycopg2.connect(
        dbname=settings.DATABASE_NAME,
        user=settings.DATABASE_USER,
        password=settings.DATABASE_PASS,
        host=settings.DATABASE_HOST,
        port=settings.DATABASE_PORT
    )

def get_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
