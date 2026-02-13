import requests
from bs4 import BeautifulSoup
import json
import time
import sys
import os

# --- AYARLAR ---
# GitHub Actions'tan gelen URL'yi kullan, yoksa varsayılanı al
BASE_URL = os.environ.get('SITE_URL', 'https://dizipal.cx/filmler/page/')
DATA_FILE = 'movies.json'
# Kaç sayfa taranacağını belirle (Sitede toplam ~170 sayfa var)
MAX_PAGES = int(os.environ.get('MAX_PAGES', 50)) 

def get_soup(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://dizipal.cx/',
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
    """Film detay sayfasına girip iframe (tuzak) linkini çeker."""
    soup = get_soup(url)
    if not soup:
        return url
    
    # Yeni sitede iframe id'si genellikle 'iframe' olur
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
        target_url = f"{BASE_URL}{page_num}/"
        print(f"\n📄 Sayfa {page_num} taranıyor: {target_url}", flush=True)
        
        soup = get_soup(target_url)
        if not soup:
            print(f"⚠️ Sayfa {page_num} atlanıyor (Hata alındı).", flush=True)
            continue

        # Yeni HTML yapısındaki post-item class'larını bul
        items = soup.find_all('div', class_='post-item')
        
        if not items:
            print("🚫 Sayfada film bulunamadı. Arşiv sonuna gelinmiş olabilir.", flush=True)
            break

        print(f"📦 Bu sayfada {len(items)} film bulundu. İçerik çekiliyor...", flush=True)

        for index, item in enumerate(items, 1):
            try:
                link_element = item.find('a')
                if not link_element: continue
                
                title = link_element.get('title', '').strip()
                url = link_element.get('href', '')
                
                # Resim çekme (lazyload desteğiyle)
                img_element = item.find('img')
                image = ""
                if img_element:
                    image = img_element.get('data-src') or img_element.get('src') or ""
                    if image.startswith('//'): image = 'https:' + image

                if title and url:
                    # Anlık log basımı (Flush=True ile satır bitmeden yazı görünür)
                    print(f"   [{index}/{len(items)}] 🎬 {title} ... ", end="", flush=True)
                    
                    # Detay sayfasına girip iframe çekme
                    video_url = get_video_link(url)
                    
                    all_films.append({
                        'title': title,
                        'image': image,
                        'url': url,
                        'videoUrl': video_url
                    })
                    print("✅ Iframe yakalandı.", flush=True)
                    
                    # Sunucu korumasına takılmamak için kısa bekleme
                    time.sleep(0.4)
                    
            except Exception as e:
                print(f"⚠️ Hata (Film Atlandı): {e}", flush=True)
                continue

        # Her sayfa sonunda JSON'u güncelle (Kapanma riskine karşı)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_films, f, ensure_ascii=False, indent=2)
        
        print(f"✔️ Sayfa {page_num} tamamlandı. Kaydedilen toplam: {len(all_films)}", flush=True)

    print(f"\n🎉 İşlem Başarıyla Tamamlandı!", flush=True)
    print(f"📊 Toplam Çekilen Film: {len(all_films)}", flush=True)
    print(f"💾 Dosya Adı: {DATA_FILE}", flush=True)

if __name__ == "__main__":
    # Python'un çıktı biriktirmesini (buffering) engelleyen ayar
    # Alternatif olarak GitHub Actions YAML'da PYTHONUNBUFFERED: 1 yapılmalıdır.
    start_scraping()
