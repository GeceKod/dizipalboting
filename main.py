import requests
from bs4 import BeautifulSoup
import json
import os
import time
import html
from urllib.parse import urlparse

# --- AYARLAR ---
# URL'yi doğrudan buraya yazıyoruz ki karışıklık olmasın
BASE_URL = 'https://dizipal.cx/filmler/'
DATA_FILE = 'movies.json'

def get_soup(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://dizipal.cx/'
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"❌ Hata: {url} - {e}")
        return None

def get_video_link(url):
    """Film sayfasındaki iframe (tuzak) linkini çeker."""
    soup = get_soup(url)
    if not soup: return url
    # Yeni sitede id='iframe' hala duruyor mu kontrol eder
    iframe = soup.find('iframe', id='iframe') or soup.find('iframe')
    if iframe and 'src' in iframe.attrs:
        return iframe['src']
    return url

def get_films():
    films = []
    print(f"🚀 Başlatılıyor: {BASE_URL}")
    
    soup = get_soup(BASE_URL)
    if not soup:
        print("❌ Ana sayfa çekilemedi!")
        return films

    # Yeni HTML yapısına göre seçim yapıyoruz
    # Filmler artık <div class="post-item"> içinde
    items = soup.find_all('div', class_='post-item')
    
    print(f"📦 Sayfada {len(items)} film bulundu.")

    for item in items:
        try:
            link_element = item.find('a')
            if not link_element: continue
            
            title = link_element.get('title', '').strip()
            url = link_element.get('href', '')
            
            img_element = item.find('img')
            image = ""
            if img_element:
                image = img_element.get('data-src') or img_element.get('src') or ""

            if title and url:
                print(f"🔍 İşleniyor: {title}")
                
                # ÖNEMLİ: IPTV için asıl iframe linkini alıyoruz
                video_url = get_video_link(url)
                
                films.append({
                    'title': title,
                    'image': image,
                    'url': url,
                    'videoUrl': video_url,
                    'genres': [], # Liste sayfasında tür bilgisi yoksa boş bırakıyoruz
                    'year': "",
                    'imdb': ""
                })
                
                # Siteyi yormamak için kısa bekleme
                time.sleep(0.5)
                
        except Exception as e:
            print(f"⚠️ Eleman işlenirken hata: {e}")

    # Veriyi kaydet
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(films, f, ensure_ascii=False, indent=2)
    
    print(f"✅ İşlem tamamlandı! {len(films)} film kaydedildi.")
    return films

if __name__ == "__main__":
    get_films()
