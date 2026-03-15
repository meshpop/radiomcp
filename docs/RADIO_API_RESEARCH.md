# Radio API - Comprehensive Research

## Vision
Build the most complete and high-quality radio station database, independent of existing APIs.

---

## Part 1: Data Collection (All Sources)

### Tier 1: Existing APIs (Easy)
| Source | Stations | API | Notes |
|--------|----------|-----|-------|
| Radio Browser | 40K+ | Public REST | Community-driven, variable quality |
| Icecast | 15K+ | Yellow Pages | Direct listing |
| Radio Garden | 30K+ | Unofficial | Geo-based, good coverage |

### Tier 2: IPTV/Playlist Aggregation
```
Sources:
- https://github.com/iptv-org/iptv (8K+ radio)
- https://github.com/Free-TV/IPTV
- https://github.com/junguler/m3u-radio-music-playlists

Process:
1. Clone/fetch M3U files
2. Filter audio-only streams
3. Dedupe against existing DB
4. Validate and add
```

### Tier 3: Broadcaster Websites
```
Target: Official radio station websites

Approach:
1. Seed list of known broadcasters (Wikipedia, national lists)
2. Crawl website for stream URLs
3. Pattern matching: .m3u8, .mp3, .aac, /stream, /live
4. JavaScript rendering for modern players (Playwright)

Example targets:
- National broadcasters (KBS, BBC, NPR, NHK, etc.)
- University radio stations
- Community radio networks
```

### Tier 4: Search Engine Discovery
```
Queries:
- "listen live streaming" + country
- "internet radio stream url"
- site:*.edu "radio station stream"
- filetype:m3u radio

Tools:
- Google Custom Search API
- DuckDuckGo scraping
- Bing API
```

---

## Part 2: Quality Maintenance

### Quality Score Algorithm
```python
def calculate_quality(station: dict, history: list) -> int:
    """
    Calculate station quality score (0-100)
    """
    score = 0

    # === Stream Quality (40 points) ===
    bitrate = station.get('bitrate', 0)
    if bitrate >= 320:
        score += 40
    elif bitrate >= 256:
        score += 35
    elif bitrate >= 192:
        score += 30
    elif bitrate >= 128:
        score += 20
    elif bitrate >= 64:
        score += 10

    # === Reliability (30 points) ===
    # Based on health check history
    if history:
        uptime = sum(1 for h in history if h['success']) / len(history)
        score += int(uptime * 30)

    # === Metadata Completeness (20 points) ===
    if station.get('name'):
        score += 4
    if station.get('homepage'):
        score += 4
    if station.get('favicon') and is_valid_image(station['favicon']):
        score += 4
    if station.get('country'):
        score += 2
    if station.get('language'):
        score += 2
    if station.get('tags') and len(station['tags']) >= 2:
        score += 2
    if station.get('description'):
        score += 2

    # === Popularity (10 points) ===
    clicks = station.get('clickcount', 0)
    if clicks >= 10000:
        score += 10
    elif clicks >= 1000:
        score += 7
    elif clicks >= 100:
        score += 4
    elif clicks >= 10:
        score += 2

    return min(100, score)
```

### Health Check System
```python
# Continuous health monitoring

HEALTH_CHECK_INTERVAL = {
    'tier_1': 6,    # Top stations: every 6 hours
    'tier_2': 24,   # Good stations: daily
    'tier_3': 72,   # Average: every 3 days
    'tier_4': 168,  # Low quality: weekly
}

def health_check(station: dict) -> dict:
    """
    Comprehensive health check
    """
    result = {
        'station_id': station['id'],
        'timestamp': datetime.now().isoformat(),
        'success': False,
        'response_time_ms': 0,
        'bytes_received': 0,
        'content_type': None,
        'icy_metadata': {},
        'error': None
    }

    try:
        start = time.time()
        resp = requests.get(
            station['url'],
            timeout=10,
            stream=True,
            headers={'Icy-MetaData': '1'}
        )

        # Read 8KB
        data = resp.raw.read(8192)

        result['response_time_ms'] = int((time.time() - start) * 1000)
        result['bytes_received'] = len(data)
        result['content_type'] = resp.headers.get('Content-Type')
        result['success'] = len(data) >= 1024

        # Parse ICY metadata
        if 'icy-name' in resp.headers:
            result['icy_metadata']['name'] = resp.headers['icy-name']
        if 'icy-br' in resp.headers:
            result['icy_metadata']['bitrate'] = resp.headers['icy-br']

    except Exception as e:
        result['error'] = str(e)

    return result
```

### Dead Station Handling
```
Policy:
- 3 consecutive failures → mark as "unreliable"
- 7 consecutive failures → mark as "dead"
- 14 consecutive failures → archive (keep in DB but hide from search)
- 30 days dead → delete or move to archive table

Recovery:
- Monthly scan of "dead" stations
- If recovered, restore to active with penalty period
```

---

## Part 3: Metadata Enrichment

### Automatic Metadata Collection

#### 1. From Stream Headers
```python
def extract_stream_metadata(url: str) -> dict:
    """Extract metadata from stream headers"""
    resp = requests.get(url, stream=True, headers={'Icy-MetaData': '1'})

    return {
        'name': resp.headers.get('icy-name'),
        'description': resp.headers.get('icy-description'),
        'genre': resp.headers.get('icy-genre'),
        'bitrate': resp.headers.get('icy-br'),
        'url': resp.headers.get('icy-url'),
        'content_type': resp.headers.get('Content-Type'),
    }
```

#### 2. From Homepage
```python
def scrape_homepage(homepage_url: str) -> dict:
    """Scrape station website for metadata"""
    resp = requests.get(homepage_url, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')

    metadata = {}

    # Title
    title = soup.find('title')
    if title:
        metadata['name'] = title.text.strip()

    # Description
    desc = soup.find('meta', {'name': 'description'})
    if desc:
        metadata['description'] = desc.get('content')

    # Favicon
    icon = soup.find('link', rel=lambda x: x and 'icon' in x.lower())
    if icon:
        metadata['favicon'] = urljoin(homepage_url, icon.get('href'))

    # Social links
    for platform in ['facebook', 'twitter', 'instagram']:
        link = soup.find('a', href=lambda x: x and platform in x)
        if link:
            metadata[f'social_{platform}'] = link.get('href')

    # Address/Contact
    address = soup.find(class_=re.compile(r'address|contact|location', re.I))
    if address:
        metadata['address'] = address.text.strip()

    return metadata
```

#### 3. From Wikipedia/Wikidata
```python
def fetch_wikidata(station_name: str, country: str) -> dict:
    """Fetch station info from Wikidata"""
    # Search Wikidata
    search_url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={station_name}&language=en&format=json"
    results = requests.get(search_url).json()

    for item in results.get('search', []):
        entity_id = item['id']

        # Get entity details
        entity_url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
        entity = requests.get(entity_url).json()

        claims = entity['entities'][entity_id].get('claims', {})

        return {
            'wikidata_id': entity_id,
            'founded': extract_claim(claims, 'P571'),  # inception
            'country': extract_claim(claims, 'P17'),   # country
            'owner': extract_claim(claims, 'P127'),    # owned by
            'frequency': extract_claim(claims, 'P2048'), # frequency
            'website': extract_claim(claims, 'P856'),  # official website
            'logo': extract_claim(claims, 'P154'),     # logo image
        }

    return {}
```

#### 4. From AI/LLM
```python
def enrich_with_llm(station: dict) -> dict:
    """Use LLM to research station info"""
    prompt = f"""
    Research this radio station and provide structured info:

    Name: {station['name']}
    Country: {station.get('country', 'Unknown')}
    URL: {station.get('homepage', 'N/A')}

    Return JSON with:
    - description (1-2 sentences)
    - genres (list)
    - language
    - target_audience
    - founded_year (if known)
    - owner_organization (if known)
    """

    # Call Claude/GPT/Ollama
    response = llm.complete(prompt)
    return json.loads(response)
```

---

## Part 4: Crawling Architecture

### Distributed Crawler Design
```
                    ┌─────────────────┐
                    │   Coordinator   │
                    │    (g3 main)    │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
    ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐
    │  Worker 1   │   │  Worker 2   │   │  Worker 3   │
