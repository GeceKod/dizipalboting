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

# Dizipal Kaynak Kodundan Alınan Sabit Kategoriler
FIXED_GENRES = [
    "Aile", "Aksiyon", "Animasyon", "Anime", "Belgesel", "Bilimkurgu", 
    "Biyografi", "Dram", "Editörün Seçtikleri", "Erotik", "Fantastik", 
    "Gerilim", "Gizem", "Komedi", "Korku", "Macera", "Mubi", "Müzik", 
    "Romantik", "Savaş", "Spor", "Suç", "Tarih", "Western", "Yerli",
    "Netflix", "Exxen", "BluTV", "Disney+", "Amazon", "TOD", "Gain"
]

def get_base_domain(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def get_soup(url):
    """Senin verdigin ornekteki basit baglanti fonksiyonu."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"Hata: {url} adresine erisilemiyor. Mesaj: {e}")
        return None

def get_video_link(url):
    """
    Filmin sayfasina girer ve iframe linkini alir.
    Senin ornek kodundaki fonksiyonun aynisi.
    """
    soup = get_soup(url)
    if not soup:
        return None
    iframe = soup.find('iframe', id='iframe')
    if iframe and 'src' in iframe.attrs:
        return iframe['src']
    # Iframe yoksa sayfa linkini dondur, hic yoktan iyidir
    return url

def get_film_info(film_element, base_domain):
    """
    Senin kodundaki ayiklama mantiginin AYNISI.
    Ozel class aramaz, elementin icine bakar.
    """
    try:
        title_element = film_element.find('span', class_='title')
        # Eger baslik yoksa bu bir film degildir, bos don.
        if not title_element: return None
        
        title = html.unescape(title_element.text.strip())
        
        image_element = film_element.find('img')
        image = ""
        if image_element:
            # Bazen data-src, bazen src kullanilir
            image = image_element.get('data-src') or image_element.get('src') or ""
            if image.startswith('//'): image = 'https:' + image
        
        url_element = film_element.find('a')
        url = ""
        if url_element:
            href = url_element['href']
            url = base_domain + href if not href.startswith('http') else href
        
        year_element = film_element.find('span', class_='year')
        year = html.unescape(year_element.text.strip()) if year_element else ""
        
        duration_element = film_element.find('span', class_='duration')
        duration = html.unescape(duration_element.text.strip()) if duration_element else ""
        
        imdb_element = film_element.find('span', class_='imdb')
        imdb = html.unescape(imdb_element.text.strip()) if imdb_element else ""
        
        genres_element = film_element.find('span', class_='genres_x')
        genres = []
        if genres_element:
            text = html.unescape(genres_element.text.strip())
            genres = text.split(', ') if text else []
        
        summary_element = film_element.find('span', class_='summary')
        summary = html.unescape(summary_element.text.strip()) if summary_element else ""
        
        # ID al (Load More icin gerekli)
        movie_id = None
        if url_element and 'data-id' in url_element.attrs:
            movie_id = url_element['data-id']

        return {
            'id': movie_id,
            'title': title,
            'image': image,
            'videoUrl': "", # Sonra doldurulacak
            'url': url,
            'year': year,
            'duration': duration,
            'imdb': imdb,
            'genres': genres,
            'summary': summary
        }
    except Exception:
        return None

def load_more_movies(api_url, last_movie_id):
    """API uzerinden daha fazla film yukler (Senin kodun aynisi)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Requested-With': 'XMLHttpRequest'
    }
    data = {
        'movie': last_movie_id,
        'year': '',
        'tur': '',
        'siralama': ''
    }
    try:
        response = requests.post(api_url, headers=headers, data=data, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"API Hatasi: {e}")
        return None

def get_films():
    films = []
    base_domain = get_base_domain(BASE_URL)
    api_url = f"{base_domain}/api/load-movies"
    
    print(f"Baslangic URL: {BASE_URL}")
    print("Yontem: Kaba Kuvvet (Butun <li> elementleri taranacak)")

    soup = get_soup(BASE_URL)
    if not soup:
        return films

    processed_film_titles = set()
    
    # Ilk Sayfa ve Sonsuz Dongu
    # Donguyu kirmamak icin `while True` kullanacagiz ama soup degisecek
    current_soup = soup
    page_count = 1
    
    while True:
        # Sayfadaki TUM li elementlerini bul (Generic Arama)
        film_elements = current_soup.find_all('li')
        
        if not film_elements:
            print("Film elementi bulunamadi. Dongu bitiyor.")
            break
            
        new_films_on_page = 0
        last_movie_id = None
        
        for element in film_elements:
            film_info = get_film_info(element, base_domain)
            
            if film_info and film_info['title'] not in processed_film_titles:
                # Video linkini al (Senin istegin uzerine her filmde iceri girip bakacak)
                # Bu islem yavastir ama istedigin budur.
                print(f">> Isleniyor: {film_info['title']}")
                video_link = get_video_link(film_info['url'])
                film_info['videoUrl'] = video_link
                
                films.append(film_info)
                processed_film_titles.add(film_info['title'])
                new_films_on_page += 1
                
                # Son filmin ID'sini kaydet (Sonraki sayfa icin)
                if film_info['id']:
                    last_movie_id = film_info['id']
                
                time.sleep(0.1) # Sunucuyu patlatmamak icin minik bekleme

        print(f"Sayfa {page_count} Bitti. Toplam Film: {len(films)}")

        # Eger bu sayfada hic yeni film bulamadiysak veya son ID yoksa bitir
        if new_films_on_page == 0 or not last_movie_id:
            print("Yeni film gelmedi veya ID yok. Bitti.")
            break

        # Sonraki sayfayi API'den iste
        print(f"Daha fazla film yukleniyor (Son ID: {last_movie_id})...")
        more_data = load_more_movies(api_url, last_movie_id)
        
        if more_data and more_data.get('html'):
            current_soup = BeautifulSoup(more_data['html'], 'html.parser')
            page_count += 1
        else:
            print("Daha fazla veri gelmedi.")
            break
            
        # GUVEVNLI MOD: GitHub Actions suresi dolmasin diye 1000 filmde duralim mi?
        # Istersen bu if blogunu silebilirsin.
        if len(films) >= 3000:
            print("Guvenlik limiti: 3000 film. Durduruluyor.")
            break

    return films

def get_all_genres(films):
    # Sabit liste + Dinamik liste
    all_genres = set(FIXED_GENRES)
    for film in films:
        for genre in film.get('genres', []):
            if genre and genre != "Tür Belirtilmemiş":
                all_genres.add(genre)
    return sorted(list(all_genres))

def create_html(films):
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
    data = get_films() # get_all_films degil, cunku adini degistirdik
    if data:
        create_html(data)
