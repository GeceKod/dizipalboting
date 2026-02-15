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

# Global Session nesnesi (Hız için)
session = requests.Session()

def get_cookies_and_ua_with_selenium():
    """Selenium ile siteye girip Cloudflare çerezlerini ve User-Agent'ı alır."""
    print("🔓 Selenium ile Cloudflare kilidi açılıyor (Filmler)...")
    cookies = {}
    user_agent = ""
    
    with SB(uc=True, headless=False) as sb:
        try:
            # Filmler sayfasına gidiyoruz
            sb.open(BASE_DOMAIN + "/filmler/")
            time.sleep(6) # Cloudflare kontrolü için bekleme
            
            title = sb.get_title()
            print(f"   🔓 Site Başlığı: {title}")
            
            user_agent = sb.get_user_agent()
            sb_cookies = sb.get_cookies()
            for cookie in sb_cookies:
                cookies[cookie['name']] = cookie['value']
                
            print("   ✅ Giriş kartı (Cookies) alındı!")
            
        except Exception as e:
            print(f"   ❌ Selenium hatası: {e}")
            
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
            print("   ⚠️ Hızlı mod 403 yedi (Çerez yenilenmeli).")
            return "403"
    except Exception as e:
        print(f"   ⚠️ Hızlı mod hatası: {e}")
    return None

def get_video_source(soup):
    """Video kaynağını (iframe) bulur."""
    try:
        # 1. Yöntem: Güvenli alan
        player_area = soup.find('div', class_='video-player-area')
        if player_area:
            iframe = player_area.find('iframe')
            if iframe: return iframe.get('src')
        
        # 2. Yöntem: Genel arama (Senin eski kodundaki yöntem)
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
    soup = get_soup_fast(url, cookies, user_agent)
    
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
    
    if not soup or soup == "404" or soup == "403": 
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
        # Senin kodundaki mantık: Film Özeti başlığını bul, sonraki p'yi al
        summary_title = soup.find('h6', string=lambda t: t and 'Film Özeti' in t)
        if summary_title:
            summary_p = summary_title.find_next('p')
            if summary_p: details["description"] = summary_p.get_text(strip=True)
        else:
            # Alternatif: summary-text class'ı
            summ = soup.find('p', class_='summary-text')
            if summ: details["description"] = summ.get_text(strip=True)

        # --- Detay Kutuları (Senin kodundaki mantık) ---
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
        print(f"   ⚠️ Detay hatası: {e}")
        pass
        
    return details

def main():
    print("🛡️ Güneş TV: Film Botu Başlatılıyor (Hibrit Mod)...")

    # 1. ADIM: Selenium ile Çerezleri Al
    cookies, user_agent = get_cookies_and_ua_with_selenium()
    
    if not cookies:
        print("❌ Çerezler alınamadı.")
        return

    # 2. ADIM: Hızlı Tarama
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                all_films = json.load(f)
            print(f"📦 Mevcut veri: {len(all_films)} film.")
        except:
            all_films = []
    else:
        all_films = []

    page_num = 1
    empty_page_count = 0

    while True:
        target_url = f"{BASE_DOMAIN}/filmler/page/{page_num}/"
        print(f"\n--- 📄 SAYFA {page_num} ANALİZİ: {target_url} ---")
        
        soup = get_soup_fast(target_url, cookies, user_agent)
        
        # Çerez yenileme kontrolü
        if soup == "403":
            print("🔄 Çerez süresi doldu, yenileniyor...")
            cookies, user_agent = get_cookies_and_ua_with_selenium()
            soup = get_soup_fast(target_url, cookies, user_agent)

        if not soup or soup == "404":
            print("🏁 Sayfa yok veya bitti.")
            break

        # Filmleri Bul (post-item class'ı)
        items = soup.find_all('div', class_='post-item')
        
        if not items:
            print("⚠️ Bu sayfada film bulunamadı.")
            empty_page_count += 1
            if empty_page_count >= 2: break
            page_num += 1
            continue

        empty_page_count = 0
        print(f"   🔍 {len(items)} film bulundu.")

        for item in items:
            try:
                link_element = item.find('a')
                if not link_element: continue
                
                title = link_element.get('title', '').strip()
                movie_url = link_element.get('href', '')
                
                # Zaten var mı kontrolü
                if any(f['url'] == movie_url for f in all_films if 'url' in f):
                    print(f"   ⏭️ Zaten var: {title}")
                    continue

                # Detayları çek
                meta = get_full_movie_details(movie_url, cookies, user_agent)
                
                if meta:
                    meta['title'] = title # Listeden gelen başlığı kullan
                    all_films.append(meta)
                    
                    # Anlık Kayıt
                    with open(DATA_FILE, 'w', encoding='utf-8') as f:
                        json.dump(all_films, f, ensure_ascii=False, indent=2)
                    
                    print(f"   ✅ Eklendi: {title}")
                
            except Exception as e: 
                print(f"   ❌ Film işleme hatası: {e}")
                continue

        page_num += 1

    print(f"\n🎉 İşlem tamamlandı. Toplam veri: {len(all_films)}")

if __name__ == "__main__":
    main()
