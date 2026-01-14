import requests
from bs4 import BeautifulSoup
import time
import json
import html
import os
from urllib.parse import urlparse

# --- AYARLAR ---
# Site adresi değiştiğinde GitHub Secret'tan veya buradan güncelleyebilirsin.
BASE_URL = os.environ.get('SITE_URL', 'https://dizipal1225.com/filmler')
DATA_FILE = 'movies.json'
HTML_FILE = 'index.html'

def get_soup(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"Hata: {url} adresine erişilemiyor. {e}")
        return None

def get_film_info(film_element, base_domain):
    try:
        title_element = film_element.find('span', class_='title')
        title = html.unescape(title_element.text.strip()) if title_element else "Baslik Bulunamadi"
        
        image_element = film_element.find('img')
        image = image_element['src'] if image_element else ""
        
        url_element = film_element.find('a')
        url = base_domain + url_element['href'] if url_element else ""
        
        year_element = film_element.find('span', class_='year')
        year = html.unescape(year_element.text.strip()) if year_element else "Unknown"
        
        duration_element = film_element.find('span', class_='duration')
        duration = html.unescape(duration_element.text.strip()) if duration_element else "-"
        
        imdb_element = film_element.find('span', class_='imdb')
        imdb = html.unescape(imdb_element.text.strip()) if imdb_element else "-"
        
        genres_element = film_element.find('span', class_='genres_x')
        genres = html.unescape(genres_element.text.strip()).split(', ') if genres_element else []
        
        summary_element = film_element.find('span', class_='summary')
        summary = html.unescape(summary_element.text.strip()) if summary_element else ""
        
        return {
            'title': title,
            'image': image,
            'videoUrl': "", # Video linki dinamik olarak sonra alınır veya iframe linki
            'url': url,
            'year': year,
            'duration': duration,
            'imdb': imdb,
            'genres': genres,
            'summary': summary
        }
    except Exception:
        return None

def get_video_link(url):
    soup = get_soup(url)
    if not soup: return None
    iframe = soup.find('iframe', id='iframe')
    if iframe and 'src' in iframe.attrs:
        return iframe['src']
    return None

def load_existing_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_new_films():
    """Sadece ilk sayfaları tarayıp yeni filmleri alır."""
    parsed_uri = urlparse(BASE_URL)
    base_domain = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
    
    print(f"Tarama başlıyor: {BASE_URL}")
    soup = get_soup(BASE_URL)
    if not soup: return []

    new_films = []
    
    # Sadece ana sayfadaki (veya ilk yüklenen) filmleri çekelim
    # Hepsini çekmek istersek while döngüsü gerekir ama botu hızlandırmak için
    # ve sadece "yeni eklenenleri" istediğin için ilk sayfa yeterli olabilir.
    # Daha derin tarama için buraya 'load more' mantığı eklenebilir.
    
    film_elements = soup.find_all('li', class_='')
    print(f"Sayfada {len(film_elements)} film bulundu.")

    for element in film_elements:
        film_info = get_film_info(element, base_domain)
        if film_info:
            # Video linkini al
            video_link = get_video_link(film_info['url'])
            if video_link:
                film_info['videoUrl'] = video_link
                new_films.append(film_info)
                print(f"Bulundu: {film_info['title']}")
            time.sleep(0.5) # Sunucuyu yormamak için kısa bekleme
            
    return new_films

def merge_films(existing, new_found):
    """Mevcut filmlerle yenileri birleştirir, tekrarları önler."""
    existing_titles = {f['title'] for f in existing}
    added_count = 0
    
    # Yeni bulunanları listenin başına ekleyelim (En yeniler üstte olsun)
    for film in reversed(new_found):
        if film['title'] not in existing_titles:
            existing.insert(0, film)
            existing_titles.add(film['title'])
            added_count += 1
            print(f"Yeni Eklendi: {film['title']}")
            
    return existing, added_count

def create_html(films):
    # Türleri topla
    all_genres = set()
    for film in films:
        for genre in film.get('genres', []):
            if genre and genre != "Tür Belirtilmemiş":
                all_genres.add(genre)
    
    films_json = json.dumps(films, ensure_ascii=False)
    genres_json = json.dumps(sorted(list(all_genres)), ensure_ascii=False)
    
    # Senin orijinal HTML şablonun (değişmedi)
    html_template = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dizipal Arşiv</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 0; background-color: #344966; color: #fff; }}
        .header {{ position: fixed; top: 0; left: 0; right: 0; background-color: #2c3e50; padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; z-index: 1000; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }}
        h1 {{ margin: 0; color: #ecf0f1; font-size: 1.5em; }}
        .controls {{ display: flex; align-items: center; gap: 10px; }}
        #searchInput {{ padding: 8px; border-radius: 5px; border: none; }}
        #genreSelect {{ padding: 8px; border-radius: 5px; }}
        .film-container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 15px; margin-top: 80px; padding: 20px; }}
        .film-card {{ position: relative; overflow: hidden; border-radius: 8px; background-color: #496785; box-shadow: 0 4px 8px rgba(0,0,0,0.3); transition: transform 0.2s; cursor: pointer; }}
        .film-card:hover {{ transform: translateY(-5px); }}
        .film-card img {{ width: 100%; display: block; aspect-ratio: 2 / 3; object-fit: cover; }}
        .film-title {{ padding: 10px; font-weight: bold; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .modal {{ display: none; position: fixed; z-index: 1001; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.8); }}
        .modal-content {{ background-color: #2c3e50; margin: 5% auto; padding: 20px; width: 90%; max-width: 700px; border-radius: 10px; position: relative; }}
        .close {{ position: absolute; right: 15px; top: 10px; font-size: 30px; cursor: pointer; }}
        .btn-watch {{ display: inline-block; padding: 10px 20px; background: #3498db; color: white; text-decoration: none; border-radius: 5px; margin-top: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Film Arşivi ({len(films)})</h1>
        <div class="controls">
            <select id="genreSelect" onchange="filterFilms()"><option value="">Tüm Türler</option></select>
            <input type="text" id="searchInput" placeholder="Ara..." oninput="filterFilms()">
        </div>
    </div>
    <div class="film-container" id="filmContainer"></div>

    <div id="filmModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h2 id="mTitle"></h2>
            <p id="mInfo"></p>
            <p id="mSummary"></p>
            <a id="mLink" class="btn-watch" target="_blank">İzle</a>
        </div>
    </div>

    <script>
        const films = {films_json};
        const genres = {genres_json};
        
        // Populate Genres
        const genreSelect = document.getElementById('genreSelect');
        genres.forEach(g => {{
            const opt = document.createElement('option');
            opt.value = g;
            opt.innerText = g;
            genreSelect.appendChild(opt);
        }});

        function render(list) {{
            const container = document.getElementById('filmContainer');
            container.innerHTML = list.slice(0, 100).map(f => `
                <div class="film-card" onclick='showModal("${{f.title.replace(/'/g, "\\'") }}")'>
                    <img src="${{f.image}}" loading="lazy">
                    <div class="film-title">${{f.title}}</div>
                </div>
            `).join('');
            // Not: Performans için sadece ilk 100 gösteriliyor, arama yapıldıkça diğerleri gelir.
            if(document.getElementById('searchInput').value) {{
                 container.innerHTML = list.map(f => `
                <div class="film-card" onclick='showModal("${{f.title.replace(/'/g, "\\'") }}")'>
                    <img src="${{f.image}}" loading="lazy">
                    <div class="film-title">${{f.title}}</div>
                </div>
            `).join('');
            }}
        }}

        function filterFilms() {{
            const s = document.getElementById('searchInput').value.toLowerCase();
            const g = document.getElementById('genreSelect').value;
            const filtered = films.filter(f => {{
                return (f.title.toLowerCase().includes(s) || f.genres.join(',').toLowerCase().includes(s)) &&
                       (g === "" || f.genres.includes(g));
            }});
            render(filtered);
        }}

        function showModal(title) {{
            const f = films.find(x => x.title === title);
            if(f) {{
                document.getElementById('mTitle').innerText = f.title;
                document.getElementById('mInfo').innerText = `${{f.year}} | ${{f.imdb}} | ${{f.duration}}`;
                document.getElementById('mSummary').innerText = f.summary;
                document.getElementById('mLink').href = f.videoUrl;
                document.getElementById('filmModal').style.display = 'block';
            }}
        }}

        function closeModal() {{ document.getElementById('filmModal').style.display = 'none'; }}
        window.onclick = function(e) {{ if(e.target == document.getElementById('filmModal')) closeModal(); }}

        render(films);
    </script>
</body>
</html>
    """
    
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html_template)
    print(f"HTML güncellendi: {HTML_FILE}")

def main():
    # 1. Mevcut veriyi yükle
    existing_data = load_existing_data()
    print(f"Mevcut film sayısı: {len(existing_data)}")
    
    # 2. Yeni verileri siteden çek
    new_found_data = get_new_films()
    
    # 3. Birleştir
    merged_data, added_count = merge_films(existing_data, new_found_data)
    
    # 4. JSON olarak kaydet
    if added_count > 0 or not os.path.exists(HTML_FILE):
        save_data(merged_data)
        create_html(merged_data)
        print(f"İşlem tamam. {added_count} yeni film eklendi.")
    else:
        print("Yeni film bulunamadı, dosya güncellenmedi.")

if __name__ == "__main__":
    main()
