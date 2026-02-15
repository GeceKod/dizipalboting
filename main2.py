import requests
from bs4 import BeautifulSoup
import json
import time
import os

# --- AYARLAR ---
BASE_DOMAIN = "https://dizipal.cx"
BASE_URL = "https://dizipal.cx/diziler/page/{}/"  # Sayfalama yapısı
DATA_FILE = 'diziler.json'
MAX_RETRIES = 3

# Tarayıcı gibi görünmek için Header
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': f'{BASE_DOMAIN}/',
}

def get_soup(url, retry_count=0):
    """Verilen URL'e istek atıp BeautifulSoup objesi döner."""
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
    """
    Bölüm sayfasına gider ve iframe içindeki video linkini çeker.
    """
    soup = get_soup(episode_url)
    if not soup or soup == "404":
        return ""
    
    try:
        # 1. Yöntem: Senin gönderdiğin HTML yapısındaki player alanı
        player_area = soup.find('div', class_='video-player-area')
        if player_area:
            iframe = player_area.find('iframe')
            if iframe:
                return iframe.get('src')
        
        # 2. Yöntem: Yedek (Fallback) - Sayfadaki herhangi bir embed iframe'i bul
        iframes = soup.find_all('iframe')
        for frame in iframes:
            src = frame.get('src', '')
            # Genelde video linkleri bu kelimeleri veya uzantıları içerir
            if 'embed' in src or '.cfd' in src or 'player' in src or 'youtube' in src:
                return src
                
    except Exception as e:
        print(f"      ⚠️ Player çekilemedi: {e}")
    
    return ""

def get_full_series_details(url):
    """
    Dizi detay sayfasını ve bölümleri tarar.
    """
    soup = get_soup(url)
    if not soup or soup == "404":
        return None
    
    meta = {
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
        # --- 1. Başlık ve Yıl ---
        h1 = soup.find('h1')
        if h1:
            full_text = h1.get_text(" ", strip=True)
            if '(' in full_text:
                parts = full_text.split('(')
                meta['title'] = parts[0].strip()
                meta['year'] = parts[-1].replace(')', '').strip()
            else:
                meta['title'] = full_text

        # --- 2. Açıklama ---
        summary = soup.find('p', class_='summary-text')
        if summary:
            meta['description'] = summary.get_text(strip=True)

        # --- 3. Poster ---
        poster_div = soup.find('div', class_='poster')
        if poster_div and poster_div.find('img'):
            meta['poster'] = poster_div.find('img').get('src')

        # --- 4. Kapak Resmi (Background) ---
        head_div = soup.find('div', id='head', class_='cover-image')
        if head_div and head_div.has_attr('style'):
            style = head_div['style']
            if "url('" in style:
                meta['cover_image'] = style.split("url('")[1].split("')")[0]

        # --- 5. IMDB Puanı ---
        imdb_span = soup.find('span', string=lambda t: t and "IMDB Puanı" in t)
        if imdb_span:
            parent = imdb_span.find_parent('div')
            score = parent.find('h4') if parent else None
            if score:
                meta['imdb'] = score.get_text(strip=True)

        # --- 6. Türler ---
        genre_links = soup.find_all('a', href=lambda h: h and 'dizi-kategori' in h)
        meta['genres'] = list(set([g.get_text(strip=True) for g in genre_links]))

        # --- 7. Bölümler ve Player ---
        episode_items = soup.find_all('div', class_='episode-item')
        print(f"   📂 {len(episode_items)} bölüm bulundu. Player linkleri taranıyor...", flush=True)

        for item in episode_items:
            ep_data = {}
            link_tag = item.find('a')
            
            if link_tag:
                ep_url = link_tag.get('href')
                ep_data['url'] = ep_url
                ep_data['title'] = link_tag.get('title')
                
                # Thumbnail
                img_tag = link_tag.find('img')
                if img_tag:
                    ep_data['thumbnail'] = img_tag.get('src')
                
                # --- VİDEO KAYNAĞINI ÇEKME ---
                if ep_url:
                    # Sunucuyu yormamak için çok kısa bekleme
                    # time.sleep(0.5) 
                    video_src = get_video_source(ep_url)
                    ep_data['video_source'] = video_src
                    print(f"      ✅ {ep_data.get('title', 'Bölüm')} -> Kaynak Alındı", flush=True)
            
            # Bölüm numarası
            num_tag = item.find('h4', class_='font-eudoxus')
            if num_tag:
                ep_data['episode_number'] = num_tag.get_text(strip=True)
            
            meta['episodes'].append(ep_data)

    except Exception as e:
        print(f"   ❌ Detay hatası: {e}")

    return meta

def main():
    print("🚀 Dizi Tarayıcı Başlatılıyor...")
    
    # Mevcut veriyi yükle
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            all_series = json.load(f)
        print(f"📦 Mevcut {len(all_series)} dizi yüklendi.")
    else:
        all_series = []

    page_num = 1
    consecutive_errors = 0

    while True:
        url = BASE_URL.format(page_num)
        print(f"\n📄 Sayfa {page_num} taranıyor: {url}")
        
        soup = get_soup(url)
        
        if soup == "404":
            print("🏁 Sayfa bulunamadı (404). Tarama bitti.")
            break
        
        if not soup:
            consecutive_errors += 1
            if consecutive_errors > 3:
                print("⚠️ Çok fazla hata alındı, çıkılıyor.")
                break
            continue
            
        consecutive_errors = 0
        
        # Sayfadaki dizi kartlarını bul (Wordpress yapısına göre genelde article veya post-item olur)
        # Dizipal HTML yapısına göre kartları buluyoruz.
        # Genelde linkler 'dizi/dizi-adi' formatındadır.
        links = soup.find_all('a', href=True)
        series_links = []
        
        for link in links:
            href = link['href']
            # Sadece dizi detay sayfalarını al, pagination veya kategorileri alma
            if '/dizi/' in href and href.count('/') > 4: # Basit bir filtreleme
                if href not in series_links:
                    series_links.append(href)

        # Mükerrerleri temizle
        series_links = list(set(series_links))
        
        if not series_links:
            print("⚠️ Bu sayfada dizi bulunamadı. Sonraki sayfaya geçiliyor.")
            # Sayfa boşsa ama 404 değilse döngüye devam etmesi için
            # page_num += 1; continue; diyebiliriz ama sonsuz döngü riski var.
            # Şimdilik devam ediyoruz.

        print(f"   🔍 Bu sayfada {len(series_links)} dizi bulundu.")

        for s_url in series_links:
            # Zaten ekli mi kontrol et
            if any(s['url'] == s_url for s in all_series if 'url' in s):
                print(f"   ⏭️ Pas geçildi (Zaten var): {s_url}")
                continue
            
            print(f"   ▶️ İşleniyor: {s_url}")
            details = get_full_series_details(s_url)
            
            if details:
                details['url'] = s_url # Kayıt için URL'i de ekleyelim
                all_series.append(details)
                
                # Her diziden sonra kaydet (Veri kaybını önlemek için)
                with open(DATA_FILE, 'w', encoding='utf-8') as f:
                    json.dump(all_series, f, ensure_ascii=False, indent=2)

        page_num += 1
        # time.sleep(1) # Sayfalar arası bekleme

if __name__ == "__main__":
    main()
