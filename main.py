import requests
from bs4 import BeautifulSoup
import json
import time
import sys
import os

# --- AYARLAR ---
BASE_DOMAIN = "https://dizipal.cx"
DATA_FILE = 'movies_test.json'
MAX_PAGES = 1 # Deneme için 1, sonra 170 yapabilirsin Güneş.

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
    soup = get_soup(url)
    details = {
        "videoUrl": url,
        "description": "Açıklama bulunamadı.",
        "imdb": "0.0",
        "genres": [],
        "cast": [],
        "year": ""
    }
    
    if not soup:
        return details

    try:
        # 1. Video Iframe
        iframe = soup.find('iframe')
        if iframe and 'src' in iframe.attrs:
            details["videoUrl"] = iframe['src']

        # 2. Film Özeti (H6 'Film Özeti' başlığından sonraki P etiketini alıyoruz)
        summary_title = soup.find('h6', string='Film Özeti')
        if summary_title:
            summary_p = summary_title.find_next('p')
            if summary_p:
                details["description"] = summary_p.get_text(strip=True)

        # 3. 'Tüm Veriler' kutusunu tarıyoruz
        # Bu kutular içindeki span'lar başlığı, yanındaki div'ler değeri veriyor.
        info_boxes = soup.find_all('div', class_=lambda x: x and 'rounded-[10px]' in x and 'bg-white/[4%]' in x)
        
        for box in info_boxes:
            label_span = box.find('span', class_='text-xs')
            if not label_span: continue
            
            label = label_span.get_text(strip=True)
            value_div = label_span.find_next_sibling('div') or label_span.find_next_sibling('h6')
            
            if not value_div: continue

            if "IMDB Puanı" in label:
                details["imdb"] = value_div.get_text(strip=True)
            elif "Tür" in label:
                details["genres"] = [a.get_text(strip=True) for a in value_div.find_all('a')]
            elif "Oyuncular" in label:
                details["cast"] = [a.get_text(strip=True) for a in value_div.find_all('a')]
            elif "Yapım Yılı" in label:
                details["year"] = value_div.get_text(strip=True)

    except Exception as e:
        print(f"⚠️ Detay çekme hatası: {e}", flush=True)

    return details

def start_scraping():
    all_films = []
    print(f"🚀 Güneş TV için zengin veri toplama başlıyor...", flush=True)

    soup = get_soup(f"{BASE_DOMAIN}/filmler/page/1/")
    if not soup: return

    items = soup.find_all('div', class_='post-item')
    print(f"📦 İlk sayfada {len(items)} film bulundu.", flush=True)

    for index, item in enumerate(items, 1):
        try:
            link_element = item.find('a')
            if not link_element: continue
            
            title = link_element.get('title', '').strip()
            movie_page_url = link_element.get('href', '')
            
            # Resim çekme
            img_element = item.find('img')
            image = img_element.get('data-src') or img_element.get('src') or ""
            
            print(f"   [{index}/{len(items)}] 🎬 {title} ... ", end="", flush=True)
            
            # Detayları çek
            meta = get_full_movie_details(movie_page_url)
            
            all_films.append({
                'title': title,
                'image': image,
                'imdb': meta["imdb"],
                'year': meta["year"],
                'genres': meta["genres"],
                'cast': meta["cast"],
                'description': meta["description"],
                'videoUrl': meta["videoUrl"],
                'sourceUrl': movie_page_url
            })
            print("✅ Veriler çekildi.", flush=True)
            time.sleep(0.5)
        except:
            continue

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_films, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 İşlem tamam! 'movies_test.json' hazır Güneş.", flush=True)

if __name__ == "__main__":
    start_scraping()
