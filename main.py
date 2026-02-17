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
CHECK_LIMIT = 50  # Limit artırıldı: Her ihtimale karşı daha geriye baksın

# Global Session
session = requests.Session()

def get_cookies_and_ua_with_selenium():
    print("🔓 Selenium ile Cloudflare kilidi açılıyor...", flush=True)
    cookies = {}
    user_agent = ""
    with SB(uc=True, headless=False) as sb:
        try:
            sb.open(BASE_DOMAIN + "/filmler/")
            time.sleep(6)
            user_agent = sb.get_user_agent()
            sb_cookies = sb.get_cookies()
            for cookie in sb_cookies:
                cookies[cookie['name']] = cookie['value']
            print("   ✅ Giriş başarılı! Çerezler alındı.", flush=True)
        except Exception as e:
            print(f"   ❌ Selenium hatası: {e}", flush=True)
    return cookies, user_agent

def get_soup_fast(url, cookies, user_agent):
    headers = {'User-Agent': user_agent, 'Referer': BASE_DOMAIN}
    try:
        response = session.get(url, cookies=cookies, headers=headers, impersonate="chrome110", timeout=15)
        if response.status_code == 200: return BeautifulSoup(response.content, 'html.parser')
        elif response.status_code == 404: return "404"
        elif response.status_code == 403: return "403"
    except: pass
    return None

def get_video_source(soup):
    try:
        player_area = soup.find('div', class_='video-player-area')
        if player_area and player_area.find('iframe'): return player_area.find('iframe').get('src')
        iframes = soup.find_all('iframe')
        for frame in iframes:
            if 'embed' in frame.get('src', '') or 'player' in frame.get('src', ''): return frame['src']
    except: pass
    return ""

def get_full_movie_details(url, cookies, user_agent):
    soup = get_soup_fast(url, cookies, user_agent)
    if soup == "403": return "403"
    
    details = {
        "url": url, "videoUrl": "", "description": "Açıklama yok.", 
        "imdb": "0.0", "genres": [], "cast": [], "year": "",
        "poster": "", "cover_image": "", "platform": "Platform Dışı", "added_date": ""
    }
    
    if not soup or soup == "404": return None

    try:
        # Görseller
        poster_div = soup.find('div', class_='poster')
        if poster_div and poster_div.find('img'): details['poster'] = poster_div.find('img').get('src')
        
        head_div = soup.find('div', id='head')
        if head_div and "url('" in head_div.get('style', ''):
            details['cover_image'] = head_div['style'].split("url('")[1].split("')")[0]

        # Video
        details["videoUrl"] = get_video_source(soup)

        # Yeni Alanlar
        platform_link = soup.find('a', href=lambda x: x and '/platform/' in x)
        if platform_link: details['platform'] = platform_link.get_text(strip=True)
            
        upload_icon = soup.find('img', src=lambda x: x and 'Upload.svg' in x)
        if upload_icon: details['added_date'] = upload_icon.parent.get_text(strip=True)

        calendar_icon = soup.find('img', src=lambda x: x and 'Calendar.svg' in x)
        if calendar_icon: details['year'] = calendar_icon.parent.get_text(strip=True)

        # Açıklama
        summ = soup.find('p', class_='summary-text')
        if summ: details["description"] = summ.get_text(strip=True)

        # Diğer Bilgiler
        info_boxes = soup.find_all('div', class_=lambda x: x and 'bg-white/[4%]' in x)
        for box in info_boxes:
            txt = box.get_text()
            if "IMDB" in txt: details["imdb"] = box.find_next('div').get_text(strip=True)
            elif "Tür" in txt: details["genres"] = [a.get_text(strip=True) for a in box.find_all('a')]
            elif "Oyuncular" in txt: details["cast"] = [a.get_text(strip=True) for a in box.find_all('a')]
            elif "Yapım Yılı" in txt and not details["year"]: details["year"] = box.find_next('div').get_text(strip=True)

    except: pass
    return details

def main():
    print("🛡️ Güneş TV: Detaylı Tarama Modu (Geveze Mod)...", flush=True)

    cookies, user_agent = get_cookies_and_ua_with_selenium()
    if not cookies: return

    all_films = []
    url_map = {}

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                all_films = json.load(f)
            url_map = {movie.get('url'): i for i, movie in enumerate(all_films)}
            print(f"📦 Veritabanı Yüklendi: {len(all_films)} film mevcut.", flush=True)
        except: pass

    page_num = 1
    consecutive_skip_count = 0 

    while True:
        target_url = f"{BASE_DOMAIN}/filmler/page/{page_num}/"
        print(f"\n--- 📄 SAYFA {page_num} Taranıyor... ---", flush=True)
        
        soup = get_soup_fast(target_url, cookies, user_agent)
        
        if soup == "403":
            print("🔄 403 Algılandı, Çerez yenileniyor...", flush=True)
            cookies, user_agent = get_cookies_and_ua_with_selenium()
            soup = get_soup_fast(target_url, cookies, user_agent)

        if not soup or soup == "404":
            print("🏁 Sayfa bulunamadı veya bitti.", flush=True)
            break

        items = soup.find_all('div', class_='post-item')
        if not items:
            print("⚠️ Bu sayfada hiç film kutusu bulunamadı!", flush=True)
            break
        
        print(f"   🔍 Bu sayfada {len(items)} adet film bulundu.", flush=True)

        for item in items:
            link = item.find('a')
            if not link: continue
            
            title = link.get('title', '').strip()
            movie_url = link.get('href', '')
            
            # --- ANLIK GERİ BİLDİRİM BURADA ---
            print(f"   👀 Gözlenen: {title}", flush=True)
            
            should_process = True
            is_update = False
            
            if movie_url in url_map:
                existing_index = url_map[movie_url]
                existing_data = all_films[existing_index]
                
                # Platform verisi yoksa GÜNCELLE
                if 'platform' not in existing_data or existing_data['platform'] == "Platform Dışı":
                    # Bazen Platform Dışı gerçekten öyledir ama biz yine de bir kontrol edelim
                    # Eğer son kontrolde de 'Platform Dışı' dediysek ve yeni değilse atlayabiliriz
                    # Ama kullanıcının isteği üzerine, eksik hissettiğimiz her şeye bakalım.
                    if 'platform' not in existing_data:
                        print(f"      ♻️ Durum: Listede var ama verileri eksik -> GÜNCELLENECEK", flush=True)
                        is_update = True
                        consecutive_skip_count = 0
                    else:
                        # Veriler tam görünüyor
                        print(f"      ⏭️ Durum: Listede mevcut ve tam -> ATLANIYOR", flush=True)
                        consecutive_skip_count += 1
                        should_process = False
                else:
                    print(f"      ⏭️ Durum: Listede mevcut ve tam -> ATLANIYOR", flush=True)
                    consecutive_skip_count += 1
                    should_process = False
            else:
                print(f"      🆕 Durum: YENİ FİLM! -> EKLENECEK", flush=True)
                consecutive_skip_count = 0

            # Limit Kontrolü
            if consecutive_skip_count >= CHECK_LIMIT:
                print(f"\n🛑 {CHECK_LIMIT} film üst üste 'Mevcut' olarak geçildi. Tarama bitiriliyor.")
                return

            if should_process:
                print(f"      ⏳ Veriler çekiliyor...", flush=True)
                meta = get_full_movie_details(movie_url, cookies, user_agent)
                
                if meta == "403":
                    print("      🚨 Çerez patladı, yenileniyor...", flush=True)
                    cookies, user_agent = get_cookies_and_ua_with_selenium()
                    meta = get_full_movie_details(movie_url, cookies, user_agent)

                if meta and meta != "403":
                    meta['title'] = title
                    
                    if is_update:
                        idx = url_map[movie_url]
                        all_films[idx] = meta 
                        print(f"      ✅ GÜNCELLENDİ: {title} | {meta.get('platform', '-')}", flush=True)
                    else:
                        all_films.append(meta)
                        url_map[movie_url] = len(all_films) - 1
                        print(f"      ✅ EKLENDİ: {title} | {meta.get('platform', '-')}", flush=True)

                    with open(DATA_FILE, 'w', encoding='utf-8') as f:
                        json.dump(all_films, f, ensure_ascii=False, indent=2)
                else:
                    print(f"      ❌ Veri Çekilemedi!", flush=True)

        page_num += 1

if __name__ == "__main__":
    main()
