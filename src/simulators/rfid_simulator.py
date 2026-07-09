import time
import paho.mqtt.client as mqtt

#docker mqtt ayarları
MQTT_BROKER = "localhost" #aynı pc de localhost çalışıyor
MQTT_PORT = 1883 #mosquitto.conf da açılan port
MQTT_TOPIC = "pusula/arac01/rfid" #verinin basılacağı haberleşme kanalı

def rfid_simulator():
    #mqtt istemcisi oluşturma
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    try:
        # localhost yerine doğrudan yerel IP adresi olan 127.0.0.1 ile bağlanmayı garanti ediyoruz
        client.connect("127.0.0.1", 1883, 60)
        client.loop_start()
        print("[RFID SIMÜLATÖR] Docker MQTT Broker'a başarıyla bağlanıldı.")
    except Exception as e:
        print(f"[HATA] MQTT Broker'a bağlanılamadı: {e}")
        return
    
    print("\n" + "="*50)
    print("PUSULA ARAC ICI RFID DOGRULAMA SISTEMI")
    print("Simulasyon aktif. Çıkmak için q yazıp Enter'a basın.")
    print("="*50 + "\n")

    while True:
        try:
            card_id = input("Lütfen okutulacak RFID Kart ID girin (Örn: 1002003004):")

            #çıkış kontrolü
            if card_id.lower() == 'q':
                print("[RFID SIMULATOR] Kapatılıyor...")
                break

            if not card_id:
                print("[UYARI] Boş değer giremezsiniz.")
                continue

            #kart verisi mqtt ağına fırlatılıyor
            #gelen veri düz metin olarak gönderiliyor
            result = client.publish(MQTT_TOPIC, card_id, qos=1)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"[MQTT BASARILI] Kart ID '{card_id}' -> '{MQTT_TOPIC}' kanalına gönderildi \n")
            else:
                print("[HATA] MEsaj gönderilemedi. \n")

        except KeyboardInterrupt:
            break

    #bağlantı kapatılıyor
    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    rfid_simulator()

    
