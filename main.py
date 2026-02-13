import requests
from bs4 import BeautifulSoup
import json
import time
import sys
import os

# --- AYARLAR ---
# URL yapısını daha sağlam tanımlıyoruz
BASE_DOMAIN = "https://dizipal.cx"
DATA_FILE = 'movies.json'
MAX_PAGES = int(os.environ.get('MAX_PAGES', 50)) 

def get_soup(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f'{BASE_DOMAIN}/',
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"\n❌ Bağlantı Hatası: {url} - {e}", flush=True)
        return None

def get_video_link(url):
    soup = get_soup(url)
    if not soup:
        return url
    
    iframe = soup.find('iframe', id='iframe') or soup.find('iframe')
    if iframe and 'src' in iframe.attrs:
        src = iframe['src']
        if src.startswith('//'):
            src = 'https:' + src
        return src
    return url

def start_scraping():
    all_films = []
    print(f"🚀 Film çekme işlemi başlıyor... (Hedef: {MAX_PAGES} sayfa)", flush=True)

    for page_num in range(1, MAX_PAGES + 1):
        # URL yapısını burada manuel olarak kesinleştiriyoruz: /filmler/page/X/
        target_url = f"{BASE_DOMAIN}/filmler/page/{page_num}/"
        print(f"\n📄 Sayfa {page_num} taranıyor: {target_url}", flush=True)
        
        soup = get_soup(target_url)
        if not soup:
            print(f"⚠️ Sayfa {page_num} atlanıyor.", flush=True)
            continue

        items = soup.find_all('div', class_='post-item')
        
        if not items:
            print("🚫 Sayfada film bulunamadı. Arşiv sonuna gelinmiş olabilir.", flush=True)
            break

        print(f"📦 Bu sayfada {len(items)} film bulundu.", flush=True)

        for index, item in enumerate(items, 1):
            try:
                link_element = item.find('a')
                if not link_element: continue
                
                title = link_element.get('title', '').strip()
                url = link_element.get('href', '')
                
                img_element = item.find('img')
                image = ""
                if img_element:
                    image = img_element.get('data-src') or img_element.get('src') or ""
                    if image.startswith('//'): image = 'https:' + image

                if title and url:
                    print(f"   [{index}/{len(items)}] 🎬 {title} ... ", end="", flush=True)
                    
                    video_url = get_video_link(url)
                    
                    all_films.append({
                        'title': title,
                        'image': image,
                        'url': url,
                        'videoUrl': video_url
                    })
                    print("✅", flush=True)
                    
                    time.sleep(0.4)
                    
            except Exception as e:
                print(f"⚠️ Hata: {e}", flush=True)
                continue

        # JSON dosyasını güncelle
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_films, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 İşlem Bitti! Toplam {len(all_films)} film çekildi.", flush=True)

if __name__ == "__main__":
    start_scraping()
