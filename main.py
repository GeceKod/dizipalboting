from seleniumbase import SB
from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import time
import os
import random
from urllib.parse import urljoin

# --- AYARLAR ---
BASE_DOMAIN = "https://dizipal.cx"
DATA_FILE = 'movies.json'
CHECK_LIMIT = 30  # Kaç tane 'zaten var' olan film görünce dursun?

# Global Session (Hız için)
session = requests.Session()

def get_cookies_and_ua_with_selenium():
    """Selenium ile siteye girip Cloudflare çerezlerini ve User-Agent'ı alır."""
    print("🔓 Selenium ile Cloudflare kilidi açılıyor (Filmler)...", flush=True)
    cookies = {}
    user_agent = ""
    
    with SB(uc=True, headless=False) as sb:
        try:
            # Filmler sayfasına gidiyoruz
            sb.open(BASE_DOMAIN + "/filmler/")
            time.sleep(6) # Cloudflare kontrolü için bekleme
            
            title = sb.get_title()
            print(f"   🔓 Site Başlığı: {title}", flush=True)
            
            user_agent = sb.get_user_agent()
            sb_cookies = sb.get_cookies()
            for cookie in sb_cookies:
                cookies[cookie['name']] = cookie['value']
                
            print("   ✅ Giriş kartı (Cookies) alındı!", flush=True)
            
        except Exception as e:
            print(f"   ❌ Selenium hatası: {e}", flush=True)
            
    return cookies, user_agent

def get_soup_fast(url, cookies, user_agent):
    """Curl_CFFI ile hızlı istek atar (Chrome taklidi yaparak)."""
    headers = {
        'User-Agent': user_agent,
        'Referer': BASE_DOMAIN,
    }
    try:
        response = session.get(
            url, 
            cookies=cookies, 
            headers=headers, 
            impersonate="chrome110", 
            timeout=15
        )
        
        if response.status_code == 200:
            return BeautifulSoup(response.content, 'html.parser')
        elif response.status_code == 404:
            return "404"
        elif response.status_code == 403:
            # 403 durumunda özel sinyal döndür
            return "403"
    except Exception as e:
        print(f"   ⚠️ Hızlı mod hatası: {e}", flush=True)
    return None

def get_video_source(soup):
    """Video kaynağını (iframe) bulur."""
    try:
        # 1. Yöntem: Güvenli alan
        player_area = soup.find('div', class_='video-player-area')
        if player_area:
            iframe = player_area.find('iframe')
            if iframe: return iframe.get('src')
        
        # 2. Yöntem: Genel arama
        iframe = soup.find('iframe')
        if iframe and 'src' in iframe.attrs:
            return iframe['src']
            
        # 3. Yöntem: Tüm iframeler
        iframes = soup.find_all('iframe')
        for frame in iframes:
            src = frame.get('src', '')
            if 'embed' in src or '.cfd' in src or 'player' in src:
                return src
    except: pass
    return ""

def get_full_movie_details(url, cookies, user_agent):
    """Film detaylarını çeker. 403 alırsa '403' stringi döner."""
    soup = get_soup_fast(url, cookies, user_agent)
    
    # Eğer 403 aldıysak hemen bildir
    if soup == "403":
        return "403"

    # Standart boş şablon
    details = {
        "url": url,
        "videoUrl": "", 
        "description": "Açıklama bulunamadı.", 
        "imdb": "0.0", 
        "genres": [], 
        "cast": [], 
        "year": "",
        "poster": "",
        "cover_image": "",
        "platform": "Platform Dışı", # Varsayılan değer
        "added_date": ""
    }
    
    if not soup or soup == "404": 
        return None

    try:
        # --- Metadata (Poster, Kapak vs) ---
        poster_div = soup.find('div', class_='poster')
        if poster_div and poster_div.find('img'):
            details['poster'] = poster_div.find('img').get('src')

        head_div = soup.find('div', id='head', class_='cover-image')
        if head_div and head_div.has_attr('style') and "url('" in head_div['style']:
            details['cover_image'] = head_div['style'].split("url('")[1].split("')")[0]

        # --- Video Kaynağı ---
        details["videoUrl"] = get_video_source(soup)

        # --- YENİ ALANLAR: Platform, Tarih, Yıl (SVG ile) ---
        
        # 1. Platform Bilgisi
        # Link içinde '/platform/' geçen a etiketini arıyoruz
        platform_link = soup.find('a', href=lambda x: x and '/platform/' in x)
        if platform_link:
            details['platform'] = platform_link.get_text(strip=True)
            
        # 2. Eklenme Tarihi (Upload.svg ikonu ile)
        # img src içinde 'Upload.svg' geçen görseli bulup ebeveynindeki metni alıyoruz
        upload_icon = soup.find('img', src=lambda x: x and 'Upload.svg' in x)
        if upload_icon:
            # parent genelde h6 veya div olur, text'i oradan alıyoruz
            details['added_date'] = upload_icon.parent.get_text(strip=True)

        # 3. Yapım Yılı (Calendar.svg ikonu ile - Daha Kesin)
        calendar_icon = soup.find('img', src=lambda x: x and 'Calendar.svg' in x)
        if calendar_icon:
            details['year'] = calendar_icon.parent.get_text(strip=True)

        # --- Açıklama ---
        summary_title = soup.find('h6', string=lambda t: t and 'Film Özeti' in t)
        if summary_title:
            summary_p = summary_title.find_next('p')
            if summary_p: details["description"] = summary_p.get_text(strip=True)
        else:
            summ = soup.find('p', class_='summary-text')
            if summ: details["description"] = summ.get_text(strip=True)

        # --- Detay Kutuları (Eski Yöntem - Yedek) ---
        # Eğer yukarıda Calendar.svg ile yıl bulunamadıysa buradan da bakabilir
        info_boxes = soup.find_all('div', class_=lambda x: x and 'rounded-[10px]' in x and 'bg-white/[4%]' in x)
        
        for box in info_boxes:
            label_span = box.find('span', class_='text-xs')
            if label_span:
                label = label_span.get_text(strip=True)
                val_div = label_span.find_next_sibling('div') or label_span.find_next_sibling('h6')
                
                if val_div:
                    if "IMDB Puanı" in label: 
                        details["imdb"] = val_div.get_text(strip=True)
                    elif "Tür" in label: 
                        details["genres"] = [a.get_text(strip=True) for a in val_div.find_all('a')]
                    elif "Oyuncular" in label: 
                        details["cast"] = [a.get_text(strip=True) for a in val_div.find_all('a')]
                    elif "Yapım Yılı" in label and not details["year"]: 
                        # Sadece yukarıdaki SVG yöntemi bulamadıysa buradan al
                        details["year"] = val_div.get_text(strip=True)

    except Exception as e: 
        print(f"   ⚠️ Detay hatası: {e}", flush=True)
        pass
        
    return details

def main():
    print("🛡️ Güneş TV: Film Botu Başlatılıyor (Akıllı Güncelleme Modu)...", flush=True)

    # 1. ADIM: Selenium ile Çerezleri Al
    cookies, user_agent = get_cookies_and_ua_with_selenium()
    
    if not cookies:
        print("❌ Çerezler alınamadı, çıkılıyor.", flush=True)
        return

    # 2. ADIM: Mevcut Veriyi Yükle ve Hızlı Arama Seti Oluştur
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                all_films = json.load(f)
            # URL'leri hızlı kontrol için bir kümeye (set) alıyoruz
            existing_urls = {movie.get('url') for movie in all_films if 'url' in movie}
            print(f"📦 Mevcut veritabanı: {len(all_films)} film yüklendi.", flush=True)
        except:
            all_films = []
            existing_urls = set()
    else:
        all_films = []
        existing_urls = set()

    page_num = 1
    empty_page_count = 0
    consecutive_existing_count = 0  # Arka arkaya kaç tane var olan film bulduk?

    while True:
        target_url = f"{BASE_DOMAIN}/filmler/page/{page_num}/"
        print(f"\n--- 📄 SAYFA {page_num} ANALİZİ (Kontrol: {consecutive_existing_count}/{CHECK_LIMIT}) ---", flush=True)
        
        soup = get_soup_fast(target_url, cookies, user_agent)
        
        # ANA SAYFADA 403 ALIRSAK
        if soup == "403":
            print("🔄 Sayfa erişiminde 403! Çerez yenileniyor...", flush=True)
            cookies, user_agent = get_cookies_and_ua_with_selenium()
            soup = get_soup_fast(target_url, cookies, user_agent)

        if not soup or soup == "404":
            print("🏁 Sayfa yok veya bitti.", flush=True)
            break

        # Filmleri Bul
        items = soup.find_all('div', class_='post-item')
        
        if not items:
            print("⚠️ Bu sayfada film bulunamadı.", flush=True)
            empty_page_count += 1
            if empty_page_count >= 2: break
            page_num += 1
            continue

        empty_page_count = 0
        print(f"   🔍 {len(items)} film bulundu.", flush=True)

        for item in items:
            try:
                link_element = item.find('a')
                if not link_element: continue
                
                title = link_element.get('title', '').strip()
                movie_url = link_element.get('href', '')
                
                # --- AKILLI GÜNCELLEME MANTIĞI ---
                if movie_url in existing_urls:
                    consecutive_existing_count += 1
                    print(f"   ⏭️ Zaten mevcut: {title} (Sayaç: {consecutive_existing_count}/{CHECK_LIMIT})", flush=True)
                    
                    if consecutive_existing_count >= CHECK_LIMIT:
                        print(f"\n🛑 LİMİTE ULAŞILDI: Arka arkaya {CHECK_LIMIT} eski film bulundu.")
                        print("   Güncel filmlerin hepsi tarandı, işlem bitiriliyor.")
                        return  # Programı tamamen durdur
                    
                    continue # Bir sonraki filme geç
                else:
                    # Yeni bir film bulduk! Sayacı sıfırla.
                    consecutive_existing_count = 0
                    print(f"   🆕 Yeni Fİlm Tespit Edildi: {title}", flush=True)

                print(f"   ▶️ Analiz Ediliyor...", flush=True)
                
                # Detayları çek
                meta = get_full_movie_details(movie_url, cookies, user_agent)
                
                # FİLM DETAYINDA 403 ALIRSAK (HATA TELAFİSİ)
                if meta == "403":
                    print("   🚨 FİLM İÇİNDE ÇEREZ BİTTİ! Yenilenip tekrar deneniyor...", flush=True)
                    cookies, user_agent = get_cookies_and_ua_with_selenium()
                    # Aynı filmi tekrar dene
                    meta = get_full_movie_details(movie_url, cookies, user_agent)
                
                if meta and meta != "403":
                    meta['title'] = title # Listeden gelen başlığı garantiye al
                    all_films.append(meta)
                    existing_urls.add(movie_url) # Hızlı listeye de ekle
                    
                    # Anlık Kayıt
                    with open(DATA_FILE, 'w', encoding='utf-8') as f:
                        json.dump(all_films, f, ensure_ascii=False, indent=2)
                    
                    print(f"   ✅ Eklendi: {title} | {meta['year']} | {meta['platform']}", flush=True)
                else:
                    print(f"   ❌ Veri alınamadı: {title}", flush=True)
                
            except Exception as e: 
                print(f"   ❌ Film işleme hatası: {e}", flush=True)
                continue

        page_num += 1

    print(f"\n🎉 İşlem tamamlandı. Toplam veri: {len(all_films)}", flush=True)

if __name__ == "__main__":
    main()
