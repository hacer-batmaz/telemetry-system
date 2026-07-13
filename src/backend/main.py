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
        # COALESCE içindeki sütun adını 'okunma_zamani' olarak güncelledik
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