from src.backend.database import get_db_connection

def create_tables():
    """
    Sistemin ihtiyaç duyduğu PostreSQL tablolarını eğer veritabanında yoksa otomatik olarak oluşturur.
    """

    conn = get_db_connection()
    if conn is None:
        return
    
    with conn.cursor() as cur:
        #personel geçiş logları tablosu
        cur.execute("""
            CREATE TABLE IF NOT EXISTS personel_loglari (
                    id SERIAL PRIMARY KEY,
                    kart_id VARCHAR(50) NOT NULL,
                    personel_adi VARCHAR(100) NOT NULL,
                    arac_id VARCHAR(20) NOT NULL,
                    okunma_zamani TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
        """)

        #araç can bus verileri tablosu
        cur.execute("""
            CREATE TABLE IF NOT EXISTS telemetri_verileri (
                id SERIAL PRIMARY KEY,
                arac_id VARCHAR(20) NOT NULL,
                hiz INT NOT NULL,
                sicaklik INT NOT NULL,
                kayit_zamani TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        #değişiklikleri veritabanına kalıcı olarak işler
        conn.commit()

    conn.close()
    print("[VERİTABANI] Tüm Pusula sistem tabloları başarıyla oluşturuldu veya kontrol edildi.")

if __name__ == "__main__":
    create_tables()