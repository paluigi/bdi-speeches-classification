import time
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, urljoin
import requests
from bs4 import BeautifulSoup
from tinydb import TinyDB

# Configuration
DB_PATH = 'banca_ditalia_speeches.json'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
}

db = TinyDB(DB_PATH)

def build_pagination_url(base_url, page_number):
    """
    Safely injects or updates the ?page=X query parameter on a URL.
    """
    url_parts = list(urlparse(base_url))
    query = parse_qs(url_parts[4])
    query['page'] = [str(page_number)]
    url_parts[4] = urlencode(query, doseq=True)
    return urlunparse(url_parts)


def extract_catalogue_items(session, catalogue_url):
    """
    Parses the catalogue page to pull out speech items (links, authors, locations)
    and checks if a valid 'Next' page button exists in the pagination container.
    """
    items = []
    has_next_page = False
    
    try:
        response = session.get(catalogue_url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"[Warning] Failed to fetch catalogue index: {catalogue_url} ({response.status_code})")
            return items, has_next_page

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Parse speech items out of the search results block
        results_div = soup.find('div', id='search-results')
        if results_div:
            for li in results_div.find_all('li'):
                title_anchor = li.find('a', class_='bdi-result-title')
                if title_anchor and title_anchor.get('href'):
                    speech_url = urljoin(catalogue_url, title_anchor['href']).split('?')[0]
                    
                    # Extract Author
                    author_div = li.find('div', class_='bdi-author')
                    author = author_div.get_text(strip=True) if author_div else ""
                    if author.lower().startswith("by "):
                        author = author[3:].strip()
                        
                    # Extract Location
                    location_div = li.find('div', class_='bdi-location')
                    location = location_div.get_text(strip=True) if location_div else ""
                    
                    items.append({
                        'url': speech_url,
                        'scraped_author': author,
                        'scraped_location': location
                    })
        
        # Check pagination loop boundaries using the bdi-pagination-container class
        pagination_container = soup.find(class_='bdi-pagination-container')
        if pagination_container:
            next_li = pagination_container.find('li', class_='li-next')
            if next_li and next_li.find('a') and 'disabled' not in next_li.get('class', []):
                has_next_page = True
                
    except Exception as e:
        print(f"[Error] Parsing catalogue from {catalogue_url}: {e}")
        
    return items, has_next_page


def extract_speech_data(session, speech_url):
    """
    Navigates to an individual speech page, grabs structural HTML blocks within 
    the article wrapper, and catalogs accessible properties of inline images.
    """
    try:
        response = session.get(speech_url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"[Warning] Failed to fetch individual page: {speech_url} ({response.status_code})")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Target the semantic article block requested
        article = soup.find('article', class_='pbw-typography')
        if not article:
            print(f"[Warning] <article class='pbw-typography'> not found on: {speech_url}. Trying general fallback.")
            article = soup.find('main') or soup.find('article') or soup.find('div', class_='bdi-typography')
            
        if not article:
            return None

        # 1. Preserve entire structural inner-HTML hierarchy
        preserved_html = article.decode_contents()

        return {
            "html_content": preserved_html,
        }

    except Exception as e:
        print(f"[Error] Processing data tracking from {speech_url}: {e}")
        return None


def run_scraper(catalogue_sources):
    """
    Orchestrates sequential crawling steps matching parent seed targets.
    """
    with requests.Session() as session:
        for source in catalogue_sources:
            base_url = source.get('url')
            metadata = {k: v for k, v in source.items() if k != 'url'}
            
            print(f"\n⚡ Starting crawling sequence for path: {base_url}")
            page_idx = 1
            
            while True:
                target_url = build_pagination_url(base_url, page_idx)
                print(f"Scanning catalogue index page {page_idx}: {target_url}")
                
                speech_items, next_page_available = extract_catalogue_items(session, target_url)
                
                if not speech_items:
                    print("↳ Loop broken: Empty array payload isolated.")
                    break
                
                print(f"↳ Identified {len(speech_items)} item records.")
                
                for item in speech_items:
                    url = item['url']
                    print(f"  → Processing asset details: {url}")
                    
                    speech_payload = extract_speech_data(session, url)
                    
                    if speech_payload:
                        # Construct final TinyDB schema record tracking raw HTML blocks and figures
                        record = {
                            "link": url,
                            "html_content": speech_payload["html_content"],
                            "speaker": item['scraped_author'],
                            "location": item['scraped_location'],
                            **metadata
                        }
                        db.insert(record)
                    
                    time.sleep(1.0)  # Rate limiting delay
                
                if not next_page_available:
                    print("↳ Terminating index crawl: reached final pagination boundary.")
                    break
                    
                page_idx += 1
                time.sleep(1.5)


if __name__ == '__main__':
    # Execution setup mapping initial profiles configuration variables
    input_catalogues = [
        {
            "url": "https://www.bancaditalia.it/pubblicazioni/interventi-governatore/integov2025/index.html?com.dotmarketing.htmlpage.language=1&page=1",
            "year": "2025",
            "type": "Governor"
        },
                {
            "url": "https://www.bancaditalia.it/pubblicazioni/interventi-governatore/integov2026/index.html?com.dotmarketing.htmlpage.language=1&page=1",
            "year": "2026",
            "type": "Governor"
        },
        {
            "url": "https://www.bancaditalia.it/pubblicazioni/interventi-direttorio/int-dir-2025/index.html?com.dotmarketing.htmlpage.language=1&page=1",
            "year": "2025",
            "type": "Other members of the Governing Board"
        },
        {
            "url": "https://www.bancaditalia.it/pubblicazioni/interventi-direttorio/int-dir-2026/index.html?com.dotmarketing.htmlpage.language=1&page=1",
            "year": "2026",
            "type": "Other members of the Governing Board"
        }

    ]
    
    run_scraper(input_catalogues)
    print(f"\n Finished indexing. Database records synchronized inside '{DB_PATH}'")