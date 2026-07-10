import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

#.env dosyasını okur ve çevre değişkenleri olarak hafızaya alır
load_dotenv()

#docker compose dosyasındaki db bilgileri
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

def get_db_connection():
    try:
        conn = psycopg.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            row_factory=dict_row
        )
        return conn
    except Exception as e:
        print(f"[VERITABANI HATASI] PostgreSQL bağlantısı kurulamadı: {e}")
        return None