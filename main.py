import requests
from bs4 import BeautifulSoup
import json
import os
import time
from urllib.parse import urlparse

# --- AYARLAR ---
BASE_URL = os.environ.get('SITE_URL', 'https://dizipal1225.com/filmler')
DATA_FILE = 'movies.json'
HTML_FILE = 'index.html'

def get_base_domain(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def get_soup(url, method='GET', data=None):
    """Standart Requests ile siteye baglanir."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': BASE_URL,
        'X-Requested-With': 'XMLHttpRequest'
    }
    try:
        if method == 'POST':
            response = requests.post(url, headers=headers, data=data, timeout=15)
        else:
            response = requests.get(url, headers=headers, timeout=15)
            
        response.raise_for_status()
        
        # Eger API cevabi ise JSON dondurmeye calis
        if method == 'POST':
            try:
                return response.json()
            except:
                return None
                
        return BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"Baglanti Hatasi ({url}): {e}")
        return None

def parse_films(soup, base_domain):
    """HTML icinden film bilgilerini ayiklar."""
    films = []
    # Liste elementlerini bul
    elements = soup.find_all('li')
    
    # Alternatif seciciler
    if not elements:
        elements = soup.select('.movie-item') or soup.select('.item')

    for el in elements:
        try:
            # Baglanti ve ID bulma
            link_el = el.find('a')
            if not link_el: continue
            
            movie_id = link_el.get('data-id') # API icin gerekli ID
            href = link_el['href']
            
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
            image = img_el['src'] if img_el else ""

            # Diger Bilgiler
            imdb_el = el.find('span', class_='imdb')
            imdb = imdb_el.text.strip() if imdb_el else "-"
            
            year_el = el.find('span', class_='year')
            year = year_el.text.strip() if year_el else ""

            # Listeye Ekle
            if title != "Isimsiz":
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
    base_domain = get_base_domain(BASE_URL)
    api_url = f"{base_domain}/api/load-movies"
    
    all_films = []
    processed_titles = set()
    
    print(f"Tarama Baslatiliyor: {BASE_URL}")
    print("------------------------------------------------")

    # 1. SAYFA (Ana Sayfa)
    soup = get_soup(BASE_URL)
    if not soup:
        print("Ana sayfaya erisilemedi. URL'yi kontrol et.")
        return []

    new_films = parse_films(soup, base_domain)
    for f in new_films:
        if f['title'] not in processed_titles:
            all_films.append(f)
            processed_titles.add(f['title'])
            
    print(f"Sayfa 1 OK. Toplam: {len(all_films)} film.")

    # 2. API DONGUSU (Sonsuz Kaydirmayi Taklit Et)
    page = 1
    while True:
        if not all_films: break
        
        # Listenin sonundaki filmin ID'sini al
        last_film = all_films[-1]
        last_id = last_film.get('id')
        
        if not last_id:
            print("Son film ID'si yok, dongu bitti.")
            break
            
        print(f"Siradaki yukleniyor... (Ref ID: {last_id})")
        
        # API Istegi
        payload = {'movie': last_id, 'year': '', 'tur': '', 'siralama': ''}
        data = get_soup(api_url, method='POST', data=payload)
        
        if not data or not data.get('html'):
            print("Daha fazla veri gelmedi. Islem tamam.")
            break
            
        # Gelen HTML'i işle
        html_part = BeautifulSoup(data['html'], 'html.parser')
        more_films = parse_films(html_part, base_domain)
        
        added_count = 0
        for f in more_films:
            if f['title'] not in processed_titles:
                all_films.append(f)
                processed_titles.add(f['title'])
                added_count += 1
        
        if added_count == 0:
            print("Yeni film bulunamadi (Tekrar). Dongu bitiyor.")
            break
            
        page += 1
        print(f"Sayfa {page} Eklendi (+{added_count}). Toplam: {len(all_films)}")
        
        time.sleep(1) # Sunucuyu bogmamak icin bekleme

    return all_films

def create_html(films):
    films_json = json.dumps(films, ensure_ascii=False)
    
    html_template = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Film Arsivi</title>
    <style>
        body {{ background-color: #344966; color: #fff; font-family: sans-serif; margin: 0; padding: 0; }}
        .header {{ background: #2c3e50; padding: 15px; position: sticky; top:0; z-index:999; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 5px rgba(0,0,0,0.3); }}
        h1 {{ margin: 0; font-size: 1.2rem; }}
        #searchInput {{ padding: 8px; border-radius: 5px; border: none; width: 150px; transition: width 0.3s; }}
        #searchInput:focus {{ width: 250px; outline: none; }}
        
        .container {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 15px; padding: 20px; }}
        
        .card {{ background: #496785; border-radius: 8px; overflow: hidden; position: relative; transition: transform 0.2s; }}
        .card:hover {{ transform: translateY(-5px); }}
        .card img {{ width: 100%; aspect-ratio: 2/3; object-fit: cover; display: block; }}
        
        .info {{ padding: 10px; }}
        .title {{ font-weight: bold; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .meta {{ font-size: 0.8rem; color: #ccc; display: flex; justify-content: space-between; margin-top: 5px; }}
        .imdb {{ background: #f1c40f; color: #000; padding: 2px 4px; border-radius: 3px; font-weight: bold; }}
        
        .btn-watch {{ display: block; background: #3498db; color: white; text-align: center; text-decoration: none; padding: 8px; margin-top: 10px; border-radius: 4px; font-size: 0.9rem; }}
        .btn-watch:hover {{ background: #2980b9; }}
        
        #loadMoreBtn {{ display: block; margin: 30px auto; padding: 12px 30px; background: #e67e22; color: white; border: none; border-radius: 5px; font-size: 1rem; cursor: pointer; }}
        #loadMoreBtn:hover {{ background: #d35400; }}
        #totalCount {{ font-size: 0.8rem; color: #bdc3c7; }}
    </style>
</head>
<body>

<div class="header">
    <div>
        <h1>Film Arsivi</h1>
        <span id="totalCount">Yukleniyor...</span>
    </div>
    <input type="text" id="searchInput" placeholder="Film Ara..." oninput="handleSearch()">
</div>

<div class="container" id="filmContainer"></div>
<button id="loadMoreBtn" onclick="loadMore()">Daha Fazla Yukle</button>

<script>
    // Python'dan gelen tum veri burada
    const allFilms = {films_json};
    
    let displayedCount = 0;
    const itemsPerPage = 24; // Her tiklamada kac film acilsin
    let currentList = allFilms; // Arama yapilinca bu liste degisir

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
        // Sayfa basina belirlenen miktar kadarini ekle
        const nextBatch = currentList.slice(displayedCount, displayedCount + itemsPerPage);
        
        nextBatch.forEach(film => {{
            container.appendChild(createCard(film));
        }});

        displayedCount += nextBatch.length;
        
        // Buton kontrolu
        if (displayedCount >= currentList.length) {{
            loadBtn.style.display = 'none';
        }} else {{
            loadBtn.style.display = 'block';
        }}
        
        countLabel.innerText = `Toplam: ${{allFilms.length}} | Gosterilen: ${{displayedCount}}`;
    }}

    function loadMore() {{
        render();
    }}

    function handleSearch() {{
        const query = document.getElementById('searchInput').value.toLowerCase();
        container.innerHTML = ''; // Listeyi temizle
        displayedCount = 0; // Sayaci sifirla
        
        if (query.length > 0) {{
            currentList = allFilms.filter(f => f.title.toLowerCase().includes(query));
        }} else {{
            currentList = allFilms;
        }}
        
        render(); // Yeniden baslat
    }}

    // Baslangic
    render();
</script>

</body>
</html>"""
    
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html_template)
    
    # JSON Yedekle
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(films, f, ensure_ascii=False)

if __name__ == "__main__":
    data = get_all_films()
    if data:
        create_html(data)
    else:
        # Hata olsa bile bos HTML olustur ki 404 vermesin
        with open(HTML_FILE, 'w', encoding='utf-8') as f:
            f.write("<h1>Siteye baglanirken hata olustu. Loglari kontrol edin.</h1>")
