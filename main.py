import requests
from bs4 import BeautifulSoup
import json
import time
import sys
import os

# --- AYARLAR ---
BASE_DOMAIN = "https://dizipal.cx"
DATA_FILE = 'movies_test.json' # Test için ayrı bir dosya ismi verdim
MAX_PAGES = 1 # DENEME İÇİN SADECE 1 SAYFA

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
        "description": "Açıklama bulunamadı.",
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
        # Sitedeki yapıya göre farklı class isimlerini deniyoruz
        desc_div = soup.find('div', class_='description') or soup.find('div', class_='wp-content') or soup.find('p', class_='storyline')
        if desc_div:
            details["description"] = desc_div.get_text(strip=True)

        # 3. IMDB Puanı
        imdb_element = soup.select_one('.imdb-rate, .imdb, .rating')
        if imdb_element:
            details["imdb"] = imdb_element.get_text(strip=True).replace("IMDb:", "").strip()

        # 4. Kategoriler (Türler)
        genre_links = soup.select('.categories a, .genres a, .genre a')
        details["genres"] = list(set([g.get_text(strip=True) for g in genre_links])) # set() ile mükerrerleri sildik

        # 5. Oyuncular
        cast_links = soup.select('.cast a, .actors a, .actor a')
        details["cast"] = [c.get_text(strip=True) for c in cast_links]

    except Exception as e:
        print(f"⚠️ Detay çekme hatası ({url}): {e}", flush=True)

    return details

def start_scraping():
    all_films = []
    print(f"🧪 TEST BAŞLADI: Sadece ilk sayfa ({BASE_DOMAIN}/filmler/page/1/) taranıyor...", flush=True)

    for page_num in range(1, MAX_PAGES + 1):
        target_url = f"{BASE_DOMAIN}/filmler/page/{page_num}/"
        print(f"\n📄 Sayfa {page_num} taranıyor: {target_url}", flush=True)
        
        soup = get_soup(target_url)
        if not soup: continue

        items = soup.find_all('div', class_='post-item')
        if not items:
            print("🚫 Film öğeleri bulunamadı!", flush=True)
            break

        print(f"📦 Bu sayfada {len(items)} film bulundu. Detaylar toplanıyor...", flush=True)

        for index, item in enumerate(items, 1):
            try:
                link_element = item.find('a')
                if not link_element: continue
                
                title = link_element.get('title', '').strip()
                movie_page_url = link_element.get('href', '')
                
                img_element = item.find('img')
                image = ""
                if img_element:
                    image = img_element.get('data-src') or img_element.get('src') or ""
                    if image.startswith('//'): image = 'https:' + image

                if title and movie_page_url:
                    print(f"   [{index}/{len(items)}] 🎬 {title} işleniyor... ", end="", flush=True)
                    
                    # Detay sayfasına gir
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
                    
                    time.sleep(0.5) # Sunucuyu yormayalım
                    
            except Exception as e:
                print(f"❌ Hata: {e}", flush=True)
                continue

        # Test dosyasını kaydet
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_films, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 Test bitti! 'movies_test.json' dosyasını kontrol edebilirsin.", flush=True)

if __name__ == "__main__":
    start_scraping()
