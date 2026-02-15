from seleniumbase import SB
from curl_cffi import requests
from bs4 import BeautifulSoup
import json
import time
import os
import random
import re
from urllib.parse import urljoin

# --- AYARLAR ---
BASE_DOMAIN = "https://dizipal1538.com"
DATA_FILE = 'diziler_1538.json'

# Global Session
session = requests.Session()

def get_cookies_and_ua_with_selenium():
    """
    Selenium ile Cloudflare'i geçmeye çalışır.
    Yöntem: Klavye (TAB + SPACE) simülasyonu.
    """
    print(f"🔓 Selenium Başlatılıyor: {BASE_DOMAIN} ...", flush=True)
    cookies = {}
    user_agent = ""
    
    # agent: Kullanıcı ajanı (User Agent) değiştirerek Linux izini gizlemeye çalışıyoruz
    with SB(uc=True, headless=False, agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36") as sb:
        try:
            # Reconnect ile aç (İzleri temizler)
            sb.uc_open_with_reconnect(BASE_DOMAIN + "/diziler/", reconnect_time=5)
            
            print("   ⏳ Sayfa yüklendi, Cloudflare kontrol ediliyor...", flush=True)
            time.sleep(5)
            
            # --- KLAVYE İLE GEÇİŞ DENEMESİ ---
            # Cloudflare kutusu bazen fare tıklamasını algılamaz. 
            # TAB tuşuyla kutuyu seçip BOŞLUK tuşuna basmayı deneyeceğiz.
            
            for i in range(3): # 3 tur dene
                title = sb.get_title()
                if "Attention" not in title and "Just a moment" not in title:
                    print("   ✅ Engel yok veya geçildi!", flush=True)
                    break
                
                print(f"   🤖 Engel Algılandı! Klavye hilesi deneniyor... (Tur {i+1})", flush=True)
                
                # Sayfaya tıkla (odağı al)
                sb.click("body") 
                
                # 5 Kere TAB tuşuna bas (Kutucuğa gelmek için)
                for _ in range(5):
                    sb.press_keys("\t") # TAB tuşu
                    time.sleep(0.3)
                
                # Şimdi SPACE (Boşluk) ve ENTER tuşlarına bas
                sb.press_keys(" ") # Boşluk (Checkbox işaretler)
                time.sleep(1)
                sb.press_keys("\n") # Enter
                
                # Bekle ve kontrol et
                time.sleep(6)
            
            # Son Kontrol
            title = sb.get_title()
            print(f"   🔓 Site Başlığı: {title}", flush=True)
            
            if "Attention" in title or "Just a moment" in title:
                print("   ❌ Cloudflare GEÇİLEMEDİ! IP adresi bloklanmış olabilir.", flush=True)
                # Sayfa kaynağını kaydet (Hata ayıklama için - Opsiyonel)
                # sb.save_page_source("cloudflare_error.html")
                return None, None
            
            # Başarılı ise verileri al
            user_agent = sb.get_user_agent()
            sb_cookies = sb.get_cookies()
            for cookie in sb_cookies:
                cookies[cookie['name']] = cookie['value']
            
            if not cookies:
                print("   ❌ Giriş yapıldı ama çerezler boş!", flush=True)
                return None, None
                
            print(f"   ✅ Giriş Başarılı! ({len(cookies)} çerez)", flush=True)
            
        except Exception as e:
            print(f"   ❌ Selenium hatası: {e}", flush=True)
            return None, None
            
    return cookies, user_agent

def get_soup_fast(url, cookies, user_agent):
    headers = {
        'User-Agent': user_agent,
        'Referer': BASE_DOMAIN,
    }
    try:
        response = session.get(url, cookies=cookies, headers=headers, impersonate="chrome110", timeout=15)
        if response.status_code == 200: return BeautifulSoup(response.content, 'html.parser')
        elif response.status_code == 404: return "404"
        elif response.status_code == 403: return "403"
    except Exception as e:
        print(f"   ⚠️ Hızlı mod hatası: {e}", flush=True)
    return None

def get_video_source(soup):
    try:
        player_area = soup.find('div', class_=lambda x: x and ('video' in x or 'player' in x))
        if player_area:
            iframe = player_area.find('iframe')
            if iframe: return iframe.get('src')
        
        iframes = soup.find_all('iframe')
        for frame in iframes:
            src = frame.get('src', '')
            fid = frame.get('id', '')
            if 'psContainer' in fid or 'google' in src: continue
            if 'embed' in src or '.cfd' in src or 'player' in src or 'get_video' in src: return src
    except: pass
    return ""

def get_episodes_from_page(soup, cookies, user_agent, known_urls=[]):
    new_episodes = []
    all_links = soup.find_all('a', href=True)
    
    for link in all_links:
        ep_url = link.get('href')
        if '/dizi/' in ep_url and 'sezon' in ep_url and 'bolum' in ep_url:
            full_ep_url = urljoin(BASE_DOMAIN, ep_url)
            if full_ep_url in known_urls: continue
            if any(e['url'] == full_ep_url for e in new_episodes): continue

            title = link.get('title') or link.get_text(strip=True)
            ep_data = {'url': full_ep_url, 'title': title, 'episode_number': ''}
            
            try:
                match = re.search(r'(\d+)-sezon-(\d+)-bolum', full_ep_url)
                if match: ep_data['episode_number'] = f"S{match.group(1)} E{match.group(2)}"
            except: pass

            print(f"      ▶️ {title}", flush=True)
            ep_soup = get_soup_fast(full_ep_url, cookies, user_agent)
            
            if ep_soup == "403":
                print("      ⚠️ 403 (Atlandı)", flush=True)
                continue 
            if ep_soup and ep_soup != "404":
                video_src = get_video_source(ep_soup)
                ep_data['video_source'] = video_src
                print(f"      ✅ KAYNAK: {video_src}", flush=True)
                new_episodes.append(ep_data)
    return new_episodes

def get_full_series_details(url, cookies, user_agent, existing_episodes_list=[]):
    print(f"   ▶️ Analiz: {url}", flush=True)
    soup = get_soup_fast(url, cookies, user_agent)
    
    if soup == "403": return "403"
    if not soup or soup == "404": return None
    
    meta = {"url": url, "title": "", "year": "", "description": "", "poster": "", "cover_image": "", "imdb": "0", "genres": [], "episodes": []}
    
    try:
        h1 = soup.find('h1')
        if h1: meta['title'] = h1.get_text(" ", strip=True)

        summary = soup.find('div', class_=lambda x: x and ('ozet' in x or 'summary' in x or 'description' in x))
        if summary: meta['description'] = summary.get_text(strip=True)

        poster_img = soup.find('img', class_=lambda x: x and ('poster' in x or 'cover' in x))
        if poster_img: meta['poster'] = poster_img.get('src')

        season_links = []
        all_links = soup.find_all('a', href=True)
        for l in all_links:
            href = l['href']
            if 'sezon' in href and 'bolum' not in href: 
                 full_link = urljoin(BASE_DOMAIN, href)
                 if full_link not in season_links and full_link != url: season_links.append(full_link)
        
        if not season_links: season_links.append(url)
        print(f"   📂 {len(season_links)} Sezon.", flush=True)

        for season_url in season_links:
            if season_url == url: current_season_soup = soup
            else: current_season_soup = get_soup_fast(season_url, cookies, user_agent)
            
            if current_season_soup and current_season_soup not in ["404", "403"]:
                season_episodes = get_episodes_from_page(current_season_soup, cookies, user_agent, existing_episodes_list)
                meta['episodes'].extend(season_episodes)
    except: pass
    return meta

def main():
    print("🛡️ Dizipal 1538 V3 (Klavye Modu)...", flush=True)
    cookies, user_agent = get_cookies_and_ua_with_selenium()
    
    if not cookies:
        print("❌ Çerez YOK! (GitHub IP'si bloklanmış olabilir)", flush=True)
        # Eğer Github Actions'da çalışmıyorsa lokalde çalıştırın uyarısı:
        print("💡 İPUCU: Bu kodu kendi bilgisayarınızda çalıştırırsanız %100 çalışacaktır.", flush=True)
        return

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f: all_series = json.load(f)
            print(f"📦 Veri: {len(all_series)} dizi.", flush=True)
        except: all_series = []
    else: all_series = []

    page_num = 1
    empty_page_count = 0 

    while True:
        target_url = f"{BASE_DOMAIN}/diziler/page/{page_num}/" if page_num > 1 else f"{BASE_DOMAIN}/diziler/"
        print(f"\n--- SAYFA {page_num} ---", flush=True)
        soup = get_soup_fast(target_url, cookies, user_agent)
        
        if soup == "403":
            print("🔄 403! Yenileniyor...", flush=True)
            cookies, user_agent = get_cookies_and_ua_with_selenium()
            if not cookies: break
            soup = get_soup_fast(target_url, cookies, user_agent)

        if not soup or soup == "404": break
        
        links = soup.find_all('a', href=True)
        series_urls = []
        for link in links:
            href = link['href']
            if '/dizi/' in href and href.count('/') > 3 and 'sezon' not in href and 'bolum' not in href:
                full_url = urljoin(BASE_DOMAIN, href)
                clean_url = full_url.split('?')[0]
                if clean_url not in series_urls: series_urls.append(clean_url)
        
        series_urls = list(set(series_urls))
        if not series_urls:
            empty_page_count += 1
            if empty_page_count >= 2: break
            page_num += 1
            continue
        
        empty_page_count = 0
        print(f"   🔍 {len(series_urls)} dizi.", flush=True)

        for s_url in series_urls:
            existing_series = next((s for s in all_series if s['url'] == s_url), None)
            
            if existing_series:
                known_urls = [ep['url'] for ep in existing_series.get('episodes', []) if 'url' in ep]
                update_data = get_full_series_details(s_url, cookies, user_agent, existing_episodes_list=known_urls)
                
                if update_data == "403":
                    cookies, user_agent = get_cookies_and_ua_with_selenium()
                    if cookies: update_data = get_full_series_details(s_url, cookies, user_agent, existing_episodes_list=known_urls)

                if update_data and update_data != "403" and update_data['episodes']:
                    existing_series['episodes'].extend(update_data['episodes'])
                    print(f"   🆙 +{len(update_data['episodes'])} bölüm.", flush=True)
                    with open(DATA_FILE, 'w', encoding='utf-8') as f: json.dump(all_series, f, ensure_ascii=False, indent=2)
                else:
                    print(f"   ⏭️ {existing_series.get('title')}", flush=True)
            else:
                new_details = get_full_series_details(s_url, cookies, user_agent, existing_episodes_list=[])
                if new_details == "403":
                    cookies, user_agent = get_cookies_and_ua_with_selenium()
                    if cookies: new_details = get_full_series_details(s_url, cookies, user_agent, existing_episodes_list=[])
                
                if new_details and new_details != "403":
                    all_series.append(new_details)
                    print(f"   ✅ {new_details.get('title')}", flush=True)
                    with open(DATA_FILE, 'w', encoding='utf-8') as f: json.dump(all_series, f, ensure_ascii=False, indent=2)

        page_num += 1

    print(f"\n🎉 Bitti. Toplam: {len(all_series)}")

if __name__ == "__main__":
    main()
