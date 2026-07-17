import asyncio
from fastapi import FastAPI, HTTPException
import paho.mqtt.client as mqtt
import can
from src.backend.database import get_db_connection

app = FastAPI(title="Pusula Telemetri & Yönetim API", version="1.0")

MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_TOPIC = "pusula/+/rfid" #+ ile tüm araçlar dinlenir

PERSONEL_HARITASI = {
    "1002003004": "Ayşe Kara",
    "5554443332": "Ahmet Yılmaz",
    "1112223334": "Mehmet Demir"
}

def on_message(client, userdata, msg):
    """
    RFID simülatöründen kart okutulduğu an bu fonksiyon tetiklenir.
    """

    try:
        #gelen topikten hangi araç olduğu çözülür
        topic_parts = msg.topic.split('/')
        arac_id = topic_parts[1]

        #okunan kart id si string e çevrilir
        kart_id = msg.payload.decode("utf-8").strip()

        #kartın kime ait olduğunu buluyoruz, yoksa misafir
        personel_adi = PERSONEL_HARITASI.get(kart_id, "Bilinmeyen / Misafir Personel")

        print(f"[MQTT SINYAL] {arac_id} üzerinde Kart okundu. ID: {kart_id} | Personel: {personel_adi}")

        #veritabanına kaydetme
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("""
                INSERT INTO personel_loglari (arac_id, kart_id, personel_adi, okunma_zamani)
                VALUES (%s, %s, %s, NOW())
            """, (arac_id, kart_id, personel_adi))
                conn.commit()
            conn.close()
            print(f"[VERİTABANI] {personel_adi} geçiş logu başarıyla kaydedildi.")
    except Exception as e:
        print(f"[HATA] MQTT mesajı işlenirken hata oluştu: {e}")

#can bus arka plan dinleyicisi
async def can_bus_listener_task():
    """
    Linux vcan0 arayüzünü asenkron olarak sürekli dinler.
    Gelen telemetri paketlerini çözüp veritabanına yazar.
    """

    print("[SISTEM] Arka plan CAN Bus (vcan0) dinleyicisi başlatılıyor...")

    try:
        #sanal can hattına bağlanılıyor
        bus = can.interface.Bus(channel='vcan0', interface='socketcan')
    except Exception as e:
        print(f"[SISTEM HATASI] vcan0 hattına bağlanılamadı: {e}")
        return
    
    while True:
        try:
            #hattı bloke etmeden mesaj gelmesi bekleniyor, her döngüde asenkron olarak 0.5 sn kontrol edilir
            msg = bus.recv(timeout=0.5)
            if msg is not None and msg.arbitration_id == 0x123:
                #can_simulator de yazılan byte dizisi çözülüyor
                hiz = msg.data[0]
                sicaklik = msg.data[1]
                arac_id = "arac01"

                print(f"[CAN SINYAL] vcan0 -> Hız: {hiz} km/h | Sıcaklık: {sicaklik}°C")

                conn = get_db_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO telemetri_verileri (arac_id, hiz, sicaklik)
                            VALUES (%s, %s, %s);
                        """, (arac_id, hiz, sicaklik))
                        conn.commit()
                    conn.close()

        except Exception as e:
            print(f"[HATA] CAN mesajı işlenirkenhata oluştu: {e}")

        #fast api nin diğer işleri yapabilmesi için mola
        await asyncio.sleep(0.1)

#api endpoints
@app.get("/")
def read_root():
    return {"proje": "Pusula Telemetri Sistemi", "durum": "Aktif"}

@app.get("/api/personel-loglari")
def get_personel_loglari():
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, arac_id, kart_id, personel_adi, 
                   COALESCE(to_char(okunma_zamani, 'HH24:MI:SS'), '-') as zaman,
                   COALESCE(to_char(cikis_zamani, 'HH24:MI:SS'), '-') as cikis_zamani
            FROM personel_loglari 
            ORDER BY id DESC LIMIT 10
        """)
        logs = cursor.fetchall()
        cursor.close()
        conn.close()
        return logs
    except Exception as db_err:
        print(f"[API ERROR] Personel logları çekilemedi: {db_err}")
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()
        return []

@app.get("/api/son-surucu-performans")
def get_son_surucu_performans():
    """Son tamamlanmış (çıkış yapmış) sürücü oturumunun sürüş verimlilik istatistiklerini hesaplar."""
    #print("\n--- [PERFORMANS ANALİZİ BAŞLADI] ---")
    conn = get_db_connection()
    if not conn:
        #print("[PERFORMANS] Veritabanı bağlantısı kurulamadı!")
        return {}
    try:
        cursor = conn.cursor()
        
        #çıkış yapmış son oturumu çekiliyor
        #print("[PERFORMANS] Adım 1: Çıkış yapmış son oturum aranıyor...")
        cursor.execute("""
            SELECT personel_adi, okunma_zamani, cikis_zamani 
            FROM personel_loglari 
            WHERE cikis_zamani IS NOT NULL 
            ORDER BY id DESC LIMIT 1
        """)
        last_session = cursor.fetchone()
        
        if not last_session:
            #print("[PERFORMANS] Adım 1 Sonucu: Çıkış yapmış (cikis_zamani dolu olan) hiçbir sürücü oturumu bulunamadı! Tablo boş veya şoför çıkışı henüz tetiklenmemiş.")
            cursor.close()
            conn.close()
            return {}
            
        #sonucun Tuple veya Dict olmasına göre veri çekiliyor
        if isinstance(last_session, dict):
            p_name = last_session.get("personel_adi")
            o_time = last_session.get("okunma_zamani")
            c_time = last_session.get("cikis_zamani")
        else:
            p_name = last_session[0]
            o_time = last_session[1]
            c_time = last_session[2]
            
        #print(f"[PERFORMANS] Adım 1 Başarılı: Bulunan Sürücü = {p_name} | Giriş: {o_time} | Çıkış: {c_time}")
            
        #telemetri_verileri tablosundaki zaman kolonunu dinamik tespiti
        #print("[PERFORMANS] Adım 1.5: telemetri_verileri tablosunun kolonları sorgulanıyor...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name IN ('telemetri_verileri', 'telemetri')
        """)
        col_rows = cursor.fetchall()
        columns = []
        for r in col_rows:
            if isinstance(r, dict):
                columns.append(r.get("column_name"))
            else:
                columns.append(r[0])
        
        #print(f"[PERFORMANS] telemetri_verileri tablosunda tespit edilen kolonlar: {columns}")
        
        time_col = "zaman"  # varsayılan fallback
        for possible_col in ["okunma_zamani", "kayit_zamani", "zaman", "created_at", "timestamp", "tarih"]:
            if possible_col in columns:
                time_col = possible_col
                break
                
        #print(f"[PERFORMANS] Sorguda kullanılacak zaman kolonu otomatik seçildi: '{time_col}'")
            
        #bu zaman aralığındaki telemetri verilerini dinamik kolon ile sorgulama
        #print(f"[PERFORMANS] Adım 2: {o_time} ile {c_time} arasındaki CAN Bus telemetri istatistikleri hesaplanıyor...")
        cursor.execute(f"""
            SELECT 
                COALESCE(AVG(hiz), 0) as avg_speed,
                COALESCE(MAX(sicaklik), 0) as max_temp,
                COUNT(*) as total_records,
                SUM(CASE WHEN hiz > 100 THEN 1 ELSE 0 END) as speeding_records,
                SUM(CASE WHEN sicaklik > 90 THEN 1 ELSE 0 END) as high_temp_records
            FROM telemetri_verileri
            WHERE arac_id IN ('arac01', 'araç01') 
              AND {time_col} BETWEEN %s AND %s
        """, (o_time, c_time))
        
        stats = cursor.fetchone()
        
        if isinstance(stats, dict):
            avg_speed = stats.get("avg_speed", 0) or 0
            max_temp = stats.get("max_temp", 0) or 0
            total_records = stats.get("total_records", 0) or 0
            speeding_records = stats.get("speeding_records", 0) or 0
            high_temp_records = stats.get("high_temp_records", 0) or 0
        else:
            avg_speed = stats[0] or 0
            max_temp = stats[1] or 0
            total_records = stats[2] or 0
            speeding_records = stats[3] or 0
            high_temp_records = stats[4] or 0
        
        #print(f"[PERFORMANS] Adım 2 Sonucu: Toplam Kayıt = {total_records} | Ort Hız = {avg_speed} | Tepe Sıcaklık = {max_temp}")
        
        total = total_records if total_records > 0 else 1
        speeding_ratio = speeding_records / total
        temp_ratio = high_temp_records / total
        
        #sürüş skorlama algoritması
        eco_score = 100 - (speeding_ratio * 60) - (temp_ratio * 40)
        eco_score = max(30, min(100, round(eco_score)))
        
        result = {
            "personel_adi": p_name,
            "avg_speed": round(float(avg_speed), 1),
            "max_temp": int(max_temp),
            "eco_score": eco_score,
            "total_records": total_records
        }
        
        #print(f"[PERFORMANS] Analiz Başarıyla Tamamlandı: {result}")
        cursor.close()
        conn.close()
        return result
    except Exception as e:
        #print(f"[PERFORMANS ANALİZ HATASI] İşlem sırasında kritik hata oluştu: {e}")
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()
        return {}
    
@app.post("/api/sofor-cikis/arac01")
def sofor_cikis():
    conn = get_db_connection()
    if not conn:
        return {"status": "error"}
    cursor = conn.cursor()
    #veritabanında hem 'araç01' hem 'arac01' olma ihtimaline karşı ikisini de kapatıyor
    cursor.execute("""
        UPDATE personel_loglari 
        SET cikis_zamani = NOW() 
        WHERE (arac_id = 'araç01' OR arac_id = 'arac01') AND cikis_zamani IS NULL
    """)
    conn.commit()
    cursor.close()
    conn.close()
    return {"status": "success", "message": "araç01 şoförü başarıyla çıkarıldı."}
    
@app.get("/api/telemetri")
def get_telemetri():
    """
    Arayüze (Streamlit) grafik çizebilmesi için son 20 telemetri verisini verir.
    """
    conn = get_db_connection()
    if not conn: raise HTTPException(status_code=500, detail="DB bağlantı hatası")
    with conn.cursor() as cur:
        cur.execute("SELECT id, arac_id, hiz, sicaklik, to_char(kayit_zamani, 'HH24:MI:SS') as zaman FROM telemetri_verileri ORDER BY kayit_zamani DESC LIMIT 20;")
        data = cur.fetchall()
    conn.close()
    return data
    
#arka plan görevlerini başlatma
@app.on_event("startup")
async def startuo_event():
    """
    FastAPI ayağa kalkarken MQTT istemcisini de yanına alıp arka planda asenkron olarak çalıştırmaya başlar.
    """

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.subscribe(MQTT_TOPIC, qos=1)
        client.loop_start()
        print("[SISTEM] Arka plan MQTT dinleyicisi başlatıldı.")
    except Exception as e:
        print(f"[SISTEM HATASI] MQTT başlatılamadı: {e}")

    asyncio.create_task(can_bus_listener_task())