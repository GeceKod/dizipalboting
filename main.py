import requests
from bs4 import BeautifulSoup
import json
import os
import time
import html
from urllib.parse import urlparse

# --- AYARLAR ---
BASE_URL = os.environ.get('SITE_URL', 'https://dizipal1225.com/filmler')
DATA_FILE = 'movies.json'
HTML_FILE = 'index.html'

def get_base_domain(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def get_soup(url, method='GET', data=None):
    """Standart Requests ile siteye baglanir (Cloudscraper YOK)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Referer': BASE_URL,
        'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    try:
        if method == 'POST':
            response = requests.post(url, headers=headers, data=data, timeout=15)
        else:
            response = requests.get(url, headers=headers, timeout=15)
            
        response.raise_for_status()
        
        # Eger API cevabi ise JSON dondur
        if method == 'POST':
            try:
                return response.json()
            except:
                return None
                
        return BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        # Hata olsa bile kodun durmamasi icin None donduruyoruz
        print(f"Baglanti Hatasi ({url}): {e}")
        return None

def get_movie_details(movie_url):
    """Filmin içine girip iframe ve detayları çeker."""
    info = {
        'videoUrl': movie_url, # Varsayılan olarak sayfa linki
        'summary': 'Özet bulunamadı.',
        'genres': ['Genel'],
        'duration': 'Belirtilmemiş'
    }
    
    soup = get_soup(movie_url)
    if not soup:
        return info

    try:
        # 1. Video Linki (Iframe)
        iframe = soup.find('iframe', id='iframe')
        if iframe and 'src' in iframe.attrs:
            info['videoUrl'] = iframe['src']
            
        # 2. Özet
        summary_el = soup.select_one('.ozet-text') or soup.select_one('.summary') or soup.find('article')
        if summary_el:
            info['summary'] = html.unescape(summary_el.text.strip())
            
        # 3. Türler
        genre_links = soup.select('.tur a') or soup.select('.genres a')
        if genre_links:
            info['genres'] = [html.unescape(g.text.strip()) for g in genre_links]
            
        # 4. Süre
        duration_el = soup.select_one('.sure') or soup.select_one('.duration')
        if duration_el:
            info['duration'] = html.unescape(duration_el.text.strip())
            
    except Exception as e:
        print(f"Detay hatası: {e}")
        
    return info

def parse_films_from_list(soup, base_domain):
    """Listeden temel bilgileri alır."""
    films = []
    elements = soup.select('li.movie-item') or soup.select('li.item') or soup.find_all('li')

    for el in elements:
        try:
            link_el = el.find('a')
            if not link_el: continue
            
            movie_id = link_el.get('data-id')
            href = link_el.get('href', '')
            
            if href and not href.startswith('http'):
                full_url = base_domain + href
            else:
                full_url = href

            title_el = el.find('span', class_='title') or el.find('h2') or el.find('h3')
            title = title_el.text.strip() if title_el else "İsimsiz"

            img_el = el.find('img')
            image = img_el.get('data-src') or img_el.get('src') or ""

            imdb_el = el.find('span', class_='imdb')
            imdb = imdb_el.text.strip() if imdb_el else "-"
            
            year_el = el.find('span', class_='year')
            year = year_el.text.strip() if year_el else ""

            if title != "İsimsiz" and "dizipal" in full_url:
                films.append({
                    "id": movie_id,
                    "title": html.unescape(title),
                    "image": image,
                    "url": full_url,
                    "imdb": imdb,
                    "year": year
                })
        except:
            continue
    return films

def get_all_films():
    base_domain = get_base_domain(BASE_URL)
    api_url = f"{base_domain}/api/load-movies"
    
    all_films = []
    processed_titles = set()
    
    print(f"Tarama Başlıyor (Requests Modu): {BASE_URL}")
    print("------------------------------------------------")

    # --- 1. SAYFA ---
    soup = get_soup(BASE_URL)
    if not soup:
        print("Ana sayfaya erişilemedi. Site engellemiş olabilir veya adres yanlış.")
        return []

    new_films = parse_films_from_list(soup, base_domain)
    
    for f in new_films:
        if f['title'] not in processed_titles:
            print(f">> Detaylar: {f['title']}")
            details = get_movie_details(f['url'])
            f.update(details)
            
            all_films.append(f)
            processed_titles.add(f['title'])
            # Hız ayarı: Çok hızlı istek atarsa engellenir. 0.2 iyi bir süredir.
            time.sleep(0.2) 
            
    print(f"Sayfa 1 Bitti. ({len(all_films)} Film)")

    # --- 2. DÖNGÜ (Daha Fazla Yükle) ---
    page = 1
    # Botun 1 saatten fazla çalışıp hata vermemesi için limiti şimdilik 30 sayfa yapalım.
    # Sorunsuz çalıştığını görünce artırırsın.
    MAX_PAGES = 30 
    
    while page < MAX_PAGES:
        if not all_films: break
        
        last_film = all_films[-1]
        last_id = last_film.get('id')
        
        if not last_id: break
            
        print(f"Sıradaki sayfa isteniyor (Ref: {last_id})...")
        
        payload = {'movie': last_id, 'year': '', 'tur': '', 'siralama': ''}
        data = get_soup(api_url, method='POST', data=payload)
        
        if not data or not data.get('html'):
            print("Veri bitti veya alınamadı.")
            break
            
        html_part = BeautifulSoup(data['html'], 'html.parser')
        more_films = parse_films_from_list(html_part, base_domain)
        
        added_count = 0
        for f in more_films:
            if f['title'] not in processed_titles:
                details = get_movie_details(f['url'])
                f.update(details)
                
                all_films.append(f)
                processed_titles.add(f['title'])
                added_count += 1
                time.sleep(0.2)
        
        if added_count == 0:
            print("Yeni film yok. Bitti.")
            break
            
        page += 1
        print(f"--- Sayfa {page} Tamamlandı. Toplam: {len(all_films)} ---")

    return all_films

def get_all_genres(films):
    all_genres = set()
    for film in films:
        for genre in film.get('genres', []):
            if genre and genre != "Tür Belirtilmemiş":
                all_genres.add(genre)
    return sorted(list(all_genres))

def create_html(films):
    films_json = json.dumps(films, ensure_ascii=False)
    all_genres = get_all_genres(films)
    genres_json = json.dumps(all_genres, ensure_ascii=False)
    
    html_template = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Film Arşivi</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 0; background-color: #344966; color: #fff; }}
        .header {{ position: fixed; top: 0; left: 0; right: 0; background-color: #2c3e50; padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; z-index: 1000; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }}
        h1 {{ margin: 0; color: #ecf0f1; font-size: 1.2em; }}
        .controls {{ display: flex; align-items: center; gap: 10px; }}
        
        #genreSelect {{ padding: 8px; border-radius: 5px; background-color: #496785; color: #fff; border: 1px solid #2c3e50; }}
        .search-container {{ position: relative; }}
        #searchInput {{ padding: 8px 30px 8px 10px; border-radius: 20px; border: none; background-color: #496785; color: #fff; width: 120px; transition: width 0.3s; }}
        #searchInput:focus {{ width: 200px; outline: none; }}
        
        .film-container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 15px; margin-top: 70px; padding: 20px; }}
        .film-card {{ position: relative; overflow: hidden; border-radius: 8px; background-color: #496785; box-shadow: 0 4px 8px rgba(0,0,0,0.3); transition: transform 0.2s; cursor: pointer; }}
        .film-card:hover {{ transform: translateY(-5px); }}
        .film-card img {{ width: 100%; display: block; aspect-ratio: 2 / 3; object-fit: cover; }}
        
        .film-overlay {{ position: absolute; bottom: 0; left: 0; right: 0; background: linear-gradient(to top, rgba(0,0,0,0.9), transparent); padding: 10px; opacity: 0; transition: opacity 0.3s; }}
        .film-card:hover .film-overlay {{ opacity: 1; }}
        .film-title {{ font-weight: bold; font-size: 0.9em; text-align: center; }}
        
        #loadMore {{ display: block; width: 200px; margin: 20px auto; padding: 12px; background-color: #f39c12; color: #fff; border: none; border-radius: 5px; cursor: pointer; }}
        
        /* Modal */
        .modal {{ display: none; position: fixed; z-index: 1001; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.8); backdrop-filter: blur(5px); }}
        .modal-content {{ background-color: #2c3e50; margin: 5% auto; padding: 25px; border-radius: 8px; width: 90%; max-width: 600px; position: relative; box-shadow: 0 5px 15px rgba(0,0,0,0.5); }}
        .close {{ position: absolute; top: 10px; right: 20px; font-size: 28px; cursor: pointer; color: #bdc3c7; }}
        .btn-watch {{ display: block; width: 100%; background-color: #e74c3c; color: #fff; text-align: center; padding: 12px; border-radius: 5px; text-decoration: none; margin-top: 20px; font-weight: bold; }}
        
        .meta-tag {{ display: inline-block; background: #344966; padding: 3px 8px; border-radius: 3px; font-size: 0.8em; margin-right: 5px; margin-bottom: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Arşiv ({len(films)})</h1>
        <div class="controls">
            <select id="genreSelect" onchange="filterFilms()">
                <option value="">Tüm Türler</option>
            </select>
            <div class="search-container">
                <input type="text" id="searchInput" placeholder="Ara..." oninput="filterFilms()">
            </div>
        </div>
    </div>
    
    <div class="film-container" id="filmContainer"></div>
    <button id="loadMore" onclick="loadMoreFilms()">Daha Fazla Göster</button>

    <!-- Detay Penceresi (Modal) -->
    <div id="filmModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h2 id="mTitle"></h2>
            <div id="mMeta" style="margin-bottom: 15px;"></div>
            <p id="mSummary" style="line-height: 1.6; color: #bdc3c7;"></p>
            <a id="mWatch" class="btn-watch" target="_blank">HEMEN İZLE</a>
        </div>
    </div>

    <script>
        const films = {films_json};
        const allGenres = {genres_json};
        let currentPage = 1;
        const filmsPerPage = 24;
        let currentList = films;

        // Türleri doldur
        const select = document.getElementById('genreSelect');
        allGenres.forEach(g => {{
            const opt = document.createElement('option');
            opt.value = g;
            opt.innerText = g;
            select.appendChild(opt);
        }});

        function createCard(film) {{
            const div = document.createElement('div');
            div.className = 'film-card';
            div.innerHTML = `
                <img src="${{film.image}}" loading="lazy" onerror="this.src='https://via.placeholder.com/200x300'">
                <div class="film-overlay">
                    <div class="film-title">${{film.title}}</div>
                </div>
            `;
            div.onclick = () => openModal(film);
            return div;
        }}

        function render() {{
            const container = document.getElementById('filmContainer');
            // Sadece ilk sayfada temizle, yükle deyince ekle
            if(currentPage === 1) container.innerHTML = '';
            
            const start = (currentPage - 1) * filmsPerPage;
            const end = start + filmsPerPage;
            const batch = currentList.slice(start, end);
            
            batch.forEach(f => container.appendChild(createCard(f)));
            
            document.getElementById('loadMore').style.display = end >= currentList.length ? 'none' : 'block';
        }}

        function loadMoreFilms() {{
            currentPage++;
            render();
        }}

        function filterFilms() {{
            const search = document.getElementById('searchInput').value.toLowerCase();
            const genre = document.getElementById('genreSelect').value;
            
            currentList = films.filter(f => {{
                return (f.title.toLowerCase().includes(search)) &&
                       (genre === "" || f.genres.includes(genre));
            }});
            
            currentPage = 1;
            render();
        }}

        function openModal(film) {{
            document.getElementById('mTitle').innerText = film.title;
            document.getElementById('mSummary').innerText = film.summary || "Özet yok.";
            
            // Meta bilgiler
            let metaHtml = `<span class="meta-tag">${{film.year}}</span>`;
            metaHtml += `<span class="meta-tag">IMDB: ${{film.imdb}}</span>`;
            metaHtml += `<span class="meta-tag">${{film.duration}}</span>`;
            if(film.genres) {{
                film.genres.forEach(g => metaHtml += `<span class="meta-tag" style="background:#e67e22">${{g}}</span>`);
            }}
            document.getElementById('mMeta').innerHTML = metaHtml;
            
            // Link
            document.getElementById('mWatch').href = film.videoUrl || film.url;
            
            document.getElementById('filmModal').style.display = 'block';
        }}

        function closeModal() {{
