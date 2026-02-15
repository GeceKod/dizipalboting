from seleniumbase import SB
from bs4 import BeautifulSoup
import json
import time
import os
import random
from urllib.parse import urljoin

# --- AYARLAR ---
BASE_DOMAIN = "https://dizipal.cx"
DATA_FILE = 'diziler.json'

def get_video_source(sb, episode_url):
    """Bölüm sayfasına girip iframe src'yi alır."""
    try:
        sb.open(episode_url)
        # Sayfanın yüklenmesini bekle (Video player div'i görünene kadar)
        try:
            sb.wait_for_element('div.video-player-area', timeout=5)
        except:
            pass # Bulamazsa devam et
        
        soup = BeautifulSoup(sb.get_page_source(), 'html.parser')
        
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
    except Exception as e:
        print(f"      ⚠️ Video kaynağı alınamadı: {e}")
    return ""

def get_full_series_details(sb, url):
    print(f"   ▶️ Dizi Analiz ediliyor: {url}")
    
    try:
        sb.open(url)
        # Cloudflare kontrolü varsa geçmesini bekle
        time.sleep(random.uniform(2, 4)) 
        
        soup = BeautifulSoup(sb.get_page_source(), 'html.parser')
        
        # Eğer sayfa boş veya 404 ise
        if "Sayfa bulunamadı" in soup.text or sb.get_title() == "404 Not Found":
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

        # Metadata Çekme İşlemleri
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
        
        print(f"   📂 {len(season_links)} Sezon bulundu.", flush=True)

        # Sezonları Gez
        for s_idx, season_url in enumerate(season_links):
            print(f"      📌 Sezon {s_idx+1} taranıyor...", flush=True)
            
            # Eğer zaten o sayfadaysak tekrar yükleme
            if season_url != sb.get_current_url():
                sb.open(season_url)
                time.sleep(2)
            
            season_soup = BeautifulSoup(sb.get_page_source(), 'html.parser')
            episode_items = season_soup.find_all('div', class_='episode-item')
            
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
                        # Video için yeni sekmeye gerek yok, mevcut sayfada git-gel yapacağız
                        # Veya basitçe URL'yi ziyaret edeceğiz.
                        # NOT: Her bölüme girmek çok zaman alacağı için burada dikkatli olunmalı.
                        # Hız için şimdilik ana sayfaya dönme mantığını kurgulamalıyız.
                        pass 

                num_tag = item.find('h4', class_='font-eudoxus')
                if num_tag:
                    ep_data['episode_number'] = num_tag.get_text(strip=True)
                
                meta['episodes'].append(ep_data)

        # NOT: Video kaynaklarını toplamak için bölümleri tek tek gezmek gerek
        # Bu işlem Selenium ile ÇOK UZUN sürer (Her bölüm 5-10 saniye). 
        # O yüzden şimdilik sadece bölüm listesini alıyoruz.
        # Eğer video player'ı MUTLAKA istiyorsanız aşağıyı açın:
        
        print(f"      🎥 Bölüm playerları taranıyor ({len(meta['episodes'])} bölüm)...")
        for ep in meta['episodes']:
            if 'url' in ep:
                 src = get_video_source(sb, ep['url'])
                 ep['video_source'] = src
                 print(f"         -> {ep.get('title')} : {src}", flush=True)

        return meta

    except Exception as e:
        print(f"   ❌ Hata: {e}")
        return None

def main():
    print("🚀 DİZİPAL TARAYICI (SeleniumBase UC Modu)...")
    
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                all_series = json.load(f)
            print(f"📦 Mevcut veri: {len(all_series)} dizi.")
        except:
            all_series = []
    else:
        all_series = []

    # UC=True -> Undetected Chromedriver (Bot korumasını aşar)
    # Headless=False -> Xvfb ile sanal ekranda "görünür" çalışır (Daha güvenli)
    with SB(uc=True, headless=False) as sb:
        page_num = 1
        empty_page_count = 0 

        while True:
            if page_num == 1:
                list_url = "https://dizipal.cx/diziler/"
            else:
                list_url = f"https://dizipal.cx/diziler/page/{page_num}/"
                
            print(f"\n📄 Sayfa {page_num} açılıyor: {list_url}")
            
            try:
                sb.open(list_url)
                # Cloudflare "Human Verify" çıkarsa bekle
                time.sleep(3) 
                
                # Sayfa kaynağını al
                soup = BeautifulSoup(sb.get_page_source(), 'html.parser')
                
                # 404 Kontrolü
                if "Sayfa bulunamadı" in soup.text or sb.get_title() == "404 Not Found":
                    print("🏁 Sayfa yok. Bitti.")
                    break

                links = soup.find_all('a', href=True)
                series_urls = []
                for link in links:
                    href = link['href']
                    if '/dizi/' in href and href.count('/') > 3:
                        full_url = urljoin(BASE_DOMAIN, href)
                        clean_url = full_url.split('?')[0]
                        if clean_url not in series_urls:
                            series_urls.append(clean_url)
                
                series_urls = list(set(series_urls))
                
                if not series_urls:
                    print("⚠️ Dizi bulunamadı.")
                    empty_page_count += 1
                    if empty_page_count >= 2:
                        break
                    page_num += 1
                    continue
                
                empty_page_count = 0
                print(f"   🔍 {len(series_urls)} dizi bulundu.")

                for s_url in series_urls:
                    if any(s['url'] == s_url for s in all_series):
                        print(f"   ⏭️ Zaten var: {s_url}")
                        continue
                    
                    details = get_full_series_details(sb, s_url)
                    if details:
                        all_series.append(details)
                        with open(DATA_FILE, 'w', encoding='utf-8') as f:
                            json.dump(all_series, f, ensure_ascii=False, indent=2)

            except Exception as e:
                print(f"⚠️ Sayfa hatası: {e}")
                # Hata alınca devam etmeye çalış
                
            page_num += 1

    print(f"\n✅ TAMAMLANDI. {len(all_series)} dizi kaydedildi.")

if __name__ == "__main__":
    main()
