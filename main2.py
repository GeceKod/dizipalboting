import cloudscraper
from bs4 import BeautifulSoup
import json
import time
import os
from urllib.parse import urljoin
import random

# --- AYARLAR ---
BASE_DOMAIN = "https://dizipal.cx"
DATA_FILE = 'diziler.json'
MAX_RETRIES = 3

# CloudScraper oluştur (Gerçek bir Chrome tarayıcısı taklidi yapar)
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

def get_soup(url, retry_count=0):
    """URL'e istek atıp BeautifulSoup objesi döner."""
    try:
        # Bot korumasını aşmak için scraper kullanıyoruz
        response = scraper.get(url, timeout=30)
        
        if response.status_code == 200:
            return BeautifulSoup(response.content, 'html.parser')
        elif response.status_code == 404:
            # 404 ise gerçekten sayfa yoktur
            return "404"
        elif response.status_code == 403:
            print(f"      ⚠️ Erişim Engellendi (403). 5 saniye soğuma bekleniyor...")
            time.sleep(5)
            # 403 durumunda 1 kez daha şans verelim
            if retry_count < 1:
                return get_soup(url, retry_count + 1)
            return None
        else:
            print(f"      ⚠️ Erişim Kodu: {response.status_code} -> {url}")
            return None
            
    except Exception as e:
        if retry_count < MAX_RETRIES:
            wait_time = random.uniform(3, 7)
            print(f"      ⏳ Bağlantı hatası, {wait_time:.1f}sn sonra tekrar deneniyor... ({retry_count+1}/{MAX_RETRIES})")
            time.sleep(wait_time)
            return get_soup(url, retry_count + 1)
        else:
            print(f"      ❌ Kritik Hata: {e}")
    return None

def get_video_source(episode_url):
    """Bölüm sayfasına girip iframe src'yi alır."""
    soup = get_soup(episode_url)
    if not soup or soup == "404":
        return ""
    
    try:
        # Yöntem 1: Player alanı
        player_area = soup.find('div', class_='video-player-area')
        if player_area:
            iframe = player_area.find('iframe')
            if iframe:
                return iframe.get('src')
        
        # Yöntem 2: Genel Iframe
        iframes = soup.find_all('iframe')
        for frame in iframes:
            src = frame.get('src', '')
            if 'embed' in src or '.cfd' in src or 'player' in src:
                return src
    except:
        pass
    return ""

def get_episodes_from_page(soup):
    """Bir sayfa (sezon) içindeki bölümleri parse eder."""
    episodes = []
    episode_items = soup.find_all('div', class_='episode-item')
    
    for item in episode_items:
        ep_data = {}
        link_tag = item.find('a')
        
        if link_tag:
            ep_url = link_tag.get('href')
            ep_data['url'] = ep_url
            ep_data['title'] = link_tag.get('title')
            
            img_tag = link_tag.find('img')
            if img_tag:
                ep_data['thumbnail'] = img_tag.get('src')
            
            if ep_url:
                # Video kaynağını çek
                video_src = get_video_source(ep_url)
                ep_data['video_source'] = video_src
                print(f"      ✅ {ep_data.get('title', 'Bölüm')} -> Kaynak Alındı", flush=True)
                # Sunucuyu boğmamak için kısa bekleme
                time.sleep(random.uniform(0.5, 1.5))

        num_tag = item.find('h4', class_='font-eudoxus')
        if num_tag:
            ep_data['episode_number'] = num_tag.get_text(strip=True)
        
        episodes.append(ep_data)
    return episodes

def get_full_series_details(url):
    print(f"   ▶️ Dizi Analiz ediliyor: {url}")
    soup = get_soup(url)
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
        
        print(f"   📂 {len(season_links)} Sezon bulundu. Taranıyor...", flush=True)

        for s_idx, season_url in enumerate(season_links):
            print(f"      📌 Sezon {s_idx+1} taranıyor...", flush=True)
            if season_url == url:
                current_season_soup = soup
            else:
                current_season_soup = get_soup(season_url)
                time.sleep(random.uniform(1, 2))
            
            if current_season_soup and current_season_soup != "404":
                season_episodes = get_episodes_from_page(current_season_soup)
                meta['episodes'].extend(season_episodes)

    except Exception as e:
        print(f"   ❌ Hata: {e}")

    return meta

def main():
    print("🚀 DİZİPAL TARAYICI BAŞLATILIYOR (Anti-Bot Modu)...")
    
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                all_series = json.load(f)
            print(f"📦 Mevcut veri yüklendi: {len(all_series)} dizi.")
        except:
            all_series = []
    else:
        all_series = []

    page_num = 1
    empty_page_count = 0 

    while True: 
        # URL Yapısı: 1. sayfa için /diziler/, diğerleri için /diziler/page/X/
        if page_num == 1:
            list_url = "https://dizipal.cx/diziler/"
        else:
            list_url = f"https://dizipal.cx/diziler/page/{page_num}/"
            
        print(f"\n📄 Sayfa {page_num} taranıyor: {list_url}")
        
        # Sayfayı çek
        soup = get_soup(list_url)
        
        # Eğer sayfa yoksa veya engellendiysek
        if not soup or soup == "404":
            print("🏁 Tarama durduruldu (Sayfa yok veya erişim engeli).")
            break
        
        links = soup.find_all('a', href=True)
        series_urls = []
        for link in links:
            href = link['href']
            # Link filtresi
            if '/dizi/' in href and href.count('/') > 3:
                full_url = urljoin(BASE_DOMAIN, href)
                clean_url = full_url.split('?')[0]
                if clean_url not in series_urls:
                    series_urls.append(clean_url)

        series_urls = list(set(series_urls))
        
        if not series_urls:
            print("⚠️ Bu sayfada dizi bulunamadı.")
            empty_page_count += 1
            if empty_page_count >= 2:
                print("🏁 Üst üste boş sayfa geldi. Bitiyor.")
                break
            page_num += 1
            continue
        
        empty_page_count = 0
        print(f"   🔍 {len(series_urls)} dizi bulundu.")

        for s_url in series_urls:
            if any(s['url'] == s_url for s in all_series):
                print(f"   ⏭️ Zaten var: {s_url}")
                continue
            
            details = get_full_series_details(s_url)
            if details:
                all_series.append(details)
                with open(DATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(all_series, f, ensure_ascii=False, indent=2)
            
            # Her dizi arasında bekleme (Bot tespitini önlemek için)
            time.sleep(random.uniform(2, 4))

        page_num += 1

    print(f"\n✅ İŞLEM TAMAMLANDI. {len(all_series)} dizi kaydedildi.")

if __name__ == "__main__":
    main()
