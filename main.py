import requests
from bs4 import BeautifulSoup
import json
import time
import os

# --- AYARLAR ---
BASE_DOMAIN = "https://dizipal.cx"
DATA_FILE = 'movies.json'
MAX_RETRIES = 3 # Bir sayfa hata verirse kaç kez denenecek
FAILED_THRESHOLD = 3 # Üst üste kaç sayfa hata verirse duracak

def get_soup(url, retry_count=0):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f'{BASE_DOMAIN}/',
    }
    try:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 200:
            return BeautifulSoup(response.content, 'html.parser')
        elif response.status_code == 404:
            return "404" # Sayfa gerçekten yok
        else:
            raise Exception(f"Status Code: {response.status_code}")
    except Exception as e:
        if retry_count < MAX_RETRIES:
            print(f"   ⚠️ Hata: {url}. {retry_count+1}. deneme yapılıyor...", flush=True)
            time.sleep(2)
            return get_soup(url, retry_count + 1)
        return None

def get_full_movie_details(url):
    soup = get_soup(url)
    details = {"videoUrl": url, "description": "Açıklama bulunamadı.", "imdb": "0.0", "genres": [], "cast": [], "year": ""}
    if not soup or soup == "404": return details
    try:
        iframe = soup.find('iframe')
        if iframe and 'src' in iframe.attrs: details["videoUrl"] = iframe['src']
        summary_title = soup.find('h6', string='Film Özeti')
        if summary_title:
            summary_p = summary_title.find_next('p')
            if summary_p: details["description"] = summary_p.get_text(strip=True)
        # Detay kutularını çekme...
        info_boxes = soup.find_all('div', class_=lambda x: x and 'rounded-[10px]' in x and 'bg-white/[4%]' in x)
        for box in info_boxes:
            label_span = box.find('span', class_='text-xs')
            if label_span:
                label = label_span.get_text(strip=True)
                val_div = label_span.find_next_sibling('div') or label_span.find_next_sibling('h6')
                if val_div:
                    if "IMDB Puanı" in label: details["imdb"] = val_div.get_text(strip=True)
                    elif "Tür" in label: details["genres"] = [a.get_text(strip=True) for a in val_div.find_all('a')]
                    elif "Oyuncular" in label: details["cast"] = [a.get_text(strip=True) for a in val_div.find_all('a')]
                    elif "Yapım Yılı" in label: details["year"] = val_div.get_text(strip=True)
    except: pass
    return details

def start_scraping():
    all_films = []
    page_num = 1
    consecutive_failed_pages = 0
    
    print(f"🛡️ Güneş TV: Yüksek Toleranslı Tarama Başlatıldı...", flush=True)

    while consecutive_failed_pages < FAILED_THRESHOLD:
        target_url = f"{BASE_DOMAIN}/filmler/page/{page_num}/"
        print(f"\n--- 📄 SAYFA {page_num} ANALİZİ ---", flush=True)
        
        soup = get_soup(target_url)
        
        if soup is None or soup == "404":
            consecutive_failed_pages += 1
            print(f"   ❌ Sayfa alınamadı ({consecutive_failed_pages}/{FAILED_THRESHOLD})", flush=True)
            page_num += 1
            continue

        # Eğer buraya geldiysek sayfa başarılıdır, hata sayacını sıfırla
        consecutive_failed_pages = 0
        items = soup.find_all('div', class_='post-item')
        
        if not items:
            print("   🚫 Film listesi boş. Arşiv bitti.", flush=True)
            break

        print(f"   📦 {len(items)} film bulundu.", flush=True)

        for item in items:
            try:
                link_element = item.find('a')
                if not link_element: continue
                title = link_element.get('title', '').strip()
                movie_url = link_element.get('href', '')
                img_element = item.find('img')
                image = img_element.get('data-src') or img_element.get('src') or ""
                
                meta = get_full_movie_details(movie_url)
                all_films.append({
                    'title': title, 'image': image, 'imdb': meta["imdb"], 
                    'year': meta["year"], 'genres': meta["genres"], 
                    'cast': meta["cast"], 'description': meta["description"], 
                    'videoUrl': meta["videoUrl"]
                })
                print(f"   ✅ [{len(all_films)}] {title}", flush=True)
            except: continue

        # Sayfanın en altında "Next/Sonraki" butonu var mı kontrolü
        # Bu, sona geldiğimizi anlamanın en kesin yoludur.
        pagination = soup.find('div', class_='pagination') or soup.find('div', class_='nav-links')
        if pagination:
            next_button = pagination.find('a', class_=lambda x: x and ('next' in x or 'next-page' in x))
            if not next_button and page_num > 5: # İlk sayfalarda değilsek ve next yoksa bitmiştir
                print("   🏁 Sonraki sayfa butonu bulunamadı. Arşiv tamamlandı.", flush=True)
                # break # İstersen burada da kırabilirsin ama ardışık hata kontrolü daha garanti.

        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_films, f, ensure_ascii=False, indent=2)
        
        page_num += 1

    print(f"\n🎉 İşlem tamamlandı. Toplam veri: {len(all_films)}", flush=True)

if __name__ == "__main__":
    start_scraping()
