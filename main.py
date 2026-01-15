import cloudscraper
from bs4 import BeautifulSoup
import json
import os
import time
from urllib.parse import urlparse

# --- AYARLAR ---
# Burasi cok onemli, site adresi degistiyse buradan guncellemelisin.
BASE_URL = os.environ.get('SITE_URL', 'https://dizipal1225.com/filmler')
DATA_FILE = 'movies.json'
HTML_FILE = 'index.html'

def get_base_domain(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def get_scraper():
    """Bot korumasini asan ozel tarayici olusturur."""
    return cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

def parse_films(soup, base_domain):
    """HTML icinden film bilgilerini ayiklar."""
    films = []
    # Site temasina uygun seciciler
    elements = soup.select('li.movie-item') or soup.select('li.item') or soup.find_all('li')

    for el in elements:
        try:
            # Baglanti ve ID bulma
            link_el = el.find('a')
            if not link_el: continue
            
            movie_id = link_el.get('data-id') # API icin gerekli ID
            href = link_el.get('href', '')
            
            # Tam URL olustur
            if href and not href.startswith('http'):
                full_url = base_domain + href
            else:
                full_url = href

            # Baslik
            title_el = el.find('span', class_='title') or el.find('h2') or el.find('h3')
            title = title_el.text.strip() if title_el else "Isimsiz"

            # Resim
            img_el = el.find('img')
            image = img_el.get('data-src') or img_el.get('src') or ""

            # Diger Bilgiler
            imdb_el = el.find('span', class_='imdb')
            imdb = imdb_el.text.strip() if imdb_el else "-"
            
            year_el = el.find('span', class_='year')
            year = year_el.text.strip() if year_el else ""

            # Eger baslik ve link varsa listeye ekle
            if title != "Isimsiz" and "dizipal" in full_url:
                films.append({
                    "id": movie_id,
                    "title": title,
                    "image": image,
                    "url": full_url,
                    "imdb": imdb,
                    "year": year
                })
        except:
            continue
    return films

def get_all_films():
    scraper = get_scraper()
    base_domain = get_base_domain(BASE_URL)
    api_url = f"{base_domain}/api/load-movies"
    
    all_films = []
    processed_titles = set()
    
    print(f"Tarama Baslatiliyor: {BASE_URL}")
    print("------------------------------------------------")

    # 1. SAYFA (Ana Sayfa)
    try:
        response = scraper.get(BASE_URL, timeout=30)
        if response.status_code != 200:
            print(f"HATA: Siteye girilemedi. Kod: {response.status_code}")
            # Site adresi yanlis olabilir veya bot engellenmis olabilir
            return []
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Kontrol amaciyla sayfa basligini yazdiralim
        page_title = soup.title.text.strip() if soup.title else "Baslik Yok"
        print(f"Site Basligi: {page_title}")
        
        if "Just a moment" in page_title or "Cloudflare" in page_title:
            print("DIKKAT: Cloudflare korumasina takildi. Bot tekrar deneyecek.")
            
        new_films = parse_films(soup, base_domain)
        
        if not new_films:
            print("UYARI: Sayfa cekildi ama film bulunamadi. CSS seciciler uyusmuyor olabilir.")
            
        for f in new_films:
            if f['title'] not in processed_titles:
                all_films.append(f)
                processed_titles.add(f['title'])
                
        print(f"Sayfa 1 OK. Toplam: {len(all_films)} film.")
        
    except Exception as e:
        print(f"Baglanti Hatasi: {e}")
        return []

    # 2. API DONGUSU (Sonsuz Kaydirmayi Taklit Et)
    page = 1
    # Test icin sonsuz donguyu limitli tutalim (Github sunucusu kilitlenmesin)
    MAX_PAGES = 50 
    
    while page < MAX_PAGES:
        if not all_films: break
        
        last_film = all_films[-1]
        last_id = last_film.get('id')
        
        if not last_id:
            print("Son film ID'si yok, dongu bitti.")
            break
            
        print(f"Siradaki yukleniyor... (Ref ID: {last_id})")
        
        try:
            payload = {'movie': last_id, 'year': '', 'tur': '', 'siralama': ''}
            response = scraper.post(api_url, data=payload, timeout=20)
            
            try:
                data = response.json()
            except:
                print("API JSON dondurmedi (Cloudflare engeli olabilir).")
                break
                
            if not data or not data.get('html'):
                print("Daha fazla veri gelmedi. Islem tamam.")
                break
                
            html_part = BeautifulSoup(data['html'], 'html.parser')
            more_films = parse_films(html_part, base_domain)
            
            added_count = 0
            for f in more_films:
                if f['title'] not in processed_titles:
                    all_films.append(f)
                    processed_titles.add(f['title'])
                    added_count += 1
            
            if added_count == 0:
                print("Yeni film bulunamadi. Dongu bitiyor.")
                break
                
            page += 1
            print(f"Sayfa {page} Eklendi (+{added_count}). Toplam: {len(all_films)}")
            time.sleep(2) # Cloudflare kizmasin diye yavasla
            
        except Exception as e:
            print(f"Dongu hatasi: {e}")
            break

    return all_films

def create_html(films):
    films_json = json.dumps(films, ensure_ascii=False)
    
    html_template = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dizipal Arsiv</title>
    <style>
        body {{ background-color: #202020; color: #fff; font-family: sans-serif; margin: 0; padding: 0; }}
        .header {{ background: #111; padding: 15px; position: sticky; top:0; z-index:999; display: flex; flex-direction: column; align-items: center; box-shadow: 0 2px 5px rgba(0,0,0,0.5); }}
        h1 {{ margin: 5px 0; font-size: 1.5rem; color: #e50914; }}
        #searchInput {{ padding: 10px; border-radius: 5px; border: none; width: 90%; max-width: 400px; margin-top: 10px; background: #333; color: white; }}
        
        .container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; padding: 15px; }}
        
        .card {{ background: #2b2b2b; border-radius: 5px; overflow: hidden; position: relative; transition: transform 0.2s; }}
        .card:hover {{ transform: scale(1.03); z-index: 10; }}
        .card img {{ width: 100%; aspect-ratio: 2/3; object-fit: cover; display: block; }}
        
        .info {{ padding: 8px; }}
        .title {{ font-weight: bold; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 5px; }}
        .meta {{ font-size: 0.75rem; color: #aaa; display: flex; justify-content: space-between; }}
        .imdb {{ color: #f5c518; font-weight: bold; }}
        
        .btn-watch {{ display: block; background: #e50914; color: white; text-align: center; text-decoration: none; padding: 6px; margin-top: 8px; border-radius: 3px; font-size: 0.85rem; }}
        
        #loadMoreBtn {{ display: block; margin: 20px auto; padding: 12px 40px; background: #333; color: white; border: 1px solid #555; border-radius: 5px; cursor: pointer; }}
        #loadMoreBtn:hover {{ background: #444; }}
        #totalCount {{ font-size: 0.8rem; color: #777; margin-top: 5px; }}
    </style>
</head>
<body>

<div class="header">
    <h1>Dizipal Arsiv</h1>
    <span id="totalCount">Yukleniyor...</span>
    <input type="text" id="searchInput" placeholder="Film Ara..." oninput="handleSearch()">
</div>

<div class="container" id="filmContainer"></div>
<button id="loadMoreBtn" onclick="loadMore()">Daha Fazla Yukle</button>

<script>
    const allFilms = {films_json};
    let displayedCount = 0;
    const itemsPerPage = 30;
    let currentList = allFilms;

    const container = document.getElementById('filmContainer');
    const loadBtn = document.getElementById('loadMoreBtn');
    const countLabel = document.getElementById('totalCount');

    function createCard(film) {{
        const div = document.createElement('div');
        div.className = 'card';
        div.innerHTML = `
            <img src="${{film.image}}" loading="lazy" onerror="this.src='https://via.placeholder.com/200x300?text=Resim+Yok'">
            <div class="info">
                <div class="title" title="${{film.title.replace(/"/g, '&quot;')}}">${{film.title}}</div>
                <div class="meta">
                    <span>${{film.year}}</span>
                    <span class="imdb">${{film.imdb}}</span>
                </div>
                <a href="${{film.url}}" target="_blank" class="btn-watch">Izle</a>
            </div>
        `;
        return div;
    }}

    function render() {{
        const nextBatch = currentList.slice(displayedCount, displayedCount + itemsPerPage);
        nextBatch.forEach(film => container.appendChild(createCard(film)));
        displayedCount += nextBatch.length;
        
        loadBtn.style.display = displayedCount >= currentList.length ? 'none' : 'block';
        countLabel.innerText = `Toplam: ${{allFilms.length}} Film`;
    }}

    function loadMore() {{ render(); }}

    function handleSearch() {{
        const query = document.getElementById('searchInput').value.toLowerCase();
        container.innerHTML = '';
        displayedCount = 0;
        currentList = query ? allFilms.filter(f => f.title.toLowerCase().includes(query)) : allFilms;
        render();
    }}

    render();
</script>
</body>
</html>"""
    
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html_template)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(films, f, ensure_ascii=False)

if __name__ == "__main__":
    data = get_all_films()
    if data:
        create_html(data)
    else:
        # Hata durumunda bile bos HTML olustur
        with open(HTML_FILE, 'w', encoding='utf-8') as f:
            f.write("<h1>Bot calisti ama film cekemedi. Loglari kontrol et.</h1>")
