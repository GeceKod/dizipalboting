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
DATA_FILE = 'diziler.json'

# Global Session
session = requests.Session()

def get_cookies_and_ua_with_selenium():
    """Selenium ile siteye girip Cloudflare çerezlerini ve User-Agent'ı alır."""
    print("🔓 Selenium ile Cloudflare kilidi açılıyor (Diziler)...")
    cookies = {}
    user_agent = ""
    
    with SB(uc=True, headless=False) as sb:
        try:
            sb.open(BASE_DOMAIN + "/diziler/")
            time.sleep(6) 
            
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
    """Curl_CFFI ile hızlı istek atar."""
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
            # Burası kritik: 403 dönerse string olarak "403" yolluyoruz
            return "403"
    except Exception as e:
        print(f"   ⚠️ Hızlı mod hatası: {e}")
    return None

def get_video_source(soup):
    try:
        player_area = soup.find('div', class_='video-player-area')
        if player_area:
            iframe = player_area.find('iframe')
            if iframe: return iframe.get('src')
        
        iframes = soup.find_all('iframe')
        for frame in iframes:
            src = frame.get('src', '')
            if 'embed' in src or '.cfd' in src or 'player' in src:
                return src
    except: pass
    return ""

def get_episodes_from_page(soup, cookies, user_agent, known_urls=[]):
    """Bölümleri parse eder."""
    new_episodes = []
    episode_items = soup.find_all('div', class_='episode-item')
    
    for item in episode_items:
        ep_data = {}
        link_tag = item.find('a')
        
        if link_tag:
            ep_url = link_tag.get('href')
            title = link_tag.get('title')
            
            if ep_url in known_urls:
                continue 

            ep_data['url'] = ep_url
            ep_data['title'] = title
            
            img_tag = link_tag.find('img')
            if img_tag:
                ep_data['thumbnail'] = img_tag.get('src')
            
            if ep_url:
                ep_soup = get_soup_fast(ep_url, cookies, user_agent)
                if ep_soup and ep_soup not in ["404", "403"]:
                    video_src = get_video_source(ep_soup)
                    ep_data['video_source'] = video_src
                    print(f"      ✅ YENİ BÖLÜM: {ep_data.get('title')} -> Kaynak Alındı", flush=True)

        num_tag = item.find('h4', class_='font-eudoxus')
        if num_tag:
            ep_data['episode_number'] = num_tag.get_text(strip=True)
        
        if 'url' in ep_data:
            new_episodes.append(ep_data)

    return new_episodes

def get_full_series_details(url, cookies, user_agent, existing_episodes_list=[]):
    """Dizi detaylarını çeker."""
    print(f"   ▶️ Analiz: {url}")
    soup = get_soup_fast(url, cookies, user_agent)
    
    # EĞER BURADA 403 ALIRSAK DİREKT "403" DÖNÜYORUZ (None değil)
    if soup == "403":
        print("   ⚠️ Detay sayfasında 403 alındı! (Çerez yenilenmeli)")
        return "403"
    
    if not soup or soup == "404":
        return None
    
    meta = {
        "url": url,
        "title": "",
        "year": "",
        "description": "",
        "poster": "",
        "cover_image": "",
        "imdb": "0",
        "genres": [],
        "episodes": [] 
    }
    
    try:
        h1 = soup.find('h1')
        if h1:
            full_text = h1.get_text(" ", strip=True)
            if '(' in full_text:
                parts = full_text.split('(')
                meta['title'] = parts[0].strip()
                meta['year'] = parts[-1].replace(')', '').strip()
            else:
                meta['title'] = full_text

        summary = soup.find('p', class_='summary-text')
        if summary: meta['description'] = summary.get_text(strip=True)

        poster_div = soup.find('div', class_='poster')
        if poster_div and poster_div.find('img'):
            meta['poster'] = poster_div.find('img').get('src')

        head_div = soup.find('div', id='head', class_='cover-image')
        if head_div and head_div.has_attr('style') and "url('" in head_div['style']:
            meta['cover_image'] = head_div['style'].split("url('")[1].split("')")[0]

        imdb_span = soup.find('span', string=lambda t: t and "IMDB Puanı" in t)
        if imdb_span:
            parent = imdb_span.find_parent('div')
            score = parent.find('h4') if parent else None
            if score: meta['imdb'] = score.get_text(strip=True)

        genre_links = soup.find_all('a', href=lambda h: h and 'dizi-kategori' in h)
        meta['genres'] = list(set([g.get_text(strip=True) for g in genre_links]))

        # --- SEZON TARAMA ---
        season_links = []
        season_div = soup.find('div', id='season-options-list')
        
        if season_div:
            links = season_div.find_all('a', href=True)
            for l in links:
                full_link = urljoin(BASE_DOMAIN, l['href'])
                if full_link not in season_links:
                    season_links.append(full_link)
        
        if not season_links:
            season_links.append(url)
        
        for s_idx, season_url in enumerate(season_links):
            if season_url == url:
                current_season_soup = soup
            else:
                current_season_soup = get_soup_fast(season_url, cookies, user_agent)
            
            if current_season_soup and current_season_soup not in ["404", "403"]:
                season_episodes = get_episodes_from_page(current_season_soup, cookies, user_agent, existing_episodes_list)
                meta['episodes'].extend(season_episodes)

    except Exception as e:
        print(f"   ❌ Hata: {e}")

    return meta

def main():
    print("🛡️ Güneş TV: Dizi Botu (Hata Telafili Mod)...")
    
    cookies, user_agent = get_cookies_and_ua_with_selenium()
    if not cookies:
        print("❌ Çerezler alınamadı.")
        return

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                all_series = json.load(f)
            print(f"📦 Mevcut veri: {len(all_series)} dizi.")
        except:
            all_series = []
    else:
        all_series = []

    page_num = 1
    empty_page_count = 0 

    while True:
        target_url = f"{BASE_DOMAIN}/diziler/page/{page_num}/" if page_num > 1 else f"{BASE_DOMAIN}/diziler/"
        print(f"\n--- 📄 SAYFA {page_num}: {target_url} ---")
        
        soup = get_soup_fast(target_url, cookies, user_agent)
        
        # Sayfa listesinde 403 alırsak
        if soup == "403":
            print("🔄 Sayfa erişiminde 403! Çerez yenileniyor...")
            cookies, user_agent = get_cookies_and_ua_with_selenium()
            soup = get_soup_fast(target_url, cookies, user_agent)

        if not soup or soup == "404":
            print("🏁 Sayfa yok. Bitti.")
            break
        
        links = soup.find_all('a', href=True)
        series_urls = []
        for link in links:
            href = link['href']
            if '/dizi/' in href and href.count('/') > 3:
                full_url = urljoin(BASE_DOMAIN, href)
                clean_url = full_url.split('?')[0]
                if clean_url not in series_urls:
                    series_urls.append(clean_url)
        
        series_urls = list(set(series_urls))
        
        if not series_urls:
            print("⚠️ Dizi bulunamadı.")
            empty_page_count += 1
            if empty_page_count >= 2: break
            page_num += 1
            continue
        
        empty_page_count = 0
        print(f"   🔍 {len(series_urls)} dizi bulundu.")

        for s_url in series_urls:
            # --- YENİLENMİŞ DÖNGÜ MANTIĞI ---
            
            existing_series = next((s for s in all_series if s['url'] == s_url), None)
            
            if existing_series:
                # GÜNCELLEME MODU
                known_urls = [ep['url'] for ep in existing_series.get('episodes', []) if 'url' in ep]
                
                update_data = get_full_series_details(s_url, cookies, user_agent, existing_episodes_list=known_urls)
                
                # Eğer 403 döndüyse (Çerez bitti)
                if update_data == "403":
                    print("🚨 DİZİ İÇİNDE ÇEREZ BİTTİ! Yenilenip tekrar deneniyor...")
                    cookies, user_agent = get_cookies_and_ua_with_selenium()
                    # Aynı diziyi tekrar dene
                    update_data = get_full_series_details(s_url, cookies, user_agent, existing_episodes_list=known_urls)

                if update_data and update_data != "403" and update_data['episodes']:
                    count_new = len(update_data['episodes'])
                    existing_series['episodes'].extend(update_data['episodes'])
                    print(f"   🆙 GÜNCELLENDİ: {count_new} yeni bölüm -> {existing_series.get('title')}")
                    
                    with open(DATA_FILE, 'w', encoding='utf-8') as f:
                        json.dump(all_series, f, ensure_ascii=False, indent=2)
                else:
                    pass # Güncel veya hata
            
            else:
                # YENİ DİZİ MODU
                new_details = get_full_series_details(s_url, cookies, user_agent, existing_episodes_list=[])
                
                # Eğer 403 döndüyse (Çerez bitti)
                if new_details == "403":
                    print("🚨 DİZİ İÇİNDE ÇEREZ BİTTİ! Yenilenip tekrar deneniyor...")
                    cookies, user_agent = get_cookies_and_ua_with_selenium()
                    # Aynı diziyi tekrar dene
                    new_details = get_full_series_details(s_url, cookies, user_agent, existing_episodes_list=[])
                
                if new_details and new_details != "403":
                    all_series.append(new_details)
                    print(f"   ✅ YENİ DİZİ EKLENDİ: {new_details.get('title')}")
                    
                    with open(DATA_FILE, 'w', encoding='utf-8') as f:
                        json.dump(all_series, f, ensure_ascii=False, indent=2)

        page_num += 1

    print(f"\n✅ TAMAMLANDI. {len(all_series)} dizi kaydedildi.")

if __name__ == "__main__":
    main()
