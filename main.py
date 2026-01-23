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
    """Siteye baglanir (Requests ile)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Referer': BASE_URL,
        'X-Requested-With': 'XMLHttpRequest'
    }
    try:
        if method == 'POST':
            response = requests.post(url, headers=headers, data=data, timeout=20)
        else:
            response = requests.get(url, headers=headers, timeout=20)
            
        response.raise_for_status()
        
        if method == 'POST':
            try:
                return response.json()
            except:
                return None
        return BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"Hata ({url}): {e}")
        return None

def get_movie_details(movie_url):
    """
    Filmin içine girer; 
    1. Gerçek kategorileri (Türleri) oradan öğrenir.
    2. Video linkini alır.
    3. Özeti alır.
    """
    info = {
        'videoUrl': movie_url,
        'summary': 'Özet yok.',
        'genres': [],
        'duration': '',
        'imdb': '',
        'year': ''
    }
    
    soup = get_soup(movie_url)
    if not soup:
        return info

    try:
        # 1. Video Linki
        iframe = soup.find('iframe', id='iframe')
        if iframe and 'src' in iframe.attrs:
            info['videoUrl'] = iframe['src']
            
        # 2. Özet
        summary_el = soup.select_one('.ozet-text') or soup.select_one('.summary') or soup.find('article')
        if summary_el:
            info['summary'] = html.unescape(summary_el.text.strip())
            
        # 3. Türler (Otomatik Algılama)
        # Sitedeki 'tur' veya 'genres' etiketlerini arar
        genre_links = soup.select('.tur a') or soup.select('.genres a') or soup.select('.genre a')
        if genre_links:
            info['genres'] = [html.unescape(g.text.strip()) for g in genre_links]
            
        # 4. Süre
        duration_el = soup.select_one('.sure') or soup.select_one('.duration')
        if duration_el:
            info['duration'] = html.unescape(duration_el.text.strip())
            
        # 5. IMDB ve Yıl (Detay sayfasında daha kesin olabilir)
        imdb_el = soup.select_one('.imdb')
        if imdb_el: info['imdb'] = imdb_el.text.strip()
        
        year_el = soup.select_one('.vizyon-tarihi') or soup.select_one('.year')
        if year_el: info['year'] = year_el.text.strip()

    except Exception as e:
        print(f"Detay hatasi: {e}")
        
    return info

def parse_films_from_list(soup, base_domain):
    """Listeden temel linkleri toplar."""
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
            
            # Resim
            img_el = el.find('img')
            image = img_el.get('data-src') or img_el.get('src') or ""

            if title != "İsimsiz" and "dizipal" in full_url:
                films.append({
                    "id": movie_id,
                    "title": html.unescape(title),
                    "image": image,
                    "url": full_url
                })
        except:
            continue
    return films

def get_all_films():
    base_domain = get_base_domain(BASE_URL)
    api_url = f"{base_domain}/api/load-movies"
    
    all_films = []
    processed_titles = set()
    
    print(f"TAM TARAMA BAŞLIYOR: {BASE_URL}")
    print("NOT: Bütün filmler çekileceği için bu işlem uzun sürecektir.")
    
    # --- 1. SAYFA ---
    soup = get_soup(BASE_URL)
    if not soup:
        print("Siteye erişilemedi.")
        return []

    new_films = parse_films_from_list(soup, base_domain)
    
    for f in new_films:
        if f['title'] not in processed_titles:
            print(f">> İnceleniyor: {f['title']}")
            details = get_movie_details(f['url'])
            f.update(details) # Türler ve diğer detaylar burada eklenir
            
            all_films.append(f)
            processed_titles.add(f['title'])
            time.sleep(0.1) # Hızlı tarama
            
    print(f"Sayfa 1 Bitti. ({len(all_films)} Film)")

    # --- 2. DÖNGÜ (SONSUZA KADAR) ---
    page = 1
    # Limit yok, film bitene kadar gider.
    # Güvenlik için 5000 sayfa koydum, 5000 sayfa = 100.000 film demektir, yani sonsuz gibi.
    MAX_PAGES = 5000 
    
    while page < MAX_PAGES:
        if not all_films: break
        
        last_film = all_films[-1]
        last_id = last_film.get('id')
        
        if not last_id:
            print("Son film ID'si yok, döngü bitti.")
            break
            
        print(f"Sıradaki sayfa isteniyor... (Ref ID: {last_id})")
        
        payload = {'movie': last_id, 'year': '', 'tur': '', 'siralama': ''}
        data = get_soup(api_url, method='POST', data=payload)
        
        if not data or not data.get('html'):
            print("Daha fazla film gelmedi. TARAMA TAMAMLANDI.")
            break
            
        html_part = BeautifulSoup(data['html'], 'html.parser')
        more_films = parse_films_from_list(html_part, base_domain)
        
        added_count = 0
        for f in more_films:
            if f['title'] not in processed_titles:
                # Detaylara girip asıl türleri öğren
                details = get_movie_details(f['url'])
                f.update(details)
                
                all_films.append(f)
                processed_titles.add(f['title'])
                added_count += 1
                time.sleep(0.1)
        
        if added_count == 0:
            print("Yeni film bulunamadı. Bitti.")
            break
            
        page += 1
        print(f"--- Sayfa {page} Tamamlandı. Toplam: {len(all_films)} Film ---")

    return all_films

def get_all_genres(films):
    """
    Tüm filmleri tarar ve sitede ne kadar kategori varsa hepsini toplar.
    Elle yazma yok, tamamen dinamik.
    """
    all_genres = set()
    for film in films:
        for genre in film.get('genres', []):
            if genre and len(genre) > 1 and genre != "Tür Belirtilmemiş":
                all_genres.add(genre)
    return sorted(list(all_genres))

def create_html(films):
    # Türleri otomatik çıkar
    all_genres = get_all_genres(films)
    
    films_json = json.dumps(films, ensure_ascii=False)
    genres_json = json.dumps(all_genres, ensure_ascii=False)
    
    html_template = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dizipal Arşiv</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; margin: 0; padding: 0; background-color: #344966; color: #fff; }}
        .header {{ position: fixed; top: 0; left: 0; right: 0; background-color: #2c3e50; padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; z-index: 1000; box-shadow: 0 2px 10px rgba(0,0,0,0.3); }}
        h1 {{ margin: 0; font-size: 1.2em; }}
        .controls {{ display: flex; gap: 10px; }}
        #genreSelect, #searchInput {{ padding: 10px; border-radius: 5px; border: none; background: #496785; color: white; }}
        
        .film-container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 15px; margin-top: 70px; padding: 20px; }}
        .film-card {{ border-radius: 8px; background: #496785; overflow: hidden; cursor: pointer; transition: transform 0.2s; position: relative; }}
        .film-card:hover {{ transform: translateY(-5px); z-index: 10; }}
        .film-card img {{ width: 100%; aspect-ratio: 2/3; object-fit: cover; display: block; }}
        
        .film-overlay {{ position: absolute; bottom: 0; left: 0; right: 0; background: linear-gradient(to top, rgba(0,0,0,0.9), transparent); padding: 10px; }}
        .film-title {{ text-align: center; font-size: 0.85em; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        
        /* Modal */
        .modal {{ display: none; position: fixed; z-index: 1001; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); backdrop-filter: blur(5px); }}
        .modal-content {{ background: #2c3e50; margin: 5% auto; padding: 25px; width: 90%; max-width: 500px; border-radius: 12px; position: relative; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
        .close {{ position: absolute; top: 15px; right: 20px; font-size: 30px; cursor: pointer; color: #fff; }}
        
        .btn-watch {{ display: block; width: 100%; background-color: #e74c3c; color: white; text-align: center; padding: 15px; border-radius: 8px; text-decoration: none; margin-top: 20px; font-weight: bold; font-size: 1.1em; transition: background 0.3s; }}
        .btn-watch:hover {{ background-color: #c0392b; }}
        
        .meta-tag {{ display: inline-block; background: #344966; padding: 5px 10px; border-radius: 15px; font-size: 0.8em; margin: 5px 5px 5px 0; border: 1px solid #4a6fa5; }}
        .genre-tag {{ background: #e67e22; border: 1px solid #d35400; }}
        
        #loadMore {{ display: block; margin: 30px auto; padding: 15px 40px; background: #f39c12; border: none; border-radius: 8px; color: white; cursor: pointer; font-size: 1em; font-weight: bold; }}
        #loadMore:hover {{ background: #e67e22; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Arşiv ({len(films)})</h1>
        <div class="controls">
            <select id="genreSelect" onchange="filterFilms()"><option value="">Tüm Türler</option></select>
            <input type="text" id="searchInput" placeholder="Film Ara..." oninput="filterFilms()">
        </div>
    </div>
    
    <div class="film-container" id="filmContainer"></div>
    <button id="loadMore" onclick="loadMoreFilms()">Daha Fazla Göster</button>

    <!-- Detay Penceresi -->
    <div id="filmModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h2 id="mTitle" style="margin-top:0;"></h2>
            <div id="mMeta" style="margin-bottom:15px;"></div>
            <p id="mSummary" style="color: #bdc3c7; line-height: 1.6; font-size: 0.95em; max-height: 200px; overflow-y: auto;"></p>
            <a id="mWatch" class="btn-watch" target="_blank">🎬 HEMEN İZLE</a>
        </div>
    </div>

    <script>
        const films = {films_json};
        const allGenres = {genres_json};
        let currentPage = 1;
        const perPage = 30;
        let list = films;

        // Türleri Dinamik Doldur
        const sel = document.getElementById('genreSelect');
        allGenres.forEach(g => {{
            const opt = document.createElement('option');
            opt.value = g; opt.innerText = g; sel.appendChild(opt);
        }});

        function createCard(f) {{
            const d = document.createElement('div');
            d.className = 'film-card';
            d.innerHTML = `
                <img src="${{f.image}}" loading="lazy" onerror="this.src='https://via.placeholder.com/200x300?text=Resim+Yok'">
                <div class="film-overlay">
                    <div class="film-title">${{f.title}}</div>
                </div>`;
            d.onclick = () => openModal(f);
            return d;
        }}

        function render() {{
            const c = document.getElementById('filmContainer');
            if(currentPage===1) c.innerHTML='';
            
            const start = (currentPage-1)*perPage;
            const end = start+perPage;
            const batch = list.slice(start, end);
            
            batch.forEach(f => c.appendChild(createCard(f)));
            document.getElementById('loadMore').style.display = end>=list.length ? 'none' : 'block';
        }}

        function loadMoreFilms() {{ currentPage++; render(); }}

        function filterFilms() {{
            const s = document.getElementById('searchInput').value.toLowerCase();
            const g = document.getElementById('genreSelect').value;
            
            list = films.filter(f => {{
                // Film genres bir liste oldugu icin includes ile bakariz
                const hasGenre = g === "" || (f.genres && f.genres.includes(g));
                const matchesSearch = f.title.toLowerCase().includes(s);
                return hasGenre && matchesSearch;
            }});
            
            currentPage=1; render();
        }}

        function openModal(f) {{
            document.getElementById('mTitle').innerText = f.title;
            document.getElementById('mSummary').innerText = f.summary || "Özet bilgisi bulunamadı.";
            
            let h = '';
            if(f.year) h += `<span class="meta-tag">${{f.year}}</span>`;
            if(f.imdb) h += `<span class="meta-tag">IMDB: ${{f.imdb}}</span>`;
            if(f.duration) h += `<span class="meta-tag">${{f.duration}}</span>`;
            
            if(f.genres && f.genres.length > 0) {{
                f.genres.forEach(g => h+=`<span class="meta-tag genre-tag">${{g}}</span>`);
            }}
            
            document.getElementById('mMeta').innerHTML = h;
            document.getElementById('mWatch').href = f.videoUrl || f.url;
            document.getElementById('filmModal').style.display = 'block';
        }}

        function closeModal() {{ document.getElementById('filmModal').style.display='none'; }}
        window.onclick = (e) => {{ if(e.target == document.getElementById('filmModal')) closeModal(); }}
        
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
