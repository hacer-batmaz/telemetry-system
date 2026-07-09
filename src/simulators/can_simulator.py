import time
import random
import can

def can_bus_simulator():
    try:
        bus = can.interface.Bus(channel='vcan0', interface='socketcan')
        print("[CAN SIMULATOR] Sanal CAN hattına (vcan0) başarıyla bağlanıldı.")
    except Exception as e:
        print(f"[HATA] van0 hattına bağlanılamadı: {e}")
        return
    
    print("[CAN SIMULATOR] Araç verileri hatta basıyor... (Durdurmak için CTRL+C)")

    while True:
        try:
            #rastgele hız ve sıcaklık üretimi
            hiz = random.randint(40, 110)
            sicaklik = random.randint(80, 100)

            #veriyi can'a uygun 8 byte'lik diziye çevirdik
            data_bytes = [hiz, sicaklik, 0, 0, 0, 0, 0, 0]

            #can mesaj paketi oluşturuldu
            #0x123 id'sini bu aracın telemetri paketi olarak belirlendi
            msg = can.Message(
                arbitration_id=0x123,
                data=data_bytes,
                is_extended_id=False
            )

            #mesajı can hattına fırlattık
            bus.send(msg)
            print(f"[CAN GONDERILDI] ID: 0x123 | Hız: {hiz} km/h | Sıcaklık: {sicaklik}°C")

            #her 2 saniyede bir yeni veri üret
            time.sleep(2)

        except KeyboardInterrupt:
            print(f"[CAN SIMULATOR] KUllanıcı tarafından durduruldu.")
            break
        except Exception as e:
            print(f"[HATA] Mesaj gönderilemedi: {e}")
            time.sleep(2)

if __name__ == "__main__":
    can_bus_simulator()