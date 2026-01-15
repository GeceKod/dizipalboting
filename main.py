import cloudscraper
from bs4 import BeautifulSoup
import json
import os
import time
from urllib.parse import urlparse

# --- AYARLAR ---
BASE_URL = os.environ.get('SITE_URL', 'https://dizipal1225.com/filmler')
DATA_FILE = 'movies.json'
HTML_FILE = 'index.html'

# Siteyi yormamak için her sayfa isteği arası bekleme (saniye)
DELAY = 1 

def get_base_domain(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def parse_html_content(soup, base_domain):
    """Verilen HTML parçasındaki (Soup) filmleri ayıklar."""
    films = []
    # Genelde li etiketi içindedir
    elements = soup.find_all('li')
    
    # Eğer li bulamazsa div class="movie-item" dener
    if not elements:
        elements = soup.select('.movie-item') or soup.select('.item')

    for el in elements:
        try:
            # Data ID (Sonraki sayfayı çekmek için gerekli)
            # Genelde <a> etiketinin içinde data-id olur
            link_el = el.find('a')
            movie_id = link_el.get('data-id') if link_el else None
            
            # Başlık
            title_el = el.find('span', class_='title') or el.find('h2') or el.find('h3')
            title = title_el.text.strip() if title_el else "Isimsiz"
            
            # Resim
            img_el = el.find('img')
            image = img_el['src'] if img_el else ""
            
            # Link
            href = link_el['href'] if link_el else ""
            if href and not href.startswith('http'):
                href = base_domain + href
                
            # Türler, Yıl vb (Varsa)
            year_el = el.find('span', class_='year')
            year = year_el.text.strip() if year_el else "-"
            
            imdb_el = el.find('span', class_='imdb')
            imdb = imdb_el.text.strip() if imdb_el else "-"

            if title != "Isimsiz" and href:
                films.append({
                    "id": movie_id, # Sonraki sayfa için önemli
                    "title": title,
                    "image": image,
                    "url": href,
                    "year": year,
                    "imdb": imdb,
                    "videoUrl": href # Şimdilik siteye yönlendirsin
                })
        except Exception as e:
            continue
            
    return films

def get_all_films():
    scraper = cloudscraper.create_scraper(delay=10)
    base_domain = get_base_domain(BASE_URL)
    api_url = f"{base_domain}/api/load-movies"
    
    all_films = []
    processed_titles = set()
    
    print(f"Tarama Basliyor: {BASE_URL}")
    print("------------------------------------------------")

    # 1. ILK SAYFAYI CEK
    try:
        response = scraper.get(BASE_URL, timeout=30)
        if response.status_code != 200:
            print(f"Siteye girilemedi. Kod: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        new_films = parse_html_content(soup, base_domain)
        
        for f in new_films:
            if f['title'] not in processed_titles:
                all_films.append(f)
                processed_titles.add(f['title'])
        
        print(f"Sayfa 1 Tamamlandi. Toplam Film: {len(all_films)}")
        
    except Exception as e:
        print(f"Ilk sayfa hatasi: {e}")
        return []

    # 2. LOAD MORE DONGUSU (SONSUZ KAYDIRMA)
    page_count = 1
    
    while True:
        if not all_films:
            break
            
        # Son eklenen filmin ID'sini al (API buna göre sıradakileri verir)
        last_film = all_films[-1]
        last_id = last_film.get('id')
        
        if not last_id:
            print("Son film ID'si bulunamadi, dongu bitiyor.")
            break
            
        print(f"Siradaki sayfa isteniyor (Son ID: {last_id})...")
        
        try:
            # API'ye istek at
            payload = {
                'movie': last_id,
                'year': '',
                'tur': '',
                'siralama': ''
            }
            # Burasi kritik: API istegi post ile yapilir
            api_response = scraper.post(api_url, data=payload, timeout=20)
            
            if api_response.status_code != 200:
                print(f"API Hatasi: {api_response.status_code}")
                break
                
            try:
                data = api_response.json()
            except:
                print("API JSON dondurmedi, islem bitti.")
                break
                
            if not data.get('html'):
                print("Daha fazla film yok (HTML bos).")
                break
                
            # Gelen HTML parcasini işle
            soup = BeautifulSoup(data['html'], 'html.parser')
            more_films = parse_html_content(soup, base_domain)
            
            added_count = 0
            for f in more_films:
                if f['title'] not in processed_titles:
                    all_films.append(f)
                    processed_titles.add(f['title'])
                    added_count += 1
            
            page_count += 1
            print(f"Sayfa {page_count} eklendi. (+{added_count} film). Toplam: {len(all_films)}")
            
            if added_count == 0:
                print("Yeni film gelmedi, dongu bitiriliyor.")
                break
                
            time.sleep(DELAY) # Siteyi yormamak icin bekle
            
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
    <title>Dizipal Dev Arsiv</title>
    <style>
        body {{ background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin:0; padding:0; }}
        .header {{ background-color: #1f1f1f; padding: 20px; position: sticky; top: 0; z-index: 100; box-shadow: 0 2px 10px rgba(0,0,0,0.5); display: flex; justify-content: space-between; align-items: center; }}
        h1 {{ margin: 0; font-size: 1.5rem; color: #e50914; }}
        #search {{ padding: 10px; border-radius: 5px; border: none; width: 200px; background: #333; color: white; }}
        .stats {{ font-size: 0.9rem; color: #888; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 20px; padding: 20px; }}
        .card {{ background: #1f1f1f; border-radius: 8px; overflow: hidden; transition: transform 0.2s; position: relative; }}
        .card:hover {{ transform: scale(1.05); z-index: 10; box-shadow: 0 5px 15px rgba(0,0,0,0.5); }}
        .card img {{ width: 100%; height: 240px; object-fit: cover; }}
        .info {{ padding: 10px; }}
        .title {{ font-weight: bold; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 5px; }}
        .meta {{ font-size: 0.8rem; color: #aaa; display: flex; justify-content: space-between; }}
        .imdb {{ color: #f5c518; font-weight: bold; }}
        .btn {{ display: block; width: 100%; padding: 8px 0; background: #e50914; color: white; text-align: center; text-decoration: none; font-size: 0.9rem; margin-top: 10px; border-radius: 4px; }}
        .btn:hover {{ background: #b20710; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>Arsiv Botu</h1>
            <span class="stats" id="count">Toplam: 0 Film</span>
        </div>
        <input type="text" id="search" placeholder="Film Ara..." oninput="filterFilms()">
    </div>
    
    <div class="grid" id="grid"></div>

    <script>
        const films = {films_json};
        const grid = document.getElementById('grid');
        const countLabel = document.getElementById('count');

        function render(list) {{
            countLabel.innerText = `Toplam: ${{list.length}} Film`;
            // Performans için ilk 100 filmi goster, sonra scroll ettikce acilabilir ama basit tutalim
            // Hepsini basarsak tarayici kasabilir 3000 filmde.
            // Bu ornekte ilk 500'u gosterelim, arama yapinca hepsi icinde arar.
            
            const displayList = list.length > 500 && document.getElementById('search').value === '' ? list.slice(0, 500) : list;
            
            grid.innerHTML = displayList.map(f => `
                <div class="card">
                    <img src="${{f.image}}" loading="lazy" onerror="this.src='https://via.placeholder.com/160x240?text=Resim+Yok'">
                    <div class="info">
                        <div class="title" title="${{f.title.replace(/"/g, '&quot;')}}">${{f.title}}</div>
                        <div class="meta">
                            <span>${{f.year}}</span>
                            <span class="imdb">★ ${{f.imdb}}</span>
                        </div>
                        <a href="${{f.url}}" target="_blank" class="btn">Izle</a>
                    </div>
                </div>
            `).join('');
            
            if(list.length > 500 && document.getElementById('search').value === '') {{
                const moreMsg = document.createElement('div');
                moreMsg.style.gridColumn = "1 / -1";
                moreMsg.style.textAlign = "center";
                moreMsg.style.padding = "20px";
                moreMsg.innerHTML = "<p>Performans icin sadece son 500 film gosteriliyor. Aradığınız film icin yukaridan arama yapin.</p>";
                grid.appendChild(moreMsg);
            }}
        }}

        function filterFilms() {{
            const query = document.getElementById('search').value.toLowerCase();
            const filtered = films.filter(f => f.title.toLowerCase().includes(query));
            render(filtered);
        }}

        // Baslangic
        render(films);
    </script>
</body>
</html>"""
    
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html_template)
    
    # Verileri kaydet (Yedek)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(films, f, ensure_ascii=False)

if __name__ == "__main__":
    # Onceki verileri de yuklemek istersen load_existing eklenebilir ama
    # Temiz baslangic en sagliklisidir.
    films = get_all_films()
    
    if films:
        create_html(films)
        print(f"ISLEM TAMAM: {len(films)} film kaydedildi.")
    else:
        print("Hic film bulunamadi.")
