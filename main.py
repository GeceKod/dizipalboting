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
        "cover_image": ""
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

        # --- Açıklama ---
        summary_title = soup.find('h6', string=lambda t: t and 'Film Özeti' in t)
        if summary_title:
            summary_p = summary_title.find_next('p')
            if summary_p: details["description"] = summary_p.get_text(strip=True)
        else:
            summ = soup.find('p', class_='summary-text')
            if summ: details["description"] = summ.get_text(strip=True)

        # --- Detay Kutuları ---
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
                    elif "Yapım Yılı" in label: 
                        details["year"] = val_div.get_text(strip=True)

    except Exception as e: 
        print(f"   ⚠️ Detay hatası: {e}", flush=True)
        pass
        
    return details

def main():
    print("🛡️ Güneş TV: Film Botu Başlatılıyor (Hibrit Mod)...", flush=True)

    # 1. ADIM: Selenium ile Çerezleri Al
    cookies, user_agent = get_cookies_and_ua_with_selenium()
    
    if not cookies:
        print("❌ Çerezler alınamadı, çıkılıyor.", flush=True)
        return

    # 2. ADIM: Hızlı Tarama
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                all_films = json.load(f)
            print(f"📦 Mevcut veri: {len(all_films)} film.", flush=True)
        except:
            all_films = []
    else:
        all_films = []

    page_num = 1
    empty_page_count = 0

    while True:
        target_url = f"{BASE_DOMAIN}/filmler/page/{page_num}/"
        print(f"\n--- 📄 SAYFA {page_num} ANALİZİ: {target_url} ---", flush=True)
        
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
                
                # Zaten var mı kontrolü
                if any(f['url'] == movie_url for f in all_films if 'url' in f):
                    print(f"   ⏭️ Zaten var: {title}", flush=True)
                    continue

                print(f"   ▶️ Analiz: {title}", flush=True)
                
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
                    
                    # Anlık Kayıt
                    with open(DATA_FILE, 'w', encoding='utf-8') as f:
                        json.dump(all_films, f, ensure_ascii=False, indent=2)
                    
                    print(f"   ✅ Eklendi: {title} (Video: {'VAR' if meta['videoUrl'] else 'YOK'})", flush=True)
                else:
                    print(f"   ❌ Veri alınamadı: {title}", flush=True)
                
            except Exception as e: 
                print(f"   ❌ Film işleme hatası: {e}", flush=True)
                continue

        page_num += 1

    print(f"\n🎉 İşlem tamamlandı. Toplam veri: {len(all_films)}", flush=True)

if __name__ == "__main__":
    main()
