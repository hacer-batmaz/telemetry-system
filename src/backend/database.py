import psycopg
from psycopg.rows import dict_row

#docker compose dosyasındaki db bilgileri
DB_USER = "hacer"
DB_PASSWORD = "12345"
DB_HOST = "127.0.0.1"
DB_PORT = "5432"
DB_NAME = "telemetry_db"

def get_db_connection():
    """
    URL string yerine doğrudan parametre havuzu (kwargs) kullanarak
    PostgreSQL bağlantısı kurar. URL çözümleme hatalarını kökten engeller.
    """
    try:
        # Bağlantıyı parametreleri açıkça vererek kuruyoruz
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
        print(f"[VERİTABANI HATASI] PostgreSQL bağlantısı kurulamadı: {e}")
        return None