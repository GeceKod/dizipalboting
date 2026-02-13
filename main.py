import requests
from bs4 import BeautifulSoup
import json
import time
import sys
import os

# --- AYARLAR ---
BASE_DOMAIN = "https://dizipal.cx"
DATA_FILE = 'movies.json'
MAX_PAGES = int(os.environ.get('MAX_PAGES', 50)) 

def get_soup(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f'{BASE_DOMAIN}/',
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"\n❌ Bağlantı Hatası: {url} - {e}", flush=True)
        return None

def get_full_movie_details(url):
    """Film detay sayfasına girer; iframe, puan, kategori ve özeti çeker."""
    soup = get_soup(url)
    details = {
        "videoUrl": url,
        "description": "",
        "imdb": "0.0",
        "genres": [],
        "cast": []
    }
    
    if not soup:
        return details

    try:
        # 1. Video Iframe Yakalama
        iframe = soup.find('iframe', id='iframe') or soup.find('iframe')
        if iframe and 'src' in iframe.attrs:
            src = iframe['src']
            details["videoUrl"] = 'https:' + src if src.startswith('//') else src

        # 2. Film Özeti (Açıklama)
        # Sitedeki yapıya göre genellikle 'description' veya 'summary' class'ında olur
        desc_div = soup.find('div', class_='description') or soup.find('p', class_='summary')
        if desc_div:
            details["description"] = desc_div.get_text(strip=True)

        # 3. IMDB Puanı
        imdb_span = soup.find('span', class_='imdb') or soup.find('div', class_='imdb-rate')
        if imdb_span:
            details["imdb"] = imdb_span.get_text(strip=True).replace("IMDb:", "").strip()

        # 4. Kategoriler (Türler)
        genre_links = soup.select('div.categories a, div.genres a')
        details["genres"] = [g.get_text(strip=True) for g in genre_links]

        # 5. Oyuncular
        cast_links = soup.select('div.cast a, div.actors a')
        details["cast"] = [c.get_text(strip=True) for c in cast_links]

    except Exception as e:
        print(f"⚠️ Detay çekme hatası: {e}", flush=True)

    return details

def start_scraping():
    all_films = []
    print(f"🚀 Zengin veri toplama işlemi başlıyor... (Hedef: {MAX_PAGES} sayfa)", flush=True)

    for page_num in range(1, MAX_PAGES + 1):
        target_url = f"{BASE_DOMAIN}/filmler/page/{page_num}/"
        print(f"\n📄 Sayfa {page_num} taranıyor...", flush=True)
        
        soup = get_soup(target_url)
        if not soup: continue

        items = soup.find_all('div', class_='post-item')
        if not items: break

        for index, item in enumerate(items, 1):
            try:
                link_element = item.find('a')
                if not link_element: continue
                
                title = link_element.get('title', '').strip()
                movie_page_url = link_element.get('href', '')
                
                img_element = item.find('img')
                image = img_element.get('data-src') or img_element.get('src') or ""
                if image.startswith('//'): image = 'https:' + image

                if title and movie_page_url:
                    print(f"   [{index}/{len(items)}] 🎬 {title} (Veriler çekiliyor...) ", end="", flush=True)
                    
                    # Sayfanın içine girip tüm bilgileri alıyoruz
                    movie_meta = get_full_movie_details(movie_page_url)
                    
                    all_films.append({
                        'title': title,
                        'image': image,
                        'url': movie_page_url,
                        'videoUrl': movie_meta["videoUrl"],
                        'imdb': movie_meta["imdb"],
                        'description': movie_meta["description"],
                        'genres': movie_meta["genres"],
                        'cast': movie_meta["cast"]
                    })
                    print("✅", flush=True)
                    
                    # Sunucuyu korumak için kısa bekleme
                    time.sleep(0.5)
                    
            except Exception as e:
                continue

        # JSON dosyasını her sayfa sonunda kaydet
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_films, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 İşlem Bitti! Zenginleştirilmiş {len(all_films)} film hazır.", flush=True)

if __name__ == "__main__":
    start_scraping()
