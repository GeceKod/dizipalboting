import requests
from bs4 import BeautifulSoup
import json
import time
import os
from urllib.parse import urljoin

# --- AYARLAR ---
BASE_DOMAIN = "https://dizipal.cx"
BASE_URL = "https://dizipal.cx/diziler/page/{}/" 
DATA_FILE = 'diziler_full.json'
MAX_RETRIES = 3

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': f'{BASE_DOMAIN}/',
}

def get_soup(url, retry_count=0):
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            return BeautifulSoup(response.content, 'html.parser')
        elif response.status_code == 404:
            return "404"
    except Exception as e:
        if retry_count < MAX_RETRIES:
            time.sleep(2)
            return get_soup(url, retry_count + 1)
    return None

def get_video_source(episode_url):
    """Bölüm sayfasına girip iframe src'yi alır."""
    soup = get_soup(episode_url)
    if not soup or soup == "404":
        return ""
    
    try:
        player_area = soup.find('div', class_='video-player-area')
        if player_area:
            iframe = player_area.find('iframe')
            if iframe:
                return iframe.get('src')
        
        # Fallback
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
            
            # Video kaynağını çek
            if ep_url:
                # time.sleep(0.5) # Sunucuyu yormamak için açabilirsin
                video_src = get_video_source(ep_url)
                ep_data['video_source'] = video_src
                print(f"      ✅ {ep_data.get('title', 'Bölüm')} -> Kaynak Alındı", flush=True)
        
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
        # --- Metadata (Başlık, Yıl, Poster vb.) ---
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

        # --- SEZON TARAMA MANTIĞI ---
        # 1. Sezon listesini bul
        season_links = []
        season_div = soup.find('div', id='season-options-list')
        
        if season_div:
            # Dropdown varsa içindeki tüm sezon linklerini al
            links = season_div.find_all('a', href=True)
            for l in links:
                full_link = urljoin(BASE_DOMAIN, l['href'])
                if full_link not in season_links:
                    season_links.append(full_link)
        
        # Eğer sezon dropdown'ı yoksa veya boşsa, sadece mevcut sayfayı (tek sezon) al
        if not season_links:
            season_links.append(url)
        
        print(f"   📂 Toplam {len(season_links)} sezon bulundu. Taranıyor...", flush=True)

        # 2. Her bir sezon linkini gez
        for s_idx, season_url in enumerate(season_links):
            print(f"      📌 Sezon {s_idx+1} taranıyor...", flush=True)
            
            # İlk sayfa zaten elimizde (soup), tekrar istek atmayalım
            if season_url == url:
                current_season_soup = soup
            else:
                current_season_soup = get_soup(season_url)
            
            if current_season_soup and current_season_soup != "404":
                # O sezonun bölümlerini çek ve ana listeye ekle
                season_episodes = get_episodes_from_page(current_season_soup)
                meta['episodes'].extend(season_episodes)

    except Exception as e:
        print(f"   ❌ Hata oluştu: {e}")

    return meta

def main():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            all_series = json.load(f)
    else:
        all_series = []

    page_num = 1
    
    while True:
        list_url = BASE_URL.format(page_num)
        print(f"\n📄 Sayfa {page_num} taranıyor: {list_url}")
        
        soup = get_soup(list_url)
        if not soup or soup == "404":
            print("🏁 Tarama tamamlandı.")
            break
        
        # Dizi detay linklerini bul
        links = soup.find_all('a', href=True)
        series_urls = []
        for link in links:
            href = link['href']
            # Basit filtre: /dizi/ altında ve en az 2 slash daha içermeli
            if '/dizi/' in href and href.count('/') > 3:
                full_url = urljoin(BASE_DOMAIN, href)
                # Query parametrelerini temizle (?sezon=1 vs olmasın)
                clean_url = full_url.split('?')[0]
                if clean_url not in series_urls:
                    series_urls.append(clean_url)

        # Mükerrerleri temizle
        series_urls = list(set(series_urls))
        
        if not series_urls:
            print("⚠️ Dizi bulunamadı, sonraki sayfaya geçiliyor.")
            page_num += 1
            continue

        for s_url in series_urls:
            # Zaten ekli mi?
            if any(s['url'] == s_url for s in all_series):
                print(f"   ⏭️ Zaten var: {s_url}")
                continue
            
            details = get_full_series_details(s_url)
            if details:
                all_series.append(details)
                # Anlık kaydetme
                with open(DATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(all_series, f, ensure_ascii=False, indent=2)

        page_num += 1

if __name__ == "__main__":
    main()
