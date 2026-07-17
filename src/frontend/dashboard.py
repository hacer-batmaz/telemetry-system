import streamlit as pd_st
import requests
import pandas as pd
from streamlit_autorefresh import st_autorefresh

pd_st.set_page_config(
    page_title="Pusula Telemetri Paneli",
    page_icon="🧭",
    layout="wide"
)

# Yenileme Motoru (Sayfayı saniyede bir tetikler)
st_autorefresh(interval=1000, limit=10000, key="pusula_refresh")

API_TELEMETRI_URL = "http://127.0.0.1:8000/api/telemetri"
API_PERSONEL_URL = "http://127.0.0.1:8000/api/personel-loglari"
API_PERFORMANS_URL = "http://127.0.0.1:8000/api/son-surucu-performans"
API_SOFOR_CIKIS_URL = "http://127.0.0.1:8000/api/sofor-cikis/arac01"

pd_st.title("PUSULA - CAN Bus & RFID Canlı İzleme Paneli")
pd_st.markdown("---")

#sürücü kontrol paneli
with pd_st.sidebar:
    pd_st.header("Sürücü Giriş / Çıkış")
    pd_st.write("araç01 sürücü yönetimi:")
    
    #giriş sistemi
    input_kart = pd_st.text_input("Kart ID Giriniz (Örn: 1002003004):", placeholder="10 haneli numara...")
    if pd_st.button("Kartı Okut (Giriş Yap)", use_container_width=True):
        if input_kart.strip():
            try:
                import paho.mqtt.publish as publish
                #arka plandaki MQTT hattına kartı fırlatıyor
                publish.single("pusula/araç01/rfid", input_kart.strip(), hostname="127.0.0.1")
                pd_st.success("Giriş sinyali başarıyla iletildi!")
            except Exception as mqtt_err:
                pd_st.error(f"Sinyal hatası: {mqtt_err}")
        else:
            pd_st.warning("Lütfen geçerli bir Kart ID yazın.")
            
    pd_st.markdown("---")
    
    #çıkış Sistemi
    if pd_st.button("Şoför Çıkışı Yap", use_container_width=True, type="primary"):
        try:
            res = requests.post(API_SOFOR_CIKIS_URL, timeout=1)
            if res.status_code == 200:
                pd_st.info("Çıkış sinyali gönderildi.")
        except Exception as e:
            pd_st.error(f"Çıkış işlemi yapılamadı: {e}")

#ana alan
try:
    telemetri_response = requests.get(API_TELEMETRI_URL, timeout=1)
    personel_response = requests.get(API_PERSONEL_URL, timeout=1)
    performans_response = requests.get(API_PERFORMANS_URL, timeout=1)

    telemetri_verisi = telemetri_response.json() if telemetri_response.status_code == 200 else []
    personel_verisi = personel_response.json() if personel_response.status_code == 200 else []
    performans_verisi = performans_response.json() if performans_response.status_code == 200 else {}

    #aktif şoför var mı
    aktif_sofor = "Şoför Yok (Araç Boşta)"
    if personel_verisi:
        en_son_log = personel_verisi[0]
        if en_son_log.get("arac_id") in ["araç01", "arac01"] and (en_son_log.get("cikis_zamani") == "-" or not en_son_log.get("cikis_zamani")):
            aktif_sofor = en_son_log["personel_adi"]

    pd_st.subheader(f"Aktif Sürücü: {aktif_sofor}")

    #şoför yoksa verileri güvenlik gereği gösterme
    if aktif_sofor != "Şoför Yok (Araç Boşta)":
        
        #anlık göstergeler
        filtreli = [d for d in telemetri_verisi if d["arac_id"] in ["araç01", "arac01"]]
        if filtreli:
            en_guncel_can = filtreli[0]
            anlik_hiz = en_guncel_can["hiz"]
            anlik_sicaklik = en_guncel_can["sicaklik"]
        else:
            anlik_hiz, anlik_sicaklik = 0, 0
            
        kpi1, kpi2 = pd_st.columns(2)
        kpi1.metric(label="⚡ Anlık Araç Hızı", value=f"{anlik_hiz} km/h")
        if anlik_sicaklik >= 90:
            kpi2.metric(label="Motor Sıcaklığı (KRİTİK!)", value=f"{anlik_sicaklik} °C", delta="- Yüksek!", delta_color="inverse")
        else:
            kpi2.metric(label="Motor Sıcaklığı (Normal)", value=f"{anlik_sicaklik} °C")
            
        pd_st.markdown("###")

        sol_sutun, sag_sutun = pd_st.columns([2, 1])
        with sol_sutun:
            pd_st.subheader("Canlı Telemetri Grafikleri (CAN Bus)")
            if filtreli:
                df = pd.DataFrame(filtreli)
                df = df.iloc[::-1]
                pd_st.line_chart(data=df, x="zaman", y="hiz", color="#00ff00")
                pd_st.line_chart(data=df, x="zaman", y="sicaklik", color="#ff4b4b")
            else:
                pd_st.warning("CAN verisi bekleniyor...")
    else:
        pd_st.info("Araç bekleme modunda. Veri akışını başlatmak için lütfen kart okutun.")
        pd_st.write("") 

    #alt alan: personel geçmişi ve son sürücünün detayları
    pd_st.markdown("---")
    col_logs, col_perf = pd_st.columns([5, 4])
    
    with col_logs:
        pd_st.subheader("Personel Geçmişi")
        if personel_verisi:
            df_personel = pd.DataFrame(personel_verisi)
            df_gosterim = df_personel[["zaman", "cikis_zamani", "personel_adi", "kart_id"]]
            df_gosterim.columns = ["Giriş Saati", "Çıkış Saati", "Personel Adı", "Kart ID"]
            pd_st.dataframe(df_gosterim.fillna("-"), use_container_width=True, hide_index=True)
        else:
            pd_st.info("Henüz kart okutulmadı.")
            
    with col_perf:
        pd_st.subheader("Son Sürücünün Karnesi")
        if performans_verisi and "personel_adi" in performans_verisi:
            pd_st.markdown(f"**Değerlendirilen Sürücü:** `{performans_verisi['personel_adi']}`")
            
            p_kpi1, p_kpi2 = pd_st.columns(2)
            p_kpi1.metric("Ortalama Sürüş Hızı", f"{performans_verisi['avg_speed']} km/h")
            p_kpi2.metric("Tepe Motor Sıcaklığı", f"{performans_verisi['max_temp']} °C")
            
            score = performans_verisi['eco_score']
            if score >= 85:
                score_color = "#2ecc71" # Yeşil
                score_label = "Mükemmel - Ekonomik Sürüş"
            elif score >= 60:
                score_color = "#e67e22" # Turuncu
                score_label = "Orta Seviye - İyileştirilebilir"
            else:
                score_color = "#e74c3c" # Kırmızı
                score_label = "Agresif - Yüksek Yakıt Tüketimi"
                
            pd_st.markdown(f"**Sürüş Verimlilik Skoru:** <span style='color:{score_color}; font-size: 26px; font-weight: bold;'>%{score}</span>", unsafe_allow_html=True)
            pd_st.markdown(f"*Değerlendirme:* `{score_label}`")
            pd_st.progress(score / 100)
            
            pd_st.caption(f"Bu skor, seyahat boyunca kaydedilen {performans_verisi['total_records']} adet anlık CAN Bus verisi analiz edilerek hesaplanmıştır.")
        else:
            pd_st.info("Analiz edilecek, tamamlanmış (çıkış yapmış) bir sürücü oturumu henüz bulunmuyor.")
                
except Exception as e:
    pd_st.error(f"Sistem hatası: {e}")