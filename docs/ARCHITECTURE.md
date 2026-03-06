# Radio System Architecture

## Projects

| Project | Description | Status |
|---------|-------------|--------|
| **radiocli** | CLI app | Released |
| **radiomcp** | MCP server for Claude Desktop | Released |
| **Radio API** | Backend API (g3:8092) | Running |
| **Radio MCP API** | Public MCP server for API | Planned |

**Current:**
- radiocli/radiomcp → Local DB (radio_stations.db)

**Future:**
- radiocli/radiomcp → Radio API (g3:8092)
- Radio MCP API → Public MCP server

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  RadioCli   │  │  Radio MCP  │  │   Web App   │  │ Mobile App  │        │
│  │   (CLI)     │  │  (Claude)   │  │  (Future)   │  │  (Future)   │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
└─────────┼────────────────┼────────────────┼────────────────┼────────────────┘
          │                │                │                │
          └────────────────┴────────────────┴────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RADIO API (g3:8092)                                  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         radio_api_v4.py                               │   │
│  │                                                                       │   │
│  │  Endpoints:                                                           │   │
│  │  • /search?q=&countrycode=&tag=    Search (multilingual)              │   │
│  │  • /stations?country=&tag=         Filter query                       │   │
│  │  • /station/{id}                   Single station                     │   │
│  │  • /countries, /tags, /languages   Metadata                           │   │
│  │  • /health, /stats                 Status                             │   │
│  │                                                                       │   │
│  │  Features:                                                            │   │
│  │  • Multilingual keywords (183: ko, ja, zh, ru, fr, de, es)            │   │
│  │  • Search relevance scoring (word-boundary priority)                  │   │
│  │  • Real-time URL Resolver (Korean broadcasters)                       │   │
│  │  • Health Score calculation                                           │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│          ┌─────────────────────────┼─────────────────────────┐              │
│          ▼                         ▼                         ▼              │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐        │
│  │   SQLite DB  │         │   Korean     │         │     HLS      │        │
│  │radio_unified │         │  Resolvers   │         │  Validator   │        │
│  │    .db       │         │              │         │              │        │
│  │              │         │ • KBS API    │         │ • M3U8 parse │        │
│  │ 51,915       │         │ • MBC API    │         │ • Segment    │        │
│  │ stations     │         │ • YTN        │         │   verify     │        │
│  └──────────────┘         └──────────────┘         └──────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Cron Jobs (Daily)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA PIPELINE                                        │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐     │
│  │  04:00  radio_revalidate_v2.py                                     │     │
│  │         └─ Validate station URLs → update is_verified              │     │
│  │                                                                     │     │
│  │  05:00  sync_radiobrowser.py                                       │     │
│  │         └─ Radio Browser API → sync new/updated stations           │     │
│  │                                                                     │     │
│  │  05:30  auto_broadcaster.py                                        │     │
│  │         └─ Refresh major broadcaster URLs (KBS, MBC, BBC)          │     │
│  └────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│                              DATA SOURCES                                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │Radio Browser│ │   Icecast   │ │   TuneIn    │ │  Shoutcast  │           │
│  │  27,468     │ │   14,253    │ │   10,042    │ │   (Weekly)  │           │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. New Station Discovery
```
Radio Browser API ──┐
Icecast Directory ──┼──▶ sync_radiobrowser.py ──▶ radio_unified.db
TuneIn Scraper ─────┤                              (INSERT OR REPLACE)
Shoutcast Crawler ──┘
```

### 2. Station Validation
```
radio_unified.db ──▶ radio_revalidate_v2.py ──▶ radio_unified.db
     │                      │                        │
     │                      ├─ HTTP HEAD/GET         │
     │                      ├─ HLS Segment Test      │
     │                      └─ Timeout Check         │
     │                                               │
     └─ is_verified=1 (working)                      │
        is_verified=0 (dead)                         │
        bytes_received (stream size)                 │
```

### 3. Korean Broadcaster Resolution
```
Client Request: "KBS 1라디오"
        │
        ▼
┌───────────────────────────────────────┐
│ API: station has resolver='kbs'       │
│      │                                │
│      ▼                                │
│ korean_resolvers.py                   │
│      │                                │
│      ├─ KBS: cfpwwwapi.kbs.co.kr     │
│      │       → CloudFront Signed URL  │
│      │       → Valid ~5 hours         │
│      │                                │
│      ├─ MBC: sminiplay.imbc.com      │
│      │       → Token URL              │
│      │       → Valid ~1 hour          │
│      │                                │
│      └─ YTN: Static URLs              │
│              → No expiration          │
└───────────────────────────────────────┘
        │
        ▼
Client receives: Fresh streaming URL with valid token
```

## Database Schema

```sql
CREATE TABLE stations (
    id TEXT PRIMARY KEY,
    name TEXT,
    url TEXT,
    url_resolved TEXT,
    homepage TEXT,
    favicon TEXT,
    country TEXT,
    countrycode TEXT,        -- ISO 3166-1 alpha-2
    language TEXT,
    tags TEXT,               -- Comma-separated
    codec TEXT,              -- mp3, aac, ogg, etc.
    bitrate INTEGER,
    votes INTEGER,
    clickcount INTEGER,
    listeners INTEGER,

    -- Validation
    is_verified INTEGER,     -- 1=working, 0=dead
    bytes_received INTEGER,  -- Stream test bytes
    verified_at TEXT,

    -- Source tracking
    source TEXT,             -- radiobrowser, icecast, tunein, etc.
    resolver TEXT,           -- kbs, mbc, ytn (for Korean)
    broadcaster TEXT,        -- Broadcaster registry ID

    -- Metadata
    geo_lat REAL,
    geo_long REAL,
    created_at TEXT,
    is_blocked INTEGER       -- Takedown requests
);

CREATE TABLE clicks (
    id INTEGER PRIMARY KEY,
    station_id TEXT,
    ip TEXT,
    clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Health Score Calculation

```python
def calc_health(station):
    score = 0

    if station['is_verified']:      score += 40  # Stream works
    if bytes_received > 4000:       score += 20  # Good bandwidth
    if bitrate >= 128:              score += 20  # High quality
    elif bitrate >= 64:             score += 10  # Medium quality
    if listeners > 0:               score += 10  # Has audience
    if votes > 0:                   score += 10  # Community rated

    # Grade: A(80+), B(60+), C(40+), D(<40)
    return score
```

## Multilingual Search

```
User Input          → Keyword Lookup    → DB Search
─────────────────────────────────────────────────────
"재즈"              → "jazz"            → tags LIKE '%jazz%'
"クラシック"        → "classical"       → tags LIKE '%classical%'
"новости"           → "news"            → tags LIKE '%news%'
"한국"              → "korea"           → country LIKE '%korea%'
```

**Supported Languages:** Korean, Japanese, Chinese, Russian, French, German, Spanish, Italian, Portuguese, Vietnamese, Thai

## File Structure (g3 Server)

```
/home/dragon/
├── radio_api_v4.py          # Main API server (port 8092)
├── radio_unified.db         # SQLite database (51,915 stations)
├── korean_resolvers.py      # KBS, MBC, YTN URL resolvers
├── hls_validator.py         # HLS stream validation
├── radio_revalidate_v2.py   # Daily URL validation
├── sync_radiobrowser.py     # Radio Browser sync
├── auto_broadcaster.py      # Major broadcaster updates
├── broadcaster_registry.json # Broadcaster definitions
└── logs/
    ├── sync_radiobrowser.log
    ├── auto_broadcaster.log
    └── radio_revalidate.log
```

## Client Integration

### RadioCli (CLI)
```
radiocli → Local DB (radio_stations.db) → mpv/vlc/ffplay
                ↓
         Falls back to API when needed
```

### Radio MCP (Claude Desktop)
```
Claude → MCP Server → g3 API → Stream URL → mpv
                         ↓
                   AI translates user intent to API params
```

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/search?q=&countrycode=&tag=` | GET | Full-text search with filters |
| `/stations?country=&tag=` | GET | List with filters |
| `/station/{id}` | GET | Single station (with resolver) |
| `/stations/bycountrycode/{cc}` | GET | By country code |
| `/countries` | GET | Country list with counts |
| `/tags` | GET | Tag list with counts |
| `/languages` | GET | Language list |
| `/health` | GET | API health status |
| `/stats` | GET | Database statistics |

## Deployment

```bash
# API Server (systemd or nohup)
nohup python3 /home/dragon/radio_api_v4.py > /tmp/radio_api.log 2>&1 &

# Cron Jobs
0 4 * * * /usr/bin/python3 /home/dragon/radio_revalidate_v2.py
0 5 * * * /usr/bin/python3 /home/dragon/sync_radiobrowser.py
30 5 * * * /usr/bin/python3 /home/dragon/auto_broadcaster.py
```
