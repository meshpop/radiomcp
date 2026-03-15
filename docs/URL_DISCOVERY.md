# Independent URL Discovery Methods

## Goal
Reduce dependency on Radio Browser API by discovering radio stream URLs independently.

---

## Methods

### 1. IPTV M3U Lists (Recommended)
```
Source: https://github.com/iptv-org/iptv
        https://github.com/Free-TV/IPTV

Process:
1. Download M3U files
2. Filter radio channels (audio-only streams)
3. Validate URLs
4. Add to DB
```

**Pros:** Easy, thousands of URLs, community maintained
**Cons:** Overlap with existing sources, quality varies

### 3. Playlist File Collection
```
Search:
- GitHub: "extension:m3u radio stream"
- GitHub: "extension:pls radio"
- Web: site:pastebin.com m3u radio

Parse .m3u/.pls → Extract stream URLs
```

### 4. DNS/Subdomain Discovery
```python
# Known broadcaster domains
domains = ["kbs.co.kr", "mbc.co.kr", "bbc.co.uk", "npr.org"]

# Common stream subdomains
prefixes = ["stream", "live", "radio", "audio", "listen", "player"]

# Check: stream.kbs.co.kr, live.kbs.co.kr, etc.
```

### 5. Web Scraping (Advanced)
```
Target: Radio station websites with "Listen Live" buttons

Patterns to find:
- <audio src="...">
- <source src="...">
- *.m3u8, *.mp3, *.aac URLs
- JavaScript player configs

Tools: playwright, beautifulsoup
```

### 6. User Submissions
```python
# CLI command
radiocli submit --url "http://stream.example.com/live" \
                --name "My Local Radio" \
                --country "KR" \
                --genre "jazz"

# Validation
1. Test stream (3KB minimum)
2. Extract metadata (icy-name, etc.)
3. Queue for manual review or auto-add
```

### 7. AI-Assisted Discovery
```
1. Search: "radio station streaming URL" + country/city
2. Feed results to LLM
3. LLM extracts stream URLs from pages
4. Validate and add

Use: Claude API, local Ollama
```

---

## Priority Implementation

### Phase 1: Low-hanging fruit
- [ ] IPTV M3U parser
- [ ] Radio Garden sync (already have crawler)
- [ ] GitHub playlist search

### Phase 2: Community
- [ ] User submission endpoint
- [ ] Submission review queue
- [ ] Contributor credits

### Phase 3: Advanced
- [ ] Web scraper for major broadcasters
- [ ] DNS subdomain scanner
- [ ] AI-assisted discovery

---

## Implementation: IPTV M3U Parser

```python
#!/usr/bin/env python3
"""Parse IPTV M3U files for radio streams"""
import re
import requests
import sqlite3

IPTV_SOURCES = [
    "https://iptv-org.github.io/iptv/categories/music.m3u",
    "https://iptv-org.github.io/iptv/categories/news.m3u",
]

def parse_m3u(content: str) -> list:
    """Extract stations from M3U content"""
    stations = []
    lines = content.strip().split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            # Parse: #EXTINF:-1 tvg-name="..." tvg-logo="...",Station Name
            match = re.search(r'tvg-name="([^"]*)"', line)
            name = match.group(1) if match else line.split(',')[-1]

            logo_match = re.search(r'tvg-logo="([^"]*)"', line)
            logo = logo_match.group(1) if logo_match else ""

            # Next line is URL
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and not url.startswith('#'):
                    stations.append({
                        'name': name,
                        'url': url,
                        'favicon': logo,
                        'source': 'iptv'
                    })
            i += 2
        else:
            i += 1

    return stations

def is_audio_stream(url: str) -> bool:
    """Check if URL is audio (not video)"""
    audio_patterns = ['.mp3', '.aac', '.ogg', '/radio', 'audio', 'stream']
    return any(p in url.lower() for p in audio_patterns)

def main():
    all_stations = []

    for source in IPTV_SOURCES:
        resp = requests.get(source, timeout=30)
        stations = parse_m3u(resp.text)

        # Filter audio-only
        audio_stations = [s for s in stations if is_audio_stream(s['url'])]
        all_stations.extend(audio_stations)

        print(f"{source}: {len(audio_stations)} audio streams")

    print(f"Total: {len(all_stations)} stations")

    # TODO: Validate and add to DB

if __name__ == "__main__":
    main()
```

---


## Data Quality

### Validation Pipeline
```
New URL discovered
    |
    +-> Stream test (download 4KB)
    |
    +-> Metadata extraction (icy-name, bitrate)
    |
    +-> Duplicate check (URL/name similarity)
    |
    +-> Add to DB with source tag
```

### Quality Score
```python
def calculate_quality_score(station):
    score = 0

    if station['bitrate'] >= 128:
        score += 20
    if station['bitrate'] >= 256:
        score += 10

    if station['favicon']:
        score += 10

    if station['homepage']:
        score += 10

    if station['verified']:
        score += 30

    # Uptime history
    score += station['uptime_pct'] * 0.2

    return min(100, score)
```

---

## Differentiation from Radio Browser

| Feature | Radio Browser | RadioCli (Future) |
|---------|--------------|-------------------|
| Data source | Community submissions | Multi-source aggregation |
| Verification | Basic vote system | Active stream testing |
| Freshness | Variable | Daily validation |
| Coverage | 40K+ | 50K+ (goal) |
| Unique sources | - | IPTV, Radio Garden, crawlers |
